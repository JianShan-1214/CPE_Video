/**
 * config.json 的 TypeScript 型別定義
 *
 * 顏色預設值（color 欄位）：
 *   blue      — #58a6ff  一般說明
 *   yellow    — #e3b341  迴圈 / 流程
 *   red       — #f85149  條件判斷
 *   green     — #3fb950  修改 / 輸出
 *   lightblue — #79c0ff  函式宣告
 *
 * 也可直接指定 bgColor / borderColor 做完全自訂。
 */

export type HighlightPreset = "blue" | "yellow" | "red" | "green" | "lightblue";

export type HighlightConfigJSON =
  | { startLine: number; endLine: number; color: HighlightPreset }
  | { startLine: number; endLine: number; bgColor: string; borderColor: string };

export type AnnotationJSON = {
  /** 要標注的行（1-indexed） */
  targetLine: number;
  /** 標注文字 */
  text: string;
  /** 距步驟開始幾秒後出現（例：3.2 代表打字結束後約 0.4 秒）*/
  startTime: number;
  /** 顏色主題 */
  theme?: "blue" | "yellow" | "green" | "red";
};

export type StepJSON = {
  /** 在 Remotion Studio 時間軸上顯示的名稱 */
  label: string;
  /** 步驟開始時間（秒）*/
  from: number;
  /** 步驟結束時間（秒）*/
  to: number;
  /** public/ 資料夾內的 cpp 檔名 */
  file: string;
  /** 字幕文字 */
  subtitle: string;
  /** 強制捲動對齊的行號（若未指定，則對齊 highlight 中間）*/
  focusLine?: number;
  /** highlight 設定 */
  highlight?: HighlightConfigJSON;
  /** 浮動標注（可多個，也可省略）*/
  annotations?: AnnotationJSON[];
  /** 右側演算法動畫（可省略；省略時畫面與純程式碼影片完全相同）*/
  animation?: StepAnimation;
};

// ── 演算法動畫（keyframes 平均分配在步驟時長內）──────────────────────────────

export type ArrayAnimation = {
  type: "array";
  frames: {
    values: (number | string)[];
    /** 具名指標（例：i、j）→ 指向的 index */
    pointers?: Record<string, number>;
    /** 要標亮的 index */
    mark?: number[];
    caption?: string;
    vars?: AnimationVars;
  }[];
};

export type StacksAnimation = {
  type: "stacks";
  /** 各堆下方的標籤 */
  labels?: string[];
  /** 每個 stack 由下而上的 block id */
  frames: {
    stacks: (number | string)[][];
    caption?: string;
    vars?: AnimationVars;
  }[];
};

/** 2D 表格（≤ 12×12，列長可不齊）；null 畫成空格 */
export type GridAnimation = {
  type: "grid";
  frames: {
    cells: VarValue[][];
    /** 要標亮的 [row, col]；超出範圍的忽略 */
    mark?: [number, number][];
    caption?: string;
    vars?: AnimationVars;
  }[];
};

/** 只有變數表 */
export type VarsAnimation = {
  type: "vars";
  frames: { vars: AnimationVars; caption?: string }[];
};

export type VarValue = number | string | boolean | null;
/** 變數名 → 值（≤ 8 項）；每種動畫的每一格都可帶，畫成主圖下方的變數表 */
export type AnimationVars = Record<string, VarValue>;

export type StepAnimation =
  | ArrayAnimation
  | StacksAnimation
  | GridAnimation
  | VarsAnimation;

export type VideoConfigJSON = {
  steps: StepJSON[];
};

// ── 預設顏色對應表 ─────────────────────────────────────────────────────────────

export const HIGHLIGHT_PRESETS: Record<
  HighlightPreset,
  { bgColor: string; borderColor: string }
> = {
  blue:      { bgColor: "rgba(88,166,255,0.18)",  borderColor: "#58a6ff" },
  yellow:    { bgColor: "rgba(227,179,65,0.22)",  borderColor: "#e3b341" },
  red:       { bgColor: "rgba(248,81,73,0.22)",   borderColor: "#f85149" },
  green:     { bgColor: "rgba(63,185,80,0.23)",   borderColor: "#3fb950" },
  lightblue: { bgColor: "rgba(121,192,255,0.18)", borderColor: "#79c0ff" },
};

/** 將 JSON highlight 設定轉成渲染用的 HighlightConfig */
export function resolveHighlight(h: HighlightConfigJSON): {
  startLine: number;
  endLine: number;
  bgColor: string;
  borderColor: string;
} {
  if ("color" in h) {
    return { startLine: h.startLine, endLine: h.endLine, ...HIGHLIGHT_PRESETS[h.color] };
  }
  return h;
}
