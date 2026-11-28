// Shapes returned by /city/api/*. No rendering or UI code may live in src/client.
export type AgentStatus = "idle" | "queued" | "running" | "waiting_approval" | "completed" | "failed" | "cancelled";

export type Offer = { title: string; company: string; location: string; url: string; kind?: string; start_period?: string;
  published?: string; published_inferred?: boolean; source?: string };
export type MarketReading = { series_id: string; label: string; value: number; unit: string; observed_at: string;
  change?: number | null; change_display?: string; source_url?: string };

export type TaskResult = { title?: string; text?: string; summary?: string; plain_summary?: string; market_points?: number;
  question?: string; answer?: string; subject?: string; body?: string; followup?: string;
  new_count?: number; total_count?: number; as_of?: string; market_data?: MarketReading[];
  offers?: Offer[]; contacts?: { id: string; name: string; role: string; company: string; verification: string; linkedin_url: string }[];
  approval_required?: boolean; branch?: string; role_version?: number; review_decision?: string; revision?: string;
  files?: string[]; diff?: string; integrated?: boolean; commit?: string; limitations?: string; server_checks?: string[];
  errors?: { source: string; status: string; error: string }[] };

export type Task = {
  id: string; agent_id: string; task_type: string; description: string; status: AgentStatus;
  created_at: string; started_at?: string; finished_at?: string; result: TaskResult;
  error?: string; xp_awarded: number; workflow_id?: string; priority?: number;
  retry_count?: number; max_retries?: number; depends_on?: string[]; delegated_by?: string; retry_of?: string;
  operation?: string; read_only?: boolean; scheduled_at?: string; heartbeat_at?: string;
  last_event?: { message: string; created_at: string };
};
export type Agent = {
  id: string; name: string; role: string; area: string; description: string; available: boolean;
  health?: { last_success_at?: string; last_failure_at?: string; next_run_at?: string };
  xp: number; level: number; level_progress: number; achievements: string[];
  status: AgentStatus; latest: Task | null;
};
export type CityEvent = { id: number; agent_id: string; task_id: string; status: string; message: string; created_at: string };
export type Workflow = { id: string; template: string; request: string; status: AgentStatus; priority: number; created_at: string };
export type Snapshot = {
  shared_coding_tasks?: Task[]; shared_coding_events?: CityEvent[];
  agents: Agent[]; tasks: Task[]; events: CityEvent[]; workflows: Workflow[];
  today_completed: number; week_completed: number; manager_console_version?: number;
  api_usage: { calls: number; estimated_usd: number };
};
export type ChatMessage = { id?: number; role: "user" | "assistant"; content: string; model?: string; created_at?: string };
export type ChatEvent = { type: "status" | "delta" | "replace" | "tool" | "error" | "done"; text?: string; name?: string; status?: string; model?: string };

export const STATUS_LABELS: Record<string, string> = {
  idle: "Disponible", queued: "En attente", running: "Au travail", waiting_approval: "Validation requise",
  completed: "Terminée", failed: "Échec", cancelled: "Annulée",
};

// A finished proposal from Jules or Nova that still waits for the user's decision.
export function isPendingProposal(task: Task): boolean {
  return task.status === "completed" && task.result.role_version === 2 && !!task.result.approval_required
    && !task.result.branch && !task.result.review_decision && ["job_hunter", "innovation_lab"].includes(task.agent_id);
}
export const needsReview = (task: Task): boolean => task.status === "waiting_approval" || isPendingProposal(task);
