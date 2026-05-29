import type { Job } from "./draft-types";

const JOB_KEY_PREFIX = "cpe-video:job:";
const JOBS_INDEX_KEY = "cpe-video:jobs-index";

function readIndex(): string[] {
  const raw = localStorage.getItem(JOBS_INDEX_KEY);
  if (!raw) return [];
  try {
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function writeIndex(ids: string[]): void {
  localStorage.setItem(JOBS_INDEX_KEY, JSON.stringify(ids));
}

export function getJob(id: string): Job | null {
  const raw = localStorage.getItem(JOB_KEY_PREFIX + id);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as Job;
  } catch {
    return null;
  }
}

export function listJobs(): Job[] {
  const ids = readIndex();
  return ids
    .map((id) => getJob(id))
    .filter((j): j is Job => j !== null)
    .sort((a, b) => b.updatedAt - a.updatedAt);
}

export function saveJob(job: Job): void {
  const updated: Job = { ...job, updatedAt: Date.now() };
  localStorage.setItem(JOB_KEY_PREFIX + job.id, JSON.stringify(updated));
  const ids = readIndex();
  if (!ids.includes(job.id)) {
    writeIndex([...ids, job.id]);
  }
}

export function deleteJob(id: string): void {
  localStorage.removeItem(JOB_KEY_PREFIX + id);
  writeIndex(readIndex().filter((i) => i !== id));
}

export function createEmptyJob(name = "Untitled Job"): Job {
  const now = Date.now();
  return {
    id: crypto.randomUUID(),
    name,
    createdAt: now,
    updatedAt: now,
    theme: "github-dark",
    width: { type: "fixed", value: 1920 },
    steps: [],
  };
}
