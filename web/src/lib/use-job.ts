import { useCallback, useEffect, useRef, useState } from "react";
import type { Job } from "./draft-types";
import { createDebouncedJobSaver } from "./debounced-job-saver";
import { getJob, saveJob } from "./storage";

export type JobUpdater = (prev: Job) => Job;

const SAVE_DEBOUNCE_MS = 300;

export function useJob(id: string | undefined) {
  const [job, setJobState] = useState<Job | null>(null);
  const [saving, setSaving] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const saverRef = useRef(
    createDebouncedJobSaver({
      delayMs: SAVE_DEBOUNCE_MS,
      save: saveJob,
      setSaving,
    }),
  );

  useEffect(() => {
    saverRef.current.flush();
    if (!id) {
      setJobState(null);
      setLoaded(true);
      return;
    }
    setJobState(getJob(id));
    setLoaded(true);
  }, [id]);

  useEffect(() => {
    return () => saverRef.current.flush();
  }, []);

  const update = useCallback((updater: JobUpdater) => {
    setJobState((prev) => {
      if (!prev) return prev;
      const next = updater(prev);
      saverRef.current.schedule(next);
      return next;
    });
  }, []);

  return { job, update, saving, loaded };
}

export function useDebouncedValue<T>(value: T, delayMs: number): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setDebounced(value), delayMs);
    return () => clearTimeout(t);
  }, [value, delayMs]);
  return debounced;
}
