import React from "react";
import { interpolate, useCurrentFrame } from "remotion";
import { verticalPadding } from "./font";
import { LINE_HEIGHT } from "./HighlightOverlay";

const HPAD = 6;  // 水平留白
const VPAD = 4;  // 垂直留白
const BORDER = 2;

const THEMES = {
  blue:   "#388bfd",
  yellow: "#e3b341",
  green:  "#3fb950",
  red:    "#f85149",
};

// 順時針繪製框線（共 24 frames）
// Top:    df 0→8   左→右
// Right:  df 5→13  上→下
// Bottom: df 10→18 右→左
// Left:   df 15→23 下→上
const clamp01 = (v: number) => Math.max(0, Math.min(1, v));

export const HighlightBox: React.FC<{
  targetLine: number;
  lineStartX: number;
  lineEndX: number;
  startFrame: number;
  stepDuration: number;
  theme?: "blue" | "yellow" | "green" | "red";
}> = ({ targetLine, lineStartX, lineEndX, startFrame, stepDuration, theme = "yellow" }) => {
  const frame = useCurrentFrame();
  const df = frame - startFrame;

  const fadeIn = interpolate(frame, [startFrame, startFrame + 6], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const fadeOut = interpolate(frame, [stepDuration - 10, stepDuration - 2], [1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const baseOpacity = Math.min(fadeIn, fadeOut);

  const topProg    = clamp01(df / 8);
  const rightProg  = clamp01((df - 5) / 8);
  const bottomProg = clamp01((df - 10) / 8);
  const leftProg   = clamp01((df - 15) / 8);

  // 緊包程式碼文字的幾何（含小 padding）
  const boxLeft   = lineStartX - HPAD;
  const boxWidth  = lineEndX - lineStartX + HPAD * 2;
  const boxTop    = (targetLine - 1) * LINE_HEIGHT + verticalPadding - VPAD;
  const boxHeight = LINE_HEIGHT + VPAD * 2;

  const color = THEMES[theme];

  return (
    <div
      style={{
        position: "absolute",
        top: boxTop,
        left: boxLeft,
        width: boxWidth,
        height: boxHeight,
        opacity: baseOpacity,
        pointerEvents: "none",
        zIndex: 8,
      }}
    >
      {/* 上邊框：左→右 */}
      <div style={{ position: "absolute", top: 0, left: 0, width: `${topProg * 100}%`, height: BORDER, backgroundColor: color }} />
      {/* 右邊框：上→下 */}
      <div style={{ position: "absolute", top: 0, right: 0, width: BORDER, height: `${rightProg * 100}%`, backgroundColor: color }} />
      {/* 下邊框：右→左 */}
      <div style={{ position: "absolute", bottom: 0, right: 0, width: `${bottomProg * 100}%`, height: BORDER, backgroundColor: color }} />
      {/* 左邊框：下→上 */}
      <div style={{ position: "absolute", bottom: 0, left: 0, width: BORDER, height: `${leftProg * 100}%`, backgroundColor: color }} />
    </div>
  );
};
