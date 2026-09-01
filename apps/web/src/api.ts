export type Task = {
  id: string;
  prompt: string;
  workflowId?: string | null;
  templateId?: string | null;
  status: string;
  result?: string | null;
  tokensUsed?: number;
  createdAt: string;
  error?: string | null;
};

export type Template = { id: string; name: string; body: string };
export type Workflow = { id: string; name: string; description?: string; steps: { type: string }[] };
export type Usage = { totalTokens: number; taskCount: number };

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`, {
    ...init,
    headers: {
      "content-type": "application/json",
      ...(init?.headers ?? {}),
    },
  });
  if (response.status === 204) return undefined as T;
  const body = await response.json();
  if (!response.ok) {
    throw new Error(body.detail ?? body.error ?? response.statusText);
  }
  return body as T;
}

export const api = {
  health: () => request<{ ok: boolean; provider: string }>("/health"),
  tasks: () => request<{ items: Task[] }>("/tasks"),
  createTask: (payload: { prompt: string; workflowId?: string; templateId?: string }) =>
    request<Task>("/tasks", { method: "POST", body: JSON.stringify(payload) }),
  task: (id: string) => request<Task>(`/tasks/${id}`),
  templates: () => request<{ items: Template[] }>("/templates"),
  workflows: () => request<{ items: Workflow[] }>("/workflows"),
  usage: () => request<Usage>("/usage"),
};
