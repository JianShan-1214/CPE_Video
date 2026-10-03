#!/usr/bin/env node
// 讀 public/<folder>/story.json，量每句旁白音檔長度（沒有音檔就用字數估），算出每個 cue 的起點，
// 輸出 public/<folder>/timeline.json，並做規則檢查。
import { readFileSync, writeFileSync, existsSync } from "fs";
import { execFileSync } from "child_process";
import { join } from "path";

const folder = process.argv[2];
const noAudio = process.argv.includes("--no-audio");
if (!folder) { console.error("用法：node scripts/story-build.mjs <folder> [--no-audio]"); process.exit(1); }
const dir = join("public", folder);
const story = JSON.parse(readFileSync(join(dir, "story.json"), "utf8"));
const FPS = 30, LEAD = 0.25, PAUSE = 0.4, SCENE_GAP = 0.5, CPS = 4.3; // onyx 約 4.3 字/秒

const speakLen = (t) => {
  let n = 0;
  for (const ch of t.replace(/[，。！？；：、「」\s]/g, "")) n += /[\u4e00-\u9fff]/.test(ch) ? 1 : 0.5;
  return n;
};
const probe = (f) => parseFloat(execFileSync("ffprobe", ["-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", f]).toString());

let t = 0, usedAudio = 0, cuesOut = [], warn = [];
const chunkOK = (text) => text.match(/[^，。！？；：、]+[，。！？；：、]?/g).every((p) => p.replace(/[，。！？；：、]/g, "").length <= 18);
let lastStart = "", noticeCount = 0;
story.scenes.forEach((sc, si) => {
  const all = sc.cues.map((c) => c.text).join("");
  const n = all.replace(/[，。！？；：、「」\s]/g, "").length;
  const solo = sc.layout === "code" && sc.cues.length <= 4;
  if (!solo && (n < 28 || n > 75)) warn.push(`場景 ${sc.id} 旁白 ${n} 字（建議 45–70）`);
  const start = all.slice(0, 2);
  if (start === lastStart) warn.push(`場景 ${sc.id} 開頭「${start}」與上一場景相同`);
  lastStart = start;
  sc.cues.forEach((c, ci) => {
    if (!chunkOK(c.text)) warn.push(`${c.id} 有單行字幕片段超過 18 字`);
    if (c.cap && c.cap.length > 14) warn.push(`${c.id} cap 超過 14 字：${c.cap}`);
    if (c.cap && c.text.includes(c.cap)) warn.push(`${c.id} cap 與旁白重複`);
    noticeCount += (c.text.match(/這裡要注意/g) || []).length;
    const af = join(dir, "audio", `${c.id}.mp3`);
    let audioDur, audio = null;
    if (!noAudio && existsSync(af)) { audioDur = probe(af); audio = `audio/${c.id}.mp3`; usedAudio++; }
    else audioDur = speakLen(c.say ?? c.text) / CPS;
    const last = ci === sc.cues.length - 1;
    // 有 dt 秒數的 op（快轉）不能超出 cue；at 綁旁白的 op 已在旁白內
    let span = 0;
    for (const o of c.ops ?? []) {
      const tt = o.at !== undefined ? LEAD + o.at * audioDur + (o.dt ?? 0) : (o.dt ?? 0);
      span = Math.max(span, tt + (o.dur ?? 0.5));
    }
    const dur = Math.max(LEAD + audioDur + (c.pauseAfter ?? PAUSE), span + 0.2) + (last ? SCENE_GAP : 0);
    cuesOut.push({ id: c.id, start: +t.toFixed(3), dur: +dur.toFixed(3), lead: LEAD, audioDur: +audioDur.toFixed(3), audio });
    t += dur;
  });
});
if (noticeCount > 1) warn.push(`「這裡要注意」出現 ${noticeCount} 次（最多 1 次）`);
const total = cuesOut.length ? +(t + 1.0).toFixed(3) : 0;
const mode = usedAudio === cuesOut.length ? "audio" : "estimate";
writeFileSync(join(dir, "timeline.json"), JSON.stringify({ fps: FPS, total, mode, cues: cuesOut }, null, 1));
console.log(`cues=${cuesOut.length} total=${total}s mode=${mode}`);
warn.forEach((w) => console.log("⚠", w));
