import type { ReactNode } from "react";
import type { AnnotationJSON, HighlightPreset } from "@remotion-src/config-types";
import { HIGHLIGHT_PRESETS } from "@remotion-src/config-types";
import { Plus, Trash2 } from "lucide-react";
import type { DraftStep } from "@/lib/draft-types";

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
    <div className="space-y-3 text-sm">
      <Field label="標籤 (label)">
        <input
          type="text"
          value={step.label}
          onChange={(e) => patch({ label: e.target.value })}
          className={inputCls}
        />
      </Field>

      <div className="grid grid-cols-2 gap-3">
        <Field label="from (秒)">
          <input
            type="number"
            step="0.1"
            value={step.from}
            onChange={(e) => patch({ from: Number(e.target.value) })}
            className={inputCls}
          />
        </Field>
        <Field label="to (秒)">
          <input
            type="number"
            step="0.1"
            value={step.to}
            onChange={(e) => patch({ to: Number(e.target.value) })}
            className={inputCls}
          />
        </Field>
      </div>

      <Field label="cpp 檔名 (fileLabel)">
        <input
          type="text"
          value={step.fileLabel}
          onChange={(e) => patch({ fileLabel: e.target.value })}
          placeholder="code01.cpp"
          className={inputCls}
        />
      </Field>

      <Field label="字幕 (subtitle)">
        <textarea
          value={step.subtitle}
          onChange={(e) => patch({ subtitle: e.target.value })}
          rows={2}
          className={inputCls}
        />
      </Field>

      <Field label="cpp 內容 (fileContent)">
        <textarea
          value={step.fileContent}
          onChange={(e) => patch({ fileContent: e.target.value })}
          rows={10}
          className={`${inputCls} font-mono text-xs`}
          spellCheck={false}
        />
      </Field>

      <Field label="focusLine (可留空)">
        <input
          type="number"
          min={1}
          value={step.focusLine ?? ""}
          onChange={(e) => {
            const v = e.target.value;
            patch({ focusLine: v === "" ? undefined : Number(v) });
          }}
          placeholder="(未設定)"
          className={inputCls}
        />
      </Field>

      <Field label="Highlight">
        <div className="space-y-2">
          <select
            value={currentColor}
            onChange={(e) => setHighlightColor(e.target.value)}
            className={inputCls}
          >
            {HIGHLIGHT_COLOR_OPTIONS.map((c) => (
              <option key={c} value={c}>
                {c === "none" ? "（無）" : c}
              </option>
            ))}
          </select>
          {step.highlight && (
            <div className="grid grid-cols-2 gap-2">
              <input
                type="number"
                min={1}
                value={step.highlight.startLine}
                onChange={(e) =>
                  setHighlightRange("startLine", Number(e.target.value))
                }
                placeholder="startLine"
                className={inputCls}
              />
              <input
                type="number"
                min={1}
                value={step.highlight.endLine}
                onChange={(e) =>
                  setHighlightRange("endLine", Number(e.target.value))
                }
                placeholder="endLine"
                className={inputCls}
              />
            </div>
          )}
        </div>
      </Field>

      <Field label="Annotations">
        <div className="space-y-2">
          {annotations.length === 0 ? (
            <div className="text-xs text-neutral-500 border border-dashed border-neutral-800 rounded px-3 py-3">
              尚無標注。
            </div>
          ) : (
            annotations.map((ann, i) => (
              <div
                key={i}
                className="grid grid-cols-[72px_88px_1fr_84px_32px] gap-2 items-start"
              >
                <input
                  type="number"
                  min={1}
                  value={ann.targetLine}
                  onChange={(e) =>
                    updateAnnotation(i, {
                      targetLine: Number(e.target.value),
                    })
                  }
                  className={inputCls}
                  aria-label={`標注 ${i + 1} 行號`}
                />
                <input
                  type="number"
                  min={0}
                  step={0.1}
                  value={ann.startTime}
                  onChange={(e) =>
                    updateAnnotation(i, {
                      startTime: Number(e.target.value),
                    })
                  }
                  className={inputCls}
                  aria-label={`標注 ${i + 1} 開始秒數`}
                />
                <input
                  type="text"
                  value={ann.text}
                  onChange={(e) => updateAnnotation(i, { text: e.target.value })}
                  className={inputCls}
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
                  className={inputCls}
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
                  className="text-neutral-500 hover:text-red-400 p-2"
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
            className="text-blue-400 hover:text-blue-300 text-sm flex items-center gap-1"
          >
            <Plus size={14} /> 新增標注
          </button>
        </div>
      </Field>
    </div>
  );
}

const inputCls =
  "w-full bg-neutral-900 border border-neutral-800 rounded px-2 py-1.5 text-sm focus:outline-none focus:border-blue-500";

function Field({
  label,
  children,
}: {
  label: string;
  children: ReactNode;
}) {
  return (
    <label className="block">
      <span className="text-xs text-neutral-400 mb-1 block">{label}</span>
      {children}
    </label>
  );
}
