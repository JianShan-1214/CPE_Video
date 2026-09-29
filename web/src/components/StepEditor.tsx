import { type ReactNode, useState } from "react";
import type { AnnotationJSON, HighlightPreset } from "@remotion-src/config-types";
import { HIGHLIGHT_PRESETS } from "@remotion-src/config-types";
import { Clapperboard, Highlighter, MessageSquareText, Plus, Trash2 } from "lucide-react";
import type { DraftStep } from "@/lib/draft-types";
import { parseAnimationJson, toLine, toOptionalLine, toSeconds } from "@/lib/step-fields";

const HIGHLIGHT_COLOR_OPTIONS: (HighlightPreset | "none")[] = [
  "none",
  "blue",
  "yellow",
  "red",
  "green",
  "lightblue",
];

const ANNOTATION_THEME_OPTIONS: (NonNullable<AnnotationJSON["theme"]> | "none")[] =
  ["none", "blue", "yellow", "green", "red"];

type Props = {
  step: DraftStep;
  onChange: (next: DraftStep) => void;
};

export function StepEditor({ step, onChange }: Props) {
  const patch = (p: Partial<DraftStep>) => onChange({ ...step, ...p });

  const currentColor =
    step.highlight && "color" in step.highlight ? step.highlight.color : "none";

  const setHighlightColor = (value: string) => {
    if (value === "none") {
      patch({ highlight: undefined });
      return;
    }
    const color = value as HighlightPreset;
    if (!(color in HIGHLIGHT_PRESETS)) return;
    const existing = step.highlight;
    patch({
      highlight: {
        startLine: existing && "startLine" in existing ? existing.startLine : 1,
        endLine: existing && "endLine" in existing ? existing.endLine : 1,
        color,
      },
    });
  };

  const setHighlightRange = (field: "startLine" | "endLine", n: number) => {
    if (!step.highlight) return;
    patch({
      highlight: {
        ...step.highlight,
        [field]: n,
      } as DraftStep["highlight"],
    });
  };

  const annotations = step.annotations ?? [];

  const setAnnotations = (next: AnnotationJSON[]) => {
    patch({ annotations: next.length > 0 ? next : undefined });
  };

  const addAnnotation = () => {
    setAnnotations([
      ...annotations,
      {
        targetLine: step.highlight?.startLine ?? step.focusLine ?? 1,
        text: "",
        startTime: 0,
        theme: "blue",
      },
    ]);
  };

  const updateAnnotation = (
    index: number,
    next: Partial<AnnotationJSON>,
  ) => {
    setAnnotations(
      annotations.map((ann, i) => (i === index ? { ...ann, ...next } : ann)),
    );
  };

  const removeAnnotation = (index: number) => {
    setAnnotations(annotations.filter((_, i) => i !== index));
  };

  return (
    <div className="space-y-4 text-sm">
      <Field label="標籤 (label)">
        <input
          type="text"
          value={step.label}
          onChange={(e) => patch({ label: e.target.value })}
          className="input"
        />
      </Field>

      <div className="grid grid-cols-2 gap-3">
        <Field label="from (秒)">
          <input
            type="number"
            step="0.1"
            value={step.from}
            onChange={(e) => {
              const from = toSeconds(e.target.value);
              if (from !== null) patch({ from });
            }}
            className="input font-mono"
          />
        </Field>
        <Field label="to (秒)">
          <input
            type="number"
            step="0.1"
            value={step.to}
            onChange={(e) => {
              const to = toSeconds(e.target.value);
              if (to !== null) patch({ to });
            }}
            className="input font-mono"
          />
        </Field>
      </div>

      <Field label="cpp 檔名 (fileLabel)">
        <input
          type="text"
          value={step.fileLabel}
          onChange={(e) => patch({ fileLabel: e.target.value })}
          placeholder="code01.cpp"
          className="input font-mono"
        />
      </Field>

      <Field label="字幕 (subtitle)">
        <textarea
          value={step.subtitle}
          onChange={(e) => patch({ subtitle: e.target.value })}
          rows={2}
          className="input resize-y"
        />
      </Field>

      <Field label="cpp 內容 (fileContent)">
        <textarea
          value={step.fileContent}
          onChange={(e) => patch({ fileContent: e.target.value })}
          rows={10}
          className="input resize-y font-mono text-xs leading-relaxed"
          spellCheck={false}
        />
      </Field>

      <Field label="focusLine (可留空)">
        <input
          type="number"
          min={1}
          value={step.focusLine ?? ""}
          onChange={(e) => patch({ focusLine: toOptionalLine(e.target.value) })}
          placeholder="(未設定)"
          className="input font-mono"
        />
      </Field>

      <section className="rounded-xl border border-line bg-ink-900/60 p-4 space-y-3">
        <div className="flex items-center gap-2">
          <Highlighter size={13} className="text-faint" strokeWidth={1.8} />
          <span className="eyebrow">Highlight</span>
        </div>
        <div className="space-y-2">
          <select
            value={currentColor}
            onChange={(e) => setHighlightColor(e.target.value)}
            className="input"
          >
            {HIGHLIGHT_COLOR_OPTIONS.map((c) => (
              <option key={c} value={c}>
                {c === "none" ? "（無）" : c}
              </option>
            ))}
          </select>
          {step.highlight && (
            <div className="grid grid-cols-2 gap-2">
              <div>
                <span className="field-label">起始行</span>
                <input
                  type="number"
                  min={1}
                  value={step.highlight.startLine}
                  onChange={(e) =>
                    setHighlightRange("startLine", toLine(e.target.value))
                  }
                  placeholder="startLine"
                  className="input font-mono"
                />
              </div>
              <div>
                <span className="field-label">結束行</span>
                <input
                  type="number"
                  min={1}
                  value={step.highlight.endLine}
                  onChange={(e) =>
                    setHighlightRange("endLine", toLine(e.target.value))
                  }
                  placeholder="endLine"
                  className="input font-mono"
                />
              </div>
            </div>
          )}
        </div>
      </section>

      <section className="rounded-xl border border-line bg-ink-900/60 p-4 space-y-3">
        <div className="flex items-center gap-2">
          <MessageSquareText size={13} className="text-faint" strokeWidth={1.8} />
          <span className="eyebrow">Annotations</span>
          <span className="meta-mono text-xs ml-auto">{annotations.length}</span>
        </div>
        <div className="space-y-2">
          {annotations.length === 0 ? (
            <div className="text-xs text-faint border border-dashed border-line rounded-lg px-3 py-4 text-center">
              尚無標注。
            </div>
          ) : (
            annotations.map((ann, i) => (
              <div
                key={i}
                className="grid grid-cols-[72px_88px_1fr_84px_32px] gap-2 items-center"
              >
                <input
                  type="number"
                  min={1}
                  value={ann.targetLine}
                  onChange={(e) =>
                    updateAnnotation(i, {
                      targetLine: toLine(e.target.value),
                    })
                  }
                  className="input font-mono"
                  aria-label={`標注 ${i + 1} 行號`}
                />
                <input
                  type="number"
                  min={0}
                  step={0.1}
                  value={ann.startTime}
                  onChange={(e) => {
                    const startTime = toSeconds(e.target.value, 0);
                    if (startTime !== null) updateAnnotation(i, { startTime });
                  }}
                  className="input font-mono"
                  aria-label={`標注 ${i + 1} 開始秒數`}
                />
                <input
                  type="text"
                  value={ann.text}
                  onChange={(e) => updateAnnotation(i, { text: e.target.value })}
                  className="input"
                  aria-label={`標注 ${i + 1} 文字`}
                  placeholder="標注文字"
                />
                <select
                  value={ann.theme ?? "none"}
                  onChange={(e) =>
                    updateAnnotation(i, {
                      theme:
                        e.target.value === "none"
                          ? undefined
                          : (e.target.value as AnnotationJSON["theme"]),
                    })
                  }
                  className="input"
                  aria-label={`標注 ${i + 1} 顏色`}
                >
                  {ANNOTATION_THEME_OPTIONS.map((theme) => (
                    <option key={theme} value={theme}>
                      {theme === "none" ? "預設" : theme}
                    </option>
                  ))}
                </select>
                <button
                  type="button"
                  onClick={() => removeAnnotation(i)}
                  className="grid size-8 place-items-center rounded-lg text-faint hover:text-danger hover:bg-ink-850 transition-colors"
                  aria-label={`刪除標注 ${i + 1}`}
                >
                  <Trash2 size={14} />
                </button>
              </div>
            ))
          )}
          <button
            type="button"
            onClick={addAnnotation}
            className="btn btn-ghost w-full"
          >
            <Plus size={14} /> 新增標注
          </button>
        </div>
      </section>

      <AnimationField
        animation={step.animation}
        onChange={(animation) => patch({ animation })}
      />
    </div>
  );
}

