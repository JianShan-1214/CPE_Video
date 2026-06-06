import { apiClient } from "./api-client";

export type RenderMp4Input = {
  jobId: string;
  folderName: string;
};

const POLL_INTERVAL_MS = 1000;
const POLL_TIMEOUT_MS = 30 * 60 * 1000;

export async function renderMp4(input: RenderMp4Input): Promise<Blob> {
  const renderJob = await apiClient.createRenderJob({
    jobId: input.jobId,
    folderName: input.folderName,
  });

  const deadline = Date.now() + POLL_TIMEOUT_MS;
  for (;;) {
    const status = await apiClient.getRenderJob(renderJob.id);
    if (status.status === "succeeded") {
      return apiClient.downloadRenderJob(renderJob.id);
    }
    if (status.status === "failed") {
      throw new Error(status.error ?? "MP4 render failed");
    }
    if (Date.now() > deadline) {
      throw new Error("Render 等待逾時，請稍後再試或查看後端記錄。");
    }
    await new Promise((resolve) => setTimeout(resolve, POLL_INTERVAL_MS));
  }
}

export function triggerMp4Download(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
