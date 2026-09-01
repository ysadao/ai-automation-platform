export type User = {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  email_verified_at: string | null;
  created_at: string;
};

export type TokenPair = {
  access_token: string;
  refresh_token: string;
  token_type: string;
  user: User;
  verification_token?: string;
};

export type Session = {
  id: string;
  user_agent: string | null;
  ip: string | null;
  created_at: string;
  expires_at: string;
  revoked_at: string | null;
  current: boolean;
};

export type Task = {
  id: string;
  prompt: string;
  workflow_id?: string | null;
  template_id?: string | null;
  status: string;
  result?: string | null;
  tokens_used?: number;
  created_at: string;
  error?: string | null;
  steps?: { type: string; status?: string }[];
};

export type Template = { id: string; name: string; body: string };
export type Workflow = { id: string; name: string; description?: string; steps: { type: string }[] };
export type Usage = { total_tokens: number; task_count: number };

const ACCESS_KEY = "inkworks.access";
const REFRESH_KEY = "inkworks.refresh";

export function getAccessToken(): string | null {
  return localStorage.getItem(ACCESS_KEY);
}

export function getRefreshToken(): string | null {
  return localStorage.getItem(REFRESH_KEY);
}

export function setTokens(access: string, refresh: string) {
  localStorage.setItem(ACCESS_KEY, access);
  localStorage.setItem(REFRESH_KEY, refresh);
}

export function clearTokens() {
  localStorage.removeItem(ACCESS_KEY);
  localStorage.removeItem(REFRESH_KEY);
}

async function parseError(response: Response): Promise<string> {
  try {
    const body = await response.json();
    if (typeof body.detail === "string") return body.detail;
    if (Array.isArray(body.detail)) return body.detail.map((d: { msg?: string }) => d.msg ?? d).join(", ");
    return body.error ?? response.statusText;
  } catch {
    return response.statusText;
  }
}

async function refreshAccess(): Promise<boolean> {
  const refresh = getRefreshToken();
  if (!refresh) return false;
  const response = await fetch("/api/auth/refresh", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ refresh_token: refresh }),
  });
  if (!response.ok) {
    clearTokens();
    return false;
  }
  const body = (await response.json()) as TokenPair;
  setTokens(body.access_token, body.refresh_token);
  return true;
}

const PUBLIC_PATHS = new Set([
  "/health",
  "/auth/register",
  "/auth/login",
  "/auth/refresh",
  "/auth/verify-email",
  "/auth/forgot-password",
  "/auth/reset-password",
]);

async function request<T>(path: string, init?: RequestInit, retry = true): Promise<T> {
  const access = PUBLIC_PATHS.has(path) ? null : getAccessToken();
  const response = await fetch(`/api${path}`, {
    ...init,
    headers: {
      "content-type": "application/json",
      ...(access ? { authorization: `Bearer ${access}` } : {}),
      ...(init?.headers ?? {}),
    },
  });
  if (response.status === 401 && retry && access && getRefreshToken()) {
    const ok = await refreshAccess();
    if (ok) return request<T>(path, init, false);
  }
  if (response.status === 204) return undefined as T;
  if (!response.ok) {
    throw new Error(await parseError(response));
  }
  return (await response.json()) as T;
}

export const api = {
  health: () => request<{ ok: boolean; provider: string }>("/health"),
  register: (payload: { email: string; password: string; first_name?: string; last_name?: string }) =>
    request<TokenPair>("/auth/register", { method: "POST", body: JSON.stringify(payload) }),
  login: (payload: { email: string; password: string }) =>
    request<TokenPair>("/auth/login", { method: "POST", body: JSON.stringify(payload) }),
  logout: (refresh_token?: string) =>
    request<{ ok: boolean }>("/auth/logout", { method: "POST", body: JSON.stringify({ refresh_token }) }),
  logoutAll: () => request<{ ok: boolean }>("/auth/logout-all", { method: "POST" }),
  verifyEmail: (token: string) =>
    request<{ ok: boolean; user: User }>("/auth/verify-email", {
      method: "POST",
      body: JSON.stringify({ token }),
    }),
  forgotPassword: (email: string) =>
    request<{ ok: boolean; reset_token?: string }>("/auth/forgot-password", {
      method: "POST",
      body: JSON.stringify({ email }),
    }),
  resetPassword: (token: string, password: string) =>
    request<{ ok: boolean }>("/auth/reset-password", {
      method: "POST",
      body: JSON.stringify({ token, password }),
    }),
  me: () => request<User>("/me"),
  sessions: () => request<{ items: Session[] }>("/me/sessions"),
  revokeSession: (id: string) => request<void>(`/me/sessions/${id}`, { method: "DELETE" }),
  tasks: () => request<{ items: Task[] }>("/tasks"),
  createTask: (payload: { prompt: string; workflow_id?: string; template_id?: string }) =>
    request<Task>("/tasks", { method: "POST", body: JSON.stringify(payload) }),
  task: (id: string) => request<Task>(`/tasks/${id}`),
  templates: () => request<{ items: Template[] }>("/templates"),
  createTemplate: (payload: { name: string; body: string }) =>
    request<Template>("/templates", { method: "POST", body: JSON.stringify(payload) }),
  updateTemplate: (id: string, payload: { name?: string; body?: string }) =>
    request<Template>(`/templates/${id}`, { method: "PUT", body: JSON.stringify(payload) }),
  deleteTemplate: (id: string) => request<void>(`/templates/${id}`, { method: "DELETE" }),
  workflows: () => request<{ items: Workflow[] }>("/workflows"),
  usage: () => request<Usage>("/usage"),
};
