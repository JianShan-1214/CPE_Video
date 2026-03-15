#!/usr/bin/env node
import { spawnSync } from "child_process";
import { existsSync, mkdirSync, readFileSync } from "fs";
import { join } from "path";

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

// ── Check uv ───────────────────────────────────────────────────────────────
const check = spawnSync("uv", ["--version"], { encoding: "utf8" });
if (check.error) {
  console.error("Error: uv not found. Install from https://docs.astral.sh/uv/getting-started/installation/");
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

// ── SSML builder ───────────────────────────────────────────────────────────
// 將中英混雜的字幕轉成 SSML，英文 token 用 <lang xml:lang="en-US"> 包住
// 讓 zh-TW 語音引擎對英文單字切換成英文發音
const VOICE = "zh-TW-HsiaoChenNeural";

function toSSML(text) {
  const escaped = text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
  // 連續的英文 token（含底線、數字）合併為同一段 en-US，避免切換過於頻繁
  const body = escaped.replace(/[A-Za-z][A-Za-z0-9_]*(?:[ \t][A-Za-z][A-Za-z0-9_]*)*/g,
    (m) => `<lang xml:lang="en-US">${m}</lang>`,
  );
  return `<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="zh-TW"><voice name="${VOICE}">${body}</voice></speak>`;
}

// ── Generate ───────────────────────────────────────────────────────────────
const total = steps.length;
for (let i = 0; i < total; i++) {
  const num    = i + 1;
  const padded = String(num).padStart(2, "0");
  const label  = `[${num}/${total}] step_${padded}.mp3`;

  // Filter by --step if provided
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
  const result = spawnSync(
    "uv",
    ["run", "--with", "edge-tts", "edge-tts", "--voice", VOICE, "--text", toSSML(subtitle), "--write-media", outPath],
    { stdio: "inherit" },
  );
  if (result.status !== 0) {
    console.error(`${label} failed`);
    process.exit(1);
  }
  console.log(`${label} ✓`);
}
