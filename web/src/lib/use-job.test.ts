import assert from "node:assert/strict";
import test from "node:test";
import type { Job } from "./draft-types.ts";
import { createDebouncedJobSaver } from "./debounced-job-saver.ts";

const job: Job = {
  id: "job-1",
  name: "Pending Save",
  createdAt: 1,
  updatedAt: 1,
  theme: "github-dark",
  width: { type: "fixed", value: 1920 },
  steps: [],
};

test("flush saves a pending debounced job before cleanup", () => {
  const saved: Job[] = [];
  const savingStates: boolean[] = [];
  const saver = createDebouncedJobSaver({
    delayMs: 10_000,
    save: (next) => saved.push(next),
    setSaving: (saving) => savingStates.push(saving),
  });

  saver.schedule(job);
  saver.flush();

  assert.deepEqual(saved, [job]);
  assert.deepEqual(savingStates, [true, false]);
});
