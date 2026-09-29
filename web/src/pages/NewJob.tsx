import { ArrowLeft, FilePlus, Upload, WandSparkles } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { apiClient } from "@/lib/api-client";

export function NewJob() {
  const navigate = useNavigate();
  const [error, setError] = useState<string | null>(null);

  const handleFromScratch = async () => {
    setError(null);
    try {
      const job = await apiClient.createJob({ name: "Untitled Job" });
      navigate(`/jobs/${job.id}/edit`);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  return (
    <div className="min-h-screen px-6 py-10 sm:px-10">
      <div className="max-w-4xl mx-auto">
        <header className="reveal mb-10">
          <Link to="/" className="btn btn-quiet -ml-2 mb-4">
            <ArrowLeft size={15} />
            返回列表
          </Link>
          <span className="eyebrow">New project</span>
          <h1 className="text-4xl font-bold tracking-tight mt-2">建立新 Job</h1>
          <p className="text-mist mt-2">選一個起點。</p>
        </header>

        {error && <div className="error-banner mb-6">{error}</div>}

        <main className="stagger grid grid-cols-1 sm:grid-cols-3 gap-4">
          <button
            type="button"
            onClick={handleFromScratch}
            className="card card-interactive group text-left p-6"
          >
            <ChoiceBody
              num="01"
              icon={<FilePlus size={24} strokeWidth={1.6} />}
              title="從零開始"
              desc="建立空白 job，手動加入步驟與內容。"
            />
          </button>

          <Link to="/new/import" className="card card-interactive group text-left p-6 block">
            <ChoiceBody
              num="02"
              icon={<Upload size={24} strokeWidth={1.6} />}
              title="匯入既有 config"
              desc="貼上 config.json 與上傳對應 cpp 檔。"
            />
          </Link>

          <Link to="/new/generate" className="card card-interactive group text-left p-6 block">
            <ChoiceBody
              num="03"
              icon={<WandSparkles size={24} strokeWidth={1.6} />}
              title="AI 生成草稿"
              desc="貼上題目與 C++ 答案，AI 自動產生影片草稿。"
            />
          </Link>
        </main>
      </div>
    </div>
  );
}

function ChoiceBody({
  num,
  icon,
  title,
  desc,
}: {
  num: string;
  icon: React.ReactNode;
  title: string;
  desc: string;
}) {
  return (
    <>
      <div className="flex items-center justify-between">
        <span className="grid size-12 place-items-center rounded-xl bg-ink-850 border border-line text-faint transition-colors group-hover:text-accent group-hover:border-line-strong">
          {icon}
        </span>
        <span className="eyebrow">{num}</span>
      </div>
      <h3 className="text-lg font-semibold mt-5 transition-colors group-hover:text-accent">
        {title}
      </h3>
      <p className="text-sm text-mist mt-1.5 leading-relaxed">{desc}</p>
    </>
  );
}
