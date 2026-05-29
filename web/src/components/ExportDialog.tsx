import { useState } from "react";
import type { Job } from "@/lib/draft-types";
import { normalizeFolderName } from "@/lib/export-files";
import { renderMp4, triggerMp4Download } from "@/lib/render-mp4";

type Props = {
  job: Job;
  open: boolean;
  onClose: () => void;
};

function toKebab(input: string): string {
  return normalizeFolderName(input, "untitled");
}

export function ExportDialog({ job, open, onClose }: Props) {
  const [folderName, setFolderName] = useState(() => toKebab(job.name));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!open) return null;

  const handleExport = async () => {
    setError(null);
    setBusy(true);
    try {
      const blob = await renderMp4({ job, folderName });
      const normalizedFolder = normalizeFolderName(folderName, job.name);
      triggerMp4Download(blob, `${normalizedFolder}.mp4`);
      onClose();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-4"
      onClick={onClose}
    >
      <div
        className="bg-neutral-900 border border-neutral-800 rounded-lg p-6 max-w-md w-full"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="text-lg font-semibold mb-4">匯出 MP4</h2>

        <label className="block mb-4">
          <span className="text-xs text-neutral-400 mb-1 block">
            影片名稱（輸出為 {normalizeFolderName(folderName, job.name)}.mp4）
          </span>
          <input
            type="text"
            value={folderName}
            onChange={(e) => setFolderName(e.target.value)}
            className="w-full bg-neutral-950 border border-neutral-800 rounded px-3 py-2 text-sm focus:outline-none focus:border-blue-500"
          />
        </label>

        <div className="text-xs text-neutral-500 mb-4 space-y-1">
          <div>步驟數：{job.steps.length}</div>
          <div>
            cpp 檔（dedupe）：
            {new Set(job.steps.map((s) => s.fileLabel)).size} 個
          </div>
          <div>Render 會使用本機 Remotion CLI，過程可能需要一段時間。</div>
        </div>

        {error && (
          <div className="bg-red-950/50 border border-red-900/50 text-red-300 rounded px-3 py-2 text-sm mb-4">
            {error}
          </div>
        )}

        <div className="flex justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            className="px-3 py-1.5 text-sm text-neutral-400 hover:text-neutral-200"
          >
            取消
          </button>
          <button
            type="button"
            onClick={handleExport}
            disabled={busy || job.steps.length === 0}
            className="bg-blue-600 hover:bg-blue-500 disabled:bg-neutral-800 disabled:text-neutral-500 disabled:cursor-not-allowed text-white px-3 py-1.5 rounded text-sm transition-colors"
          >
            {busy ? "Render 中…" : "匯出 MP4"}
          </button>
        </div>
      </div>
    </div>
  );
}
