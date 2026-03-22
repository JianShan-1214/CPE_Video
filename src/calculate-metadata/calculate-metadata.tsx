import { getThemeColors } from "@code-hike/lighter";
import { measureText } from "@remotion/layout-utils";
import { HighlightedCode } from "codehike/code";
import { getAudioDurationInSeconds } from "@remotion/media-utils";
import { CalculateMetadataFunction, staticFile } from "remotion";
import { z } from "zod";
import { resolveHighlight } from "../config-types";
import { fontFamily, fontSize, horizontalPadding, lineNumberGutterWidth, tabSize, waitUntilDone } from "../font";
import { Props } from "../Main";
import { getFileByName, getVideoConfig } from "./get-files";
import { processSnippet } from "./process-snippet";
import { schema } from "./schema";

const FPS = 30;

export const calculateMetadata: CalculateMetadataFunction<
  Props & z.infer<typeof schema>
> = async ({ props }) => {
  const folder = props.folder;

  // 讀取 public/<folder>/config.json
  const config = await getVideoConfig(folder);
  const { steps: stepConfigs } = config;

  await waitUntilDone();

  // 載入各步驟的 cpp 原始碼（從同一個 folder 讀取）
  const rawCodes: string[] = [];
  for (const stepConfig of stepConfigs) {
    rawCodes.push(await getFileByName(folder, stepConfig.file));
  }

  // Syntax highlight
  const highlightedSteps: HighlightedCode[] = [];
  for (let i = 0; i < stepConfigs.length; i++) {
    const highlighted = await processSnippet(
      { filename: stepConfigs[i].file, value: rawCodes[i] },
      props.theme,
    );
    highlightedSteps.push(highlighted);
  }

  // 計算影片寬度（以最長的一行的原始字元數為準）
  const widthPerCharacter = measureText({
    text: "A",
    fontFamily,
    fontSize,
    validateFontIsLoaded: true,
  }).width;

  const maxCharacters = Math.max(
    ...rawCodes
      .flatMap((code) => code.split("\n"))
      .map((line) => line.replaceAll("\t", " ".repeat(tabSize)).length),
  );
  const codeWidth = widthPerCharacter * maxCharacters;
  const charWidth = widthPerCharacter;

  const themeColors = await getThemeColors(props.theme);

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

      return {
        code: highlightedSteps[i],
        durationInFrames: stepDuration,
        subtitle: stepConfig.subtitle,
        focusLine: stepConfig.focusLine ?? null,
        highlight: stepConfig.highlight ? resolveHighlight(stepConfig.highlight) : null,
        annotations: (stepConfig.annotations ?? []).map((ann) => {
          const rawLine = rawCodes[i].split("\n")[ann.targetLine - 1] ?? "";
          const expanded = rawLine.replaceAll("\t", " ".repeat(tabSize));
          const lineChars = expanded.length;
          const leadingChars = (expanded.match(/^ */)?.[0].length ?? 0);
          return {
            targetLine: ann.targetLine,
            text: ann.text,
            startFrame: Math.round(ann.startTime * FPS),
            theme: ann.theme,
            lineStartX: horizontalPadding + lineNumberGutterWidth + leadingChars * charWidth,
            lineEndX: horizontalPadding + lineNumberGutterWidth + lineChars * charWidth,
          };
        }),
        audioSrc: resolvedAudioSrc,
      };
    }),
  );

  const totalFrames = resolvedSteps.reduce((a, s) => a + s.durationInFrames, 0);

  const naturalWidth = codeWidth + (horizontalPadding + lineNumberGutterWidth) * 2;
  const divisibleByTwo = Math.ceil(naturalWidth / 2) * 2;
  const minimumWidth = props.width.type === "fixed" ? 0 : 1080;
  const minimumWidthApplied = Math.max(minimumWidth, divisibleByTwo);

  return {
    durationInFrames: totalFrames,
    width:
      props.width.type === "fixed"
        ? Math.max(minimumWidthApplied, props.width.value)
        : minimumWidthApplied,
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
};
