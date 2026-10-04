import {
  ColorName,
  ElProps,
  FocusName,
  LayoutName,
  Story,
  Timeline,
} from "./types";

export const DEFAULT_EL: ElProps = {
  x: 0,
  y: 0,
  w: 170,
  h: 110,
  text: "",
  sub: "",
  color: "neutral",
  dashed: false,
  opacity: 1,
  scale: 1,
  fs: 40,
  sfs: 26,
  plain: false,
  shape: "rect",
  arrow: false,
};

export type FlatCue = {
  id: string;
  scene: number;
  sceneLabel: string;
  sceneFirst: boolean;
  text: string;
  cap: string;
  lines: number[];
  layout: LayoutName;
  focus: FocusName;
  start: number;
  dur: number;
  lead: number;
  audioDur: number;
  audio: string | null;
  ops: { dt: number; dur: number; set: Record<string, Partial<ElProps>> }[];
};

export const clamp01 = (v: number) => Math.min(1, Math.max(0, v));
export const ease = (p: number) => {
  const q = clamp01(p);
  return q * q * (3 - 2 * q);
};
const lerp = (a: number, b: number, q: number) => a + (b - a) * q;

export const flatten = (story: Story, timeline: Timeline): FlatCue[] => {
  const byId = new Map(timeline.cues.map((c) => [c.id, c]));
  const out: FlatCue[] = [];
  let cap = "";
  let lines: number[] = [];
  story.scenes.forEach((scene, si) => {
    scene.cues.forEach((cue, ci) => {
      const tl = byId.get(cue.id);
      if (!tl) throw new Error(`timeline 缺少 cue ${cue.id}，請重跑 story-build`);
      if (ci === 0) cap = "";
      if (cue.cap !== undefined) cap = cue.cap;
      if (cue.lines !== undefined) lines = cue.lines;
      out.push({
        id: cue.id,
        scene: si,
        sceneLabel: scene.label,
        sceneFirst: ci === 0,
        text: cue.text,
        cap,
        lines,
        layout: cue.layout ?? scene.layout,
        focus: cue.focus ?? scene.focus,
        start: tl.start,
        dur: tl.dur,
        lead: tl.lead,
        audioDur: tl.audioDur,
        audio: tl.audio,
        ops: (cue.ops ?? []).map((o) => ({
          dt:
            o.at !== undefined
              ? Math.max(0, tl.lead + o.at * tl.audioDur + (o.dt ?? 0))
              : (o.dt ?? 0),
          dur: o.dur ?? 0.5,
          set: o.set,
        })),
      });
    });
  });
  return out;
};

// ── 元素關鍵幀 ───────────────────────────────────────────────────────────────

type KF = { t: number; dur: number; p: ElProps };

export const buildKeyframes = (cues: FlatCue[]): Map<string, KF[]> => {
  const state = new Map<string, ElProps>();
  const kfs = new Map<string, KF[]>();
  for (const cue of cues) {
    const ops = [...cue.ops].sort((a, b) => a.dt - b.dt);
    for (const op of ops) {
      for (const [id, patch] of Object.entries(op.set)) {
        const cur: ElProps = { ...(state.get(id) ?? DEFAULT_EL), ...patch };
        state.set(id, cur);
        const list = kfs.get(id) ?? [];
        list.push({ t: cue.start + op.dt, dur: op.dur, p: cur });
        kfs.set(id, list);
      }
    }
  }
  return kfs;
};

const PALETTE: Record<ColorName, { border: number[]; bg: number[]; text: number[] }> = {
  neutral: { border: [110, 118, 129], bg: [22, 27, 34], text: [230, 237, 243] },
  yellow: { border: [227, 170, 40], bg: [72, 54, 10], text: [255, 226, 130] },
  green: { border: [63, 185, 80], bg: [16, 58, 30], text: [160, 242, 178] },
  gray: { border: [72, 79, 88], bg: [18, 22, 28], text: [118, 126, 137] },
  red: { border: [248, 81, 73], bg: [74, 22, 22], text: [255, 155, 150] },
};

const mix = (a: number[], b: number[], q: number) =>
  `rgb(${a.map((v, i) => Math.round(lerp(v, b[i], q))).join(",")})`;

export type ElRender = {
  x: number;
  y: number;
  w: number;
  h: number;
  text: string;
  sub: string;
  opacity: number;
  scale: number;
  flip: number;
  fs: number;
  sfs: number;
  plain: boolean;
  dashed: boolean;
  shape: "rect" | "circle" | "line";
  arrow: boolean;
  border: string;
  bg: string;
  fg: string;
};

