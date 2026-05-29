import assert from "node:assert/strict";
import test from "node:test";
import {
  generatedDraftToJob,
  generateMockVideoDraft,
} from "./generated-video.ts";
import { getJob, saveJob } from "./storage.ts";

const problemStatement = "給定兩個整數 A 和 B，請輸出它們的總和。";
const solutionCode = `#include <iostream>
using namespace std;

int main() {
  int a, b;
  cin >> a >> b;
  cout << a + b << endl;
  return 0;
}
`;

class MemoryStorage {
  private values = new Map<string, string>();

  getItem(key: string): string | null {
    return this.values.get(key) ?? null;
  }

  setItem(key: string, value: string): void {
    this.values.set(key, value);
  }

  removeItem(key: string): void {
    this.values.delete(key);
  }
}

test("mock generator returns a complete editable draft", () => {
  const draft = generateMockVideoDraft({
    name: "A plus B",
    problemStatement,
    solutionCode,
  });

  assert.equal(draft.jobName, "A plus B");
  assert.ok(draft.steps.length >= 4);
  for (const step of draft.steps) {
    assert.ok(step.label);
    assert.equal(typeof step.from, "number");
    assert.equal(typeof step.to, "number");
    assert.ok(step.fileLabel);
    assert.ok(step.fileContent);
    assert.ok(step.subtitle);
  }
});

test("mock generator uses problem comments first and full answer last", () => {
  const draft = generateMockVideoDraft({
    problemStatement,
    solutionCode,
  });

  const first = draft.steps[0];
  const last = draft.steps.at(-1);

  assert.ok(first.fileContent.includes("/*"));
  assert.ok(first.fileContent.includes(problemStatement));
  assert.ok(first.highlight);
  assert.ok(last);
  assert.ok(last.fileContent.includes(solutionCode.trim()));
  assert.equal(last.highlight, undefined);
  assert.equal(last.focusLine, 1);
});

test("generated draft converts to a localStorage-backed job", () => {
  globalThis.localStorage = new MemoryStorage() as Storage;

  const draft = generateMockVideoDraft({
    name: "Local Draft",
    problemStatement,
    solutionCode,
  });
  const job = generatedDraftToJob(draft);

  saveJob(job);

  const loaded = getJob(job.id);
  assert.ok(loaded);
  assert.equal(loaded.name, "Local Draft");
  assert.equal(loaded.steps.length, draft.steps.length);
});
