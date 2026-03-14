import React from "react";
import { Easing, interpolate, useCurrentFrame } from "remotion";
import { fontSize, verticalPadding } from "./font";
import { HighlightConfig } from "./step-animations";

export const LINE_HEIGHT = fontSize * 1.5; // 36px
const DIM_BG = "rgb(13,17,23)";           // github-dark 背景色

/**
 * 三層視覺效果（全部 position:absolute，跟著捲動）：
 *  1. Highlight 背景光帶 + 左邊框
 *  2. 上方遮罩（highlight 以上的行變暗）
 *  3. 下方遮罩（highlight 以下的行變暗）
 */
export const HighlightOverlay: React.FC<{
  config: HighlightConfig;
  showFromFrame: number;
  stepDuration: number;
  totalLines: number;   // step.tokens.length
}> = ({ config, showFromFrame, stepDuration, totalLines }) => {
  const frame = useCurrentFrame();

  // 淡入（highlight 出現後）
  const fadeIn = interpolate(frame, [showFromFrame, showFromFrame + 14], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.out(Easing.quad),
  });

  // 步驟末尾淡出
  const fadeOut = interpolate(frame, [stepDuration - 8, stepDuration], [1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const progress = Math.min(fadeIn, fadeOut);
  const dimOpacity = progress * 0.82;       // 遮罩最深 82%
  const glowOpacity = progress;            // highlight 光帶

  // ── 尺寸計算 ────────────────────────────────────────────────────────
  const hlStart = config.startLine;
  const hlEnd   = config.endLine;

  const hlTop    = (hlStart - 1) * LINE_HEIGHT + verticalPadding;
  const hlHeight = (hlEnd - hlStart + 1) * LINE_HEIGHT;

  const topDimHeight    = hlTop;                               // 0 → hlTop
  const bottomDimTop    = hlTop + hlHeight;                    // hlEnd 之後
  const bottomDimHeight = (totalLines - hlEnd) * LINE_HEIGHT + 20;

  return (
    <>
      {/* ── 1. Highlight 光帶 ── */}
      <div
        style={{
          position: "absolute",
          top: hlTop,
          left: 0,
          right: 0,
          height: hlHeight,
          backgroundColor: config.bgColor,
          opacity: glowOpacity,
          pointerEvents: "none",
          zIndex: 1,
        }}
      />
      {/* 左側彩色邊框 */}
      <div
        style={{
          position: "absolute",
          top: hlTop,
          left: 0,
          width: 4,
          height: hlHeight,
          backgroundColor: config.borderColor,
          opacity: glowOpacity,
          pointerEvents: "none",
          zIndex: 2,
        }}
      />

      {/* ── 2. 上方暗化遮罩 ── */}
      {topDimHeight > 0 && (
        <div
          style={{
            position: "absolute",
            top: 0,
            left: 0,
            right: 0,
            height: topDimHeight,
            backgroundColor: DIM_BG,
            opacity: dimOpacity,
            pointerEvents: "none",
            zIndex: 5,
          }}
        />
      )}

      {/* ── 3. 下方暗化遮罩 ── */}
      {bottomDimHeight > 0 && (
        <div
          style={{
            position: "absolute",
            top: bottomDimTop,
            left: 0,
            right: 0,
            height: Math.max(0, bottomDimHeight),
            backgroundColor: DIM_BG,
            opacity: dimOpacity,
            pointerEvents: "none",
            zIndex: 5,
          }}
        />
      )}
    </>
  );
};
