import React from "react";
import { interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import {
  captionState,
  getSegment,
  gridCellSize,
  layoutArray,
  layoutGrid,
  layoutStacks,
  layoutVars,
} from "./animation-layout";
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
  bottom: number;
  colors: Colors;
}> = ({ state, bottom, colors }) => {
  const slot = INNER_W / state.slotCount;
  const size = Math.min(72, slot * 0.84);
  const rowY = CAPTION_H + (bottom - CAPTION_H) * 0.38 - size / 2;
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
  bottom: number;
  colors: Colors;
}> = ({ state, labels, bottom, colors }) => {
  const col = INNER_W / state.stackCount;
  const w = Math.min(120, col * 0.8);
  const labelH = 44;
  const baseY = bottom - PAD - labelH;
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

/** 格子內文字：舊值淡出、新值淡入，疊在同一位置 */
const Fading: React.FC<{
  t: { text: string; textOpacity: number; prevText: string; prevTextOpacity: number };
  render: (text: string) => React.ReactNode;
}> = ({ t, render }) => (
  <>
    {t.prevTextOpacity > 0 && (
      <div style={{ ...fill, opacity: t.prevTextOpacity }}>{render(t.prevText)}</div>
    )}
    <div style={{ ...fill, opacity: t.textOpacity }}>{render(t.text)}</div>
  </>
);

const fill: React.CSSProperties = {
  position: "absolute",
  inset: 0,
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
};

const GridView: React.FC<{
  state: ReturnType<typeof layoutGrid>;
  bottom: number;
  colors: Colors;
}> = ({ state, bottom, colors }) => {
  const areaH = bottom - PAD - CAPTION_H;
  const { slotW, slotH, cellW, cellH } = gridCellSize(
    state.rows,
    state.cols,
    INNER_W,
    areaH,
  );
  const left = PAD + (INNER_W - slotW * state.cols) / 2;
  const top = CAPTION_H + (areaH - slotH * state.rows) / 2;
  const base = Math.min(30, cellH * 0.45);
  return (
    <>
      {state.cells.map((c) => (
        <div
          key={c.key}
          style={{
            ...cellBox(cellH, colors),
            width: cellW,
            left: left + c.c * slotW + (slotW - cellW) / 2,
            top: top + c.r * slotH + (slotH - cellH) / 2,
            opacity: c.opacity,
            borderRadius: Math.min(8, cellH / 6),
            borderColor:
              c.mark > 0.5 ? MARK.borderColor : colors.editorGroup.border,
          }}
        >
          <div
            style={{
              position: "absolute",
              inset: 0,
              borderRadius: Math.min(6, cellH / 8),
              backgroundColor: MARK.bgColor,
              opacity: c.mark,
            }}
          />
          <Fading
            t={c}
            render={(text) => <CellText text={text} boxW={cellW} base={base} />}
          />
        </div>
      ))}
    </>
  );
};

const VarsTable: React.FC<{
  state: ReturnType<typeof layoutVars>;
  top: number;
  colors: Colors;
}> = ({ state, top, colors }) => {
  const { columns, rowH, fontSize } = state.table;
  const gap = 24;
  const colW = (INNER_W - gap * (columns - 1)) / columns;
  // 名稱欄依最長變數名決定，最多佔半欄；值欄拿剩下的
  const nameW = Math.min(
    colW / 2,
    Math.max(...state.items.map((v) => textEm(v.name))) * fontSize + 24,
  );
  const text: React.CSSProperties = {
    whiteSpace: "pre",
    overflow: "hidden",
    textOverflow: "ellipsis",
    fontFamily,
    fontSize,
  };
  return (
    <>
      {state.items.map((v) => (
        <div
          key={v.name}
          style={{
            position: "absolute",
            left: PAD + v.col * (colW + gap),
            top: top + v.row * rowH,
            width: colW,
            height: rowH - 6,
            opacity: v.opacity,
            display: "flex",
            alignItems: "center",
            borderRadius: 6,
            border: `2px solid ${
              v.mark > 0.5 ? MARK.borderColor : colors.editorGroup.border
            }`,
            backgroundColor: colors.editor.background,
            boxSizing: "border-box",
            overflow: "hidden",
          }}
        >
          <div
            style={{ ...fill, backgroundColor: MARK.bgColor, opacity: v.mark }}
          />
          <div
            style={{
              ...text,
              position: "relative",
              width: nameW,
              padding: "0 10px",
              boxSizing: "border-box",
              color: colors.editorLineNumber.foreground,
              borderRight: `1px solid ${colors.editorGroup.border}`,
            }}
          >
            {v.name}
          </div>
          <div
            style={{ position: "relative", flex: 1, height: "100%", minWidth: 0 }}
          >
            <Fading
              t={v}
              render={(t) => (
                <span
                  style={{
                    ...text,
                    maxWidth: "100%",
                    padding: "0 10px",
                    boxSizing: "border-box",
                    color: colors.editor.foreground,
                    fontWeight: 700,
                  }}
                >
                  {t}
                </span>
              )}
            />
          </div>
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
  const { index, progress } = getSegment(
    frame,
    duration,
    animation.frames.length,
  );
  const standalone = animation.type === "vars";
  const vars = layoutVars(animation.frames, index, progress, standalone);
  const tableH = vars.table.height;
  // 變數表貼底；沒有變數時 bottom = 面板底，主圖位置與加入變數表之前完全相同
  const tableTop = standalone
    ? CAPTION_H + (CODE_AREA_HEIGHT - PAD - CAPTION_H - tableH) / 2
    : CODE_AREA_HEIGHT - PAD - tableH;
  const bottom = tableH > 0 ? tableTop : CODE_AREA_HEIGHT;
  let main: React.ReactNode = null;
  let cap: ReturnType<typeof captionState>;
  if (animation.type === "array") {
    const s = layoutArray(animation, frame, duration);
    cap = s;
    main = <ArrayView state={s} bottom={bottom} colors={colors} />;
  } else if (animation.type === "stacks") {
    const s = layoutStacks(animation, frame, duration);
    cap = s;
    main = (
      <StacksView
        state={s}
        labels={animation.labels ?? []}
        bottom={bottom}
        colors={colors}
      />
    );
  } else if (animation.type === "grid") {
    const s = layoutGrid(animation, frame, duration);
    cap = s;
    main = <GridView state={s} bottom={bottom} colors={colors} />;
  } else {
    cap = captionState(
      animation.frames[Math.max(0, index - 1)].caption,
      animation.frames[index].caption,
      progress,
    );
  }
  return (
    <>
      <Caption
        text={cap.prevCaption}
        opacity={cap.prevCaptionOpacity}
        colors={colors}
      />
      <Caption text={cap.caption} opacity={cap.captionOpacity} colors={colors} />
      {main}
      {tableH > 0 && <VarsTable state={vars} top={tableTop} colors={colors} />}
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
