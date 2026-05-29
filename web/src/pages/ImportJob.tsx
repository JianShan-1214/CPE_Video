import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { importFromConfig } from "@/lib/import-config";
import { saveJob } from "@/lib/storage";

const inputCls =
  "w-full bg-neutral-900 border border-neutral-800 rounded px-3 py-2 text-sm focus:outline-none focus:border-blue-500";

function Field({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <label className="block">
      <span className="text-xs text-neutral-400 mb-1 block">{label}</span>
      {children}
    </label>
  );
}

export function ImportJob() {
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [configText, setConfigText] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const handleSubmit = async () => {
    setError(null);
    setBusy(true);
    try {
      const cppFiles: Record<string, string> = {};
      for (const file of files) {
        cppFiles[file.name] = await file.text();
      }
      const result = importFromConfig({
        configJson: configText,
        cppFiles,
        name: name.trim() || undefined,
      });
      if (!result.ok) {
        setError(result.error);
        return;
      }
      saveJob(result.job);
      navigate(`/jobs/${result.job.id}/edit`);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="min-h-screen bg-neutral-950 text-neutral-100 p-8">
      <div className="max-w-3xl mx-auto">
        <header className="mb-8">
          <Link
            to="/new"
            className="text-neutral-400 hover:text-neutral-200 text-sm"
          >
            ← 返回
          </Link>
          <h1 className="text-3xl font-semibold mt-2">匯入既有 config</h1>
          <p className="text-neutral-400 mt-2 text-sm">
            貼上 config.json 內容並上傳對應的 cpp 檔。
          </p>
        </header>

        <main className="space-y-4">
          <Field label="Job 名稱（可空，預設 “Imported Job”）">
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className={inputCls}
              placeholder="e.g. 25B4 Blocks"
            />
          </Field>

          <Field label="config.json 內容">
            <textarea
              value={configText}
              onChange={(e) => setConfigText(e.target.value)}
              rows={12}
              className={`${inputCls} font-mono text-xs`}
              placeholder='{"steps": [ ... ]}'
              spellCheck={false}
            />
          </Field>

          <Field label="cpp 檔（多選，檔名要對應 config 中的 file 欄位）">
            <input
              type="file"
              multiple
              accept=".cpp"
              onChange={(e) => setFiles(Array.from(e.target.files ?? []))}
              className="block text-sm file:mr-3 file:py-2 file:px-3 file:rounded file:border-0 file:bg-neutral-800 file:text-neutral-200 hover:file:bg-neutral-700"
            />
            {files.length > 0 && (
              <div className="text-xs text-neutral-500 mt-2">
                已選 {files.length} 個檔：
                {files.map((f) => f.name).join(", ")}
              </div>
            )}
          </Field>

          {error && (
            <div className="bg-red-950/50 border border-red-900/50 text-red-300 rounded px-3 py-2 text-sm">
              {error}
            </div>
          )}

          <button
            type="button"
            onClick={handleSubmit}
            disabled={busy || !configText.trim() || files.length === 0}
            className="bg-blue-600 hover:bg-blue-500 disabled:bg-neutral-800 disabled:text-neutral-500 disabled:cursor-not-allowed text-white px-4 py-2 rounded transition-colors"
          >
            {busy ? "匯入中…" : "匯入並進入編輯"}
          </button>
        </main>
      </div>
    </div>
  );
}
