import { Film } from "lucide-react";
import { useEffect, useState } from "react";
import type { RenderJob } from "@/lib/api-client";
import type { Job } from "@/lib/draft-types";
import { normalizeFolderName } from "@/lib/export-files";
import { renderMp4, triggerMp4Download } from "@/lib/render-mp4";

const STATUS_LABEL: Record<RenderJob["status"], string> = {
  queued: "排隊中",
  running: "Render 中",
  succeeded: "完成，下載中",
  failed: "失敗",
};

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
  const [status, setStatus] = useState<RenderJob["status"] | null>(null);
  const [elapsedSec, setElapsedSec] = useState(0);
  const [error, setError] = useState<string | null>(null);

  // A render takes minutes; without a ticking clock the dialog looks frozen.
  useEffect(() => {
    if (!busy) return;
    setElapsedSec(0);
    const started = Date.now();
    const timer = setInterval(
      () => setElapsedSec(Math.floor((Date.now() - started) / 1000)),
      1000,
    );
    return () => clearInterval(timer);
  }, [busy]);

  if (!open) return null;

  const handleExport = async () => {
    setError(null);
    setStatus(null);
    setBusy(true);
    try {
      const blob = await renderMp4({ jobId: job.id, folderName }, setStatus);
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
      className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4"
      onClick={onClose}
    >
      <div
        className="reveal panel p-6 max-w-md w-full"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center gap-3 mb-5">
          <span className="grid size-9 place-items-center rounded-lg bg-accent-soft border border-line text-accent">
            <Film size={18} strokeWidth={1.7} />
          </span>
          <h2 className="text-lg font-semibold">匯出 MP4</h2>
        </div>

        <label className="block mb-4">
          <span className="field-label">
            影片名稱（輸出為 {normalizeFolderName(folderName, job.name)}.mp4）
          </span>
          <input
            type="text"
            value={folderName}
            onChange={(e) => setFolderName(e.target.value)}
            className="input font-mono"
          />
        </label>

        <div className="rounded-lg border border-line bg-ink-950/40 p-3 mb-4 space-y-1.5">
          <Stat label="步驟數" value={`${job.steps.length}`} />
          <Stat
            label="cpp 檔（dedupe）"
            value={`${new Set(job.steps.map((s) => s.fileLabel)).size} 個`}
          />
          <Stat label="主題 / 寬度" value={`${job.theme} · ${job.width.type === "auto" ? "auto" : `${job.width.value}px`}`} />
          <p className="text-xs text-faint pt-1">
            伺服器會用 Remotion 逐格算圖，數分鐘不等。未設定語音金鑰時會輸出無旁白版本。
          </p>
        </div>

        {busy && (
          <div className="rounded-lg border border-line bg-ink-950/40 p-3 mb-4 flex items-center justify-between text-xs">
            <span className="text-mist">
              {status ? STATUS_LABEL[status] : "送出中"}…
            </span>
            <span className="meta-mono text-paper">{elapsedSec}s</span>
          </div>
        )}

        {error && <div className="error-banner mb-4">{error}</div>}

        <div className="flex justify-end gap-2">
          <button type="button" onClick={onClose} className="btn btn-quiet">
            取消
          </button>
          <button
            type="button"
            onClick={handleExport}
            disabled={busy || job.steps.length === 0}
            className="btn btn-primary px-3 py-2 text-sm"
          >
            {busy ? "Render 中…" : "匯出 MP4"}
          </button>
        </div>
      </div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between text-xs">
      <span className="text-mist">{label}</span>
      <span className="meta-mono text-paper">{value}</span>
    </div>
  );
}
