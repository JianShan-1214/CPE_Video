type HighlightConfigLike = {
  startLine: number;
  endLine: number;
  bgColor: string;
  borderColor: string;
};

// Keep these layout constants aligned with font.ts, IDEFrame.tsx, and step-animations.ts.
const FONT_SIZE = 24;
const LINE_HEIGHT = FONT_SIZE * 1.5;
const VERTICAL_PADDING = 60;
const CODE_AREA_HEIGHT = 800;

type ComputeStepScrollParams = {
  focusLine: number | null;
  highlight: HighlightConfigLike | null;
  totalLines: number;
  prevScroll: number;
};

export function computeStepScroll({
  focusLine,
  highlight,
  totalLines,
  prevScroll,
}: ComputeStepScrollParams): number {
  if (focusLine === null && highlight === null) {
    return prevScroll;
  }

  const estimatedHeight = totalLines * LINE_HEIGHT + VERTICAL_PADDING + 20;
  const maxScroll = Math.max(0, estimatedHeight - CODE_AREA_HEIGHT);

  // focusLine：指定行對齊畫面頂部
  if (focusLine !== null) {
    const topY = (focusLine - 1) * LINE_HEIGHT + VERTICAL_PADDING;
    return Math.min(Math.max(0, topY), maxScroll);
  }

  // highlight：置中 highlight 範圍，只增不減
  const centerLine = (highlight!.startLine + highlight!.endLine) / 2;
  const centerY = (centerLine - 1) * LINE_HEIGHT + VERTICAL_PADDING + LINE_HEIGHT / 2;
  const idealScroll = Math.max(0, centerY - CODE_AREA_HEIGHT / 2);
  const clampedScroll = Math.min(idealScroll, maxScroll);
  return Math.max(prevScroll, clampedScroll);
}

export function getLineNumberAppearance(
  lineNumber: number,
  config: HighlightConfigLike | undefined,
  progress: number,
): {
  color: string;
  fontWeight: "400" | "700";
  opacity: number;
} {
  if (!config) {
    return {
      color: "#4a5568",
      fontWeight: "400",
      opacity: 0.5,
    };
  }

  const isHighlighted =
    lineNumber >= config.startLine && lineNumber <= config.endLine;

  return {
    color: isHighlighted ? config.borderColor : "#4a5568",
    fontWeight: isHighlighted ? "700" : "400",
    opacity: isHighlighted ? 0.4 + progress * 0.6 : 0.5,
  };
}
