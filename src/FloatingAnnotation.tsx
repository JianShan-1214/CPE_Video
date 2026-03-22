import React from "react";
import { interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { fontSize, verticalPadding } from "./font";
import { LINE_HEIGHT } from "./HighlightOverlay";

export interface AnnotationCallout {
  /** 要標注的行（1-indexed） */
  targetLine: number;
  /** 標注文字 */
  text: string;
  /** 相對步驟起點的出現 frame */
  startFrame: number;
  /** 顏色主題：blue | yellow | green | red */
  theme?: "blue" | "yellow" | "green" | "red";
}

const THEMES = {
  blue:   { bg: "rgba(56,139,253,0.15)",  border: "#388bfd", text: "#79c0ff" },
  yellow: { bg: "rgba(227,179,65,0.15)",  border: "#e3b341", text: "#e3b341" },
  green:  { bg: "rgba(63,185,80,0.15)",   border: "#3fb950", text: "#56d364" },
  red:    { bg: "rgba(248,81,73,0.15)",   border: "#f85149", text: "#ff7b72" },
};

const LINE_GAP = 16;    // 程式碼右端到垂直指示條的間距
const LEAD_LENGTH = 52; // 水平引導線長度

export const FloatingAnnotation: React.FC<{
  callout: AnnotationCallout;
  stepDuration: number;
  /** 該行程式碼右端的 X 座標（px），由 calculateMetadata 計算後填入 */
  lineEndX: number;
}> = ({ callout, stepDuration, lineEndX }) => {
  const frame = useCurrentFrame();
  const { fps, width: videoWidth } = useVideoConfig();

  const theme = THEMES[callout.theme ?? "yellow"];

  // spring 彈出動畫
  const pop = spring({
    frame: frame - callout.startFrame,
    fps,
    config: { damping: 12, stiffness: 160, mass: 0.7 },
    durationInFrames: 18,
  });

  // 步驟末尾淡出
  const fadeOut = interpolate(
    frame,
    [stepDuration - 12, stepDuration - 2],
    [1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );

  const opacity = pop * fadeOut;
  const scale  = interpolate(pop, [0, 1], [0.6, 1]);

  // 目標行垂直中心
  const lineY = (callout.targetLine - 1) * LINE_HEIGHT + verticalPadding + LINE_HEIGHT / 2;

  // X 座標計算
  const SAFE_MARGIN = 32;
  const indicatorX  = lineEndX + LINE_GAP;
  const guideStartX = indicatorX + 3;
  const bubbleX     = guideStartX + LEAD_LENGTH;
  const bubbleMaxWidth = Math.max(160, videoWidth - bubbleX - SAFE_MARGIN);
  const slideX      = interpolate(pop, [0, 1], [-16, 0]);

  return (
    <>
      {/* 垂直指示條：跨越整行高度，明確標示這是哪一行 */}
      <div
        style={{
          position: "absolute",
          top: lineY - LINE_HEIGHT / 2,
          left: indicatorX,
          width: 3,
          height: LINE_HEIGHT,
          backgroundColor: theme.border,
          opacity: opacity * 0.85,
          borderRadius: 1.5,
          pointerEvents: "none",
          zIndex: 20,
        }}
      />

      {/* 水平引導線：從垂直條中心往右延伸到氣泡 */}
      <div
        style={{
          position: "absolute",
          top: lineY - 0.75,
          left: guideStartX,
          width: LEAD_LENGTH,
          height: 1.5,
          backgroundColor: theme.border,
          opacity: opacity * 0.65,
          pointerEvents: "none",
          zIndex: 20,
        }}
      />

      {/* 標注氣泡 */}
      <div
        style={{
          position: "absolute",
          top: lineY,
          left: bubbleX,
          opacity,
          transform: `translateY(-50%) translateX(${slideX}px) scale(${scale})`,
          transformOrigin: "left center",
          pointerEvents: "none",
          zIndex: 20,
        }}
      >
        <div
          style={{
            backgroundColor: theme.bg,
            border: `1px solid ${theme.border}`,
            borderRadius: 6,
            padding: "7px 18px",
            color: theme.text,
            fontSize: fontSize * 0.95,
            fontFamily: "-apple-system, 'PingFang TC', 'Microsoft JhengHei', sans-serif",
            maxWidth: bubbleMaxWidth,
            whiteSpace: "normal",
            boxShadow: "0 4px 20px rgba(0,0,0,0.5)",
            letterSpacing: "0.03em",
          }}
        >
          {callout.text}
        </div>
      </div>
    </>
  );
};
