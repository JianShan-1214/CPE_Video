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
