import type { DraftStep } from "./draft-types";

export function reorderSteps<T>(
  items: readonly T[],
  fromIndex: number,
  toIndex: number,
): T[] {
  if (
    fromIndex < 0 ||
    toIndex < 0 ||
    fromIndex >= items.length ||
    toIndex >= items.length
  ) {
    return [...items];
  }

  const next = [...items];
  const [moved] = next.splice(fromIndex, 1);
  next.splice(toIndex, 0, moved);
  return next;
}

/**
 * Copy `animation` from a /api/drafts/trace response (same order as `sent`) onto
 * the current steps. Only traced steps that are still the exact objects that were
 * sent get it: a step edited, moved or deleted meanwhile keeps what it has.
 */
export function applyTraceAnimations(
  current: readonly DraftStep[],
  sent: readonly DraftStep[],
  traced: readonly DraftStep[],
): DraftStep[] {
  return current.map((step, i) =>
    step === sent[i] && step.trace ? { ...step, animation: traced[i]?.animation ?? undefined } : step,
  );
}
