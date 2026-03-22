import { HighlightedCode } from "codehike/code";
import React, { useMemo } from "react";
import {
  AbsoluteFill,
  Easing,
  interpolate,
  Series,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { AudioPlayer } from "./AudioPlayer";
import { CodeTransition } from "./CodeTransition";
import { FloatingAnnotation } from "./FloatingAnnotation";
import { HighlightBox } from "./HighlightBox";
import { HighlightOverlay } from "./HighlightOverlay";
import { LineNumbers } from "./LineNumbers";
import { RefreshOnCodeChange } from "./ReloadOnCodeChange";
import { ThemeColors, ThemeProvider } from "./calculate-metadata/theme";
import { horizontalPadding, lineNumberGutterWidth, verticalPadding } from "./font";
import { CODE_SECTION_HEIGHT, IDEFrame, SUBTITLE_HEIGHT } from "./IDEFrame";
import { SubtitleBar } from "./SubtitleBar";
import { AnnotationCallout, HighlightConfig } from "./step-animations";
import { computeStepScroll } from "./step-visual-elements";

// ─── 型別定義 ──────────────────────────────────────────────────────────────────

export type StepProps = {
  code: HighlightedCode;
  durationInFrames: number;
  subtitle: string;
  focusLine: number | null;
  highlight: HighlightConfig | null;
  annotations: AnnotationCallout[];
  audioSrc: string | undefined;
};

export type Props = {
  steps: StepProps[] | null;
  themeColors: ThemeColors | null;
  codeWidth: number | null;
  charWidth: number | null;
  folder: string;
};

// ─── 常數 ─────────────────────────────────────────────────────────────────────

// 打字機動畫時長：85 frames ≈ 2.8 秒
const TRANSITION_DURATION = 85;
// Highlight 在打字結束後淡入
const ANIM_IN_START = TRANSITION_DURATION;

// ─── CodeStep ────────────────────────────────────────────────────────────────

const CodeStep: React.FC<{
  step: StepProps;
  prevCode: HighlightedCode | null;
  scrollFrom: number;
  scrollTo: number;
}> = ({ step, prevCode, scrollFrom, scrollTo }) => {
  const frame = useCurrentFrame();
  const { durationInFrames: stepDuration } = useVideoConfig();

  // ── 捲動：從上一步位置平滑移至本步目標，方向只往下 ──────────────
  const scrollY = interpolate(
    frame,
    [0, TRANSITION_DURATION],
    [scrollFrom, scrollTo],
    {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
      easing: Easing.inOut(Easing.ease),
    },
  );

  // ── 步驟進場：slide + fade in ───────────────────────────────────────
  const fadeIn = interpolate(frame, [0, 8], [0.88, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const slideY = interpolate(frame, [0, 12], [6, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.out(Easing.quad),
  });

  const outerStyle: React.CSSProperties = useMemo(
    () => ({
      position: "absolute" as const,
      inset: 0,
      opacity: fadeIn,
      transform: `translateY(${slideY}px)`,
    }),
    [fadeIn, slideY],
  );

  const scrollWrapStyle: React.CSSProperties = useMemo(
    () => ({
      position: "relative" as const,
      transform: `translateY(${-scrollY}px)`,
    }),
    [scrollY],
  );

  const codeWrapStyle: React.CSSProperties = useMemo(
    () => ({
      paddingTop: verticalPadding,
      paddingBottom: 20,
      paddingLeft: horizontalPadding + lineNumberGutterWidth,
      position: "relative" as const,
      zIndex: 3,
    }),
    [],
  );

  return (
    <div style={outerStyle}>
      <div style={scrollWrapStyle}>
        {step.highlight && (
          <HighlightOverlay
            config={step.highlight}
            showFromFrame={ANIM_IN_START}
            stepDuration={stepDuration}
            totalLines={step.code.tokens.length}
          />
        )}

        <LineNumbers
          totalLines={step.code.tokens.length}
          config={step.highlight ?? undefined}
          showFromFrame={ANIM_IN_START}
          stepDuration={stepDuration}
        />

        {step.annotations.map((callout, i) => (
          <React.Fragment key={i}>
            <HighlightBox
              targetLine={callout.targetLine}
              lineStartX={callout.lineStartX}
              lineEndX={callout.lineEndX}
              startFrame={callout.startFrame}
              stepDuration={stepDuration}
              theme={callout.theme}
            />
            <FloatingAnnotation
              callout={callout}
              stepDuration={stepDuration}
              lineEndX={callout.lineEndX}
            />
          </React.Fragment>
        ))}

        <div style={codeWrapStyle}>
          <CodeTransition
            oldCode={prevCode}
            newCode={step.code}
            durationInFrames={TRANSITION_DURATION}
          />
        </div>
      </div>
      {step.audioSrc && <AudioPlayer src={step.audioSrc} />}
    </div>
  );
};

// ─── Main ─────────────────────────────────────────────────────────────────────

export const Main: React.FC<Props> = ({ steps, themeColors, folder }) => {
  if (!steps) throw new Error("Steps are not defined");
  if (!themeColors) throw new Error("Theme colors are not defined");

  // ── 預計算每步捲動目標 ────────────────────────────────────────────
  const scrollTargets = useMemo(() => {
    const acc: number[] = [];
    for (let i = 0; i < steps.length; i++) {
      const prev = i > 0 ? acc[i - 1] : 0;
      acc.push(
        computeStepScroll({
          focusLine: steps[i].focusLine,
          highlight: steps[i].highlight,
          totalLines: steps[i].code.tokens.length,
          prevScroll: prev,
        }),
      );
    }
    return acc;
  }, [steps]);

  const subtitles = useMemo(() => steps.map((s) => s.subtitle), [steps]);

  return (
    <ThemeProvider themeColors={themeColors}>
      {/* ── 上方 85%：程式碼 IDE 區域 ── */}
      <div
        style={{
          position: "absolute",
          top: 0,
          left: 0,
          right: 0,
          height: CODE_SECTION_HEIGHT,
        }}
      >
        <IDEFrame filename={`${folder}.cpp`}>
          <AbsoluteFill>
            <Series>
              {steps.map((step, index) => (
                <Series.Sequence
                  key={index}
                  layout="none"
                  durationInFrames={step.durationInFrames}
                  name={
                    step.highlight
                      ? `${step.highlight.startLine}-${step.highlight.endLine}`
                      : step.focusLine
                        ? `focus-${step.focusLine}`
                        : "no-highlight"
                  }
                >
                  <CodeStep
                    step={step}
                    prevCode={steps[index - 1]?.code ?? null}
                    scrollFrom={index > 0 ? scrollTargets[index - 1] : 0}
                    scrollTo={scrollTargets[index]}
                  />
                </Series.Sequence>
              ))}
            </Series>
          </AbsoluteFill>
        </IDEFrame>
      </div>

      {/* ── 下方 15%：字幕區域 ── */}
      <div
        style={{
          position: "absolute",
          bottom: 0,
          left: 0,
          right: 0,
          height: SUBTITLE_HEIGHT,
        }}
      >
        <SubtitleBar subtitles={subtitles} stepDurations={steps.map((s) => s.durationInFrames)} />
      </div>

      <RefreshOnCodeChange />
    </ThemeProvider>
  );
};
