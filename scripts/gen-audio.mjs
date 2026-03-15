#!/usr/bin/env node
import { GoogleAuth } from "google-auth-library";
import { writeFileSync, existsSync, mkdirSync, readFileSync } from "fs";
import { join } from "path";
import "dotenv/config";

// ── Parse args ─────────────────────────────────────────────────────────────
const args = process.argv.slice(2);
const folder = args.find((a) => !a.startsWith("--"));
const force  = args.includes("--force");
const stepArg = (() => {
  const i = args.indexOf("--step");
  return i !== -1 ? parseInt(args[i + 1], 10) : null;
})();

if (!folder) {
  console.error("Usage: npm run gen-audio <folder> [--force] [--step N]");
  process.exit(1);
}

// ── Check credentials ───────────────────────────────────────────────────────
if (!process.env.GOOGLE_APPLICATION_CREDENTIALS) {
  console.error("Error: GOOGLE_APPLICATION_CREDENTIALS is not set in .env");
  process.exit(1);
}

// ── Read config ────────────────────────────────────────────────────────────
const configPath = join("public", folder, "config.json");
if (!existsSync(configPath)) {
  console.error(`Error: ${configPath} not found`);
  process.exit(1);
}
const config = JSON.parse(readFileSync(configPath, "utf8"));
const steps  = config.steps;

// ── Ensure audio dir ───────────────────────────────────────────────────────
const audioDir = join("public", folder, "audio");
mkdirSync(audioDir, { recursive: true });

// ── Auth ───────────────────────────────────────────────────────────────────
const auth = new GoogleAuth({
  keyFilename: process.env.GOOGLE_APPLICATION_CREDENTIALS,
  scopes: ["https://www.googleapis.com/auth/cloud-platform"],
});
const authClient = await auth.getClient();
const { token } = await authClient.getAccessToken();

// ── Generate ───────────────────────────────────────────────────────────────
const total = steps.length;
for (let i = 0; i < total; i++) {
  const num    = i + 1;
  const padded = String(num).padStart(2, "0");
  const label  = `[${num}/${total}] step_${padded}.mp3`;

  if (stepArg !== null && stepArg !== num) continue;

  const subtitle = steps[i].subtitle;
  if (!subtitle || subtitle.trim() === "") {
    console.log(`${label} (skipped — no subtitle)`);
    continue;
  }

  const outPath = join(audioDir, `step_${padded}.mp3`);
  if (existsSync(outPath) && !force) {
    console.log(`${label} (skipped — exists)`);
    continue;
  }

  console.log(`${label} generating…`);
  const res = await fetch("https://texttospeech.googleapis.com/v1beta1/text:synthesize", {
    method: "POST",
    headers: {
      "Authorization": `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      audioConfig: {
        audioEncoding: "MP3",
        speakingRate: 1,
      },
      input: {
        prompt: "以清晰、自然、適合教學影片的語氣朗讀。",
        text: subtitle,
      },
      voice: {
        languageCode: "cmn-TW",
        modelName: "gemini-2.5-flash-tts",
        name: "Achernar",
      },
    }),
  });

  if (!res.ok) {
    const err = await res.text();
    console.error(`${label} failed: ${err}`);
    process.exit(1);
  }

  const { audioContent } = await res.json();
  writeFileSync(outPath, Buffer.from(audioContent, "base64"));
  console.log(`${label} ✓`);
}
