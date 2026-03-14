# Audio Narration Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add edge-tts AI voice narration to each video step, generated independently before rendering.

**Architecture:** A Node.js script reads `config.json` and spawns `edge-tts` to produce per-step mp3 files in `public/<folder>/audio/`. `calculateMetadata` then reads each mp3's duration (via `@remotion/media-utils`) and extends the step if the audio is longer than the configured time. `CodeStep` renders `<Audio />` inside each `Series.Sequence` so audio is scoped to its step.

**Tech Stack:** Node.js (gen-audio script), edge-tts (Python CLI), `@remotion/media-utils`, Remotion `<Audio />` component, TypeScript

---

## Chunk 1: Dependencies + Audio Generation Script

### Task 1: Install `@remotion/media-utils` and register `gen-audio` script

**Files:**
- Modify: `package.json`

- [ ] **Step 1: Install the package**

```bash
npm install @remotion/media-utils@4.0.435
```

Expected: package added to `dependencies` in `package.json`.

- [ ] **Step 2: Add the `gen-audio` script entry**

In `package.json`, add to `"scripts"`:
```json
"gen-audio": "node scripts/gen-audio.mjs"
```

- [ ] **Step 3: Verify TypeScript still compiles**

```bash
npm run lint
```

Expected: 0 errors.

- [ ] **Step 4: Commit**

```bash
git add package.json package-lock.json
git commit -m "chore: add @remotion/media-utils and gen-audio script entry"
```

---

### Task 2: Create `scripts/gen-audio.mjs`

**Files:**
- Create: `scripts/gen-audio.mjs`

This script reads `public/<folder>/config.json`, creates `public/<folder>/audio/`, and spawns `edge-tts` once per step.

- [ ] **Step 1: Verify edge-tts is installed**

```bash
edge-tts --version
```

If not installed:
```bash
pip install edge-tts
```

- [ ] **Step 2: Create the script**

```js
#!/usr/bin/env node
import { execSync, spawnSync } from "child_process";
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

// ── Check edge-tts ─────────────────────────────────────────────────────────
const check = spawnSync("edge-tts", ["--version"], { encoding: "utf8" });
if (check.error) {
  console.error("Error: edge-tts not found. Install with:\n  pip install edge-tts");
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
  execSync(
    `edge-tts --voice zh-TW-HsiaoChenNeural --text "${subtitle.replace(/"/g, '\\"')}" --write-media "${outPath}"`,
    { stdio: "inherit" },
  );
  console.log(`${label} ✓`);
}
```

- [ ] **Step 3: Smoke-test with a single step**

```bash
npm run gen-audio bubble_sort -- --step 1
```

Expected output:
```
[1/12] step_01.mp3 generating…
[1/12] step_01.mp3 ✓
```

Verify file created: `ls public/bubble_sort/audio/step_01.mp3`

- [ ] **Step 4: Test --force regenerates**

```bash
npm run gen-audio bubble_sort -- --step 1 --force
```

Expected: `[1/12] step_01.mp3 generating…` (not skipped).

- [ ] **Step 5: Test skip behaviour**

```bash
npm run gen-audio bubble_sort -- --step 1
```

Expected: `[1/12] step_01.mp3 (skipped — exists)`.

- [ ] **Step 6: Test missing folder error**

```bash
node scripts/gen-audio.mjs
```

Expected: `Usage: npm run gen-audio <folder> [--force] [--step N]` and exit code 1.

- [ ] **Step 7: Generate all steps**

```bash
npm run gen-audio bubble_sort
```

Expected: all 12 steps generated or skipped. Verify:
```bash
ls public/bubble_sort/audio/
```
Should show `step_01.mp3` through `step_12.mp3`.

- [ ] **Step 8: Commit**

```bash
git add scripts/gen-audio.mjs
git commit -m "feat: add gen-audio script for edge-tts narration"
```

---

## Chunk 2: Remotion Integration

### Task 3: Create `src/AudioPlayer.tsx`

**Files:**
- Create: `src/AudioPlayer.tsx`

- [ ] **Step 1: Create the component**

```tsx
import React from "react";
import { Audio } from "remotion";

