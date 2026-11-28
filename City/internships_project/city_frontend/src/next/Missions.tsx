// Quest journal: missions in progress, to review, finished and failed.
import React, { useEffect, useMemo, useState } from "react";
import { actions } from "../client/api";
import { STATUS_LABELS, isPendingProposal, needsReview, type Snapshot, type Task } from "../client/types";
import { LEVELS, SEATS } from "../scene/building";
import { Panel, Portrait, when } from "./ui";

type Tab = "active" | "review" | "done" | "failed";
const TABS: [Tab, string][] = [["active", "En cours"], ["review", "À valider"], ["done", "Terminées"], ["failed", "Échecs"]];
const inTab = (task: Task, tab: Tab): boolean => tab === "review" ? needsReview(task)
  : tab === "active" ? ["running", "queued"].includes(task.status)
  : tab === "done" ? task.status === "completed" && !isPendingProposal(task) : ["failed", "cancelled"].includes(task.status);

export function Missions(props: { snapshot: Snapshot; initialTab: Tab; initialTask: string; onClose(): void; onRefresh(): Promise<void>;
  onLocate(agentId: string): void; onError(message: string): void }): React.ReactElement {
  const { snapshot } = props;
  const [tab, setTab] = useState<Tab>(props.initialTab), [selected, setSelected] = useState(props.initialTask), [busy, setBusy] = useState(false);
  useEffect(() => { setTab(props.initialTab); setSelected(props.initialTask); }, [props.initialTab, props.initialTask]);
  const counts = useMemo(() => Object.fromEntries(TABS.map(([id]) => [id, snapshot.tasks.filter(task => inTab(task, id)).length])), [snapshot.tasks]);
  const tasks = snapshot.tasks.filter(task => inTab(task, tab));
  const task = tasks.find(item => item.id === selected) || tasks[0];
  const agentName = (id: string) => snapshot.agents.find(agent => agent.id === id)?.name || id;

  const run = async (action: () => Promise<unknown>) => {
    setBusy(true);
    try { await action(); await props.onRefresh(); }
    catch (exc) { props.onError(exc instanceof Error ? exc.message : "Action impossible."); }
    finally { setBusy(false); }
  };

  return <Panel title="Journal des missions" icon="missions" subtitle={`${counts.active} en cours · ${counts.review} à valider`} onClose={props.onClose}>
    <div className="tabs" role="tablist">{TABS.map(([id, label]) =>
      <button key={id} type="button" role="tab" aria-selected={tab === id} className={id === "review" && counts.review ? "needs" : ""} onClick={() => { setTab(id); setSelected(""); }}>{label}<b>{counts[id]}</b></button>)}</div>
    <div className="quest-layout">
      <ul className="quest-list">
        {!tasks.length && <li className="empty">Rien dans cette page du journal.</li>}
        {tasks.map(item => <li key={item.id}><button type="button" className={`quest ${item.status} ${item === task ? "current" : ""}`} onClick={() => setSelected(item.id)}>
          <span className="quest-mark" aria-hidden="true">{needsReview(item) ? "!" : item.status === "running" ? "▶" : item.status === "queued" ? "…" : item.status === "completed" ? "✓" : "×"}</span>
          <span><strong>{item.description}</strong><small>{agentName(item.agent_id)} · {when(item.finished_at || item.started_at || item.created_at)}</small></span>
        </button></li>)}
      </ul>
      {task ? <article className="quest-page">
        <header><Portrait id={task.agent_id} scale={3} /><div><h3>{task.description}</h3>
          <p className="chips"><span>{agentName(task.agent_id)}</span><span>{LEVELS[SEATS[task.agent_id]?.level ?? 1].name}</span>
            <span className={`status ${needsReview(task) ? "waiting_approval" : task.status}`}>{isPendingProposal(task) ? "Proposition à valider" : STATUS_LABELS[task.status]}</span></p></div></header>
        <dl><dt>Créée</dt><dd>{when(task.created_at)}</dd>{task.started_at && <><dt>Démarrée</dt><dd>{when(task.started_at)}</dd></>}
          {task.finished_at && <><dt>Terminée</dt><dd>{when(task.finished_at)}</dd></>}<dt>Identifiant</dt><dd><code>#{task.id.slice(0, 10)}</code></dd></dl>
        {task.error && <p className="quest-error">{task.error}</p>}
        {task.status === "waiting_approval" && <p className="quest-note">Cette mission attend ta validation avant de démarrer.</p>}
        {(task.result.plain_summary || task.result.summary || task.result.title) && <p className="quest-summary">{task.result.plain_summary || task.result.summary || task.result.title}</p>}
        {task.result.text && <div className="quest-text">{task.result.text.split(/\n{2,}/).slice(0, 12).map((block, i) => <p key={i}>{block.replace(/[*#`]/g, "")}</p>)}</div>}
        {!!task.result.files?.length && <p className="quest-note">{task.result.files.length} fichier(s) modifié(s) : {task.result.files.slice(0, 4).join(", ")}{task.result.files.length > 4 ? "…" : ""}</p>}
        <h4>Journal</h4>
        <ol className="quest-log">{snapshot.events.filter(event => event.task_id === task.id).sort((a, b) => a.id - b.id).map(event =>
          <li key={event.id}><time>{when(event.created_at)}</time>{event.message}</li>)}
          {!snapshot.events.some(event => event.task_id === task.id) && <li>Aucune étape récente enregistrée.</li>}</ol>
        <footer>
          {task.status === "waiting_approval" && !task.read_only && <button type="button" className="btn primary" disabled={busy} onClick={() => void run(() => task.workflow_id ? actions.approveWorkflow(task.workflow_id) : actions.approve(task.id))}>Valider</button>}
          {isPendingProposal(task) && <><button type="button" className="btn primary" disabled={busy || (task.agent_id === "job_hunter" && !task.result.revision)} onClick={() => void run(() => actions.reviewProposal(task.id, true))}>Valider la proposition</button>
            <button type="button" className="btn" disabled={busy} onClick={() => void run(() => actions.reviewProposal(task.id, false))}>Refuser</button></>}
          {task.status === "failed" && !task.read_only && <button type="button" className="btn primary" disabled={busy} onClick={() => void run(() => actions.retry(task.id))}>Réessayer</button>}
          {["queued", "waiting_approval"].includes(task.status) && !task.read_only && <button type="button" className="btn" disabled={busy} onClick={() => void run(() => task.workflow_id ? actions.cancelWorkflow(task.workflow_id) : actions.cancel(task.id))}>Annuler</button>}
          <button type="button" className="btn" onClick={() => props.onLocate(task.agent_id)}>Aller voir {agentName(task.agent_id)}</button>
        </footer>
      </article> : <article className="quest-page empty"><p>Choisis une mission pour lire sa page.</p></article>}
    </div>
  </Panel>;
}
