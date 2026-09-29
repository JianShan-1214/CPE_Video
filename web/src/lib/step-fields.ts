import type { StepAnimation } from "@remotion-src/config-types";
import type { StepTrace } from "./draft-types";

// Number inputs hand back "" for empty or half-typed values ("-", "1e");
// these keep such input from ever reaching the draft (the backend 422s on it).

/** 1-based line number; anything unusable becomes 1. */
export function toLine(raw: string): number {
  const n = Math.trunc(Number(raw));
  return Number.isFinite(n) && n >= 1 ? n : 1;
}

/** Optional line number: empty → undefined, otherwise like `toLine`. */
export function toOptionalLine(raw: string): number | undefined {
  return raw.trim() === "" ? undefined : toLine(raw);
}

/** Seconds; `null` = not a number yet, leave the stored value alone. */
export function toSeconds(raw: string, min = -Infinity): number | null {
  const n = Number(raw);
  return raw.trim() === "" || !Number.isFinite(n) ? null : Math.max(min, n);
}

export type AnimationParse =
  | { ok: true; value: StepAnimation | undefined }
  | { ok: false; error: string };

/** Editor textarea → animation. Empty = no animation. Shape only; size limits are reported by 「檢查」. */
export function parseAnimationJson(text: string): AnimationParse {
  if (text.trim() === "") return { ok: true, value: undefined };
  let data: unknown;
  try {
    data = JSON.parse(text);
  } catch (e) {
    return { ok: false, error: `JSON 格式錯誤：${(e as Error).message}` };
  }
  const error = animationShapeError(data);
  return error ? { ok: false, error } : { ok: true, value: data as StepAnimation };
}

type Obj = Record<string, unknown>;

const isObject = (v: unknown): v is Obj =>
  typeof v === "object" && v !== null && !Array.isArray(v);

const isValue = (x: unknown) => typeof x === "string" || (typeof x === "number" && Number.isFinite(x));
const isScalar = (x: unknown) => x === null || typeof x === "boolean" || isValue(x);

const isValueList = (v: unknown) => Array.isArray(v) && v.every(isValue);

const isIntList = (v: unknown) => Array.isArray(v) && v.every(Number.isInteger);

const isCellList = (v: unknown) =>
  Array.isArray(v) && v.every((m) => Array.isArray(m) && m.length === 2 && m.every(Number.isInteger));

const isVars = (v: unknown) => isObject(v) && Object.values(v).every(isScalar);

const ANIMATION_TYPES = ["array", "stacks", "grid", "vars"];

// The renderer tolerates null in optional fields, but the editor keeps them
// out (absent, not null) so stored drafts stay clean. Stricter-or-equal to
// `isValidAnimation` on shape; size limits are left to 「檢查」.
function animationShapeError(a: unknown): string | null {
  if (!isObject(a)) return "動畫必須是 JSON 物件";
  if (!ANIMATION_TYPES.includes(a.type as string)) return 'type 必須是 "array"、"stacks"、"grid" 或 "vars"';
  if (!Array.isArray(a.frames) || a.frames.length === 0) return "frames 必須是至少一格的陣列";
  if (
    a.type === "stacks" &&
    a.labels !== undefined &&
    !(Array.isArray(a.labels) && a.labels.every((l) => typeof l === "string"))
  ) {
    return "labels 必須是字串陣列";
  }
  for (const [i, f] of a.frames.entries()) {
    const at = `frames[${i}]`;
    if (!isObject(f)) return `${at} 必須是物件`;
    if (f.caption !== undefined && typeof f.caption !== "string") return `${at}.caption 必須是字串`;
    if ((f.vars !== undefined || a.type === "vars") && !isVars(f.vars)) {
      return `${at}.vars 必須是 { "變數名": 數字／字串／布林／null }`;
    }
    if (a.type === "array") {
      if (!isValueList(f.values)) return `${at}.values 必須是數字或字串的陣列`;
      if (f.mark !== undefined && !isIntList(f.mark)) return `${at}.mark 必須是整數陣列`;
      if (
        f.pointers !== undefined &&
        !(isObject(f.pointers) && Object.values(f.pointers).every(Number.isInteger))
      ) {
        return `${at}.pointers 必須是 { "變數名": 整數 index }`;
      }
    } else if (a.type === "stacks") {
      if (!(Array.isArray(f.stacks) && f.stacks.every(isValueList))) {
        return `${at}.stacks 必須是陣列的陣列（元素為數字或字串）`;
      }
    } else if (a.type === "grid") {
      if (
        !(Array.isArray(f.cells) && f.cells.length > 0 && f.cells.every((r) => Array.isArray(r) && r.every(isScalar)))
      ) {
        return `${at}.cells 必須是至少一列的二維陣列（元素為數字／字串／布林／null）`;
      }
      if (f.mark !== undefined && !isCellList(f.mark)) return `${at}.mark 必須是 [列, 欄] 整數對的陣列`;
    }
  }
  return null;
}

export type TraceParse =
  | { ok: true; value: StepTrace | null }
  | { ok: false; error: string };

const TRACE_SHOW_AS = ["array", "grid", "stacks", "queue", "vars"];
const isStringList = (v: unknown) => Array.isArray(v) && v.every((x) => typeof x === "string");
const isOptionalString = (v: unknown) => v == null || typeof v === "string";

/** Editor textarea → trace plan (mirrors backend `StepTrace`). Empty = no plan (null). */
export function parseTraceJson(text: string): TraceParse {
  if (text.trim() === "") return { ok: true, value: null };
  let t: unknown;
  try {
    t = JSON.parse(text);
  } catch (e) {
    return { ok: false, error: `JSON 格式錯誤：${(e as Error).message}` };
  }
  const error = traceShapeError(t);
  return error ? { ok: false, error } : { ok: true, value: t as StepTrace };
}

function traceShapeError(t: unknown): string | null {
  if (!isObject(t)) return "追蹤計畫必須是 JSON 物件";
  if (!(Number.isInteger(t.line) && (t.line as number) >= 1)) return "line 必須是 ≥ 1 的整數";
  if (!isObject(t.show) || !TRACE_SHOW_AS.includes(t.show.as as string)) {
    return 'show.as 必須是 "array"、"grid"、"stacks"、"queue" 或 "vars"';
  }
  if (!isOptionalString(t.show.expr) || !isOptionalString(t.show.length)) return "show.expr / show.length 必須是字串";
  if (!isStringList(t.pointers) || !isStringList(t.vars)) return "pointers 與 vars 必須是字串陣列（沒有就給 []）";
  const n = t.maxFrames as number;
  if (!(Number.isInteger(n) && n >= 1 && n <= 12)) return "maxFrames 必須是 1–12 的整數";
  if (!isOptionalString(t.caption)) return "caption 必須是字串";
  if (t.when !== undefined && t.when !== "before" && t.when !== "after") return 'when 必須是 "before" 或 "after"';
  return null;
}
