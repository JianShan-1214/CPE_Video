import { loadFont } from "@remotion/google-fonts/JetBrainsMono";

export const { fontFamily, waitUntilDone } = loadFont("normal", {
  subsets: ["latin"],
  weights: ["400", "700"],
});
export const fontSize = 24;
export const tabSize = 3;
export const horizontalPadding = 40;
export const verticalPadding = 60;
export const lineNumberGutterWidth = 52; // 行號欄寬度（含右側間距）
export const ANIMATION_PANEL_WIDTH = 640; // 右側演算法動畫面板寬度（僅在有動畫時加寬影片）
