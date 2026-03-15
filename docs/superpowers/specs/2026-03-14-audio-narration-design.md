# Audio Narration Design

**Date:** 2026-03-14
**Project:** CPE_Video — Remotion C++ Tutorial Video Generator
**Status:** Implemented

---

## Overview

Add AI-generated voice narration to each video step using **Google Cloud Gemini 2.5 Flash TTS** (`gemini-2.5-flash-tts`, voice: `Achernar`, language: `cmn-TW`). The narration text is the existing `subtitle` field in `config.json`. Audio is generated separately before rendering so the user can review and adjust subtitles before committing to a render.

Credentials are loaded from `GOOGLE_APPLICATION_CREDENTIALS` in `.env` (Service Account JSON). Required GCP roles: **Cloud Text-to-Speech API User** + **Vertex AI User**.

---

## Goals

- Each step gets a corresponding mp3 audio file read aloud by a zh-TW neural voice
- Audio generation is decoupled from rendering (`gen-audio` → review → `render`)
- If audio is shorter than the step, silence fills the gap; if longer, the step auto-extends
- Re-generating a single step's audio is fast and does not affect other steps
- No changes to `config.json` format — subtitle is the sole source of narration text

---

## Architecture

```
npm run gen-audio <folder> [--force] [--step N]
  ├─ reads public/<folder>/config.json
  ├─ for each step with non-empty subtitle:
  │    calls edge-tts CLI → public/<folder>/audio/step_01.mp3
  └─ skips existing files unless --force

npm run render <folder>
  ├─ calculateMetadata: reads audio duration for each step
  ├─ stepDuration = max(configDuration, audioDuration)
  ├─ totalFrames = sum of all resolved step durations (after audio extension)
  └─ Series.Sequence → CodeStep → <AudioPlayer src=... />
```

---

## Files Changed

| File | Change |
|------|--------|
| `scripts/gen-audio.mjs` | **New** — TTS generation script |
| `package.json` | Add `"gen-audio": "node scripts/gen-audio.mjs"`; add `@remotion/media-utils` |
| `src/calculate-metadata/calculate-metadata.tsx` | Read audio duration, adjust stepDuration, recompute totalFrames after resolution |
| `src/Main.tsx` | Add `audioSrc: string \| undefined` to `StepProps`; render `<AudioPlayer>` in `CodeStep` |
| `src/AudioPlayer.tsx` | **New** — thin wrapper around Remotion `<Audio />` |

---

## Detailed Design

### 1. `scripts/gen-audio.mjs`

**Usage:**
```bash
npm run gen-audio bubble_sort               # generate missing steps only
npm run gen-audio bubble_sort --force       # regenerate all steps
npm run gen-audio bubble_sort --step 3      # regenerate step 3 only (1-indexed)
```

**Error: missing `<folder>` argument**
```
Usage: npm run gen-audio <folder> [--force] [--step N]
```
Exits with code 1.

**Behaviour:**
1. Parse `process.argv` for folder, `--force`, `--step N`
2. If folder not provided: print usage, exit 1
3. Read and parse `public/<folder>/config.json`
4. Create `public/<folder>/audio/` directory if it does not exist (`fs.mkdirSync(..., { recursive: true })`)
5. For each step (filtered by `--step` if provided):
   - If `subtitle` is falsy or `subtitle.trim() === ""`: skip (log `[N/M] step_NN.mp3 (skipped — no subtitle)`)
   - Determine output path: `public/<folder>/audio/step_NN.mp3` (zero-padded to 2 digits, 1-indexed)
   - Skip if file exists and `--force` is not set (log `[N/M] step_NN.mp3 (skipped — exists)`)
   - Spawn: `edge-tts --voice zh-TW-HsiaoChenNeural --text "<subtitle>" --write-media <path>`
   - Log: `[N/M] step_NN.mp3 ✓`
6. If `edge-tts` command not found, print:
   ```
   Error: edge-tts not found. Install with:
     pip install edge-tts
   ```
   Exits with code 1.

**Audio file naming:** `step_01.mp3` … `step_99.mp3` (2-digit zero-padded, maximum 99 steps per folder).

**Voice:** `zh-TW-HsiaoChenNeural` (female, natural Mandarin zh-TW).

---

### 2. `calculateMetadata` — Duration Logic

**Runtime context note:** Remotion's `calculateMetadata` runs inside a headless Chromium browser (both in the Studio and during CLI render). This means browser APIs including `fetch` are available, and `getAudioDurationInSeconds` from `@remotion/media-utils` works correctly in this context.