/**
 * Thin wrapper around Remotion <Audio />.
 * Must be rendered inside a Series.Sequence — Remotion scopes
 * audio playback to the sequence's time range automatically.
 */
export const AudioPlayer: React.FC<{ src: string }> = ({ src }) => (
  <Audio src={src} startFrom={0} />
);
```

- [ ] **Step 2: TypeScript check**

```bash
npm run lint
```

Expected: 0 errors.

- [ ] **Step 3: Commit**

```bash
git add src/AudioPlayer.tsx
git commit -m "feat: add AudioPlayer component"
```

---

### Task 4: Update `src/Main.tsx` — add `audioSrc` to `StepProps` and render in `CodeStep`

**Files:**
- Modify: `src/Main.tsx`

- [ ] **Step 1: Add `audioSrc` to `StepProps` type**

Find the `StepProps` type (around line 30) and add the new field:

```ts
export type StepProps = {
  code: HighlightedCode;
  durationInFrames: number;
  subtitle: string;
  highlight: HighlightConfig;
  annotations: AnnotationCallout[];
  audioSrc: string | undefined;   // ← add this line
};
```

- [ ] **Step 2: Import `AudioPlayer`**

At the top of the file add:
```ts
import { AudioPlayer } from "./AudioPlayer";
```

- [ ] **Step 3: Render `<AudioPlayer>` inside `CodeStep`**

In the `CodeStep` component's return JSX, find the outer `<div style={outerStyle}>`. Add `<AudioPlayer>` as a **sibling of `scrollWrapStyle`**, both inside `outerStyle`. `<Audio />` renders nothing visible — it must stay inside `outerStyle` (which is inside `Series.Sequence`) so Remotion scopes it to this step's timeline:

```tsx
  return (
    <div style={outerStyle}>
      <div style={scrollWrapStyle}>
        {/* ... existing HighlightOverlay, LineNumbers, annotations, CodeTransition unchanged ... */}
      </div>
      {step.audioSrc && <AudioPlayer src={step.audioSrc} />}
    </div>
  );
```

- [ ] **Step 4: TypeScript check**

```bash
npm run lint
```

Expected: TypeScript will error on `step.audioSrc` being undefined in `calculateMetadata` return — that's correct, it will be fixed in Task 5. Accept this error for now and move on.

- [ ] **Step 5: Commit**

```bash
git add src/Main.tsx
git commit -m "feat: add audioSrc to StepProps and render AudioPlayer in CodeStep"
```

---

### Task 5: Update `calculateMetadata` to resolve audio durations

**Files:**
- Modify: `src/calculate-metadata/calculate-metadata.tsx`

This is the most significant change. The current code computes `stepDurations` synchronously then builds `resolvedSteps` separately. We need to merge both into a single `await Promise.all(...)` that resolves audio duration for each step.

- [ ] **Step 1: Add the imports**

At the top of `calculate-metadata.tsx`, add a new line for `@remotion/media-utils`:
```ts
import { getAudioDurationInSeconds } from "@remotion/media-utils";
```

Then find the **existing** `remotion` import (which already imports `CalculateMetadataFunction`) and add `staticFile` to it:
```ts
// Before:
import { CalculateMetadataFunction } from "remotion";
// After:
import { CalculateMetadataFunction, staticFile } from "remotion";
```

Do **not** create a second `remotion` import line — add `staticFile` to the existing one.

- [ ] **Step 2: Replace the sequential stepDurations + resolvedSteps with a single parallel resolution**

Remove these lines:
```ts
// 計算每步 durationInFrames（from/to 單位為秒）
const stepDurations = stepConfigs.map((s) =>
  Math.round((s.to - s.from) * FPS),
);
const totalFrames = stepDurations.reduce((a, b) => a + b, 0);
```

And replace the existing `resolvedSteps` block (the `const resolvedSteps = stepConfigs.map(...)`) with:

```ts
// 組裝每步完整 props，同時讀取音訊長度（若存在）以調整 durationInFrames
const resolvedSteps = await Promise.all(
  stepConfigs.map(async (stepConfig, i) => {
    const paddedIndex = String(i + 1).padStart(2, "0");
    const audioSrc = staticFile(`${folder}/audio/step_${paddedIndex}.mp3`);

    let stepDuration = Math.round((stepConfig.to - stepConfig.from) * FPS);
    let resolvedAudioSrc: string | undefined = undefined;

    try {
      const secs = await getAudioDurationInSeconds(audioSrc);
      resolvedAudioSrc = audioSrc;
      stepDuration = Math.max(stepDuration, Math.ceil(secs * FPS));
    } catch {
      // 音訊檔不存在 — 使用 config 時長
    }

    const rawLine_unused = rawCodes[i]; // keep rawCodes in scope
    const annotations = (stepConfig.annotations ?? []).map((ann) => {
      const rawLine = rawCodes[i].split("\n")[ann.targetLine - 1] ?? "";
      const expanded = rawLine.replaceAll("\t", " ".repeat(tabSize));
      const lineChars = expanded.length;
      const leadingChars = expanded.match(/^ */)?.[0].length ?? 0;
      return {
        targetLine: ann.targetLine,
        text: ann.text,
        startFrame: Math.round(ann.startTime * FPS),
        theme: ann.theme,
        lineStartX: horizontalPadding + lineNumberGutterWidth + leadingChars * charWidth,
        lineEndX: horizontalPadding + lineNumberGutterWidth + lineChars * charWidth,
      };
    });

    return {
      code: highlightedSteps[i],
      durationInFrames: stepDuration,
      subtitle: stepConfig.subtitle,
      highlight: resolveHighlight(stepConfig.highlight),
      annotations,
      audioSrc: resolvedAudioSrc,
    };
  }),
);

