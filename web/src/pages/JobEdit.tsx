import { ArrowLeft, Film } from "lucide-react";
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
    <div className="min-h-screen flex flex-col">
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
        <aside className="border-r border-line p-5 overflow-y-auto space-y-6">
          <StepList
            steps={job.steps}
            selectedIndex={selectedIndex}
            onSelect={setSelectedIndex}
            onAdd={handleAddStep}
            onDelete={handleDeleteStep}
            onReorder={handleStepReorder}
          />

          {selectedStep && selectedIndex !== null && (
            <div className="border-t border-line pt-5">
              <h3 className="eyebrow mb-4">Step #{selectedIndex + 1} 編輯</h3>
              <StepEditor
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
