import { SlidersHorizontal } from "lucide-react";
import { themeSchema } from "@remotion-src/calculate-metadata/theme";
import type { Theme } from "@remotion-src/calculate-metadata/theme";
import type { Job, WidthConfig } from "@/lib/draft-types";

const THEMES = themeSchema.options;

/** Common widths; the composition height is always 1080. */
const WIDTH_PRESETS = [1280, 1600, 1920, 2560];

type Props = {
  theme: Theme;
  width: WidthConfig;
  onChange: (patch: Partial<Pick<Job, "theme" | "width">>) => void;
};

export function VideoSettings({ theme, width, onChange }: Props) {
  return (
    <details className="rounded-xl border border-line bg-ink-900/60 p-4" open>
      <summary className="flex items-center gap-2 cursor-pointer select-none">
        <SlidersHorizontal size={13} className="text-faint" strokeWidth={1.8} />
        <span className="eyebrow">影片設定</span>
        <span className="meta-mono text-xs ml-auto">
          {theme} · {width.type === "auto" ? "auto" : `${width.value}px`}
        </span>
      </summary>

      <div className="space-y-3 pt-3">
        <label className="block">
          <span className="field-label">程式碼主題 (theme)</span>
          <select
            value={theme}
            onChange={(e) => onChange({ theme: e.target.value as Theme })}
            className="input"
          >
            {THEMES.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
        </label>

        <label className="block">
          <span className="field-label">影片寬度（高度固定 1080）</span>
          <select
            value={width.type === "auto" ? "auto" : String(width.value)}
            onChange={(e) =>
              onChange({
                width:
                  e.target.value === "auto"
                    ? { type: "auto" }
                    : { type: "fixed", value: Number(e.target.value) },
              })
            }
            className="input font-mono"
          >
            <option value="auto">auto（依最長程式碼行）</option>
            {WIDTH_PRESETS.map((w) => (
              <option key={w} value={w}>
                {w} × 1080
              </option>
            ))}
          </select>
        </label>

        {width.type === "fixed" && !WIDTH_PRESETS.includes(width.value) && (
          <p className="text-xs text-faint">
            目前為自訂寬度 {width.value}px，改選預設值會覆蓋它。
          </p>
        )}
      </div>
    </details>
  );
}
