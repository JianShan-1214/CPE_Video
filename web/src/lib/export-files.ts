import type { StepJSON, VideoConfigJSON } from "@remotion-src/config-types";
import type { Job } from "./draft-types";

export type VideoExportFiles = {
  folderName: string;
  configJson: string;
  cppFiles: Map<string, string>;
};

export function createVideoExportFiles(
  job: Job,
  folderName: string,
): VideoExportFiles {
  const normalizedFolder = normalizeFolderName(folderName, job.name);
  const cppFiles = new Map<string, string>();

  for (const step of job.steps) {
    const existing = cppFiles.get(step.fileLabel);
    if (existing !== undefined && existing !== step.fileContent) {
      throw new Error(
        `同一個 cpp 檔名有不同內容：${step.fileLabel}。請改用不同檔名或讓內容一致。`,
      );
    }
    cppFiles.set(step.fileLabel, step.fileContent);
  }

  const steps: StepJSON[] = job.steps.map((step) => {
    const out: StepJSON = {
      label: step.label,
      from: step.from,
      to: step.to,
      file: step.fileLabel,
      subtitle: step.subtitle,
    };

    if (step.focusLine !== undefined) out.focusLine = step.focusLine;
    if (step.highlight) out.highlight = step.highlight;
    if (step.annotations && step.annotations.length > 0) {
      out.annotations = step.annotations;
    }
    if (step.animation) out.animation = step.animation;

    return out;
  });

  const config: VideoConfigJSON = { steps };

  return {
    folderName: normalizedFolder,
    configJson: JSON.stringify(config, null, 2),
    cppFiles,
  };
}

export function normalizeFolderName(
  folderName: string,
  fallback: string,
): string {
  return (
    (folderName.trim() || fallback.trim())
      .toLowerCase()
      .replace(/[^a-z0-9_-]+/g, "-")
      .replace(/^-+|-+$/g, "") || "untitled"
  );
}
