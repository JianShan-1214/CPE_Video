import React from "react";
import { Easing, interpolate, useCurrentFrame } from "remotion";
import { fontSize, lineNumberGutterWidth, verticalPadding } from "./font";
import { LINE_HEIGHT } from "./HighlightOverlay";
import { HighlightConfig } from "./step-animations";

export const LineNumbers: React.FC<{
  totalLines: number;
  config: HighlightConfig;
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
        const isHighlighted =
          lineNum >= config.startLine && lineNum <= config.endLine;

        return (
          <div
            key={i}
            style={{
              height: LINE_HEIGHT,
              lineHeight: `${LINE_HEIGHT}px`,
              fontSize: fontSize * 0.7,
              fontFamily: "JetBrains Mono, monospace",
              textAlign: "right",
              paddingRight: 12,
              color: isHighlighted ? config.borderColor : "#4a5568",
              opacity: isHighlighted ? 0.4 + progress * 0.6 : 0.5,
              fontWeight: isHighlighted ? "700" : "400",
            }}
          >
            {lineNum}
          </div>
        );
      })}
    </div>
  );
};