// totalFrames は音訊解析後の實際時長で計算
const totalFrames = resolvedSteps.reduce((a, s) => a + s.durationInFrames, 0);
```

> **Note:** The `rawLine_unused` line is a workaround to silence any linter warning — remove it if it causes issues; the annotations closure already captures `rawCodes[i]` directly.

- [ ] **Step 3: Remove now-unused `stepDurations` reference from the return value**

The `return` block references `steps: resolvedSteps` — verify there are no remaining references to the old `stepDurations` variable and delete the line `const rawLine_unused = rawCodes[i];` added above (it was a placeholder comment).

The final `return` object should be unchanged except that `totalFrames` now comes from the new calculation:

```ts
return {
  durationInFrames: totalFrames,
  width: ...,            // unchanged
  props: {
    theme: props.theme,
    width: props.width,
    folder: props.folder,
    steps: resolvedSteps,
    themeColors,
    codeWidth,
    charWidth,
  },
};
```

- [ ] **Step 4: TypeScript check**

```bash
npm run lint
```

Expected: 0 errors. If TypeScript complains about `audioSrc` missing from the `StepProps` type, verify Task 4 was completed first.

- [ ] **Step 5: Verify in Remotion Studio (no audio)**

```bash
npm run dev
```

Open `http://localhost:3000`. Select `bubble_sort` folder. The video should render exactly as before (no audio yet since no mp3 files exist for most steps, or step_01.mp3 was generated in Task 2 testing).

- [ ] **Step 6: Verify audio plays in Studio**

With `public/bubble_sort/audio/step_01.mp3` present (generated in Task 2), preview step 1 in the Studio timeline. Audio should play when the step is active.

- [ ] **Step 7: Verify audio-extended step duration**

Generate a step whose subtitle produces audio longer than its configured `to - from` duration. Check that the Studio timeline shows the extended step length.

- [ ] **Step 8: Commit**

```bash
git add src/calculate-metadata/calculate-metadata.tsx
git commit -m "feat: resolve audio duration in calculateMetadata, extend steps when audio is longer"
```

---

## Final Verification

- [ ] **Generate all audio for bubble_sort**

```bash
npm run gen-audio bubble_sort
```

- [ ] **Preview full video in Studio**

```bash
npm run dev
```

Scrub through the timeline — verify audio plays in each step, annotations and highlights remain correct.

- [ ] **Render the final video**

```bash
npm run render bubble_sort
```

Expected: `out/bubble_sort.mp4` renders successfully with audio narration.

- [ ] **Final commit**

```bash
git add public/bubble_sort/audio/
git commit -m "feat: add audio narration to bubble_sort"
```
