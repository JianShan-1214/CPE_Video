#!/usr/bin/env node
// npm run story-audio <folder> [--force]：逐句（cue）產生 TTS → public/<folder>/audio/<cueId>.mp3
import { readFileSync, writeFileSync, existsSync, mkdirSync } from "fs";
import { join } from "path";
import "dotenv/config";
const folder = process.argv[2];
const force = process.argv.includes("--force");
if (!folder) { console.error("用法：npm run story-audio <folder> [--force]"); process.exit(1); }
if (!process.env.OPENAI_API_KEY) { console.error("OPENAI_API_KEY 未設定"); process.exit(1); }
const MODEL = process.env.OPENAI_TTS_MODEL || "gpt-4o-mini-tts";
const VOICE = process.env.OPENAI_TTS_VOICE || "onyx";
const BASE = (process.env.OPENAI_BASE_URL || "https://api.openai.com/v1").replace(/\/$/, "");
const INSTR = process.env.TTS_INSTRUCTIONS ||
  "用台灣華語，像輕鬆親切的家教老師在一對一講題：語氣自然有起伏、偶爾帶點好奇或驚喜，語速比一般稍慢，句與句之間自然停頓；不要像在念稿。英文字母與程式名稱清楚帶過。";
const story = JSON.parse(readFileSync(join("public", folder, "story.json"), "utf8"));
const dir = join("public", folder, "audio"); mkdirSync(dir, { recursive: true });
const cues = story.scenes.flatMap((s) => s.cues);
let n = 0;
for (const c of cues) {
  n++;
  const out = join(dir, `${c.id}.mp3`);
  if (existsSync(out) && !force) { console.log(`[${n}/${cues.length}] ${c.id} skip`); continue; }
  const body = { model: MODEL, voice: VOICE, input: c.say ?? c.text, response_format: "mp3", instructions: INSTR };
  const res = await fetch(`${BASE}/audio/speech`, { method: "POST", headers: { Authorization: `Bearer ${process.env.OPENAI_API_KEY}`, "Content-Type": "application/json" }, body: JSON.stringify(body) });
  if (!res.ok) { console.error(`${c.id} failed ${res.status}: ${await res.text()}`); process.exit(1); }
  writeFileSync(out, Buffer.from(await res.arrayBuffer()));
  console.log(`[${n}/${cues.length}] ${c.id} ✓`);
}
