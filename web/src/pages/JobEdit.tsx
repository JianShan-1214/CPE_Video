import { ArrowLeft, Film, ListChecks, Loader2, Play, TerminalSquare } from "lucide-react";
import { useMemo, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { IssueList } from "@/components/DraftIssues";
import { ExportDialog } from "@/components/ExportDialog";
import { RemotionPreview } from "@/components/RemotionPreview";
import { StepEditor } from "@/components/StepEditor";
import { StepList } from "@/components/StepList";
import { VideoSettings } from "@/components/VideoSettings";
import { apiClient, type DraftIssue } from "@/lib/api-client";
import { countByStep, sortIssues } from "@/lib/draft-issues";
import type { DraftStep, Job } from "@/lib/draft-types";
import { applyTraceAnimations, reorderSteps } from "@/lib/step-order";
import { useDebouncedValue, useJob } from "@/lib/use-job";

function makeEmptyStep(index: number): DraftStep {
  const fileLabel = `code${String(index + 1).padStart(2, "0")}.cpp`;
  return {
    label: `Step ${index + 1}`,
    from: 0,
    to: 5,
    fileLabel,
    fileContent: "// TODO\n",
    subtitle: "",
  };
}

export function JobEdit() {
  const { id } = useParams<{ id: string }>();
  const { job, update, saving, loaded } = useJob(id);
  const [selectedIndex, setSelectedIndex] = useState<number | null>(null);
  const [exportOpen, setExportOpen] = useState(false);
  // `steps` is the array that was checked: any edit replaces job.steps, so a
  // reference mismatch means the results are stale.
  const [check, setCheck] = useState<{ issues: DraftIssue[]; steps: DraftStep[]; title: string } | null>(null);
  const [checking, setChecking] = useState(false);
  const [checkError, setCheckError] = useState<string | null>(null);
  const issueCounts = useMemo(() => countByStep(check?.issues ?? []), [check]);
  const [tracing, setTracing] = useState(false);
  // Bumped after 「重新產生動畫」 so the step editor remounts and shows the new animation JSON.
  const [traceRuns, setTraceRuns] = useState(0);
  const jobRef = useRef(job);
  jobRef.current = job;

  const previewJob = useDebouncedValue(job, 300);

  const selectedStep = useMemo(() => {
    if (!job || selectedIndex === null) return null;
    return job.steps[selectedIndex] ?? null;
  }, [job, selectedIndex]);

  if (!loaded) return null;
  if (!job) {
    return (
      <div className="min-h-screen grid place-items-center p-8 text-center">
        <div className="reveal">
          <p className="text-mist mb-3">找不到 job（id: {id}）。</p>
          <Link to="/" className="btn btn-ghost">
            <ArrowLeft size={15} />
            返回列表
          </Link>
        </div>
      </div>
    );
  }

  // Issues point at steps by position, so any add/delete/reorder makes them
  // point at the wrong step: drop them instead of just dimming.
  const clearCheck = () => {
    setCheck(null);
    setCheckError(null);
  };

  const handleAddStep = () => {
    clearCheck();
    update((prev) => {
      const newStep = makeEmptyStep(prev.steps.length);
      return { ...prev, steps: [...prev.steps, newStep] };
    });
    setSelectedIndex(job.steps.length);
  };

  const handleDeleteStep = (idx: number) => {
    clearCheck();
    update((prev) => ({
      ...prev,
      steps: prev.steps.filter((_, i) => i !== idx),
    }));
    setSelectedIndex((cur) => {
      if (cur === null) return null;
      if (cur === idx) return null;
      if (cur > idx) return cur - 1;
      return cur;
    });
  };

  const handleStepChange = (idx: number, next: DraftStep) => {
    update((prev) => ({
      ...prev,
      steps: prev.steps.map((s, i) => (i === idx ? next : s)),
    }));
  };

  const handleStepReorder = (fromIndex: number, toIndex: number) => {
    if (fromIndex !== toIndex) clearCheck();
    update((prev) => ({
      ...prev,
      steps: reorderSteps(prev.steps, fromIndex, toIndex),
    }));
    setSelectedIndex((cur) => remapSelectedIndex(cur, fromIndex, toIndex));
  };

  const handleNameChange = (name: string) => {
    update((prev) => ({ ...prev, name }));
  };

  const selectIssueStep = (index: number) => {
    if (index >= 0 && index < job.steps.length) setSelectedIndex(index);
  };

  const handleCheck = async () => {
    const steps = job.steps;
    setChecking(true);
    setCheckError(null);
    try {
      const issues = await apiClient.checkDraft(steps, true);
      setCheck({ issues: sortIssues(issues), steps, title: "檢查結果" });
    } catch (e: unknown) {
      setCheckError(e instanceof Error ? e.message : String(e));
    } finally {
      setChecking(false);
    }
  };

  const handleTrace = async () => {
    const sent = job.steps;
    setTracing(true);
    setCheckError(null);
    try {
      const result = await apiClient.traceDraft(sent, job.sampleInput ?? "", job.sampleOutput ?? "");
      // Apply to the latest steps (the user may have kept editing while it ran).
      const steps = applyTraceAnimations(jobRef.current?.steps ?? sent, sent, result.steps);
      update((prev) => ({ ...prev, steps }));
      setCheck({ issues: sortIssues(result.issues), steps, title: "動畫產生結果" });
      setTraceRuns((n) => n + 1);
    } catch (e: unknown) {
      setCheck(null);
      setCheckError(e instanceof Error ? e.message : String(e));
    } finally {
      setTracing(false);
    }
  };

  const issuesStale = check !== null && check.steps !== job.steps;
  const selectedIssues =
    check?.issues.filter((i) => i.stepIndex !== null && i.stepIndex === selectedIndex) ?? [];

  return (
    <div className="min-h-screen flex flex-col">
      <Header
        job={job}
        saving={saving}
        onNameChange={handleNameChange}
        onExport={() => setExportOpen(true)}
        checking={checking}
        onCheck={handleCheck}
      />
      <ExportDialog
        job={job}
        open={exportOpen}
        onClose={() => setExportOpen(false)}
      />

      <div className="flex-1 grid grid-cols-1 lg:grid-cols-[2fr_3fr] gap-0 overflow-hidden">
        <aside className="border-r border-line p-5 overflow-y-auto space-y-6">
          <VideoSettings
            theme={job.theme}
            width={job.width}
            onChange={(patch) => update((prev) => ({ ...prev, ...patch }))}
          />

          <SampleIoPanel
            sampleInput={job.sampleInput ?? ""}
            sampleOutput={job.sampleOutput ?? ""}
            onChange={(patch) => update((prev) => ({ ...prev, ...patch }))}
            hasTrace={job.steps.some((s) => s.trace)}
            tracing={tracing}
            onTrace={handleTrace}
          />

          {(check || checkError) && (
            <CheckResults
              title={check?.title ?? "檢查結果"}
              issues={check?.issues ?? []}
              stale={issuesStale}
              error={checkError}
              onSelectStep={selectIssueStep}
            />
          )}

          <StepList
            steps={job.steps}
            selectedIndex={selectedIndex}
            onSelect={setSelectedIndex}
            onAdd={handleAddStep}
            onDelete={handleDeleteStep}
            onReorder={handleStepReorder}
            issueCounts={issueCounts}
            issuesStale={issuesStale}
          />

          {selectedStep && selectedIndex !== null && (
            <div className="border-t border-line pt-5">
              <h3 className="eyebrow mb-4">Step #{selectedIndex + 1} 編輯</h3>
              {selectedIssues.length > 0 && (
                <div className={`mb-4 rounded-lg border border-line bg-ink-950/40 p-1.5 ${issuesStale ? "opacity-60" : ""}`}>
                  <IssueList issues={selectedIssues} showStep={false} />
                </div>
              )}
              <StepEditor
                key={`${selectedIndex}-${traceRuns}`}
                step={selectedStep}
                onChange={(next) => handleStepChange(selectedIndex, next)}
              />
            </div>
          )}
        </aside>

        <main className="p-5 overflow-y-auto">
          {previewJob ? (
            <RemotionPreview job={previewJob} />
          ) : (
            <div className="aspect-video panel" />
          )}
        </main>
      </div>
    </div>
  );
}

function remapSelectedIndex(
  current: number | null,
  fromIndex: number,
  toIndex: number,
): number | null {
  if (current === null) return null;
  if (current === fromIndex) return toIndex;
  if (fromIndex < toIndex && current > fromIndex && current <= toIndex) {
    return current - 1;
  }
  if (fromIndex > toIndex && current >= toIndex && current < fromIndex) {
    return current + 1;
  }
  return current;
}

function SampleIoPanel({
  sampleInput,
  sampleOutput,
  onChange,
  hasTrace,
  tracing,
  onTrace,
}: {
  sampleInput: string;
  sampleOutput: string;
  onChange: (patch: Partial<Pick<Job, "sampleInput" | "sampleOutput">>) => void;
  hasTrace: boolean;
  tracing: boolean;
  onTrace: () => void;
}) {
  return (
    <details className="rounded-xl border border-line bg-ink-900/60 p-4" open>
      <summary className="flex items-center gap-2 cursor-pointer select-none">
        <TerminalSquare size={13} className="text-faint" strokeWidth={1.8} />
        <span className="eyebrow">範例輸入/輸出</span>
      </summary>
      <div className="space-y-3 pt-3">
        <div className="grid grid-cols-2 gap-3">
          <label className="block">
            <span className="field-label">範例輸入</span>
            <textarea
              value={sampleInput}
              onChange={(e) => onChange({ sampleInput: e.target.value })}
              rows={4}
              className="input resize-y font-mono text-xs leading-relaxed"
              spellCheck={false}
            />
          </label>
          <label className="block">
            <span className="field-label">範例輸出</span>
            <textarea
              value={sampleOutput}
              onChange={(e) => onChange({ sampleOutput: e.target.value })}
              rows={4}
              className="input resize-y font-mono text-xs leading-relaxed"
              spellCheck={false}
            />
          </label>
        </div>
        {/* span carries the tooltip: disabled buttons don't fire hover events */}
        <span title={hasTrace ? "用範例輸入實際執行程式，依各步的追蹤計畫重算動畫" : "沒有任何步驟有追蹤計畫"} className="inline-block">
          <button
            type="button"
            onClick={onTrace}
            disabled={!hasTrace || tracing}
            className="btn btn-ghost px-3 py-2 text-sm"
          >
            {tracing ? <Loader2 size={15} className="animate-spin" /> : <Play size={15} />}
            {tracing ? "產生中" : "重新產生動畫"}
          </button>
        </span>
      </div>
    </details>
  );
}

function CheckResults({
  title,
  issues,
  stale,
  error,
  onSelectStep,
}: {
  title: string;
  issues: DraftIssue[];
  stale: boolean;
  error: string | null;
  onSelectStep: (index: number) => void;
}) {
  const errors = issues.filter((i) => i.level === "error").length;
  return (
    <div className="rounded-lg border border-line bg-ink-950/40 p-3 space-y-2">
      <div className="flex items-center justify-between gap-2">
        <span className="eyebrow">
          {title} · {errors} 錯誤 · {issues.length - errors} 警告
        </span>
        {stale && <span className="text-xs text-faint">已修改，請重新檢查</span>}
      </div>
      {error && <div className="error-banner">{error}</div>}
      {!error && issues.length === 0 && <p className="text-xs text-mist">沒有發現問題。</p>}
      {issues.length > 0 && (
        <div className={`max-h-60 overflow-y-auto ${stale ? "opacity-60" : ""}`}>
          <IssueList issues={issues} onSelectStep={onSelectStep} />
        </div>
      )}
    </div>
  );
}

function Header({
  job,
  saving,
  onNameChange,
  onExport,
  checking,
  onCheck,
}: {
  job: Job;
  saving: boolean;
  onNameChange: (name: string) => void;
  onExport: () => void;
  checking: boolean;
  onCheck: () => void;
}) {
  return (
    <header className="border-b border-line px-4 py-3 flex items-center gap-3 sticky top-0 z-20 bg-ink-950/80 backdrop-blur-md">
      <Link to="/" className="btn btn-quiet shrink-0">
        <ArrowLeft size={15} />
        列表
      </Link>
      <div className="h-5 w-px bg-line shrink-0" />
      <input
        type="text"
        value={job.name}
        onChange={(e) => onNameChange(e.target.value)}
        className="bg-transparent border border-transparent outline-none text-lg font-semibold flex-1 min-w-0 focus:border-line focus:bg-ink-900 rounded-lg px-2 py-1 transition-colors"
      />
      <span className="flex items-center gap-2 shrink-0">
        <span
          className={`size-2 rounded-full transition-colors ${
            saving ? "bg-accent animate-pulse" : "bg-faint"
          }`}
        />
        <span className="meta-mono text-xs">{saving ? "儲存中" : "已儲存"}</span>
      </span>
      <button
        type="button"
        onClick={onCheck}
        disabled={checking || job.steps.length === 0}
        className="btn btn-ghost shrink-0 px-3 py-2 text-sm"
      >
        {checking ? <Loader2 size={15} className="animate-spin" /> : <ListChecks size={15} />}
        {checking ? "檢查中" : "檢查"}
      </button>
      <button
        type="button"
        onClick={onExport}
        disabled={job.steps.length === 0}
        className="btn btn-primary shrink-0 px-3 py-2 text-sm"
      >
        <Film size={15} />
        匯出 MP4
      </button>
    </header>
  );
}
