import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { createReadStream } from "node:fs";
import { mkdir, rm, writeFile } from "node:fs/promises";
import type { IncomingMessage, ServerResponse } from "node:http";
import path from "node:path";
import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";
import { defineConfig } from "vite";
import { createVideoExportFiles } from "./src/lib/export-files";
import type { Job } from "./src/lib/draft-types";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const projectRoot = path.resolve(__dirname, "..");

export default defineConfig({
  plugins: [react(), tailwindcss(), localRenderApi()],
  resolve: {
    alias: {
      "@remotion-src": path.resolve(__dirname, "../src"),
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    port: 5173,
  },
});

function localRenderApi() {
  return {
    name: "cpe-video-local-render-api",
    configureServer(server: import("vite").ViteDevServer) {
      server.middlewares.use("/api/render-mp4", async (req, res) => {
        if (req.method !== "POST") {
          sendJson(res, 405, { error: "Method not allowed" });
          return;
        }

        let renderFolder: string | null = null;
        try {
          const body = await readJsonBody(req);
          const job = body.job as Job | undefined;
          const folderName =
            typeof body.folderName === "string" ? body.folderName : "";

          if (!job || !Array.isArray(job.steps) || job.steps.length === 0) {
            sendJson(res, 400, { error: "Job must contain at least one step" });
            return;
          }

          const files = createVideoExportFiles(job, folderName);
          renderFolder = `__render_${files.folderName}_${crypto.randomUUID().slice(0, 8)}`;
          const publicFolder = path.join(projectRoot, "public", renderFolder);
          const outputPath = path.join(projectRoot, "out", `${renderFolder}.mp4`);

          await mkdir(publicFolder, { recursive: true });
          await writeFile(path.join(publicFolder, "config.json"), files.configJson);
          for (const [filename, content] of files.cppFiles.entries()) {
            await writeFile(path.join(publicFolder, filename), content);
          }

          await renderMp4(renderFolder, outputPath);

          res.statusCode = 200;
          res.setHeader("Content-Type", "video/mp4");
          res.setHeader(
            "Content-Disposition",
            `attachment; filename="${files.folderName}.mp4"`,
          );

          createReadStream(outputPath).pipe(res);
          res.on("finish", () => {
            if (renderFolder) {
              void rm(path.join(projectRoot, "public", renderFolder), {
                recursive: true,
                force: true,
              });
            }
          });
        } catch (error) {
          if (renderFolder) {
            await rm(path.join(projectRoot, "public", renderFolder), {
              recursive: true,
              force: true,
            });
          }
          sendJson(res, 500, {
            error: error instanceof Error ? error.message : String(error),
          });
        }
      });
    },
  };
}

function readJsonBody(req: IncomingMessage): Promise<Record<string, unknown>> {
  return new Promise((resolve, reject) => {
    let raw = "";
    req.setEncoding("utf8");
    req.on("data", (chunk: string) => {
      raw += chunk;
      if (raw.length > 10_000_000) {
        reject(new Error("Request body is too large"));
      }
    });
    req.on("end", () => {
      try {
        resolve(JSON.parse(raw || "{}") as Record<string, unknown>);
      } catch {
        reject(new Error("Invalid JSON request body"));
      }
    });
    req.on("error", reject);
  });
}

function renderMp4(folder: string, outputPath: string): Promise<void> {
  const props = JSON.stringify({ folder });
  const args = [
    "remotion",
    "render",
    "src/index.ts",
    "Main",
    outputPath,
    "--props",
    props,
    "--overwrite",
  ];

  return new Promise((resolve, reject) => {
    const child = spawn("npx", args, { cwd: projectRoot });
    let stderr = "";

    child.stderr.on("data", (chunk: Buffer) => {
      stderr += chunk.toString();
    });

    child.on("error", reject);
    child.on("close", (code) => {
      if (code === 0) {
        resolve();
        return;
      }
      reject(new Error(stderr.trim() || `Remotion render failed with code ${code}`));
    });
  });
}

function sendJson(
  res: ServerResponse,
  statusCode: number,
  body: Record<string, unknown>,
): void {
  res.statusCode = statusCode;
  res.setHeader("Content-Type", "application/json");
  res.end(JSON.stringify(body));
}
