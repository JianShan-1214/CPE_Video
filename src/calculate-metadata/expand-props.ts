import { getThemeColors } from "@code-hike/lighter";
import { measureText } from "@remotion/layout-utils";
import { HighlightedCode } from "codehike/code";
import { isValidAnimation } from "../animation-layout";
import { ANNOTATION_ROOM } from "../FloatingAnnotation";
import { resolveHighlight, StepJSON } from "../config-types";
import {
  ANIMATION_PANEL_WIDTH,
  fontFamily,
  fontSize,
  horizontalPadding,
  lineNumberGutterWidth,
  tabSize,
  waitUntilDone,
} from "../font";
import { Props } from "../Main";
import { processSnippet } from "./process-snippet";
import { Theme } from "./theme";

export const FPS = 30;

export type RawStepInput = StepJSON & {
  /** 完整 cpp 內容（IO 層讀檔／前端 draft state 餵入） */
  fileContent: string;
  /** 音訊長度（秒），若提供則用於延長 durationInFrames */
  audioDurationSeconds?: number;
  /** 音訊資源 src（給 AudioPlayer），通常只有 render 時提供 */
  audioSrc?: string;
};

export type WidthConfig =
  | { type: "fixed"; value: number }
  | { type: "auto" };

export type ExpandPropsInput = {
  steps: RawStepInput[];
  theme: Theme;
  width: WidthConfig;
  folder: string;
};

export type ExpandPropsOutput = {
  durationInFrames: number;
  width: number;
  props: Props & { theme: Theme; width: WidthConfig };
};

/**
 * 純運算層：把已帶 cpp 內容的 raw steps 展開成 Main 需要的完整 props。
 *
 * IO 由呼叫方負責：
 *   - 後端 (calculate-metadata.tsx) 讀檔 + 讀音訊長度
 *   - 前端 (編輯介面) 從 localStorage 草稿讀 fileContent
 */
export const expandProps = async (
  input: ExpandPropsInput,
): Promise<ExpandPropsOutput> => {
  await waitUntilDone();

  // Syntax highlight
  const highlightedSteps: HighlightedCode[] = [];
  for (const step of input.steps) {
    const highlighted = await processSnippet(
      { filename: step.file, value: step.fileContent },
      input.theme,
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
    ...input.steps
      .flatMap((s) => s.fileContent.split("\n"))
      .map((line) => line.replaceAll("\t", " ".repeat(tabSize)).length),
  );
  const codeWidth = widthPerCharacter * maxCharacters;
  const charWidth = widthPerCharacter;

  const themeColors = await getThemeColors(input.theme);

  // 組裝每步完整 props
  const resolvedSteps = input.steps.map((step, i) => {
    let stepDuration = Math.round((step.to - step.from) * FPS);
    if (step.audioDurationSeconds !== undefined) {
      stepDuration = Math.max(
        stepDuration,
        Math.ceil(step.audioDurationSeconds * FPS),
      );
    }

    return {
      code: highlightedSteps[i],
      durationInFrames: stepDuration,
      subtitle: step.subtitle,
      focusLine: step.focusLine ?? null,
      highlight: step.highlight ? resolveHighlight(step.highlight) : null,
      annotations: (step.annotations ?? []).map((ann) => {
        const rawLine = step.fileContent.split("\n")[ann.targetLine - 1] ?? "";
        const expanded = rawLine.replaceAll("\t", " ".repeat(tabSize));
        const lineChars = expanded.length;
        const leadingChars = expanded.match(/^ */)?.[0].length ?? 0;
        return {
          targetLine: ann.targetLine,
          text: ann.text,
          startFrame: Math.round(ann.startTime * FPS),
          theme: ann.theme,
          lineStartX:
            horizontalPadding + lineNumberGutterWidth + leadingChars * charWidth,
          lineEndX:
            horizontalPadding + lineNumberGutterWidth + lineChars * charWidth,
        };
      }),
      audioSrc: step.audioSrc,
      // 不合法的動畫直接丟掉（不畫），不讓 render 崩潰
      animation: isValidAnimation(step.animation) ? step.animation : null,
    };
  });

  const totalFrames = resolvedSteps.reduce((a, s) => a + s.durationInFrames, 0);

  // 有任一步帶動畫時，右側加一塊固定寬度的動畫面板，並在程式碼與面板間留足標注氣泡的空間；
  // 沒有動畫的影片寬度完全不變
  const hasAnimation = resolvedSteps.some((s) => s.animation);
  const naturalWidth = hasAnimation
    ? horizontalPadding + lineNumberGutterWidth + codeWidth + ANNOTATION_ROOM + ANIMATION_PANEL_WIDTH
    : codeWidth + (horizontalPadding + lineNumberGutterWidth) * 2;
  const divisibleByTwo = Math.ceil(naturalWidth / 2) * 2;
  const minimumWidth = input.width.type === "fixed" ? 0 : 1080;
  const minimumWidthApplied = Math.max(minimumWidth, divisibleByTwo);

  return {
    durationInFrames: totalFrames,
    width:
      input.width.type === "fixed"
        ? Math.max(minimumWidthApplied, input.width.value)
        : minimumWidthApplied,
    props: {
      theme: input.theme,
      width: input.width,
      folder: input.folder,
      steps: resolvedSteps,
      themeColors,
      codeWidth,
      charWidth,
    },
  };
};
