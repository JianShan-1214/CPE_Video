import { useEffect, useState } from "react";
import { Navigate, Outlet, Route, Routes } from "react-router-dom";
import { apiClient } from "@/lib/api-client";
import { getToken } from "@/lib/auth";
import { GenerateJob } from "@/pages/GenerateJob";
import { ImportJob } from "@/pages/ImportJob";
import { JobEdit } from "@/pages/JobEdit";
import { JobList } from "@/pages/JobList";
import { Login } from "@/pages/Login";
import { NewJob } from "@/pages/NewJob";

function RequireAuth() {
  const [state, setState] = useState<"checking" | "ok" | "redirect">("checking");

  useEffect(() => {
    let cancelled = false;
    apiClient
      .authStatus()
      .then(({ authRequired }) => {
        if (cancelled) return;
        setState(!authRequired || getToken() ? "ok" : "redirect");
      })
      .catch(() => {
        // If the status check itself fails, let the pages surface the error.
        if (!cancelled) setState("ok");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (state === "checking") {
    return (
      <div className="min-h-screen flex items-center justify-center text-mist">
        載入中…
      </div>
    );
  }
  if (state === "redirect") return <Navigate to="/login" replace />;
  return <Outlet />;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route element={<RequireAuth />}>
        <Route path="/" element={<JobList />} />
        <Route path="/new" element={<NewJob />} />
        <Route path="/new/generate" element={<GenerateJob />} />
        <Route path="/new/import" element={<ImportJob />} />
        <Route path="/jobs/:id/edit" element={<JobEdit />} />
      </Route>
    </Routes>
  );
}
