import React from "react";
import { interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { fontSize, horizontalPadding, lineNumberGutterWidth, verticalPadding } from "./font";
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

const LINE_GAP = 24;    // 程式碼右端到標注氣泡左邊的間距
const LEAD_LENGTH = 60; // 引導線長度

export const FloatingAnnotation: React.FC<{
  callout: AnnotationCallout;
  stepDuration: number;
  /** 程式碼內容最大寬度（px），用來定位標注氣泡 */
  codeWidth: number;
}> = ({ callout, stepDuration, codeWidth }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

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
  // 從左側滑入（程式碼右邊往右彈出）
  const slideX = interpolate(pop, [0, 1], [-12, 0]);

  // Y 座標：目標行的垂直中心
  const lineY = (callout.targetLine - 1) * LINE_HEIGHT + verticalPadding + LINE_HEIGHT / 2;

  // X 座標：程式碼右端 + 引導線 + 間距
  const annotationLeft =
    horizontalPadding + lineNumberGutterWidth + codeWidth + LINE_GAP + LEAD_LENGTH;

  return (
    <div
      style={{
        position: "absolute",
        top: lineY,            // 目標行垂直中心
        left: annotationLeft,
        opacity,
        // translateY(-50%) 讓容器自身高度不影響對齊，永遠置中於 lineY
        transform: `translateY(-50%) translateX(${slideX}px) scale(${scale})`,
        transformOrigin: "left center",
        pointerEvents: "none",
        zIndex: 20,
      }}
    >
      {/* 引導線（從氣泡左側往左延伸至程式碼右端） */}
      <div
        style={{
          position: "absolute",
          right: "100%",
          top: "50%",
          width: LEAD_LENGTH,
          height: 1.5,
          backgroundColor: theme.border,
          opacity: 0.7,
          marginRight: 0,
          transform: "translateY(-50%)",
        }}
      />

      {/* 引導線起點的小圓點 */}
      <div
        style={{
          position: "absolute",
          right: `calc(100% + ${LEAD_LENGTH}px)`,
          top: "50%",
          width: 5,
          height: 5,
          borderRadius: "50%",
          backgroundColor: theme.border,
          opacity: 0.8,
          transform: "translate(50%, -50%)",
        }}
      />

      {/* 標注氣泡 */}
      <div
        style={{
          backgroundColor: theme.bg,
          border: `1px solid ${theme.border}`,
          borderRadius: 6,
          padding: "7px 18px",
          color: theme.text,
          fontSize: fontSize * 0.95,
          fontFamily: "-apple-system, 'PingFang TC', 'Microsoft JhengHei', sans-serif",
          whiteSpace: "nowrap",
          boxShadow: "0 4px 20px rgba(0,0,0,0.5)",
          letterSpacing: "0.03em",
        }}
      >
        {callout.text}
      </div>
    </div>
  );
};
