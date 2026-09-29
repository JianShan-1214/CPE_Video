import assert from "node:assert/strict";
import test from "node:test";
import type { DraftIssue } from "./api-client.ts";
import { countByStep, sortIssues } from "./draft-issues.ts";

const issue = (stepIndex: number | null, level: DraftIssue["level"], message = ""): DraftIssue => ({
  stepIndex,
  level,
  message,
  source: "rule",
});

test("sorts draft-level first, then by step with errors first", () => {
  const sorted = sortIssues([issue(1, "warning"), issue(0, "warning"), issue(1, "error"), issue(null, "warning")]);
  assert.deepEqual(
    sorted.map((i) => [i.stepIndex, i.level]),
    [[null, "warning"], [0, "warning"], [1, "error"], [1, "warning"]],
  );
});

test("counts errors and warnings per step, skipping draft-level issues", () => {
  const counts = countByStep([issue(2, "error"), issue(2, "warning"), issue(2, "warning"), issue(null, "error")]);
  assert.deepEqual([...counts], [[2, { errors: 1, warnings: 2 }]]);
});
