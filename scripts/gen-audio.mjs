#!/usr/bin/env node
import { GoogleAuth } from "google-auth-library";
import { writeFileSync, existsSync, mkdirSync, readFileSync } from "fs";
import { join } from "path";
import "dotenv/config";

// ── Parse args ─────────────────────────────────────────────────────────────
const args = process.argv.slice(2);
const folder = args.find((a) => !a.startsWith("--"));
const force  = args.includes("--force") || process.env.npm_config_force === "true";
const stepArg = (() => {
  const i = args.indexOf("--step");
  return i !== -1 ? parseInt(args[i + 1], 10) : null;
})();

if (!folder) {
  console.error("Usage: npm run gen-audio <folder> [--force] [--step N]");
  process.exit(1);
}

// ── Provider ───────────────────────────────────────────────────────────────
// TTS_PROVIDER=openai（預設）| google
const provider = (process.env.TTS_PROVIDER || "openai").toLowerCase();
if (!["openai", "google"].includes(provider)) {
  console.error(`Error: unknown TTS_PROVIDER "${provider}" (use openai | google)`);
  process.exit(1);
}
if (provider === "openai") {
  if (!process.env.OPENAI_API_KEY) {
    console.error("Error: OPENAI_API_KEY is not set (put it in .env or the environment)");
    process.exit(1);
  }
} else {
  if (!process.env.GOOGLE_APPLICATION_CREDENTIALS) {
    console.error("Error: GOOGLE_APPLICATION_CREDENTIALS is not set in .env");
    process.exit(1);
  }
  if (!existsSync(process.env.GOOGLE_APPLICATION_CREDENTIALS)) {
    console.error(`Error: credential file not found: ${process.env.GOOGLE_APPLICATION_CREDENTIALS}`);
    process.exit(1);
  }
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

// ── Auth (google only) ─────────────────────────────────────────────────────
let token = null;
if (provider === "google") {
  const auth = new GoogleAuth({
    keyFilename: process.env.GOOGLE_APPLICATION_CREDENTIALS,
    scopes: ["https://www.googleapis.com/auth/cloud-platform"],
  });
  const authClient = await auth.getClient();
  ({ token } = await authClient.getAccessToken());
}

// ── Synthesizers → Buffer(mp3) ─────────────────────────────────────────────
const OPENAI_MODEL = process.env.OPENAI_TTS_MODEL || "gpt-4o-mini-tts";
const OPENAI_VOICE = process.env.OPENAI_TTS_VOICE || "onyx";
const OPENAI_SPEED = parseFloat(process.env.OPENAI_TTS_SPEED || "1");
const OPENAI_BASE = (process.env.OPENAI_BASE_URL || "https://api.openai.com/v1").replace(/\/$/, "");
const PROMPT = "以清晰、自然、適合教學影片的語氣，用台灣華語朗讀；英文術語與程式碼名稱自然帶過。";

async function synthOpenAI(text) {
  const body = {
    model: OPENAI_MODEL,
    voice: OPENAI_VOICE,
    input: text,
    response_format: "mp3",
    speed: OPENAI_SPEED,
  };
  // instructions 只有 gpt-4o-mini-tts 支援（tts-1 / tts-1-hd 不支援）
  if (OPENAI_MODEL.startsWith("gpt-")) body.instructions = PROMPT;
  const res = await fetch(`${OPENAI_BASE}/audio/speech`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${process.env.OPENAI_API_KEY}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}: ${await res.text()}`);
  return Buffer.from(await res.arrayBuffer());
}

async function synthGoogle(text) {
  const res = await fetch("https://texttospeech.googleapis.com/v1beta1/text:synthesize", {
    method: "POST",
    headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
    body: JSON.stringify({
      audioConfig: { audioEncoding: "MP3", speakingRate: 1 },
      input: { prompt: "以清晰、自然、適合教學影片的語氣朗讀。", text },
      voice: { languageCode: "cmn-TW", modelName: "gemini-2.5-flash-tts", name: "Achernar" },
    }),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}: ${await res.text()}`);
  const body = await res.json();
  if (!body.audioContent) throw new Error("response missing audioContent");
  return Buffer.from(body.audioContent, "base64");
}

console.log(`Provider: ${provider}${provider === "openai" ? ` (${OPENAI_MODEL}, voice=${OPENAI_VOICE})` : ""}`);

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
  try {
    const audio = provider === "openai" ? await synthOpenAI(subtitle) : await synthGoogle(subtitle);
    writeFileSync(outPath, audio);
  } catch (e) {
    console.error(`${label} failed: ${e.message}`);
    process.exit(1);
  }
  console.log(`${label} ✓`);
}