export const evalElement = (kfs: KF[], T: number): ElRender | null => {
  let idx = -1;
  for (let i = 0; i < kfs.length; i++) {
    if (kfs[i].t <= T) idx = i;
    else break;
  }
  if (idx < 0) return null;
  const cur = kfs[idx];
  const prev: ElProps = idx > 0 ? kfs[idx - 1].p : { ...cur.p, opacity: 0 };
  const q = ease((T - cur.t) / Math.max(cur.dur, 0.01));
  const pc = PALETTE[prev.color];
  const cc = PALETTE[cur.p.color];
  let flip = 1;
  let text = cur.p.text;
  let sub = cur.p.sub;
  const changed = idx > 0 && (prev.text !== cur.p.text || prev.sub !== cur.p.sub);
  if (changed) {
    const r = clamp01((T - cur.t) / Math.max(Math.min(cur.dur, 0.4), 0.05));
    if (r < 0.5) {
      flip = 1 - 2 * r;
      text = prev.text;
      sub = prev.sub;
    } else {
      flip = 2 * r - 1;
    }
    flip = Math.max(flip, 0.02);
  }
  if (cur.p.opacity === 0 && prev.opacity === 0) return null;
  return {
    x: lerp(prev.x, cur.p.x, q),
    y: lerp(prev.y, cur.p.y, q),
    w: lerp(prev.w, cur.p.w, q),
    h: lerp(prev.h, cur.p.h, q),
    text,
    sub,
    opacity: lerp(prev.opacity, cur.p.opacity, q),
    scale: lerp(prev.scale, cur.p.scale, q),
    flip,
    fs: cur.p.fs,
    sfs: cur.p.sfs,
    plain: cur.p.plain,
    dashed: cur.p.dashed,
    shape: cur.p.shape,
    arrow: cur.p.arrow,
    border: mix(pc.border, cc.border, q),
    bg: mix(pc.bg, cc.bg, q),
    fg: mix(pc.text, cc.text, q),
  };
};

// ── 版面 ─────────────────────────────────────────────────────────────────────

export type Rects = {
  stageX: number;
  stageY: number;
  stageScale: number;
  codeX: number;
  codeY: number;
  codeW: number;
  codeH: number;
  codeFs: number;
  codeLh: number;
};

export const RECTS = {
  concept: {
    stageX: 90,
    stageY: 150,
    stageScale: 1.45,
    codeX: 60,
    codeY: 842,
    codeW: 1800,
    codeH: 126,
    codeFs: 27,
    codeLh: 40,
  },
  // wide：大舞台（1.2 倍，高 580 的舞台也放得下）＋底部小程式列；給「內容多的概念動畫」用（autoanim --layout wide）
  wide: {
    stageX: 240,
    stageY: 150,
    stageScale: 1.2,
    codeX: 60,
    codeY: 872,
    codeW: 1800,
    codeH: 126,
    codeFs: 27,
    codeLh: 40,
  },
  code: {
    stageX: 1215,
    stageY: 215,
    stageScale: 0.55,
    codeX: 40,
    codeY: 125,
    codeW: 1150,
    codeH: 835,
    codeFs: 22,
    codeLh: 38,
  },
  split: {
    stageX: 1070,
    stageY: 150,
    stageScale: 0.7,
    codeX: 40,
    codeY: 125,
    codeW: 1000,
    codeH: 835,
    codeFs: 22,
    codeLh: 38,
  },
  // split2（D-020 E2）：左程式面板 x24,y100,w820,h852（字級 22、行高 38 → 整行可見 22 行；窄行號欄見 SPLIT2）；
  // 右窗 x856–1896、y150–950（stageFit 區 1020×800，見 FIT_REGIONS.split2）。固定模式（無 stageFit）舞台 0.85 倍：1200×0.85＝1020 寬。
  split2: {
    stageX: 866,
    stageY: 150,
    stageScale: 0.85,
    codeX: 24,
    codeY: 100,
    codeW: 820,
    codeH: 852,
    codeFs: 22,
    codeLh: 38,
  },
  // fullcode（D-020 E1）：畫面由 Story.tsx 的專用雙欄元件（FULLCODE）繪製；這裡的數值只供 rect 補間用，
  // fullcode 時舞台與一般程式面板會被淡出（見 evalLayout 的 fullOp）。數值同 code。
  fullcode: {
    stageX: 1215,
    stageY: 215,
    stageScale: 0.55,
    codeX: 40,
    codeY: 125,
    codeW: 1150,
    codeH: 835,
    codeFs: 22,
    codeLh: 38,
  },
} as Record<LayoutName, Rects>;

