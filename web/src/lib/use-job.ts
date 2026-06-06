import { useCallback, useEffect, useRef, useState } from "react";
import { apiClient } from "./api-client";
import type { Job } from "./draft-types";
import { createDebouncedJobSaver } from "./debounced-job-saver";

export type JobUpdater = (prev: Job) => Job;

const SAVE_DEBOUNCE_MS = 300;

export function useJob(id: string | undefined) {
  const [job, setJobState] = useState<Job | null>(null);
  const [saving, setSaving] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const saverRef = useRef(
    createDebouncedJobSaver({
      delayMs: SAVE_DEBOUNCE_MS,
      save: (job) => {
        void apiClient.updateJob(job.id, job);
      },
      setSaving,
    }),
  );

  useEffect(() => {
    saverRef.current.flush();
    let cancelled = false;
    setLoaded(false);
    if (!id) {
      setJobState(null);
      setLoaded(true);
      return () => {
        cancelled = true;
      };
    }
    apiClient
      .getJob(id)
      .then((loadedJob) => {
        if (!cancelled) setJobState(loadedJob);
      })
      .catch(() => {
        if (!cancelled) setJobState(null);
      })
      .finally(() => {
        if (!cancelled) setLoaded(true);
      });
    return () => {
      cancelled = true;
    };
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
