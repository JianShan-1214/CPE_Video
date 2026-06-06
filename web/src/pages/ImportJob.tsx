import { ArrowLeft, Upload } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { apiClient } from "@/lib/api-client";

function Field({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <label className="block">
      <span className="field-label">{label}</span>
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
      const job = await apiClient.importJob({
        configJson: configText,
        cppFiles,
        name: name.trim() || undefined,
      });
      navigate(`/jobs/${job.id}/edit`);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="min-h-screen px-6 py-10 sm:px-10">
      <div className="max-w-3xl mx-auto reveal">
        <header className="mb-8">
          <Link to="/new" className="btn btn-quiet -ml-2 mb-4">
            <ArrowLeft size={15} />
            返回
          </Link>
          <div className="flex items-center gap-3">
            <span className="grid size-10 place-items-center rounded-xl bg-ink-850 border border-line text-faint">
              <Upload size={20} strokeWidth={1.7} />
            </span>
            <h1 className="text-3xl font-bold tracking-tight">匯入既有 config</h1>
          </div>
          <p className="text-mist mt-3 text-sm">
            貼上 config.json 內容並上傳對應的 cpp 檔。
          </p>
        </header>

        <main className="space-y-5">
          <Field label="Job 名稱（可空，預設 Imported Job）">
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="input"
              placeholder="e.g. 25B4 Blocks"
            />
          </Field>

          <Field label="config.json 內容">
            <textarea
              value={configText}
              onChange={(e) => setConfigText(e.target.value)}
              rows={12}
              className="input resize-y font-mono text-xs leading-relaxed"
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
              className="block w-full text-sm text-mist file:mr-3 file:py-2 file:px-3 file:rounded-lg file:border file:border-line file:bg-ink-850 file:text-paper file:cursor-pointer hover:file:border-line-strong file:transition-colors"
            />
            {files.length > 0 && (
              <div className="mt-2 flex flex-wrap gap-1.5">
                {files.map((f) => (
                  <span key={f.name} className="chip">
                    {f.name}
                  </span>
                ))}
              </div>
            )}
          </Field>

          {error && <div className="error-banner">{error}</div>}

          <button
            type="button"
            onClick={handleSubmit}
            disabled={busy || !configText.trim() || files.length === 0}
            className="btn btn-primary"
          >
            {busy ? "匯入中…" : "匯入並進入編輯"}
          </button>
        </main>
      </div>
    </div>
  );
}
