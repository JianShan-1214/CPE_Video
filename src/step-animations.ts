/**
 * 動畫元件所需的型別定義與工具函式。
 * 步驟設定已移至 public/config.json。
 */

export interface HighlightConfig {
  startLine: number;
  endLine: number;
  bgColor: string;
  borderColor: string;
}

export interface AnnotationCallout {
  /** 要標注的行（1-indexed） */
  targetLine: number;
  /** 標注文字 */
  text: string;
  /** 相對步驟起點的出現 frame */
  startFrame: number;
  /** 顏色主題 */
  theme?: "blue" | "yellow" | "green" | "red";
  /** 該行程式碼文字起始 X 座標（px，含縮排），由 calculateMetadata 計算後填入 */
  lineStartX: number;
  /** 該行程式碼右端的 X 座標（px），由 calculateMetadata 計算後填入 */
  lineEndX: number;
}

const LINE_HEIGHT_PX = 36; // fontSize(24) * lineHeight(1.5)

/** 計算目標行在程式碼區域中的 Y 座標（含 padding） */
export function targetLineY(targetLine: number, paddingTop: number): number {
  return (targetLine - 1) * LINE_HEIGHT_PX + paddingTop + LINE_HEIGHT_PX / 2;
}
