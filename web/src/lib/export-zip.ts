import JSZip from "jszip";
import type { Job } from "./draft-types";
import { createVideoExportFiles } from "./export-files";

export type ExportResult = {
  blob: Blob;
  filename: string;
};

/**
 * 將 Job 匯出成 zip：
 *   <folder>/config.json
 *   <folder>/<fileLabel> (各步驟用到的 cpp 檔，dedupe 後)
 *
 * 若多個步驟用同一個 fileLabel 但 fileContent 不同，後者覆蓋前者。
 */
export async function exportToZip(
  job: Job,
  folderName: string,
): Promise<ExportResult> {
  const files = createVideoExportFiles(job, folderName);

  const zip = new JSZip();
  const folder = zip.folder(files.folderName);
  if (!folder) throw new Error("無法建立 zip 子資料夾");

  folder.file("config.json", files.configJson);
  for (const [filename, content] of files.cppFiles.entries()) {
    folder.file(filename, content);
  }

  const blob = await zip.generateAsync({ type: "blob" });
  return { blob, filename: `${files.folderName}.zip` };
}

export function triggerDownload(result: ExportResult): void {
  const url = URL.createObjectURL(result.blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = result.filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