// ── fullcode 雙欄幾何（D-020 E1；與 /workspace/cpe-tools/autoanim/stagefit.py 的 FULLCODE 逐值相同，tests_d020 對拍）──
// 1080p：標題「完整程式碼」y=94–134；兩欄各 colW=900（左 x=50、右 x=970）；字級 24（JetBrains Mono 每字 0.6em＝14.4px，58 字元＝835.2px）；
// 行高 33；面板 y=140 起，底不得超過 bottomMax=975（字幕框頂 983，留 8px）→ 每欄最多 floor((975−140−8)/33)=25 列 → 容量 maxLines=50 行
// （47 行 → 左 24／右 23 列，面板底 940；40 行 → 20 列，底 808）。欄內可用寬 = colW − 2（邊框）− 5（左邊線）− gutter(46) = 847 ≥ 835.2。
export const FULLCODE = {
  fs: 24,
  lh: 33,
  x0: 50,
  colW: 900,
  gap: 20,
  y0: 140,
  titleTop: 94,
  titleH: 40,
  titleFs: 32,
  gutter: 46,
  pad: 4,
  bottomMax: 975,
  maxLines: 50,
  maxCols: 58,
  title: "完整程式碼",
};

// ── split2 幾何（D-020 E2；與 /workspace/cpe-tools/autoanim/stagefit.py 的 SPLIT2 逐值相同，tests_d020 對拍）──
// 程式面板 820 寬：欄內可用 = 820 − 2（邊框）− 5（左邊線）− 行號欄(寬 fs×gutterW + 右內距 fs×gutterPad = 26.4+11=37.4) = 775.6px ≥ 58 字元×13.2 = 765.6px（字級 22、每字 0.6em）。
// 面板高 852 / 行高 38 → 整行可見 22 行（22.4）。cap 放右窗上緣（top 104、字級 30，離 stage 區頂 150 有餘）；字幕仍在全寬底，面板底 952 < 字幕框頂 983。
export const SPLIT2 = {
  panel: { x: 24, y: 100, w: 820, h: 852 },
  win: { x: 856, y: 150, w: 1040, h: 800 },
  fs: 22,
  lh: 38,
  gutterW: 1.2,
  gutterPad: 0.5,
  maxCols: 58,
  visibleLines: 22,
  cap: { left: 856, width: 1040, top: 104, fontSize: 30 },
};

/** 把 n 行程式分成左（前半）右（後半）兩欄；回傳每欄 [起, 迄)（0-based）與列數、面板高 */
export const fullcodeColumns = (n: number) => {
  const rows = Math.max(1, Math.ceil(n / 2));
  return {
    rows,
    h: rows * FULLCODE.lh + 2 * FULLCODE.pad,
    cols: [
      [0, Math.min(n, rows)],
      [Math.min(n, rows), n],
    ] as [number, number][],
  };
};

/** 字幕框的 top（D-020 E4）：layoutRev≥2 → 1003（框 y≈1001–1075，與 wide 程式列底 998 零重疊）；舊 story → 985（與以前逐值相同） */
export const subtitleTop = (layoutRev?: number) => ((layoutRev ?? 0) >= 2 ? 1003 : 985);

export const findCue = (cues: FlatCue[], T: number) => {
  let idx = 0;
  for (let i = 0; i < cues.length; i++) {
    if (cues[i].start <= T) idx = i;
    else break;
  }
  return idx;
};

