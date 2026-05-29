import type { VideoConfigJSON } from "@remotion-src/config-types";
import type { DraftStep, Job, WidthConfig } from "./draft-types";

export type ImportInput = {
  configJson: string;
  cppFiles: Record<string, string>;
  name?: string;
};

export type ImportResult =
  | { ok: true; job: Job }
  | { ok: false; error: string };

export function importFromConfig(input: ImportInput): ImportResult {
  let parsed: VideoConfigJSON;
  try {
    parsed = JSON.parse(input.configJson) as VideoConfigJSON;
  } catch (e) {
    return {
      ok: false,
      error: `config.json 解析失敗：${(e as Error).message}`,
    };
  }

  if (!parsed.steps || !Array.isArray(parsed.steps)) {
    return { ok: false, error: "config.json 必須包含 steps 陣列" };
  }

  const steps: DraftStep[] = [];
  const missing: string[] = [];

  for (let i = 0; i < parsed.steps.length; i++) {
    const s = parsed.steps[i];
    const fileContent = input.cppFiles[s.file];
    if (fileContent === undefined) {
      missing.push(s.file);
      continue;
    }
    steps.push({
      label: s.label,
      from: s.from,
      to: s.to,
      fileLabel: s.file,
      fileContent,
      subtitle: s.subtitle,
      focusLine: s.focusLine,
      highlight: s.highlight,
      annotations: s.annotations,
    });
  }

  if (missing.length > 0) {
    const unique = [...new Set(missing)];
    return {
      ok: false,
      error: `找不到 cpp 檔：${unique.join(", ")}。請一併上傳這些檔案。`,
    };
  }

  const now = Date.now();
  const width: WidthConfig = { type: "fixed", value: 1920 };
  return {
    ok: true,
    job: {
      id: crypto.randomUUID(),
      name: input.name ?? "Imported Job",
      createdAt: now,
      updatedAt: now,
      theme: "github-dark",
      width,
      steps,
    },
  };
}
