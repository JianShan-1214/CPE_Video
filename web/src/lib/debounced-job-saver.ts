import type { Job } from "./draft-types";

export type DebouncedJobSaverOptions = {
  delayMs: number;
  save: (job: Job) => void;
  setSaving: (saving: boolean) => void;
};

export function createDebouncedJobSaver({
  delayMs,
  save,
  setSaving,
}: DebouncedJobSaverOptions) {
  let timeout: ReturnType<typeof setTimeout> | null = null;
  let pending: Job | null = null;

  const clearPendingTimeout = () => {
    if (timeout) {
      clearTimeout(timeout);
      timeout = null;
    }
  };

  const commit = () => {
    if (!pending) return;
    save(pending);
    pending = null;
    timeout = null;
    setSaving(false);
  };

  return {
    schedule(job: Job) {
      clearPendingTimeout();
      pending = job;
      setSaving(true);
      timeout = setTimeout(commit, delayMs);
    },
    flush() {
      clearPendingTimeout();
      commit();
    },
  };
}
