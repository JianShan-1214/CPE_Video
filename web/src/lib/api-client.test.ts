import assert from "node:assert/strict";
import test from "node:test";
import { ApiClient } from "./api-client.ts";

test("api client surfaces JSON error detail", async () => {
  const client = new ApiClient({
    baseUrl: "http://api.test",
    fetchImpl: async () =>
      new Response(JSON.stringify({ detail: "missing job" }), {
        status: 404,
        headers: { "Content-Type": "application/json" },
      }),
  });

  await assert.rejects(
    () => client.getJob("missing"),
    /missing job/,
  );
});

test("api client creates render jobs and downloads blobs", async () => {
  const calls: string[] = [];
  const client = new ApiClient({
    baseUrl: "http://api.test/",
    fetchImpl: async (input, init) => {
      calls.push(`${init?.method ?? "GET"} ${String(input)}`);
      if (String(input).endsWith("/api/render-jobs") && init?.method === "POST") {
        return Response.json({ id: "render-1", status: "queued" }, { status: 201 });
      }
      return new Response("mp4", {
        status: 200,
        headers: { "Content-Type": "video/mp4" },
      });
    },
  });

  const renderJob = await client.createRenderJob({ jobId: "job-1" });
  const blob = await client.downloadRenderJob("render-1");

  assert.equal(renderJob.id, "render-1");
  assert.equal(await blob.text(), "mp4");
  assert.deepEqual(calls, [
    "POST http://api.test/api/render-jobs",
    "GET http://api.test/api/render-jobs/render-1/download",
  ]);
});

test("api client fetches a UVa problem statement", async () => {
  const calls: string[] = [];
  const client = new ApiClient({
    baseUrl: "http://api.test",
    fetchImpl: async (input, init) => {
      calls.push(`${init?.method} ${String(input)} ${String(init?.body)}`);
      return Response.json({ uvaId: 101, problemStatement: "題意：…" });
    },
  });

  const result = await client.fetchProblemStatement(101);

  assert.equal(result.problemStatement, "題意：…");
  assert.deepEqual(calls, [
    'POST http://api.test/api/problem-statement {"uvaId":101}',
  ]);
});

test("api client checks a draft and unwraps the issues", async () => {
  const calls: string[] = [];
  const issue = { stepIndex: 0, level: "error", message: "錯", source: "rule" };
  const client = new ApiClient({
    baseUrl: "http://api.test",
    fetchImpl: async (input, init) => {
      calls.push(`${init?.method} ${String(input)} ${String(init?.body)}`);
      return Response.json({ issues: [issue] });
    },
  });
  const step = { label: "a", from: 0, to: 5, fileLabel: "c.cpp", fileContent: "x\n", subtitle: "s" };

  const issues = await client.checkDraft([step], false);

  assert.deepEqual(issues, [issue]);
  assert.deepEqual(calls, [
    `POST http://api.test/api/drafts/check ${JSON.stringify({ steps: [step], ai: false })}`,
  ]);
});

test("api client turns FastAPI validation arrays into readable text", async () => {
  const client = new ApiClient({
    baseUrl: "http://api.test",
    fetchImpl: async () =>
      Response.json(
        {
          detail: [
            { loc: ["body", "steps", 0, "focusLine"], msg: "Input should be greater than or equal to 1" },
            { loc: ["body", "steps"], msg: "List should have at least 1 item" },
          ],
        },
        { status: 422 },
      ),
  });

  await assert.rejects(() => client.checkDraft([], false), (e: Error) => {
    assert.equal(
      e.message,
      "資料格式錯誤：第 1 步 focusLine：Input should be greater than or equal to 1；steps：List should have at least 1 item",
    );
    return true;
  });
});

test("api client sends the withAnimation flag", async () => {
  const bodies: string[] = [];
  const client = new ApiClient({
    baseUrl: "http://api.test",
    fetchImpl: async (_input, init) => {
      bodies.push(String(init?.body));
      return Response.json({ id: "job-1" }, { status: 201 });
    },
  });

  await client.generateDraft({ problemStatement: "p", solutionCode: "c", withAnimation: true });

  assert.deepEqual(JSON.parse(bodies[0]), { problemStatement: "p", solutionCode: "c", withAnimation: true });
});
