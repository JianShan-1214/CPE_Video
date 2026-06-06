import type { Job } from "./draft-types";
import { clearToken, getToken } from "./auth.ts";

export type JobSummary = Pick<Job, "id" | "name" | "createdAt" | "updatedAt" | "steps">;

export type CreateJobInput = {
  name?: string;
};

export type ImportJobInput = {
  name?: string;
  configJson: string;
  cppFiles: Record<string, string>;
};

export type GenerateDraftInput = {
  name?: string;
  problemStatement: string;
  solutionCode: string;
};

export type RenderJob = {
  id: string;
  jobId?: string;
  status: "queued" | "running" | "succeeded" | "failed";
  progress?: number | null;
  error?: string | null;
  outputFilename?: string | null;
  createdAt?: number;
  updatedAt?: number;
};

export type CreateRenderJobInput = {
  jobId: string;
  folderName?: string;
};

export type AuthStatus = {
  authRequired: boolean;
};

type FetchLike = typeof fetch;

type ApiClientOptions = {
  baseUrl?: string;
  fetchImpl?: FetchLike;
};

// Called when a protected request comes back 401. Defaults to clearing the
// stored token and bouncing to the login page; overridable for tests.
let unauthorizedHandler: () => void = () => {
  clearToken();
  if (typeof window !== "undefined" && window.location.pathname !== "/login") {
    window.location.assign("/login");
  }
};

export function setUnauthorizedHandler(handler: () => void): void {
  unauthorizedHandler = handler;
}

function defaultBaseUrl(): string {
  const meta = import.meta as ImportMeta & {
    env?: { VITE_API_BASE_URL?: string };
  };
  // Default to same-origin relative URLs: the backend serves the built web app
  // in production, and the Vite dev server proxies /api + /health in dev.
  return meta.env?.VITE_API_BASE_URL ?? "";
}

function joinUrl(baseUrl: string, path: string): string {
  return `${baseUrl.replace(/\/+$/, "")}${path}`;
}

export class ApiClient {
  private readonly baseUrl: string;
  private readonly fetchImpl: FetchLike;

  constructor(options: ApiClientOptions = {}) {
    this.baseUrl = options.baseUrl ?? defaultBaseUrl();
    this.fetchImpl = options.fetchImpl ?? ((input, init) => fetch(input, init));
  }

  authStatus(): Promise<AuthStatus> {
    return this.requestJson("/api/auth/status", {}, { skipAuthRedirect: true });
  }

  async login(password: string): Promise<string> {
    const response = await this.fetchImpl(joinUrl(this.baseUrl, "/api/login"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ password }),
    });
    await assertOk(response, "登入失敗");
    const body = (await response.json()) as { token: string };
    return body.token;
  }

  listJobs(): Promise<JobSummary[]> {
    return this.requestJson("/api/jobs");
  }

  createJob(input: CreateJobInput): Promise<Job> {
    return this.requestJson("/api/jobs", {
      method: "POST",
      body: JSON.stringify(input),
    });
  }

  getJob(id: string): Promise<Job> {
    return this.requestJson(`/api/jobs/${encodeURIComponent(id)}`);
  }

  updateJob(id: string, job: Job): Promise<Job> {
    return this.requestJson(`/api/jobs/${encodeURIComponent(id)}`, {
      method: "PUT",
      body: JSON.stringify({
        name: job.name,
        theme: job.theme,
        width: job.width,
        steps: job.steps,
      }),
    });
  }

  deleteJob(id: string): Promise<void> {
    return this.requestVoid(`/api/jobs/${encodeURIComponent(id)}`, {
      method: "DELETE",
    });
  }

  importJob(input: ImportJobInput): Promise<Job> {
    return this.requestJson("/api/jobs/import", {
      method: "POST",
      body: JSON.stringify(input),
    });
  }

  generateDraft(input: GenerateDraftInput): Promise<Job> {
    return this.requestJson("/api/generate-draft", {
      method: "POST",
      body: JSON.stringify(input),
    });
  }

  createRenderJob(input: CreateRenderJobInput): Promise<RenderJob> {
    return this.requestJson("/api/render-jobs", {
      method: "POST",
      body: JSON.stringify(input),
    });
  }

  getRenderJob(id: string): Promise<RenderJob> {
    return this.requestJson(`/api/render-jobs/${encodeURIComponent(id)}`);
  }

  async downloadRenderJob(id: string): Promise<Blob> {
    const response = await this.fetchImpl(
      joinUrl(this.baseUrl, `/api/render-jobs/${encodeURIComponent(id)}/download`),
      { headers: authHeaders() },
    );
    this.handleUnauthorized(response);
    await assertOk(response, "MP4 download failed");
    return response.blob();
  }

  private async requestJson<T>(
    path: string,
    init: RequestInit = {},
    options: { skipAuthRedirect?: boolean } = {},
  ): Promise<T> {
    const response = await this.fetchImpl(joinUrl(this.baseUrl, path), {
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...authHeaders(),
        ...init.headers,
      },
    });
    if (!options.skipAuthRedirect) this.handleUnauthorized(response);
    await assertOk(response, "API request failed");
    return (await response.json()) as T;
  }

  private async requestVoid(path: string, init: RequestInit): Promise<void> {
    const response = await this.fetchImpl(joinUrl(this.baseUrl, path), {
      ...init,
      headers: { ...authHeaders(), ...init.headers },
    });
    this.handleUnauthorized(response);
    await assertOk(response, "API request failed");
  }

  private handleUnauthorized(response: Response): void {
    if (response.status === 401) unauthorizedHandler();
  }
}

function authHeaders(): Record<string, string> {
  const token = getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function assertOk(response: Response, fallback: string): Promise<void> {
  if (response.ok) return;
  let message = `${fallback} (${response.status})`;
  try {
    const body = (await response.json()) as {
      detail?: string;
      error?: string;
    };
    message = body.detail ?? body.error ?? message;
  } catch {
    // Keep fallback for non-JSON responses.
  }
  throw new Error(message);
}

export const apiClient = new ApiClient();
