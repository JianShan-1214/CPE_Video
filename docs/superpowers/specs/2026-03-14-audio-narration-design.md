# Audio Narration Design

**Date:** 2026-03-14
**Project:** CPE_Video — Remotion C++ Tutorial Video Generator
**Status:** Approved

---

## Overview

Add AI-generated voice narration to each video step using `edge-tts` (Microsoft Azure Neural TTS, free). The narration text is the existing `subtitle` field in `config.json`. Audio is generated separately before rendering so the user can review and adjust subtitles before committing to a render.

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
  ├─ for each step: calls edge-tts CLI → public/<folder>/audio/step_01.mp3
  └─ skips existing files unless --force

npm run render <folder>
  ├─ calculateMetadata: reads audio duration for each step
  ├─ stepDuration = max(configDuration, audioDuration)
  └─ Series.Sequence → CodeStep → <Audio src=... startFrom={0} />
```

---

## Files Changed

| File | Change |
|------|--------|
| `scripts/gen-audio.mjs` | **New** — TTS generation script |
| `package.json` | Add `"gen-audio": "node scripts/gen-audio.mjs"` |
| `src/calculate-metadata/calculate-metadata.tsx` | Read audio duration, adjust stepDuration |
| `src/Main.tsx` | Add `audioSrc?: string` to `StepProps`; pass to CodeStep |
| `src/AudioPlayer.tsx` | **New** — thin wrapper around Remotion `<Audio />` |

---

## Detailed Design

### 1. `scripts/gen-audio.mjs`

**Usage:**
```bash
npm run gen-audio bubble_sort               # generate missing steps only
npm run gen-audio bubble_sort --force       # regenerate all steps
npm run gen-audio bubble_sort --step 3     # regenerate step 3 only
```

**Behaviour:**
1. Parse `process.argv` for folder, `--force`, `--step N`
2. Read and parse `public/<folder>/config.json`
3. Create `public/<folder>/audio/` directory if absent
4. For each step (filtered by `--step` if provided):
   - Determine output path: `public/<folder>/audio/step_NN.mp3` (zero-padded, 1-indexed)
   - Skip if file exists and `--force` is not set
   - Spawn `edge-tts --voice zh-TW-HsiaoChenNeural --text "<subtitle>" --write-media <path>`
   - Log progress: `[1/12] step_01.mp3 ✓` or `[1/12] step_01.mp3 (skipped)`
5. If `edge-tts` command not found, print:
   ```
   edge-tts not found. Install with:  pip install edge-tts
   ```
   and exit with code 1

**Audio file naming:** `step_01.mp3`, `step_02.mp3`, … (zero-padded to 2 digits)

**Voice:** `zh-TW-HsiaoChenNeural` (female, natural Mandarin zh-TW)

---

### 2. `calculateMetadata` — Duration Logic

```ts
import { getAudioDurationInSeconds, staticFile } from "remotion";

// for each step i:
const audioPath = `${folder}/audio/step_${String(i + 1).padStart(2, "0")}.mp3`;
let audioDurationFrames = 0;
try {
  const secs = await getAudioDurationInSeconds(staticFile(audioPath));
  audioDurationFrames = Math.ceil(secs * FPS);
} catch {
  // audio file does not exist — use config duration only
}

const configFrames = Math.round((stepConfig.to - stepConfig.from) * FPS);
const stepDuration = Math.max(configFrames, audioDurationFrames);
```

- `audioSrc` is set to `staticFile(audioPath)` when the file exists, otherwise `undefined`
- `audioSrc` is stored in `StepProps` and passed through to the component tree

---

### 3. `src/AudioPlayer.tsx` (new)

A minimal component that renders Remotion's `<Audio />` only when an `audioSrc` is provided:

```tsx
import { Audio } from "remotion";

export const AudioPlayer: React.FC<{ src: string }> = ({ src }) => (
  <Audio src={src} startFrom={0} />
);
```

Kept as a separate file so it can be conditionally imported and easily mocked in tests.

---

### 4. `src/Main.tsx` — `StepProps` and `CodeStep`

Add to `StepProps`:
```ts
audioSrc?: string;
```

Inside `CodeStep` render:
```tsx
{step.audioSrc && <AudioPlayer src={step.audioSrc} />}
```

The `<Audio />` starts at frame 0 of each `Series.Sequence`, synchronised with the typewriter animation onset.

---

## Timing Behaviour

| Scenario | Behaviour |
|----------|-----------|
| No audio file | Step uses `config.json` duration, no audio plays |
| Audio shorter than config duration | Audio plays, silence fills remaining frames |
| Audio longer than config duration | Step duration extended to `ceil(audioDuration × FPS)` |

---

## Dependencies

- **edge-tts** (Python): `pip install edge-tts`
  No new npm packages required. Remotion's `getAudioDurationInSeconds` and `<Audio />` are already available in the existing `remotion` dependency.

---

## Workflow

```
1. Edit subtitles in public/<folder>/config.json
2. npm run gen-audio <folder>          # produces mp3 files
3. Preview audio files (play manually or in Remotion Studio)
4. Adjust subtitle text if needed → repeat step 2 with --force
5. npm run render <folder>             # final render with audio
```

---

## Out of Scope

- Custom voice selection per step (all steps use the same voice)
- Background music or sound effects
- Subtitle/caption rendering from audio (already handled by existing SubtitleBar)
- Automatic subtitle sync to audio timing (subtitles follow step boundaries, not word-by-word)
