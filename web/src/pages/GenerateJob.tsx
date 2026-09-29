import { ArrowLeft, FileDown, WandSparkles } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { apiClient } from "@/lib/api-client";

export function GenerateJob() {
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [problemStatement, setProblemStatement] = useState("");
  const [solutionCode, setSolutionCode] = useState("");
  const [withAnimation, setWithAnimation] = useState(false);
  const [sampleInput, setSampleInput] = useState("");
  const [sampleOutput, setSampleOutput] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [uvaId, setUvaId] = useState("");
  const [fetching, setFetching] = useState(false);
  const [fetchError, setFetchError] = useState<string | null>(null);

  const handleFetchProblem = async () => {
    setFetchError(null);
    const id = Number(uvaId);
    if (!Number.isInteger(id) || id < 100 || id > 99999) {
      setFetchError("請輸入 100–99999 的 UVa 題號。");
      return;
    }
    setFetching(true);
    try {
      const result = await apiClient.fetchProblemStatement(id);
      setProblemStatement(result.problemStatement);
      setSampleInput(result.sampleInput);
      setSampleOutput(result.sampleOutput);
      setName((current) => (current.trim() ? current : `UVa ${id}`));
    } catch (e: unknown) {
      setFetchError(e instanceof Error ? e.message : String(e));
    } finally {
      setFetching(false);
    }
  };

  const handleGenerate = async () => {
    setError(null);
    if (!problemStatement.trim()) {
      setError("請先貼上題目內容。");
      return;
    }
    if (!solutionCode.trim()) {
      setError("請先貼上完整 C++ 答案。");
      return;
    }

    setBusy(true);
    try {
      const job = await apiClient.generateDraft({
        name,
        problemStatement,
        solutionCode,
        withAnimation,
        sampleInput,
        sampleOutput,
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
            <span className="grid size-10 place-items-center rounded-xl bg-accent-soft border border-line text-accent">
              <WandSparkles size={20} strokeWidth={1.7} />
            </span>
            <h1 className="text-3xl font-bold tracking-tight">AI 生成草稿</h1>
          </div>
          <p className="text-mist mt-3 text-sm leading-relaxed">
            貼上題目與完整 C++ 解答，AI 會依四段式結構自動切出影片草稿，再到編輯器微調。
          </p>
        </header>

        <main className="space-y-5">
          <Field label="Job 名稱（可空，預設 AI 生成草稿）">
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="input"
              placeholder="e.g. 26D5 Containers"
            />
          </Field>

          <div>
            <label htmlFor="uva-id" className="field-label">UVa 題號（可選，自動抓題目並整理成繁中）</label>
            <div className="flex gap-2">
              <input
                id="uva-id"
                type="number"
                min={100}
                max={99999}
                value={uvaId}
                onChange={(e) => setUvaId(e.target.value)}
                className="input min-w-0"
                placeholder="e.g. 10038"
              />
              <button
                type="button"
                onClick={handleFetchProblem}
                disabled={fetching || busy}
                className="btn btn-ghost shrink-0"
              >
                <FileDown size={16} />
                {fetching ? "抓取中…" : "抓題目"}
              </button>
            </div>
            {fetchError && <div className="error-banner mt-2">{fetchError}</div>}
          </div>

          <Field label="題目內容">
            <textarea
              value={problemStatement}
              onChange={(e) => setProblemStatement(e.target.value)}
              rows={8}
              className="input resize-y"
              placeholder="貼上 OJ 題目、輸入輸出說明或題目描述"
            />
          </Field>

          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="範例輸入">
              <textarea
                value={sampleInput}
                onChange={(e) => setSampleInput(e.target.value)}
                rows={5}
                className="input resize-y font-mono text-xs leading-relaxed"
                spellCheck={false}
              />
            </Field>
            <Field label="範例輸出">
              <textarea
                value={sampleOutput}
                onChange={(e) => setSampleOutput(e.target.value)}
                rows={5}
                className="input resize-y font-mono text-xs leading-relaxed"
                spellCheck={false}
              />
            </Field>
          </div>

          <Field label="完整 C++ 答案">
            <textarea
              value={solutionCode}
              onChange={(e) => setSolutionCode(e.target.value)}
              rows={16}
              className="input resize-y font-mono text-xs leading-relaxed"
              placeholder="#include <bits/stdc++.h>"
              spellCheck={false}
            />
          </Field>

          <div>
            <label className="flex items-center gap-2 text-sm text-mist cursor-pointer">
              <input
                type="checkbox"
                checked={withAnimation}
                onChange={(e) => setWithAnimation(e.target.checked)}
              />
              加入程式執行動畫（實驗性）
            </label>
            <p className="text-xs text-faint mt-1 ml-6">
              會實際編譯並執行你的程式，動畫數值來自範例輸入的真實執行結果
            </p>
          </div>

          {error && <div className="error-banner">{error}</div>}

          <button
            type="button"
            onClick={handleGenerate}
            disabled={busy}
            className="btn btn-primary"
          >
            <WandSparkles size={16} />
            {busy ? "生成中…" : "生成草稿"}
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
      <span className="field-label">{label}</span>
      {children}
    </label>
  );
}
