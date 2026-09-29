import assert from "node:assert/strict";
import test from "node:test";
import { createVideoExportFiles } from "./export-files.ts";
import { importFromConfig } from "./import-config.ts";
import type { Job } from "./draft-types.ts";

const job: Job = {
  id: "job-1",
  name: "Sample Job",
  createdAt: 1,
  updatedAt: 1,
  theme: "github-dark",
  width: { type: "fixed", value: 1920 },
  steps: [
    {
      label: "Intro",
      from: 0,
      to: 5,
      fileLabel: "code01.cpp",
      fileContent: "// problem\n",
      subtitle: "題目說明",
      highlight: { startLine: 1, endLine: 1, color: "blue" },
    },
    {
      label: "Done",
      from: 5,
      to: 10,
      fileLabel: "code02.cpp",
      fileContent: "int main() { return 0; }\n",
      subtitle: "完成",
      focusLine: 1,
    },
  ],
};

test("creates render-ready config and cpp files from a job", () => {
  const result = createVideoExportFiles(job, "My Render!");
  const config = JSON.parse(result.configJson);

  assert.equal(result.folderName, "my-render");
  assert.deepEqual([...result.cppFiles.keys()], ["code01.cpp", "code02.cpp"]);
  assert.equal(config.steps[0].file, "code01.cpp");
  assert.equal(config.steps[0].fileContent, undefined);
  assert.equal(config.steps[1].focusLine, 1);
});

test("dedupes matching content when multiple steps share a file label", () => {
  const result = createVideoExportFiles(
    {
      ...job,
      steps: [
        job.steps[0],
        { ...job.steps[0] },
      ],
    },
    "",
  );

  assert.equal(result.folderName, "sample-job");
  assert.equal(result.cppFiles.get("code01.cpp"), "// problem\n");
});

test("rejects duplicate file labels with different content", () => {
  assert.throws(
    () =>
      createVideoExportFiles(
        {
          ...job,
          steps: [
            job.steps[0],
            { ...job.steps[0], fileContent: "// different\n" },
          ],
        },
        "",
      ),
    /同一個 cpp 檔名有不同內容/,
  );
});

test("animation survives export and re-import", () => {
  const animation = {
    type: "array" as const,
    frames: [{ values: [3, 1], pointers: { i: 0 }, caption: "開始" }],
  };
  const withAnim: Job = { ...job, steps: [{ ...job.steps[0], animation }, job.steps[1]] };
  const files = createVideoExportFiles(withAnim, "x");
  const config = JSON.parse(files.configJson);

  assert.deepEqual(config.steps[0].animation, animation);
  assert.equal("animation" in config.steps[1], false);

  const imported = importFromConfig({
    configJson: files.configJson,
    cppFiles: Object.fromEntries(files.cppFiles),
  });
  assert.ok(imported.ok);
  assert.deepEqual(imported.job.steps[0].animation, animation);
  assert.equal(imported.job.steps[1].animation, undefined);
});
