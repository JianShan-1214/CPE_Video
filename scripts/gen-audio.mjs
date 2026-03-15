#!/usr/bin/env node
import { TextToSpeechClient } from "@google-cloud/text-to-speech";
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

// ── SSML builder ───────────────────────────────────────────────────────────
// 英文 token 用 <lang xml:lang="en-US"> 包住，讓 zh-TW 語音引擎正確發音
function toSSML(text) {
  const escaped = text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
  const body = escaped.replace(/[A-Za-z][A-Za-z0-9_]*(?:[ \t][A-Za-z][A-Za-z0-9_]*)*/g,
    (m) => `<lang xml:lang="en-US">${m}</lang>`,
  );
  return `<speak>${body}</speak>`;
}

// ── TTS client ─────────────────────────────────────────────────────────────
const client = new TextToSpeechClient();

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
  const [response] = await client.synthesizeSpeech({
    input: { ssml: toSSML(subtitle) },
    voice: {
      languageCode: "zh-TW",
      name: "zh-TW-Neural2-A",
    },
    audioConfig: {
      audioEncoding: "MP3",
      speakingRate: 1.0,
    },
  });

  writeFileSync(outPath, response.audioContent, "binary");
  console.log(`${label} ✓`);
}
