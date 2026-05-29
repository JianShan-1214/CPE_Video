import type { Job } from "./draft-types";

export type RenderMp4Input = {
  job: Job;
  folderName: string;
};

export async function renderMp4(input: RenderMp4Input): Promise<Blob> {
  const response = await fetch("/api/render-mp4", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });

  if (!response.ok) {
    let message = `MP4 render failed (${response.status})`;
    try {
      const body = (await response.json()) as { error?: string };
      if (body.error) message = body.error;
    } catch {
      // Keep default message when the server did not return JSON.
    }
    throw new Error(message);
  }

  return response.blob();
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
