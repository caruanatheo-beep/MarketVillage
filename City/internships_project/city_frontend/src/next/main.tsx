// New MarketDesk City interface: the building fills the screen, a game HUD sits on top.
import React, { useCallback, useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import { actions } from "../client/api";
import { STATUS_LABELS, isPendingProposal, needsReview, type Agent, type Snapshot, type Task } from "../client/types";
import { useCity } from "../client/useCity";
import { LEVELS, SEATS, floorLabel } from "../scene/building";
import { Scene, type SceneHandle, type SceneInfo } from "../scene/Scene";
import { blip, setEffects, setMusic } from "./audio";
import { Dialogue } from "./Dialogue";
import { Missions } from "./Missions";
import { Icon, Panel, Portrait, useCountUp } from "./ui";

type Section = "code" | "contacts" | "missions" | "team" | "internships" | "notifications" | "settings";
const SECTIONS: [Section, string][] = [["code", "Développement"], ["contacts", "Contacts"], ["missions", "Missions"], ["team", "Équipe"],
  ["internships", "Stages"], ["notifications", "Notifications"], ["settings", "Réglages"]];
type MissionTab = "active" | "review" | "done" | "failed";

function Counter({ icon, value, label, alert, onClick }: { icon: string; value: number; label: string; alert?: boolean; onClick(): void }): React.ReactElement {
  const shown = useCountUp(value);
  return <button type="button" className={`counter ${alert && value ? "alert" : ""}`} onClick={onClick} title={label}>
    <Icon name={icon} size={24} /><strong>{shown}</strong><span>{label}</span></button>;
}

function MiniMap({ snapshot, info, onGo }: { snapshot: Snapshot | null; info: SceneInfo | null; onGo(level: number): void }): React.ReactElement {
  const scale = 26 / 96, height = LEVELS.length * 26;
  return <nav className="minimap" aria-label="Étages de l’immeuble">
    <div className="minimap-roof" aria-hidden="true" />
    <div className="minimap-floors">
      {LEVELS.map((level, index) => {
        const team = (snapshot?.agents || []).filter(agent => SEATS[agent.id]?.level === index);
        const review = info?.review.includes(index) || team.some(agent => (snapshot?.tasks || []).some(task => task.agent_id === agent.id && needsReview(task)));
        return <button type="button" key={level.id} className={`${review ? "review" : ""} ${team.some(agent => agent.status === "running") ? "active" : ""}`}
          onClick={() => onGo(index)} title={`${level.name}${level.built ? "" : " · aménagement à venir"}`} aria-label={`Aller à l’étage ${level.name}`}>
          <b>{floorLabel(index)}</b><span>{team.map(agent => <i key={agent.id} className={agent.status} />)}</span></button>;
      })}
      {info && <div className="minimap-view" aria-hidden="true" style={{ top: 3 + Math.max(0, info.camY * scale), height: Math.max(8, Math.min(height, (info.camY + info.viewH) * scale) - Math.max(0, info.camY * scale)) }} />}
    </div>
  </nav>;
}

function AgentCard(props: { agent: Agent; tasks: Task[]; anchor: SceneInfo["anchor"]; onClose(): void; onReview(task: Task): void;
  onRead(task: Task | null): void; onTalk(): void; busy: boolean }): React.ReactElement | null {
  const { agent, anchor } = props;
  if (!anchor) return null;
  const review = props.tasks.find(task => task.agent_id === agent.id && needsReview(task));
  const current = review || props.tasks.find(task => task.agent_id === agent.id && ["running", "queued"].includes(task.status)) || null;
  const left = anchor.x + 330 > window.innerWidth ? anchor.x - 316 : anchor.x + 36;
  const top = Math.max(96, Math.min(window.innerHeight - 420, anchor.y - anchor.h - 150));
  return <aside className="agent-card" style={{ left, top }} role="dialog" aria-label={`Fiche de ${agent.name}`}>
    <button type="button" className="window-close" onClick={props.onClose} aria-label="Fermer">×</button>
    <header><Portrait id={agent.id} scale={4} /><div><h3>{agent.name}</h3><small>{agent.role}</small>
      <small>{LEVELS[SEATS[agent.id]?.level ?? 1].name} · étage {floorLabel(SEATS[agent.id]?.level ?? 1)}</small></div></header>
    <p className={`status ${review ? "waiting_approval" : agent.status}`}>{review ? "À examiner" : STATUS_LABELS[agent.status]}</p>
    <div className="xp" title={`${agent.xp} XP`}><span style={{ width: `${Math.round((agent.level_progress || 0) * 100)}%` }} /><b>Niv. {agent.level}</b></div>
    <p className="card-task">{current ? current.description : "Disponible pour une mission."}</p>
    <footer>
      {review && <button type="button" className="btn primary" disabled={props.busy} onClick={() => props.onReview(review)}>{isPendingProposal(review) ? "Examiner" : "Valider"}</button>}
      <button type="button" className="btn" onClick={() => props.onRead(current || agent.latest)}>Relire</button>
      <button type="button" className="btn" onClick={props.onTalk}>Parler</button>
    </footer>
  </aside>;
}

function App(): React.ReactElement {
  const { snapshot, error, refresh } = useCity();
  const scene = useRef<SceneHandle>(null);
  const [info, setInfo] = useState<SceneInfo | null>(null);
  const [section, setSection] = useState<Section | null>(null);
  const [missionTab, setMissionTab] = useState<MissionTab>("active"), [missionTask, setMissionTask] = useState("");
  const [selected, setSelected] = useState(""), [talking, setTalking] = useState(false), [draft, setDraft] = useState("");
  const [toast, setToast] = useState(""), [busy, setBusy] = useState(false);
  const [music, setMusicOn] = useState(false), [sound, setSound] = useState(() => localStorage.getItem("city-sound") !== "off");
  const [clock, setClock] = useState("");

  useEffect(() => { setEffects(sound); localStorage.setItem("city-sound", sound ? "on" : "off"); }, [sound]);
  useEffect(() => {
    const tick = () => setClock(new Intl.DateTimeFormat("fr-FR", { hour: "2-digit", minute: "2-digit", timeZone: "Europe/Paris" }).format(new Date()));
    tick(); const id = window.setInterval(tick, 10000); return () => window.clearInterval(id);
  }, []);
  useEffect(() => { if (error) setToast(error); }, [error]);

  const tasks = snapshot?.tasks || [];
  const reviewCount = tasks.filter(needsReview).length, runningCount = tasks.filter(task => task.status === "running").length;
  const activeAgents = (snapshot?.agents || []).filter(agent => agent.status === "running").length;
  const previousReview = useRef(0);
  useEffect(() => { if (reviewCount > previousReview.current) blip("alert"); previousReview.current = reviewCount; }, [reviewCount]);

  const open = useCallback((next: Section | null) => { setSection(current => { blip(next && next !== current ? "open" : "close"); return next === current ? null : next; }); setTalking(false); }, []);
  const openMissions = (tab: MissionTab, taskId = "") => { setMissionTab(tab); setMissionTask(taskId); setSection("missions"); setTalking(false); blip("open"); };
  const pick = (id: string) => {
    if (!id) { setSelected(""); return; }
    blip("click");
    if (id === "desk_manager" && !tasks.some(task => task.agent_id === id && needsReview(task))) { setSelected(id); setDraft(""); setTalking(true); setSection(null); return; }
    setSelected(id);
  };
  const locate = (agentId: string) => { setSection(null); setSelected(agentId); scene.current?.focusAgent(agentId); };

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      const typing = ["INPUT", "TEXTAREA", "SELECT"].includes((event.target as HTMLElement).tagName);
      if (event.key === "Escape") { if (section) open(null); else if (talking) { setTalking(false); setSelected(""); blip("close"); } else setSelected(""); return; }
      if (typing || event.ctrlKey || event.metaKey || event.altKey) return;
      if (/^[1-7]$/.test(event.key)) { open(SECTIONS[Number(event.key) - 1][0]); return; }
      if (event.key === "ArrowUp") { event.preventDefault(); scene.current?.scrollLevels(-1); }
      if (event.key === "ArrowDown") { event.preventDefault(); scene.current?.scrollLevels(1); }
      if (event.key === "+" || event.key === "=") scene.current?.zoomBy(1);
      if (event.key === "-") scene.current?.zoomBy(-1);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [section, talking, open]);

  const agent = snapshot?.agents.find(item => item.id === selected);
  const review = async (task: Task) => {
    if (isPendingProposal(task)) { openMissions("review", task.id); return; }
    setBusy(true);
    try { await (task.workflow_id ? actions.approveWorkflow(task.workflow_id) : actions.approve(task.id)); await refresh(); }
    catch (exc) { setToast(exc instanceof Error ? exc.message : "Validation impossible."); }
    finally { setBusy(false); }
  };
  const tabOf = (task: Task): MissionTab => needsReview(task) ? "review" : ["running", "queued"].includes(task.status) ? "active" : task.status === "completed" ? "done" : "failed";

  return <div className="city-next">
    <Scene ref={scene} agents={snapshot?.agents || []} tasks={tasks} selectedId={selected} onPick={pick} onInfo={setInfo} />

    <div className="hud hud-brand">
      <strong>MarketDesk Tower</strong>
      <span className="hud-clock">Paris · {clock}</span>
      <div className="hud-row">
        <button type="button" className={`lofi ${music ? "on" : ""}`} aria-pressed={music} onClick={() => { setMusic(!music); setMusicOn(!music); }} title="Lecteur lofi">
          <Icon name="note" size={18} /><span>Lofi {music ? "on" : "off"}</span><i /><i /><i /></button>
        <button type="button" className="mini" aria-pressed={sound} onClick={() => setSound(!sound)} title="Sons de l’interface">{sound ? "Sons on" : "Sons off"}</button>
        <form action="/logout" method="post"><button type="submit" className="mini">Quitter</button></form>
      </div>
    </div>

    <div className="hud hud-counters">
      <Counter icon="agent" value={activeAgents} label="agents actifs" onClick={() => open("team")} />
      <Counter icon="missions" value={runningCount} label="missions en cours" onClick={() => openMissions("active")} />
      <Counter icon="alert" value={reviewCount} label="à examiner" alert onClick={() => openMissions("review")} />
    </div>

    <div className="hud-side">
      <MiniMap snapshot={snapshot} info={info} onGo={level => { blip("click"); scene.current?.goToLevel(level); }} />
      <div className="hud zoom"><button type="button" onClick={() => scene.current?.zoomBy(1)} aria-label="Zoomer">+</button>
        <button type="button" onClick={() => scene.current?.zoomBy(-1)} aria-label="Dézoomer">−</button></div>
    </div>

    <nav className="hud hotbar" aria-label="Sections">
      {SECTIONS.map(([id, label], index) => {
        const badge = id === "missions" ? runningCount : id === "notifications" ? reviewCount : 0;
        return <button type="button" key={id} className={section === id ? "active" : ""} aria-pressed={section === id} onClick={() => id === "missions" ? (section === id ? open(null) : openMissions(reviewCount ? "review" : "active")) : open(id)}>
          <kbd>{index + 1}</kbd><Icon name={id} size={30} /><span>{label}</span>{badge > 0 && <b>{badge}</b>}</button>;
      })}
    </nav>

    {agent && !talking && !section && <AgentCard agent={agent} tasks={tasks} anchor={info?.anchor || null} busy={busy} onClose={() => setSelected("")}
      onReview={task => void review(task)} onRead={task => task ? openMissions(tabOf(task), task.id) : openMissions("active")}
      onTalk={() => { setDraft(agent.id === "desk_manager" ? "" : `À propos de ${agent.name} : `); setTalking(true); }} />}

    {section === "missions" && snapshot && <Missions snapshot={snapshot} initialTab={missionTab} initialTask={missionTask} onClose={() => open(null)}
      onRefresh={refresh} onLocate={locate} onError={setToast} />}
    {section && section !== "missions" && <Panel narrow title={SECTIONS.find(([id]) => id === section)![1]} icon={section} subtitle="Bientôt dans la nouvelle interface" onClose={() => open(null)}>
      <div className="soon"><p>Ce panneau arrive dans une prochaine étape de la refonte. En attendant, toutes ses fonctions restent disponibles dans l’interface actuelle.</p>
        <a className="btn primary" href="/city/">Ouvrir l’interface actuelle</a></div></Panel>}
    {talking && <Dialogue draft={draft} onClose={() => { setTalking(false); setSelected(""); blip("close"); }} onRefresh={refresh} />}
    {toast && <div className="toast" role="alert"><span>{toast}</span><button type="button" onClick={() => setToast("")} aria-label="Fermer">×</button></div>}
    {!snapshot && !error && <div className="loading">Ouverture de l’immeuble…</div>}
  </div>;
}

createRoot(document.getElementById("root")!).render(<App />);
