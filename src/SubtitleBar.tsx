import React, { useMemo } from "react";
import { interpolate, useCurrentFrame } from "remotion";
import { SUBTITLE_HEIGHT } from "./IDEFrame";

export const SubtitleBar: React.FC<{
  subtitles: string[];
  stepDurations: number[];
}> = ({ subtitles, stepDurations }) => {
  const frame = useCurrentFrame();

  // 從累積 frame 計算當前步驟
  const { currentStep, stepFrame } = useMemo(() => {
    let elapsed = 0;
    for (let i = 0; i < stepDurations.length; i++) {
      if (frame < elapsed + stepDurations[i]) {
        return { currentStep: i, stepFrame: frame - elapsed };
      }
      elapsed += stepDurations[i];
    }
    const last = stepDurations.length - 1;
    return {
      currentStep: last,
      stepFrame: frame - (stepDurations.reduce((a, b) => a + b, 0) - stepDurations[last]),
    };
  }, [frame, stepDurations]);

  const text = subtitles[currentStep] ?? "";

  const opacity = interpolate(stepFrame, [0, 18], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const translateY = interpolate(stepFrame, [0, 18], [14, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const containerStyle: React.CSSProperties = useMemo(
    () => ({
      position: "absolute",
      inset: 0,
      backgroundColor: "#080c10",
      borderTop: "1px solid #21262d",
      display: "flex",
      flexDirection: "column",
      alignItems: "center",
      justifyContent: "center",
      padding: "0 100px",
      gap: 10,
    }),
    [],
  );

  const textStyle: React.CSSProperties = {
    opacity,
    transform: `translateY(${translateY}px)`,
    color: "#e6edf3",
    fontSize: 26,
    fontFamily: "'Noto Sans TC', 'PingFang TC', 'Microsoft JhengHei', sans-serif",
    lineHeight: 1.55,
    textAlign: "center",
    letterSpacing: "0.02em",
  };

  const dotsStyle: React.CSSProperties = useMemo(
    () => ({ display: "flex", gap: 10, marginTop: 4 }),
    [],
  );

  return (
    <div style={containerStyle}>
      <p style={textStyle}>{text}</p>
      <div style={dotsStyle}>
        {subtitles.map((_, i) => (
          <div
            key={i}
            style={{
              width: i === currentStep ? 24 : 8,
              height: 8,
              borderRadius: 4,
              backgroundColor:
                i < currentStep ? "#388bfd" : i === currentStep ? "#58a6ff" : "#30363d",
              transition: "width 0.2s",
            }}
          />
        ))}
      </div>
    </div>
  );
};

export { SUBTITLE_HEIGHT };
