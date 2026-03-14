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
  /** highlight 設定 */
  highlight: HighlightConfigJSON;
  /** 浮動標注（可多個，也可省略）*/
  annotations?: AnnotationJSON[];
};

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