// The textarea keeps its own text so half-typed JSON isn't lost; only a valid
// animation (or empty → none) reaches the draft. The parent remounts this
// editor per step, so the initial text always matches the selected step.
function AnimationField({
  animation,
  onChange,
}: {
  animation: DraftStep["animation"];
  onChange: (next: DraftStep["animation"]) => void;
}) {
  const [text, setText] = useState(() =>
    animation ? JSON.stringify(animation, null, 2) : "",
  );
  const [error, setError] = useState<string | null>(null);

  const handleChange = (value: string) => {
    setText(value);
    const parsed = parseAnimationJson(value);
    if (!parsed.ok) {
      setError(parsed.error);
      return;
    }
    setError(null);
    onChange(parsed.value);
  };

  return (
    <section className="rounded-xl border border-line bg-ink-900/60 p-4 space-y-3">
      <div className="flex items-center gap-2">
        <Clapperboard size={13} className="text-faint" strokeWidth={1.8} />
        <span className="eyebrow">動畫（選填，JSON）</span>
      </div>
      <textarea
        value={text}
        onChange={(e) => handleChange(e.target.value)}
        rows={6}
        className="input resize-y font-mono text-xs leading-relaxed"
        spellCheck={false}
        placeholder='{"type": "array", "frames": [{"values": [3, 1, 2], "pointers": {"i": 0}}]}'
        aria-label="動畫 JSON"
      />
      {error && <div className="error-banner">{error}（尚未套用）</div>}
    </section>
  );
}

function Field({
  label,
  children,
}: {
  label: string;
  children: ReactNode;
}) {
  return (
    <label className="block">
      <span className="field-label">{label}</span>
      {children}
    </label>
  );
}
