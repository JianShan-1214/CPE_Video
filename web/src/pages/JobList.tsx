import { Clapperboard, LogOut, Plus, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { apiClient } from "@/lib/api-client";
import { clearToken, getToken } from "@/lib/auth";
import type { Job } from "@/lib/draft-types";

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
  const [jobs, setJobs] = useState<Job[]>([]);
  const navigate = useNavigate();
  const loggedIn = getToken() !== null;

  const refresh = () => {
    void apiClient.listJobs().then((next) => setJobs(next as Job[]));
  };

  const handleLogout = () => {
    clearToken();
    navigate("/login", { replace: true });
  };

  useEffect(() => {
    refresh();
  }, []);

  const handleDelete = (id: string, name: string) => {
    if (!confirm(`確定刪除「${name}」？此操作無法復原。`)) return;
    void apiClient.deleteJob(id).then(refresh);
  };

  return (
    <div className="min-h-screen px-6 py-10 sm:px-10">
      <div className="max-w-5xl mx-auto">
        <header className="reveal mb-10 flex items-end justify-between gap-4">
          <div>
            <div className="flex items-center gap-2.5 mb-3">
              <span className="size-2.5 rounded-sm bg-accent shadow-[0_0_12px_var(--color-accent)]" />
              <span className="eyebrow">CPE Video Studio</span>
            </div>
            <h1 className="text-4xl font-bold tracking-tight">你的影片</h1>
            <p className="meta-mono text-sm mt-2">
              {jobs.length === 0 ? "尚無專案" : `${jobs.length} 個專案`}
            </p>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            {loggedIn && (
              <button type="button" onClick={handleLogout} className="btn btn-quiet">
                <LogOut size={15} />
                登出
              </button>
            )}
            <Link to="/new" className="btn btn-primary">
              <Plus size={16} />
              新增 Job
            </Link>
          </div>
        </header>

        <main>
          {jobs.length === 0 ? (
            <div className="reveal card flex flex-col items-center justify-center text-center py-20 px-6 border-dashed">
              <Clapperboard className="text-faint mb-4" size={40} strokeWidth={1.4} />
              <p className="text-mist">
                還沒有專案。點右上角{" "}
                <span className="text-accent font-medium">新增 Job</span> 建立第一支影片。
              </p>
            </div>
          ) : (
            <ul className="stagger space-y-3">
              {jobs.map((job, i) => (
                <li
                  key={job.id}
                  className="card card-interactive group flex items-center gap-4 p-4"
                >
                  <Link
                    to={`/jobs/${job.id}/edit`}
                    className="flex flex-1 items-center gap-4 min-w-0"
                  >
                    <span className="grid size-11 shrink-0 place-items-center rounded-lg bg-ink-850 border border-line text-faint transition-colors group-hover:text-accent group-hover:border-line-strong">
                      <Clapperboard size={20} strokeWidth={1.6} />
                    </span>
                    <span className="min-w-0">
                      <span className="block font-semibold truncate transition-colors group-hover:text-accent">
                        {job.name}
                      </span>
                      <span className="meta-mono text-xs mt-1 block truncate">
                        <span className="text-mist">{String(i + 1).padStart(2, "0")}</span>
                        {"  ·  "}
                        {job.steps.length} 步 · 更新 {formatDate(job.updatedAt)}
                      </span>
                    </span>
                  </Link>
                  <button
                    type="button"
                    onClick={() => handleDelete(job.id, job.name)}
                    className="text-faint hover:text-danger p-2 rounded-lg transition-colors"
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
