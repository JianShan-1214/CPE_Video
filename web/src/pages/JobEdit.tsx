import { useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ExportDialog } from "@/components/ExportDialog";
import { RemotionPreview } from "@/components/RemotionPreview";
import { StepEditor } from "@/components/StepEditor";
import { StepList } from "@/components/StepList";
import type { DraftStep, Job } from "@/lib/draft-types";
import { reorderSteps } from "@/lib/step-order";
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

  const previewJob = useDebouncedValue(job, 300);

  const selectedStep = useMemo(() => {
    if (!job || selectedIndex === null) return null;
    return job.steps[selectedIndex] ?? null;
  }, [job, selectedIndex]);

  if (!loaded) return null;
  if (!job) {
    return (
      <div className="min-h-screen bg-neutral-950 text-neutral-100 p-8">
        <p>找不到 job（id: {id}）。</p>
        <Link to="/" className="text-blue-400 hover:underline">
          ← 返回列表
        </Link>
      </div>
    );
  }

  const handleAddStep = () => {
    update((prev) => {
      const newStep = makeEmptyStep(prev.steps.length);
      return { ...prev, steps: [...prev.steps, newStep] };
    });
    setSelectedIndex(job.steps.length);
  };

  const handleDeleteStep = (idx: number) => {
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
    update((prev) => ({
      ...prev,
      steps: reorderSteps(prev.steps, fromIndex, toIndex),
    }));
    setSelectedIndex((cur) => remapSelectedIndex(cur, fromIndex, toIndex));
  };

  const handleNameChange = (name: string) => {
    update((prev) => ({ ...prev, name }));
  };

  return (
    <div className="min-h-screen bg-neutral-950 text-neutral-100 flex flex-col">
      <Header
        job={job}
        saving={saving}
        onNameChange={handleNameChange}
        onExport={() => setExportOpen(true)}
      />
      <ExportDialog
        job={job}
        open={exportOpen}
        onClose={() => setExportOpen(false)}
      />

      <div className="flex-1 grid grid-cols-1 lg:grid-cols-[2fr_3fr] gap-0 overflow-hidden">
        <aside className="border-r border-neutral-900 p-4 overflow-y-auto space-y-6">
          <StepList
            steps={job.steps}
            selectedIndex={selectedIndex}
            onSelect={setSelectedIndex}
            onAdd={handleAddStep}
            onDelete={handleDeleteStep}
            onReorder={handleStepReorder}
          />

          {selectedStep && selectedIndex !== null && (
            <div className="border-t border-neutral-900 pt-4">
              <h3 className="text-sm font-semibold uppercase tracking-wider text-neutral-400 mb-3">
                Step #{selectedIndex + 1} 編輯
              </h3>
              <StepEditor
                step={selectedStep}
                onChange={(next) => handleStepChange(selectedIndex, next)}
              />
            </div>
          )}
        </aside>

        <main className="p-4 overflow-y-auto">
          {previewJob ? (
            <RemotionPreview job={previewJob} />
          ) : (
            <div className="aspect-video bg-neutral-900 rounded" />
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

function Header({
  job,
  saving,
  onNameChange,
  onExport,
}: {
  job: Job;
  saving: boolean;
  onNameChange: (name: string) => void;
  onExport: () => void;
}) {
  return (
    <header className="border-b border-neutral-900 p-3 flex items-center gap-4">
      <Link
        to="/"
        className="text-neutral-400 hover:text-neutral-200 text-sm shrink-0"
      >
        ← 列表
      </Link>
      <input
        type="text"
        value={job.name}
        onChange={(e) => onNameChange(e.target.value)}
        className="bg-transparent border-none outline-none text-lg font-semibold flex-1 focus:bg-neutral-900 rounded px-2 py-1"
      />
      <span className="text-xs text-neutral-500 shrink-0">
        {saving ? "儲存中…" : "已儲存"}
      </span>
      <button
        type="button"
        onClick={onExport}
        disabled={job.steps.length === 0}
        className="bg-blue-600 hover:bg-blue-500 disabled:bg-neutral-800 disabled:text-neutral-500 disabled:cursor-not-allowed text-white px-3 py-1.5 rounded text-sm transition-colors"
      >
        匯出 MP4
      </button>
    </header>
  );
}
