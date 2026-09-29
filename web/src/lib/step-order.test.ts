import assert from "node:assert/strict";
import test from "node:test";
import { reorderSteps } from "./step-order.ts";

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
