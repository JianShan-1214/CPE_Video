import { FilePlus, Upload, WandSparkles } from "lucide-react";
import { Link, useNavigate } from "react-router-dom";
import { createEmptyJob, saveJob } from "@/lib/storage";

export function NewJob() {
  const navigate = useNavigate();

  const handleFromScratch = () => {
    const job = createEmptyJob("Untitled Job");
    saveJob(job);
    navigate(`/jobs/${job.id}/edit`);
  };

  return (
    <div className="min-h-screen bg-neutral-950 text-neutral-100 p-8">
      <div className="max-w-3xl mx-auto">
        <header className="mb-8">
          <Link
            to="/"
            className="text-neutral-400 hover:text-neutral-200 text-sm"
          >
            ← 返回列表
          </Link>
          <h1 className="text-3xl font-semibold mt-2">建立新 Job</h1>
        </header>

        <main className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <button
            type="button"
            onClick={handleFromScratch}
            className="text-left bg-neutral-900 hover:bg-neutral-800 border border-neutral-800 hover:border-blue-500 rounded-lg p-6 transition-colors"
          >
            <FilePlus className="text-blue-400 mb-3" size={28} />
            <h3 className="text-lg font-semibold">從零開始</h3>
            <p className="text-sm text-neutral-400 mt-1">
              建立空白 job，手動加入步驟與內容。
            </p>
          </button>

          <Link
            to="/new/import"
            className="text-left bg-neutral-900 hover:bg-neutral-800 border border-neutral-800 hover:border-blue-500 rounded-lg p-6 transition-colors block"
          >
            <Upload className="text-blue-400 mb-3" size={28} />
            <h3 className="text-lg font-semibold">匯入既有 config</h3>
            <p className="text-sm text-neutral-400 mt-1">
              貼上 config.json 與上傳對應 cpp 檔。
            </p>
          </Link>

          <Link
            to="/new/generate"
            className="text-left bg-neutral-900 hover:bg-neutral-800 border border-neutral-800 hover:border-blue-500 rounded-lg p-6 transition-colors block"
          >
            <WandSparkles className="text-blue-400 mb-3" size={28} />
            <h3 className="text-lg font-semibold">AI 生成草稿</h3>
            <p className="text-sm text-neutral-400 mt-1">
              貼上題目與 C++ 答案，產生 mock GPT 影片草稿。
            </p>
          </Link>
        </main>
      </div>
    </div>
  );
}
