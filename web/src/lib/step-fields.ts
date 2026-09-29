import type { StepAnimation } from "@remotion-src/config-types";

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

const isValueList = (v: unknown) =>
  Array.isArray(v) &&
  v.every((x) => typeof x === "string" || (typeof x === "number" && Number.isFinite(x)));

const isIntList = (v: unknown) => Array.isArray(v) && v.every(Number.isInteger);

// Optional fields must be absent, not null: the renderer drops an animation with nulls.
function animationShapeError(a: unknown): string | null {
  if (!isObject(a)) return "動畫必須是 JSON 物件";
  if (a.type !== "array" && a.type !== "stacks") return 'type 必須是 "array" 或 "stacks"';
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
    if (a.type === "array") {
      if (!isValueList(f.values)) return `${at}.values 必須是數字或字串的陣列`;
      if (f.mark !== undefined && !isIntList(f.mark)) return `${at}.mark 必須是整數陣列`;
      if (
        f.pointers !== undefined &&
        !(isObject(f.pointers) && Object.values(f.pointers).every(Number.isInteger))
      ) {
        return `${at}.pointers 必須是 { "變數名": 整數 index }`;
      }
    } else if (!(Array.isArray(f.stacks) && f.stacks.every(isValueList))) {
      return `${at}.stacks 必須是陣列的陣列（元素為數字或字串）`;
    }
  }
  return null;
}
