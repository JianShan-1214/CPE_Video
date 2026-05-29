import { Trash2 } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import type { Job } from "@/lib/draft-types";
import { deleteJob, listJobs } from "@/lib/storage";

function formatDate(ms: number): string {
  return new Date(ms).toLocaleString("zh-Hant", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function JobList() {
  const [jobs, setJobs] = useState<Job[]>(() => listJobs());

  const refresh = () => setJobs(listJobs());

  const handleDelete = (id: string, name: string) => {
    if (!confirm(`確定刪除「${name}」？此操作無法復原。`)) return;
    deleteJob(id);
    refresh();
  };

  return (
    <div className="min-h-screen bg-neutral-950 text-neutral-100 p-8">
      <div className="max-w-5xl mx-auto">
        <header className="mb-8 flex items-end justify-between">
          <div>
            <h1 className="text-3xl font-semibold">CPE Video Editor</h1>
            <p className="text-neutral-400 mt-1">
              {jobs.length === 0 ? "尚無 job" : `共 ${jobs.length} 個 job`}
            </p>
          </div>
          <Link
            to="/new"
            className="bg-blue-600 hover:bg-blue-500 text-white px-4 py-2 rounded transition-colors"
          >
            + 新增 Job
          </Link>
        </header>

        <main>
          {jobs.length === 0 ? (
            <div className="rounded-lg border border-dashed border-neutral-800 p-12 text-center text-neutral-500">
              還沒有 job，點右上角「+ 新增 Job」建立第一個。
            </div>
          ) : (
            <ul className="space-y-2">
              {jobs.map((job) => (
                <li
                  key={job.id}
                  className="bg-neutral-900 rounded-lg p-4 flex items-center justify-between hover:bg-neutral-800 transition-colors"
                >
                  <Link
                    to={`/jobs/${job.id}/edit`}
                    className="flex-1 group"
                  >
                    <div className="font-medium group-hover:text-blue-400">
                      {job.name}
                    </div>
                    <div className="text-xs text-neutral-500 mt-1">
                      {job.steps.length} 步 · 更新於 {formatDate(job.updatedAt)}
                    </div>
                  </Link>
                  <button
                    type="button"
                    onClick={() => handleDelete(job.id, job.name)}
                    className="text-neutral-500 hover:text-red-400 p-2 rounded transition-colors"
                    aria-label="刪除"
                  >
                    <Trash2 size={18} />
                  </button>
                </li>
              ))}
            </ul>
          )}
        </main>
      </div>
    </div>
  );
}
