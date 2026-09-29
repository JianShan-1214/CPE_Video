import type { DraftIssue } from "./api-client.ts";

export type IssueCount = { errors: number; warnings: number };

/** Draft-level issues first, then by step; errors before warnings within a step. */
export function sortIssues(issues: DraftIssue[]): DraftIssue[] {
  const key = (i: DraftIssue) => (i.stepIndex ?? -1) * 2 + (i.level === "error" ? 0 : 1);
  return [...issues].sort((a, b) => key(a) - key(b));
}

export function countByStep(issues: DraftIssue[]): Map<number, IssueCount> {
  const counts = new Map<number, IssueCount>();
  for (const issue of issues) {
    if (issue.stepIndex === null) continue;
    const count = counts.get(issue.stepIndex) ?? { errors: 0, warnings: 0 };
    if (issue.level === "error") count.errors += 1;
    else count.warnings += 1;
    counts.set(issue.stepIndex, count);
  }
  return counts;
}
