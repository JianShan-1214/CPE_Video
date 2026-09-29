import { Lock } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { apiClient } from "@/lib/api-client";
import { setToken } from "@/lib/auth";

export function Login() {
  const navigate = useNavigate();
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const token = await apiClient.login(password);
      setToken(token);
      navigate("/", { replace: true });
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-6">
      <form
        onSubmit={handleSubmit}
        className="reveal panel w-full max-w-sm p-8"
      >
        <div className="flex items-center gap-2.5 mb-7">
          <span className="size-2.5 rounded-sm bg-accent shadow-[0_0_12px_var(--color-accent)]" />
          <span className="eyebrow">CPE Video Studio</span>
        </div>

        <h1 className="text-2xl font-bold tracking-tight">歡迎回來</h1>
        <p className="text-sm text-mist mt-1.5 mb-6">輸入存取密碼以進入工作室。</p>

        <label className="block">
          <span className="field-label">密碼</span>
          <div className="relative">
            <Lock
              className="absolute left-3 top-1/2 -translate-y-1/2 text-faint"
              size={16}
            />
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoFocus
              className="input pl-9"
              placeholder="••••••••"
            />
          </div>
        </label>

        {error && <div className="error-banner mt-4">{error}</div>}

        <button
          type="submit"
          disabled={submitting}
          className="btn btn-primary w-full mt-6"
        >
          {submitting ? "登入中…" : "進入工作室"}
        </button>
      </form>
    </div>
  );
}
