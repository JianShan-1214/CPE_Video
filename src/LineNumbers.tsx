import React from "react";
import { Easing, interpolate, useCurrentFrame } from "remotion";
import { fontSize, lineNumberGutterWidth, verticalPadding } from "./font";
import { LINE_HEIGHT } from "./HighlightOverlay";
import { HighlightConfig } from "./step-animations";
import { getLineNumberAppearance } from "./step-visual-elements";

export const LineNumbers: React.FC<{
  totalLines: number;
  config?: HighlightConfig;
  showFromFrame: number;
  stepDuration: number;
}> = ({ totalLines, config, showFromFrame, stepDuration }) => {
  const frame = useCurrentFrame();

  const fadeIn = interpolate(frame, [showFromFrame, showFromFrame + 14], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.out(Easing.quad),
  });
  const fadeOut = interpolate(frame, [stepDuration - 8, stepDuration], [1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const progress = Math.min(fadeIn, fadeOut);

  return (
    <div
      style={{
        position: "absolute",
        top: verticalPadding,
        left: 0,
        width: lineNumberGutterWidth - 8,
        pointerEvents: "none",
        zIndex: 6,
        userSelect: "none",
      }}
    >
      {Array.from({ length: totalLines }, (_, i) => {
        const lineNum = i + 1;
        const appearance = getLineNumberAppearance(lineNum, config, progress);

        return (
          <div
            key={i}
            style={{
              height: LINE_HEIGHT,
              display: "flex",
              alignItems: "center",
              justifyContent: "flex-end",
              fontSize: fontSize * 0.7,
              fontFamily: "JetBrains Mono, monospace",
              paddingRight: 12,
              color: appearance.color,
              opacity: appearance.opacity,
              fontWeight: appearance.fontWeight,
            }}
          >
            {lineNum}
          </div>
        );
      })}
    </div>
  );
};