// ── 舞台自適應（CPE-003；story.stageFit === "auto" 時才啟用，其餘維持上面的固定 RECTS）──────────
// 虛擬舞台座標 → 版面可用區域：依「該版面的 cue 內實際出現過的元素外框」決定 stageScale，並把外框置中放進區域。
// 與 /workspace/cpe-tools/autoanim/stagefit.py 逐式相同（tests_cpe003 會用 esbuild 打包本檔對拍）。
export type FitRegion = { rx: number; ry: number; rw: number; rh: number; min: number; max: number };
export const FIT_REGIONS: Partial<Record<LayoutName, FitRegion>> = {
  concept: { rx: 60, ry: 150, rw: 1800, rh: 680, min: 0.5, max: 1.8 },
  wide: { rx: 60, ry: 150, rw: 1800, rh: 710, min: 0.5, max: 1.8 },
  split: { rx: 1060, ry: 150, rw: 830, rh: 790, min: 0.5, max: 1.4 },
  // D-020 E2：右窗 1020×800（≥ 950×700）；倍率 0.5–1.5（內容少放大、多縮小）
  split2: { rx: 866, ry: 150, rw: 1020, rh: 800, min: 0.5, max: 1.5 },
};
export const OUT_ROW = /^o\d+$/; // 輸出列（o0、o1…）：框寬收縮到文字寬度，不再佔滿 1100
const WIDE_CH = /[\u2e80-\u9fff\uff00-\uffef]/;
export const OUT_PAD = 40;
export const textWidth = (t: string, fs: number) => {
  let n = 0;
  for (const ch of t) n += WIDE_CH.test(ch) ? 1 : 0.62;
  return n * fs;
};
export const autoWidth = (id: string, w: number, text: string, fs: number) =>
  OUT_ROW.test(id) ? Math.min(w, textWidth(text, fs) + OUT_PAD) : w;

export type BBox = { x0: number; y0: number; x1: number; y1: number };
const extent = (id: string, p: ElProps): BBox => {
  if (p.shape === "line") {
    return { x0: Math.min(p.x, p.x + p.w), y0: Math.min(p.y, p.y + p.h), x1: Math.max(p.x, p.x + p.w), y1: Math.max(p.y, p.y + p.h) };
  }
  return { x0: p.x, y0: p.y, x1: p.x + autoWidth(id, p.w, p.text, p.fs), y1: p.y + p.h };
};

export const fitBoxes = (cues: FlatCue[]): Map<LayoutName, BBox> => {
  const state = new Map<string, ElProps>();
  const boxes = new Map<LayoutName, BBox>();
  const add = (L: LayoutName, b: BBox) => {
    const o = boxes.get(L);
    if (!o) boxes.set(L, { ...b });
    else {
      o.x0 = Math.min(o.x0, b.x0);
      o.y0 = Math.min(o.y0, b.y0);
      o.x1 = Math.max(o.x1, b.x1);
      o.y1 = Math.max(o.y1, b.y1);
    }
  };
  for (const cue of cues) {
    for (const [id, p] of state) if (p.opacity > 0) add(cue.layout, extent(id, p));
    const ops = [...cue.ops].sort((a, b) => a.dt - b.dt);
    for (const op of ops) {
      for (const [id, patch] of Object.entries(op.set)) {
        const cur: ElProps = { ...(state.get(id) ?? DEFAULT_EL), ...patch };
        state.set(id, cur);
        if (cur.opacity > 0) add(cue.layout, extent(id, cur));
      }
    }
  }
  return boxes;
};

export const fitRect = (L: LayoutName, b: BBox): Rects | null => {
  const g = FIT_REGIONS[L];
  if (!g) return null;
  const bw = Math.max(b.x1 - b.x0, 1);
  const bh = Math.max(b.y1 - b.y0, 1);
  const s = Math.min(g.max, Math.max(g.min, Math.min(g.rw / bw, g.rh / bh)));
  return { ...RECTS[L], stageScale: s, stageX: g.rx + (g.rw - bw * s) / 2 - b.x0 * s, stageY: g.ry - b.y0 * s };
};

export const fitRects = (cues: FlatCue[]): Partial<Record<LayoutName, Rects>> => {
  const out: Partial<Record<LayoutName, Rects>> = {};
  fitBoxes(cues).forEach((b, L) => {
    const r = fitRect(L, b);
    if (r) out[L] = r;
  });
  return out;
};

