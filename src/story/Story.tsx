import React, { useMemo } from "react";
import { AbsoluteFill, Audio, Sequence, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import { fontFamily } from "../font";
import {
  buildCodeTimeline,
  buildKeyframes,
  currentSubtitle,
  evalCode,
  evalElement,
  evalLayout,
  fitRects,
  FULLCODE,
  fullcodeColumns,
  subtitleTop,
  autoWidth,
  findCue,
  flatten,
  clamp01,
} from "./timeline";
import { tokenizeLine } from "./tokenize";
import { StoryProps } from "./types";

const CJK = "'Noto Sans TC', 'PingFang TC', 'Microsoft JhengHei', sans-serif";
const STAGE_W = 1200;
const STAGE_H = 460;

export const Story: React.FC<StoryProps> = ({ story, timeline, code, folder }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const T = frame / fps;

  const data = useMemo(() => {
    if (!story || !timeline) return null;
    const cues = flatten(story, timeline);
    const kfs = buildKeyframes(cues);
    const fit = story.stageFit === "auto" ? fitRects(cues) : undefined;
    const codeTl = buildCodeTimeline(cues, code.replace(/\s+$/, "").split("\n").length);
    const lines = code.replace(/\s+$/, "").split("\n");
    const toks = lines.map(tokenizeLine);
    // cap 最近一次變更的時間
    const capSince: number[] = [];
    cues.forEach((c, i) => {
      if (i === 0 || cues[i - 1].cap !== c.cap || c.sceneFirst) capSince.push(c.start);
      else capSince.push(capSince[i - 1]);
    });
    return { cues, kfs, codeTl, lines, toks, capSince, fit };
  }, [story, timeline, code]);

  if (!data || !story || !timeline) return <AbsoluteFill style={{ background: "#0d1117" }} />;
  const { cues, kfs, codeTl, toks, capSince, fit } = data;

  const L = evalLayout(cues, T, fit);
  const cue = cues[L.index];
  const codeSt = evalCode(codeTl, T, L.index);
  const sub = currentSubtitle(cues, T);
  const rect = L.rect;
  const isCode = cue.layout === "code" || cue.layout === "split";
  // D-020 E1：fullcode 時舞台與一般程式面板隨 fullOp 淡出；fullOp=0（所有舊版面）時下面的 opacity 與以前逐值相同
  const fullOp = L.fullOp;
  const animOpacity = fullOp > 0 ? L.animOp * (1 - fullOp) : L.animOp;

  // ── 程式碼 ──
  const total = toks.length;
  const maxScroll = Math.max(0, total * rect.codeLh - rect.codeH);
  const scroll = Math.min(maxScroll, Math.max(0, codeSt.center * rect.codeLh - rect.codeH / 2));
  const firstLineT = codeTl.revealAt.get(1) ?? Infinity;
  const codeShow = story.revealAll ? 1 : clamp01((T - (cues.find((c) => c.lines.length)?.start ?? Infinity)) / 0.3);
  const codeOpacity = fullOp > 0 ? L.codeOp * codeShow * (1 - fullOp) : L.codeOp * codeShow;
  void firstLineT;

  // ── cap ──
  const capA = clamp01((T - capSince[L.index]) / 0.25);
  const capPos = isCode
    ? cue.layout === "split"
      ? { left: 1070, width: 816, top: 100, fontSize: 30 }
      : { left: 1215, width: 660, top: 165, fontSize: 30 }
    : { left: 90, width: 1740, top: 100, fontSize: 40 };

  const progress = cue.scene / Math.max(1, story.scenes.length - 1);

  return (
    <AbsoluteFill style={{ background: "#0d1117", fontFamily: CJK, color: "#e6edf3" }}>
      {/* header */}
      <div style={{ position: "absolute", left: 40, top: 22, right: 40, height: 56, display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <div style={{ fontSize: 28, color: "#8b949e" }}>{story.title}</div>
        <div style={{ fontSize: 34, fontWeight: 700, color: "#e6edf3" }}>
          {cue.scene + 1}／{story.scenes.length}　{cue.sceneLabel}
        </div>
      </div>
      <div style={{ position: "absolute", left: 0, top: 84, height: 4, width: 1920, background: "#21262d" }} />
      <div style={{ position: "absolute", left: 0, top: 84, height: 4, width: 1920 * (0.04 + 0.96 * progress), background: "#e3aa28" }} />

      {/* cap */}
      {cue.cap && cue.layout !== "fullcode" ? (
        <div
          style={{
            position: "absolute",
            ...capPos,
            textAlign: "center",
            fontWeight: 700,
            color: "#ffe282",
            opacity: capA * (cue.focus === "code" ? 0.3 : 1),
            transform: `translateY(${(1 - capA) * 8}px)`,
            whiteSpace: "nowrap",
          }}
        >
          {cue.cap}
        </div>
      ) : null}

      {/* stage */}
      <div
        style={{
          position: "absolute",
          left: rect.stageX,
          top: rect.stageY,
          width: STAGE_W,
          height: STAGE_H,
          transform: `scale(${rect.stageScale})`,
          transformOrigin: "0 0",
          opacity: animOpacity,
        }}
      >
        {[...kfs.entries()].map(([id, list]) => {
          const r = evalElement(list, T);
          if (!r || r.opacity <= 0.01) return null;
          if (r.shape === "line") {
            const len = Math.hypot(r.w, r.h);
            const ang = (Math.atan2(r.h, r.w) * 180) / Math.PI;
            const th = r.fs > 0 && r.fs < 20 ? r.fs : 5;
            return (
              <div
                key={id}
                style={{
                  position: "absolute",
                  left: r.x,
                  top: r.y - th / 2,
                  width: len,
                  height: th,
                  opacity: r.opacity,
                  transform: `rotate(${ang}deg)`,
                  transformOrigin: "0 50%",
                  background: r.border,
                  borderRadius: th / 2,
                }}
              >
                {r.arrow ? (
                  <div
                    style={{
                      position: "absolute",
                      right: -2,
                      top: -th * 1.6,
                      width: 0,
                      height: 0,
                      borderTop: `${th * 2.6}px solid transparent`,
                      borderBottom: `${th * 2.6}px solid transparent`,
                      borderLeft: `${th * 4}px solid ${r.border}`,
                      transform: "translateY(" + (th * 1.6 - th * 0.5 + th * 0) + "px)",
                    }}
                  />
                ) : null}
              </div>
            );
          }
          return (
            <div
              key={id}
              style={{
                position: "absolute",
                left: r.x,
                top: r.y,
                width: fit ? autoWidth(id, r.w, r.text, r.fs) : r.w,
                height: r.h,
                opacity: r.opacity,
                transform: `scale(${r.scale}) scaleY(${r.flip})`,
                boxSizing: "border-box",
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                justifyContent: "center",
                borderRadius: r.shape === "circle" ? "50%" : 16,
                border: r.plain ? "none" : `4px ${r.dashed ? "dashed" : "solid"} ${r.border}`,
                background: r.plain ? "transparent" : r.bg,
                color: r.fg,
                lineHeight: 1.1,
              }}
            >
              {r.text ? <div style={{ fontSize: r.fs, fontWeight: 800 }}>{r.text}</div> : null}
              {r.sub ? <div style={{ fontSize: r.sfs, fontWeight: 600, opacity: 0.92, marginTop: r.text ? 4 : 0 }}>{r.sub}</div> : null}
            </div>
          );
        })}
      </div>

      {/* code */}
      <div
        style={{
          position: "absolute",
          left: rect.codeX,
          top: rect.codeY,
          width: rect.codeW,
          height: rect.codeH,
          overflow: "hidden",
          borderRadius: 12,
          background: "#010409",
          border: "1px solid #30363d",
          opacity: codeOpacity,
        }}
      >
        <div style={{ transform: `translateY(${-scroll}px)` }}>
          {toks.map((tk, i) => {
            const ln = i + 1;
            const inten = codeSt.intensity(ln);
            const base = 0.85 + (0.42 - 0.85) * codeSt.dimFactor;
            const op = base + (1 - base) * inten;
            return (
              <div
                key={i}
                style={{
                  height: rect.codeLh,
                  lineHeight: `${rect.codeLh}px`,
                  fontFamily,
                  fontSize: rect.codeFs,
                  whiteSpace: "pre",
                  display: "flex",
                  opacity: op,
                  background: `rgba(227,170,40,${0.2 * inten})`,
                  borderLeft: `5px solid rgba(227,170,40,${inten})`,
                }}
              >
                <span style={{ width: rect.codeFs * 2.6, textAlign: "right", paddingRight: rect.codeFs * 0.9, color: "#6e7681", flexShrink: 0 }}>{ln}</span>
                <span>
                  {tk.map((t, k) => (
                    <span key={k} style={{ color: t.c }}>{t.t}</span>
                  ))}
                </span>
              </div>
            );
          })}
        </div>
      </div>

      {/* fullcode（D-020 E1）：整份程式雙欄（左前半、右後半），不捲動、不截斷；只在 fullOp>0 時繪製 */}
      {fullOp > 0 ? (
        <>
          <div
            style={{
              position: "absolute",
              left: FULLCODE.x0,
              top: FULLCODE.titleTop,
              width: 2 * FULLCODE.colW + FULLCODE.gap,
              height: FULLCODE.titleH,
              lineHeight: `${FULLCODE.titleH}px`,
              fontSize: FULLCODE.titleFs,
              fontWeight: 700,
              color: "#ffe282",
              opacity: fullOp,
            }}
          >
            {FULLCODE.title}
          </div>
          {fullcodeColumns(total).cols.map(([a, b], ci) => (
            <div
              key={ci}
              style={{
                position: "absolute",
                left: FULLCODE.x0 + ci * (FULLCODE.colW + FULLCODE.gap),
                top: FULLCODE.y0,
                width: FULLCODE.colW,
                height: fullcodeColumns(total).h,
                boxSizing: "border-box",
                overflow: "hidden",
                borderRadius: 12,
                background: "#010409",
                border: "1px solid #30363d",
                padding: `${FULLCODE.pad}px 0`,
                opacity: fullOp,
              }}
            >
              {toks.slice(a, b).map((tk, k) => {
                const ln = a + k + 1;
                const inten = codeSt.intensity(ln);
                // 預設全亮；旁白講到某段時（cue.lines）該段高亮，其餘只輕微變暗（≥0.82）
                const op = 1 - 0.18 * codeSt.dimFactor * (1 - inten);
                return (
                  <div
                    key={ln}
                    style={{
                      height: FULLCODE.lh,
                      lineHeight: `${FULLCODE.lh}px`,
                      fontFamily,
                      fontSize: FULLCODE.fs,
                      whiteSpace: "pre",
                      tabSize: 4,
                      display: "flex",
                      opacity: op,
                      background: `rgba(227,170,40,${0.2 * inten})`,
                      borderLeft: `5px solid rgba(227,170,40,${inten})`,
                    }}
                  >
                    <span style={{ width: FULLCODE.gutter, boxSizing: "border-box", textAlign: "right", paddingRight: 12, color: "#6e7681", flexShrink: 0 }}>{ln}</span>
                    <span>
                      {tk.map((t, j) => (
                        <span key={j} style={{ color: t.c }}>{t.t}</span>
                      ))}
                    </span>
                  </div>
                );
              })}
            </div>
          ))}
        </>
      ) : null}

      {/* subtitle：固定位置、單行 */}
      <div style={{ position: "absolute", left: 0, right: 0, top: subtitleTop(story.layoutRev), height: 70, display: "flex", justifyContent: "center", alignItems: "center" }}>
        {sub ? (
          <div
            style={{
              fontSize: 46,
              fontWeight: 700,
              color: "#ffffff",
              background: "rgba(0,0,0,0.55)",
              padding: "4px 28px",
              borderRadius: 12,
              whiteSpace: "nowrap",
              opacity: clamp01((T - sub.since) / 0.08),
            }}
          >
            {sub.text.replace(/[，。；：、]$/, "")}
          </div>
        ) : null}
      </div>

      {/* audio */}
      {timeline.cues.map((c) =>
        c.audio ? (
          <Sequence key={c.id} from={Math.round((c.start + c.lead) * fps)} durationInFrames={Math.ceil((c.audioDur + 0.3) * fps)}>
            <Audio src={staticFile(`${folder}/${c.audio}`)} />
          </Sequence>
        ) : null,
      )}
      <span style={{ display: "none" }}>{findCue.name}</span>
    </AbsoluteFill>
  );
};
