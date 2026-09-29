import assert from "node:assert/strict";
import test from "node:test";
import { applyTraceAnimations, reorderSteps } from "./step-order.ts";
import type { DraftStep } from "./draft-types.ts";

const steps = ["a", "b", "c", "d"];

test("moves an item from one index to another", () => {
  assert.deepEqual(reorderSteps(steps, 1, 3), ["a", "c", "d", "b"]);
});

test("returns the original order for invalid indexes", () => {
  assert.deepEqual(reorderSteps(steps, -1, 2), steps);
  assert.deepEqual(reorderSteps(steps, 1, 8), steps);
});

test("does not mutate the input array", () => {
  const original = [...steps];
  reorderSteps(steps, 0, 2);
  assert.deepEqual(steps, original);
});

test("trace animations land only on traced steps that are unchanged since the request", () => {
  const base = { label: "s", from: 0, to: 5, fileLabel: "a.cpp", fileContent: "x\n", subtitle: "" };
  const trace = { line: 1, show: { as: "vars" as const }, pointers: [], vars: ["x"], maxFrames: 2 };
  const old = { type: "vars" as const, frames: [{ vars: { x: 0 } }] };
  const fresh = { type: "vars" as const, frames: [{ vars: { x: 1 } }] };
  const plain: DraftStep = { ...base, animation: old };
  const traced: DraftStep = { ...base, trace, animation: old };
  const failed: DraftStep = { ...base, trace, animation: old };
  const edited: DraftStep = { ...base, trace, animation: old };
  const sent = [plain, traced, failed, edited];
  const response = [plain, { ...traced, animation: fresh }, { ...failed, animation: null }, { ...edited, animation: fresh }] as unknown as DraftStep[];
  const editedNow = { ...edited, subtitle: "改過" };

  const result = applyTraceAnimations([plain, traced, failed, editedNow], sent, response);

  assert.equal(result[0], plain);
  assert.deepEqual(result[1], { ...traced, animation: fresh });
  assert.equal(result[2].animation, undefined);
  assert.equal(result[3], editedNow);
});
