import { useCallback, useEffect, useState } from "react";
import { loadSnapshot } from "./api";
import type { Snapshot } from "./types";

// Polls the server state every four seconds while the tab is visible.
export function useCity(): { snapshot: Snapshot | null; error: string; refresh: () => Promise<void> } {
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [error, setError] = useState("");
  const refresh = useCallback(async () => {
    try { setSnapshot(await loadSnapshot()); setError(""); }
    catch (exc) { setError(exc instanceof Error ? exc.message : "Impossible de charger MarketDesk City."); }
  }, []);
  useEffect(() => {
    void refresh();
    const interval = window.setInterval(() => { if (!document.hidden) void refresh(); }, 4000);
    const onVisible = () => { if (!document.hidden) void refresh(); };
    document.addEventListener("visibilitychange", onVisible);
    return () => { window.clearInterval(interval); document.removeEventListener("visibilitychange", onVisible); };
  }, [refresh]);
  return { snapshot, error, refresh };
}