**Key fix — `totalFrames` must be computed after audio resolution,** not from the raw config step durations. The existing `totalFrames = stepDurations.reduce(...)` must be replaced with a sum over the resolved steps.

```ts
import { getAudioDurationInSeconds } from "@remotion/media-utils";
import { staticFile } from "remotion";

// Replace the pre-computed totalFrames with post-resolution sum.
// Build resolvedSteps first (including audio-extended durations), then sum.

const resolvedSteps = await Promise.all(stepConfigs.map(async (stepConfig, i) => {
  const paddedIndex = String(i + 1).padStart(2, "0");
  const audioSrc = staticFile(`${folder}/audio/step_${paddedIndex}.mp3`);

  let stepDuration = Math.round((stepConfig.to - stepConfig.from) * FPS);
  let resolvedAudioSrc: string | undefined = undefined;

  try {
    const secs = await getAudioDurationInSeconds(audioSrc);
    resolvedAudioSrc = audioSrc;
    stepDuration = Math.max(stepDuration, Math.ceil(secs * FPS));
  } catch {
    // Audio file does not exist — use config duration only
  }

  const rawLine = rawCodes[i].split("\n")[/* annotation targetLine - 1 */];
  // ... existing annotation / highlight resolution unchanged ...

  return {
    code: highlightedSteps[i],
    durationInFrames: stepDuration,
    subtitle: stepConfig.subtitle,
    highlight: resolveHighlight(stepConfig.highlight),
    annotations: /* existing logic */,
    audioSrc: resolvedAudioSrc,
  };
}));

// totalFrames is now derived from audio-resolved durations:
const totalFrames = resolvedSteps.reduce((a, s) => a + s.durationInFrames, 0);
```

- `resolvedAudioSrc` is `undefined` when no audio file exists for a step
- Steps with no audio continue to use the config `from`/`to` duration unchanged

---

### 3. `src/AudioPlayer.tsx` (new)

```tsx
import { Audio } from "remotion";

export const AudioPlayer: React.FC<{ src: string }> = ({ src }) => (
  <Audio src={src} startFrom={0} />
);
```

`startFrom={0}` means "start from frame 0 of this audio file". This works correctly because `AudioPlayer` is always rendered inside a `Series.Sequence` — Remotion automatically scopes the audio playback to that sequence's time range.

---

### 4. `src/Main.tsx` — `StepProps` and `CodeStep`

**Updated `StepProps`:**
```ts
export type StepProps = {
  code: HighlightedCode;
  durationInFrames: number;
  subtitle: string;
  highlight: HighlightConfig;
  annotations: AnnotationCallout[];
  audioSrc: string | undefined;   // ← new
};
```

**Updated `CodeStep` JSX** (inside the returned JSX, alongside `<CodeTransition>`):
```tsx
<div style={outerStyle}>
  <div style={scrollWrapStyle}>
    {/* ... existing HighlightOverlay, LineNumbers, FloatingAnnotation, CodeTransition ... */}
  </div>
  {step.audioSrc && <AudioPlayer src={step.audioSrc} />}
</div>
```

`<AudioPlayer>` is placed inside the outer `<div>` of `CodeStep` (which is already inside `Series.Sequence`), ensuring audio is scoped to the step's duration.

---

## Timing Behaviour

| Scenario | Behaviour |
|----------|-----------|
| No audio file | Step uses `config.json` duration; no audio plays |
| Audio shorter than config duration | Audio plays; silence fills remaining frames |
| Audio longer than config duration | Step duration extended to `ceil(audioDuration × FPS)`; `totalFrames` updated accordingly |
| Subtitle empty / falsy | No mp3 generated; treated as "no audio file" at render time |

---

## Dependencies

- **edge-tts** (Python, external): `pip install edge-tts`
- **`@remotion/media-utils`** (npm): `npm install @remotion/media-utils` — add to `package.json`

---

## Workflow

```
1. Edit subtitles in public/<folder>/config.json
2. npm run gen-audio <folder>               # produce mp3 files
3. Review audio (play manually or preview in Remotion Studio)
4. Adjust subtitle text if needed → npm run gen-audio <folder> --force
5. npm run render <folder>                  # final render with audio
```

---

## Out of Scope

- Custom voice selection per step (all steps use the same voice)
- Background music or sound effects
- Word-by-word subtitle sync to audio waveform
- More than 99 steps per folder
