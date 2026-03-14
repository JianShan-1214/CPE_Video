import { TokenTransition } from "codehike/utils/token-transitions";
import { interpolate, interpolateColors } from "remotion";

export function applyStyle({
  element,
  keyframes,
  progress,
  linearProgress,
}: {
  element: HTMLElement;
  keyframes: TokenTransition["keyframes"];
  progress: number;
  linearProgress: number;
}) {
  const { translateX, translateY, color, opacity } = keyframes;

  if (opacity) {
    element.style.opacity = linearProgress.toString();
  }
  if (color && Array.isArray(color) && color.length >= 2) {
    try {
      element.style.color = interpolateColors(progress, [0, 1], color);
    } catch {
      // Remotion's interpolateColors only accepts hex, rgb(a), hsl(a), or CSS names.
      // Codehike keyframes may contain CSS variables (e.g. var(--shiki-1)) which are invalid here.
      // Leave element color unchanged (from theme/CSS) when interpolation fails.
    }
  }
  const x = translateX ? interpolate(progress, [0, 1], translateX) : 0;
  const y = translateY ? interpolate(progress, [0, 1], translateY) : 0;
  element.style.translate = `${x}px ${y}px`;
}
