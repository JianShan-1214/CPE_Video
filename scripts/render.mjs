#!/usr/bin/env node
import { execSync } from "child_process";

const folder = process.argv[2];

if (!folder) {
  console.error("用法：npm run render <資料夾名稱>");
  console.error("範例：npm run render bubble_sort");
  process.exit(1);
}

const output = `out/${folder}.mp4`;
const cmd = `npx remotion render src/index.ts Main ${output} --props '{"folder":"${folder}"}' --overwrite`;

console.log(`\n▶ 資料夾：public/${folder}/`);
console.log(`▶ 輸出：${output}\n`);

execSync(cmd, { stdio: "inherit" });