export const evalLayout = (cues: FlatCue[], T: number, fit?: Partial<Record<LayoutName, Rects>>) => {
  const i = findCue(cues, T);
  const cur = cues[i];
  const prev = cues[Math.max(0, i - 1)];
  const q = ease((T - cur.start) / 0.5);
  const a = fit?.[prev.layout] ?? RECTS[prev.layout];
  const b = fit?.[cur.layout] ?? RECTS[cur.layout];
  const rect = {} as Rects;
  (Object.keys(a) as (keyof Rects)[]).forEach((k) => {
    rect[k] = lerp(a[k], b[k], q);
  });
  const dim = (focus: FocusName, which: FocusName) => (focus === which || focus === "both" ? 1 : 0.3);
  const animOp = lerp(dim(prev.focus, "anim"), dim(cur.focus, "anim"), q);
  const codeOp = lerp(dim(prev.focus, "code"), dim(cur.focus, "code"), q);
  // D-020 E1：fullcode 的專用雙欄面板不透明度（進出 fullcode 以 0.5s 交叉淡入淡出，舞台與一般程式面板同時淡出）；沒有 fullcode 的 story 恆為 0
  const fullOp = lerp(prev.layout === "fullcode" ? 1 : 0, cur.layout === "fullcode" ? 1 : 0, q);
  // D-020 E2：split2 的窄行號欄（進出 split2 以 0.5s 補間）；沒有 split2 的 story 恆為 0
  const narrowOp = lerp(prev.layout === "split2" ? 1 : 0, cur.layout === "split2" ? 1 : 0, q);
  return { rect, animOp, codeOp, fullOp, narrowOp, index: i };
};

// ── 程式碼高亮與揭露 ─────────────────────────────────────────────────────────

export type CodeState = {
  reveal: (line: number) => number;
  intensity: (line: number) => number;
  dimFactor: number;
  center: number;
};

export const buildCodeTimeline = (cues: FlatCue[], totalLines: number) => {
  const entries = cues.map((c) => ({ t: c.start, lines: c.lines }));
  let maxLine = 0;
  const revealAt = new Map<number, number>();
  for (const c of cues) {
    let top = c.lines.length ? Math.max(...c.lines) : 0;
    if (top >= totalLines - 2) top = totalLines;
    if (top > maxLine) {
      for (let l = maxLine + 1; l <= top; l++) revealAt.set(l, c.start);
      maxLine = top;
    }
  }
  const centers: number[] = [];
  let last = 1;
  for (const e of entries) {
    if (e.lines.length) last = (Math.min(...e.lines) + Math.max(...e.lines)) / 2;
    centers.push(last);
  }
  return { entries, revealAt, centers };
};

export const evalCode = (
  tl: ReturnType<typeof buildCodeTimeline>,
  T: number,
  idx: number,
): CodeState => {
  const cur = tl.entries[idx];
  const prev = tl.entries[Math.max(0, idx - 1)];
  const q = ease((T - cur.t) / 0.3);
  const prevSet = new Set(prev.lines);
  const curSet = new Set(cur.lines);
  const centerPrev = tl.centers[Math.max(0, idx - 1)];
  const center = lerp(centerPrev, tl.centers[idx], ease((T - cur.t) / 0.5));
  return {
    reveal: (line) => {
      const rt = tl.revealAt.get(line);
      if (rt === undefined) return 0;
      return clamp01((T - rt) / 0.25);
    },
    intensity: (line) => {
      const a = prevSet.has(line) ? 1 : 0;
      const b = curSet.has(line) ? 1 : 0;
      return lerp(a, b, q);
    },
    dimFactor: lerp(prev.lines.length ? 1 : 0, cur.lines.length ? 1 : 0, q),
    center,
  };
};

// ── 逐句字幕 ─────────────────────────────────────────────────────────────────

export const MAX_SUB_CHARS = 18;

/** 依標點切成單行字幕片段，相鄰片段在 18 字內會合併 */
export const chunkText = (text: string): string[] => {
  const parts = text.match(/[^，。！？；：、]+[，。！？；：、]?/g) ?? [text];
  const out: string[] = [];
  for (const p of parts) {
    const last = out[out.length - 1];
    if (last && (last + p).length <= MAX_SUB_CHARS && !/[。！？]$/.test(last)) {
      out[out.length - 1] = last + p;
    } else out.push(p);
  }
  return out;
};

export const currentSubtitle = (cues: FlatCue[], T: number) => {
  const i = findCue(cues, T);
  const c = cues[i];
  const t0 = c.start + c.lead;
  const t1 = t0 + c.audioDur;
  if (T < t0 || T > t1 + 0.15) return null;
  const chunks = chunkText(c.text);
  const weights = chunks.map((s) => s.replace(/[，。！？；：、]/g, "").length || 1);
  const sum = weights.reduce((a, b) => a + b, 0);
  let acc = t0;
  for (let k = 0; k < chunks.length; k++) {
    const span = (c.audioDur * weights[k]) / sum;
    const end = k === chunks.length - 1 ? Infinity : acc + span;
    if (T < end) return { text: chunks[k], since: acc };
    acc += span;
  }
  return null;
};
