import React from "react";
import { interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { layoutArray, layoutStacks } from "./animation-layout";
import { useThemeColors } from "./calculate-metadata/theme";
import { HIGHLIGHT_PRESETS, StepAnimation } from "./config-types";
import { ANIMATION_PANEL_WIDTH, fontFamily } from "./font";
import { CODE_AREA_HEIGHT } from "./IDEFrame";

const PAD = 40;
const INNER_W = ANIMATION_PANEL_WIDTH - PAD * 2;
const CAPTION_H = 150;
const MARK = HIGHLIGHT_PRESETS.green;
const POINTER = HIGHLIGHT_PRESETS.yellow.borderColor;
const captionFont =
  "'Noto Sans TC', 'PingFang TC', 'Microsoft JhengHei', sans-serif";

type Colors = ReturnType<typeof useThemeColors>;

/** 字寬（em）：ASCII 等寬字 0.6em，全形字約 1em */
const textEm = (text: string) =>
  [...text].reduce((w, c) => w + (c.charCodeAt(0) > 0xff ? 1 : 0.6), 0);

/** 字級縮到塞得進 boxW，最小 MIN_FONT；再塞不下交給 ellipsis */
const MIN_FONT = 14;
const fitFont = (text: string, boxW: number, base: number) =>
  Math.max(MIN_FONT, Math.min(base, (boxW - 12) / Math.max(1, textEm(text))));

const CellText: React.FC<{ text: string; boxW: number; base: number }> = ({
  text,
  boxW,
  base,
}) => (
  <span
    style={{
      position: "relative",
      maxWidth: boxW - 8,
      fontSize: fitFont(text, boxW, base),
      whiteSpace: "pre",
      overflow: "hidden",
      textOverflow: "ellipsis",
    }}
  >
    {text}
  </span>
);

// 字幕最多兩行（超過加 ellipsis），長字幕先縮字級，絕不壓到下方的格子
const Caption: React.FC<{ text: string; opacity: number; colors: Colors }> = ({
  text,
  opacity,
  colors,
}) => (
  <div
    style={{
      position: "absolute",
      top: PAD,
      left: PAD,
      width: INNER_W,
      maxHeight: CAPTION_H - PAD,
      opacity,
      color: colors.editor.foreground,
      fontFamily: captionFont,
      fontSize: textEm(text) * 26 > INNER_W * 2 ? 22 : 26,
      lineHeight: 1.5,
      textAlign: "center",
      whiteSpace: "pre-line",
      display: "-webkit-box",
      WebkitLineClamp: 2,
      WebkitBoxOrient: "vertical",
      overflow: "hidden",
    }}
  >
    {text}
  </div>
);

const cellBox = (size: number, colors: Colors): React.CSSProperties => ({
  position: "absolute",
  width: size,
  height: size,
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  borderRadius: 8,
  border: `2px solid ${colors.editorGroup.border}`,
  backgroundColor: colors.editor.background,
  color: colors.editor.foreground,
  fontFamily,
  fontWeight: 700,
  boxSizing: "border-box",
});

const ArrayView: React.FC<{
  state: ReturnType<typeof layoutArray>;
  colors: Colors;
}> = ({ state, colors }) => {
  const slot = INNER_W / state.slotCount;
  const size = Math.min(72, slot * 0.84);
  const rowY = CAPTION_H + (CODE_AREA_HEIGHT - CAPTION_H) * 0.38 - size / 2;
  const base = Math.min(30, size * 0.45);
  return (
    <>
      {state.cells.map((c) => {
        const text = String(c.value);
        // 長字串可把格子撐寬到整個 slot，但不會超出（整列仍在面板內）
        const w = Math.max(size, Math.min(slot - 6, textEm(text) * base + 20));
        return (
          <div
            key={c.key}
            style={{
              ...cellBox(size, colors),
              width: w,
              left: PAD + c.x * slot + (slot - w) / 2,
              top: rowY + c.lift * size * 0.7,
              opacity: c.opacity,
              borderColor:
                c.mark > 0.5 ? MARK.borderColor : colors.editorGroup.border,
              zIndex: c.lift !== 0 ? 1 : 0,
            }}
          >
            <div
              style={{
                position: "absolute",
                inset: 0,
                borderRadius: 6,
                backgroundColor: MARK.bgColor,
                opacity: c.mark,
              }}
            />
            <CellText text={text} boxW={w} base={base} />
          </div>
        );
      })}
      {state.pointers.map((p) => (
        <div
          key={p.name}
          style={{
            position: "absolute",
            left: PAD + p.x * slot,
            width: slot,
            top: rowY + size + 16,
            opacity: p.opacity,
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            color: POINTER,
            fontFamily,
            fontWeight: 700,
            fontSize: 24,
            lineHeight: 1.2,
          }}
        >
          <span>▲</span>
          <span>{p.name}</span>
        </div>
      ))}
    </>
  );
};

const StacksView: React.FC<{
  state: ReturnType<typeof layoutStacks>;
  labels: string[];
  colors: Colors;
}> = ({ state, labels, colors }) => {
  const col = INNER_W / state.stackCount;
  const w = Math.min(120, col * 0.8);
  const labelH = 44;
  const baseY = CODE_AREA_HEIGHT - PAD - labelH;
  // 多留一層給換堆時的 lift-over 路徑
  const h = Math.min(56, (baseY - CAPTION_H - 20) / (state.maxHeight + 1));
  return (
    <>
      {Array.from({ length: state.stackCount }, (_, i) => (
        <React.Fragment key={i}>
          <div
            style={{
              position: "absolute",
              left: PAD + i * col + (col - w) / 2 - 8,
              width: w + 16,
              top: baseY,
              height: 3,
              backgroundColor: colors.editorLineNumber.foreground,
            }}
          />
          <div
            style={{
              position: "absolute",
              left: PAD + i * col,
              width: col,
              top: baseY + 10,
              textAlign: "center",
              color: colors.editorLineNumber.foreground,
              fontFamily: captionFont,
              fontSize: 22,
            }}
          >
            {labels[i] ?? ""}
          </div>
        </React.Fragment>
      ))}
      {state.blocks.map((b) => (
        <div
          key={b.key}
          style={{
            ...cellBox(Math.min(w, h), colors),
            width: w,
            height: h - 4,
            left: PAD + b.stack * col + (col - w) / 2,
            top: baseY - (b.level + 1) * h,
            opacity: b.opacity,
          }}
        >
          <CellText
            text={String(b.value)}
            boxW={w}
            base={Math.min(30, h * 0.45)}
          />
        </div>
      ))}
    </>
  );
};

const Content: React.FC<{
  animation: StepAnimation;
  frame: number;
  duration: number;
  colors: Colors;
}> = ({ animation, frame, duration, colors }) => {
  const s =
    animation.type === "array"
      ? layoutArray(animation, frame, duration)
      : layoutStacks(animation, frame, duration);
  return (
    <>
      <Caption
        text={s.prevCaption}
        opacity={s.prevCaptionOpacity}
        colors={colors}
      />
      <Caption text={s.caption} opacity={s.captionOpacity} colors={colors} />
      {animation.type === "array" ? (
        <ArrayView
          state={s as ReturnType<typeof layoutArray>}
          colors={colors}
        />
      ) : (
        <StacksView
          state={s as ReturnType<typeof layoutStacks>}
          labels={animation.labels ?? []}
          colors={colors}
        />
      )}
    </>
  );
};

const FADE_FRAMES = 15;

/**
 * 程式碼區右側的演算法動畫面板；frame 為步驟內的 local frame。
 * 上一步也有動畫時面板底不淡入（避免換步時閃一下），內容先淡出上一步最後一格、再淡入本步（不疊影）。
 */
export const AnimationPanel: React.FC<{
  animation: StepAnimation;
  prevAnimation: StepAnimation | null;
}> = ({ animation, prevAnimation }) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  const colors = useThemeColors();
  const fade = interpolate(frame, [0, FADE_FRAMES], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const layer: React.CSSProperties = { position: "absolute", inset: 0 };

  return (
    <div
      style={{
        position: "absolute",
        top: 0,
        right: 0,
        width: ANIMATION_PANEL_WIDTH,
        height: CODE_AREA_HEIGHT,
        backgroundColor: colors.editorGroupHeader.tabsBackground,
        borderLeft: `1px solid ${colors.editorGroup.border}`,
        opacity: prevAnimation ? 1 : fade,
        overflow: "hidden",
        zIndex: 5,
      }}
    >
      {prevAnimation && fade < 0.5 && (
        <div style={{ ...layer, opacity: 1 - 2 * fade }}>
          {/* 上一步停在最後一格：frame 取極大值即為最終狀態 */}
          <Content
            animation={prevAnimation}
            frame={Number.MAX_SAFE_INTEGER}
            duration={1}
            colors={colors}
          />
        </div>
      )}
      <div
        style={{
          ...layer,
          opacity: prevAnimation ? Math.max(0, 2 * fade - 1) : 1,
        }}
      >
        <Content
          animation={animation}
          frame={frame}
          duration={durationInFrames}
          colors={colors}
        />
      </div>
    </div>
  );
};
