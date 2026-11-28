// The only module that talks to the City server. Same endpoints and payloads as the original interface.
import type { ChatEvent, ChatMessage, Snapshot, Task } from "./types";

const POST_HEADERS = { "Content-Type": "application/json", "X-MarketDesk-City": "1" };

export async function api<T>(path: string, payload?: object): Promise<T> {
  const response = await fetch(path, {
    credentials: "same-origin", cache: "no-store",
    method: payload ? "POST" : "GET",
    headers: payload ? POST_HEADERS : undefined,
    body: payload ? JSON.stringify(payload) : undefined,
  });
  let data: Record<string, unknown> = {};
  try { data = await response.json() as Record<string, unknown>; } catch { /* readable fallback below */ }
  if (response.status === 401) throw new Error("Session expirée : reconnecte-toi à MarketDesk City.");
  if (!response.ok) throw new Error(String(data.detail || `Erreur HTTP ${response.status}`));
  return data as T;
}

export async function loadSnapshot(): Promise<Snapshot> {
  const next = await api<Snapshot>("/city/api/state");
  // Shared coding missions are merged exactly as the original interface does.
  return { ...next,
    tasks: [...next.tasks, ...(next.shared_coding_tasks || [])].sort((a, b) => b.created_at.localeCompare(a.created_at)),
    events: [...next.events, ...(next.shared_coding_events || [])].sort((a, b) => b.id - a.id) };
}

export const actions = {
  approve: (taskId: string) => api(`/city/api/tasks/${taskId}/approve`, {}),
  cancel: (taskId: string) => api(`/city/api/tasks/${taskId}/cancel`, {}),
  retry: (taskId: string) => api<{ task: { id: string } }>(`/city/api/tasks/${taskId}/retry`, {}),
  approveWorkflow: (workflowId: string) => api(`/city/api/workflows/${workflowId}/approve`, {}),
  cancelWorkflow: (workflowId: string) => api(`/city/api/workflows/${workflowId}/cancel`, {}),
  reviewProposal: (taskId: string, approved: boolean) => api(`/city/api/proposals/${taskId}/review`, { approved }),
  taskDetail: (taskId: string) => api<Task>(`/city/api/tasks/${taskId}`),
  chatHistory: () => api<{ messages: ChatMessage[] }>("/city/api/chat/desk_manager"),
  briefing: () => api<{ content: string }>("/city/api/manager/briefing", {}),
};

// Streams one Desk Manager reply. Resolves when the server closes the stream.
export async function streamChat(message: string, intent: string | undefined, signal: AbortSignal,
  onEvent: (event: ChatEvent) => void): Promise<void> {
  const response = await fetch("/city/api/chat/desk_manager", { method: "POST", credentials: "same-origin", signal,
    headers: POST_HEADERS, body: JSON.stringify({ message, selection: intent ? { intent } : undefined }) });
  if (!response.ok) {
    const data = await response.json().catch(() => ({})) as { detail?: string };
    throw new Error(data.detail || `Erreur HTTP ${response.status}`);
  }
  if (!response.body) throw new Error("Le flux de réponse est indisponible dans ce navigateur.");
  const reader = response.body.getReader(), decoder = new TextDecoder();
  let buffer = "";
  const handle = (frame: string) => {
    for (const line of frame.split("\n")) {
      if (!line.startsWith("data: ")) continue;
      try { onEvent(JSON.parse(line.slice(6)) as ChatEvent); } catch { /* incomplete frame */ }
    }
  };
  for (;;) {
    const part = await reader.read();
    buffer += decoder.decode(part.value || new Uint8Array(), { stream: !part.done });
    const frames = buffer.split("\n\n"); buffer = frames.pop() || ""; frames.forEach(handle);
    if (part.done) break;
  }
  if (buffer.trim()) handle(buffer);
}
