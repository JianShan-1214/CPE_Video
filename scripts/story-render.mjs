#!/usr/bin/env node
// npm run story-render <folder> [--no-audio] [out.mp4]
import { execFileSync } from "child_process";
import { readFileSync, writeFileSync } from "fs";
import { join } from "path";
const folder = process.argv[2];
const noAudio = process.argv.includes("--no-audio");
const outArg = process.argv.slice(3).find((a) => a.endsWith(".mp4"));
const dir = join("public", folder);
execFileSync("node", ["scripts/story-build.mjs", folder, ...(noAudio ? ["--no-audio"] : [])], { stdio: "inherit" });
const story = JSON.parse(readFileSync(join(dir, "story.json"), "utf8"));
const props = {
  folder,
  story,
  timeline: JSON.parse(readFileSync(join(dir, "timeline.json"), "utf8")),
  code: readFileSync(join(dir, story.code), "utf8"),
};
writeFileSync("/tmp/story-props.json", JSON.stringify(props));
const out = outArg ?? `out/${folder}${noAudio ? "_noaudio" : ""}.mp4`;
execFileSync("npx", ["remotion", "render", "src/index.ts", "Story", out, "--props", "/tmp/story-props.json", "--overwrite"], { stdio: "inherit" });
