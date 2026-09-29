import { AlertTriangle, CircleX, Sparkles } from "lucide-react";
import type { DraftIssue } from "@/lib/api-client";
import type { IssueCount } from "@/lib/draft-issues";
import { cn } from "@/lib/utils";

/** Issue rows; clicking one with a step selects that step. */
export function IssueList({
  issues,
  onSelectStep,
  showStep = true,
}: {
  issues: DraftIssue[];
  onSelectStep?: (index: number) => void;
  showStep?: boolean;
}) {
  return (
    <ul className="space-y-1">
      {issues.map((issue, i) => {
        const clickable = onSelectStep && issue.stepIndex !== null;
        return (
          <li key={i}>
            <button
              type="button"
              disabled={!clickable}
              onClick={() => clickable && onSelectStep(issue.stepIndex!)}
              className={cn(
                "w-full flex items-start gap-2 rounded-lg px-2 py-1.5 text-left text-xs",
                clickable ? "hover:bg-ink-850 cursor-pointer" : "cursor-default",
              )}
            >
              {issue.level === "error" ? (
                <CircleX size={14} className="mt-px shrink-0 text-danger" />
              ) : (
                <AlertTriangle size={14} className="mt-px shrink-0 text-warn" />
              )}
              {showStep && (
                <span className="meta-mono w-8 shrink-0 text-faint">
                  {issue.stepIndex === null ? "全體" : `#${String(issue.stepIndex + 1).padStart(2, "0")}`}
                </span>
              )}
              <span className="flex-1 text-mist">{issue.message}</span>
              {issue.source === "ai" && (
                <Sparkles size={12} className="mt-0.5 shrink-0 text-faint" aria-label="AI 審稿" />
              )}
            </button>
          </li>
        );
      })}
    </ul>
  );
}

export function IssueBadges({ count, stale }: { count: IssueCount; stale?: boolean }) {
  const pill = (n: number, className: string, title: string) =>
    n > 0 && (
      <span
        className={cn("meta-mono shrink-0 rounded-full px-1.5 text-[11px] leading-5", className, stale && "opacity-50")}
        title={title}
      >
        {n}
      </span>
    );
  return (
    <>
      {pill(count.errors, "bg-danger-soft text-danger", `${count.errors} 個錯誤`)}
      {pill(count.warnings, "bg-warn-soft text-warn", `${count.warnings} 個警告`)}
    </>
  );
}
