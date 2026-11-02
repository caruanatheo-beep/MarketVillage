export type AgentStatus = "idle" | "queued" | "running" | "waiting_approval" | "completed" | "failed" | "cancelled";
export type MarketReading = { series_id: string; label: string; value: number; unit: string; observed_at: string };
export type WorldInteraction = { id: string; label: string; detail: string; agentId: string; action: "markets" | "chat" | "missions" };
