import { WandSparkles } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  generatedDraftToJob,
  generateMockVideoDraft,
} from "@/lib/generated-video";
import { saveJob } from "@/lib/storage";

const inputCls =
  "w-full bg-neutral-900 border border-neutral-800 rounded px-3 py-2 text-sm focus:outline-none focus:border-blue-500";

export function GenerateJob() {
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [problemStatement, setProblemStatement] = useState("");
  const [solutionCode, setSolutionCode] = useState("");
  const [error, setError] = useState<string | null>(null);

  const handleGenerate = () => {
    setError(null);
    if (!problemStatement.trim()) {
      setError("請先貼上題目內容。");
      return;
    }
    if (!solutionCode.trim()) {
      setError("請先貼上完整 C++ 答案。");
      return;
    }

    const draft = generateMockVideoDraft({
      name,
      problemStatement,
      solutionCode,
    });
    const job = generatedDraftToJob(draft);
    saveJob(job);
    navigate(`/jobs/${job.id}/edit`);
  };

  return (
    <div className="min-h-screen bg-neutral-950 text-neutral-100 p-8">
      <div className="max-w-4xl mx-auto">
        <header className="mb-8">
          <Link
            to="/new"
            className="text-neutral-400 hover:text-neutral-200 text-sm"
          >
            ← 返回
          </Link>
          <div className="flex items-center gap-3 mt-2">
            <WandSparkles className="text-blue-400" size={28} />
            <h1 className="text-3xl font-semibold">AI 生成草稿</h1>
          </div>
          <p className="text-neutral-400 mt-2 text-sm">
            目前使用 mock GPT 回傳資料；不會呼叫 API，也不需要金鑰。
          </p>
        </header>

        <main className="space-y-4">
          <Field label="Job 名稱（可空，預設 GPT Mock Draft）">
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className={inputCls}
              placeholder="e.g. 26D5 Containers"
            />
          </Field>

          <Field label="題目內容">
            <textarea
              value={problemStatement}
              onChange={(e) => setProblemStatement(e.target.value)}
              rows={8}
              className={inputCls}
              placeholder="貼上 OJ 題目、輸入輸出說明或題目描述"
            />
          </Field>

          <Field label="完整 C++ 答案">
            <textarea
              value={solutionCode}
              onChange={(e) => setSolutionCode(e.target.value)}
              rows={16}
              className={`${inputCls} font-mono text-xs`}
              placeholder="#include <bits/stdc++.h>"
              spellCheck={false}
            />
          </Field>

          {error && (
            <div className="bg-red-950/50 border border-red-900/50 text-red-300 rounded px-3 py-2 text-sm">
              {error}
            </div>
          )}

          <button
            type="button"
            onClick={handleGenerate}
            className="bg-blue-600 hover:bg-blue-500 text-white px-4 py-2 rounded transition-colors"
          >
            生成草稿
          </button>
        </main>
      </div>
    </div>
  );
}

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
