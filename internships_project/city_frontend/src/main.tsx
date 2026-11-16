import React, { useCallback, useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import {SidebarIcon} from "./SidebarIcon";
import { type AgentStatus } from "./types";
import { PixelFloorGame } from "./PixelFloorGame";
import "./liveDashboard";
import {NetworkContactsWindow} from "./NetworkContacts";
import {ManagerChatWindow} from "./ManagerChatWindow";
import {NotificationCenter} from "./NotificationCenter";
import {Cockpit} from "./Cockpit";
import {isPendingProposal} from "./notifications";
import {agentGroup,agentSections,AGENT_GROUP_LABELS} from "./agentGroups";

// The standalone fallback panel is only used by the currently deployed bundle.
// New frontend builds render these same live feeds directly in the game canvas.
(window as Window & { __marketdeskNativePanels?: boolean }).__marketdeskNativePanels = true;

type Offer = { title: string; company: string; location: string; url: string; kind?: string; start_period?: string;
  published?: string; published_inferred?: boolean; source?: string; selection_source?: "job_hunter"|"internships_cache";
  selection_reason?: string; detected_at?: string; total_offers?: number; tracker_updated_at?: string };
type MarketReading = { series_id:string; label:string; value:number; unit:string; observed_at:string; change?:number|null; change_display?:string; source_url?:string };
type InternshipHighlight = { featured_offer: Offer | null; recent_offers?: Offer[]; recent_count?: number; updated_at?: string; total_count?: number; source_errors?: number; error?: string; catalog_source?: string; catalog_warning?: string; catalog_stale?: boolean; catalog_url?: string };
type Result = { title?: string; text?: string; summary?: string; market_points?: number; question?: string; answer?: string; subject?: string; body?: string;
  sentiment?: {label:string;confidence:string;explanation:string;signals:string[];supporting_news:{title:string;url:string;source:string;published:string}[]};
  followup?: string; new_count?: number; total_count?: number; priority_count?: number; source_errors?: number;
  updated_at?: string; as_of?: string; market_data?: MarketReading[]; featured_offer?: (Offer & { detected_at?: string; selection_reason?: string }) | null;
  offers?: Offer[]; contacts?: {id:string;name:string;role:string;company:string;verification:string;linkedin_url:string}[];
  equity?: {date:string;value:number}[]; approval_required?:boolean; branch?:string; role_version?:number; review_decision?:string; revision?:string; blockage?:string; file?:string;
  files?:string[];diff?:string;diff_truncated?:boolean;checks?:{command:string;exit_code:number|null}[]; server_checks?:string[]; limitations?:string; integrated?:boolean; live?:boolean|null; already_present?:boolean; plain_summary?:string; commit?:string; base_note?:string; publication_status?:string; public_commit?:string;
  errors?: {source:string;status:string;error:string}[]; contact?: {name?:string;company?:string}; };
type Task = {
  id: string; agent_id: string; task_type: string; description: string; status: AgentStatus;
  created_at: string; started_at?: string; finished_at?: string; result: Result;
  error?: string; xp_awarded: number; input_tokens: number; output_tokens: number; api_cost_usd: number;
  workflow_id?: string; priority?: number; retry_count?: number; max_retries?: number; depends_on?: string[];
  delegated_by?: string; retry_of?: string; operation?: string; period?: string; read_only?: boolean;
  scheduled_at?: string; heartbeat_at?: string; last_event?: {message:string;created_at:string};
};
type Workflow = {id:string;template:string;request:string;status:AgentStatus;priority:number;created_at:string;
  updated_at:string;steps:{id:string;agent_id:string;description:string;status:AgentStatus;error?:string;
  retry_count:number;max_retries:number;depends_on:string[]}[];
  result:{agent_id:string;status:AgentStatus;result:Result;error?:string}[]};
type WorkflowStepDraft = {operation?:string;id:string;agent_id:string;description:string;depends_on:string[]};
type WorkflowDefinition = {id:string;name:string;steps:WorkflowStepDraft[];created_at:string;updated_at:string};
type MemoryEntry = {id:string;agent_id:string;kind:string;title:string;content:string;created_at:string;updated_at:string;score:number};
type Agent = {
  id: string; name: string; role: string; area: string; description: string; available: boolean;
  health?: {last_success_at?:string;last_failure_at?:string;next_run_at?:string};
  xp: number; level: number; level_progress: number; achievements: string[];
  status: AgentStatus; latest: Task | null;
};
type Event = { id:number; agent_id: string; task_id: string; status: string; message: string; created_at: string };
type CodingHistory = {tasks:Task[];events:Event[];report?:{date:string;generated_at:string;overview:string;count:number;changes:{id:string;agent:string;summary:string}[]}};
type ChatMessage = { id?: number; role: "user" | "assistant"; content: string; model?: string; created_at?: string; tool_calls?:ToolReceipt[] };
type ToolReceipt = {name:string;status:"running"|"completed"|"unavailable"|"failed";text:string};
type CitySettings = { provider: string; models: Record<string,string>; daily_limit_usd: number; monthly_limit_usd: number;
  max_concurrent_tasks: number; auto_tasks: boolean; available_models?: string[]; api_key_configured?: boolean; codex_chat_available?: boolean };
type Integration = { name: string; status: "Connected" | "Unavailable" | "Error"; source: string; detail: string;
  last_sync: string; access: string; separate_process: boolean };
type Snapshot = {
  shared_coding_tasks?: Task[]; shared_coding_events?: Event[];
  agents: Agent[]; tasks: Task[]; events: Event[]; workflows: Workflow[]; today_completed: number; week_completed: number;
  manager_console_version?: number;
  api_usage: { input_tokens: number; output_tokens: number; estimated_usd: number; calls: number; unknown_costs: number; note: string;
    by_agent: Record<string,{calls:number;estimated_usd:number;unknown:number}> };
  workspace: { profiles: { id: string; name: string }[]; contacts: { id: string; name: string; company: string; email: string }[] };
};

const LABELS: Record<string, string> = {
  idle: "Disponible", queued: "En attente", running: "Au travail", waiting_approval: "Validation requise",
  completed: "Terminée", failed: "Échec", cancelled: "Annulée",
};
const SPECIALIST_OPERATIONS:Record<string,string> = {job_hunter:"repository_audit",city_ui_engineer:"develop",internships_engineer:"develop",quality_engineer:"develop",finance_tutor:"quant_report",developer:"daily_questions",innovation_lab:"innovation_review",internship_scout:"refresh_internships",securities_scout:"discover_service_contacts",prime_services_scout:"discover_prime_services_contacts"};
const INITIAL_IDS = ["desk_manager", "market_analyst", "finance_tutor", "job_hunter", "city_ui_engineer", "internships_engineer", "quality_engineer", "networker", "securities_scout", "prime_services_scout", "outreach_agent", "developer", "innovation_lab", "internship_scout"];

function MarkdownText({text,onTaskClick}: {text:string;onTaskClick?:(id:string)=>void}): React.ReactElement {
  const inline = (value:string) => value
    .replace(/\\\(|\\\)|\\\[|\\\]/g, "")
    .replace(/\\(?:text|mathrm)\{([^{}]*)\}/g, "$1")
    .replace(/\\times/g, "×").replace(/\\cdot/g, "·").replace(/\\%/g, "%")
    .split(/(\[\[mission:[a-f0-9]{32}\]\]|\[[^\]]+\]\(https?:\/\/[^\s)]+\)|\*\*[^*]+\*\*|`[^`]+`|https?:\/\/[^\s)]+)/g).map((part,index) => {
    const task = part.match(/^\[\[mission:([a-f0-9]{32})\]\]$/);
    if (task) return onTaskClick?<button type="button" key={index} className="manager-task-link" onClick={()=>onTaskClick(task[1])}>Voir la mission ↗</button>:null;
    const link = part.match(/^\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)$/);
    if (link) return <a key={index} href={link[2]} target="_blank" rel="noopener noreferrer">{link[1]} ↗</a>;
    if (part.startsWith("**") && part.endsWith("**")) return <strong key={index}>{part.slice(2,-2)}</strong>;
    if (part.startsWith("`") && part.endsWith("`")) return <code key={index}>{part.slice(1,-1)}</code>;
    if (/^https?:\/\//.test(part)) return <a key={index} href={part} target="_blank" rel="noopener noreferrer">{part}</a>;
    return part;
  });
  const rows = text.split(/\r?\n/); const out:React.ReactNode[]=[]; let bullets:string[]=[];
  const flush=()=>{if(bullets.length){out.push(<ul key={`list-${out.length}`}>{bullets.map((line,i)=><li key={i}>{inline(line)}</li>)}</ul>);bullets=[];}};
  rows.forEach((line,index)=>{
    const trimmed=line.trim();
    if(!trimmed){flush();return;}
    if(/^[-*]\s+/.test(trimmed)){bullets.push(trimmed.replace(/^[-*]\s+/,""));return;}
    flush();
    if(trimmed.startsWith("### "))out.push(<h4 key={index}>{inline(trimmed.slice(4))}</h4>);
    else if(trimmed.startsWith("## "))out.push(<h3 key={index}>{inline(trimmed.slice(3))}</h3>);
    else out.push(<p key={index}>{inline(trimmed)}</p>);
  });flush();
  return <div className="markdown-content">{out}</div>;
}


function EquityChart({points}:{points:{date:string;value:number}[]}):React.ReactElement {
  const values=points.map(p=>p.value).filter(Number.isFinite); const lo=Math.min(...values),hi=Math.max(...values);
  const coordinates=values.map((v,i)=>`${i*480/Math.max(1,values.length-1)},${100-(v-lo)/Math.max(.001,hi-lo)*90}`).join(" ");
  return <figure><svg viewBox="0 0 480 110" role="img" aria-label="Capital net après coûts de transaction"><polyline points={coordinates} fill="none" stroke="#94a8f5" strokeWidth="2"/></svg><figcaption>Capital net · {points[0]?.date} → {points[points.length-1]?.date}</figcaption></figure>;
}

function dateTime(value?: string): string {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "—" : new Intl.DateTimeFormat("fr-FR", {
    day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", timeZone: "Europe/Paris",
  }).format(date);
}

function codeChangeState(task:Task):'applied'|'waiting'|'not_applied'|'no_change' {
  if(task.result.integrated)return 'applied';
  if(['queued','running','waiting_approval'].includes(task.status))return 'waiting';
  if(task.status==='completed'&&task.result.files?.length===0)return 'no_change';
  return 'not_applied';
}

function codeChangeSummary(task:Task):string {
  if(task.status==='failed'){
    const error=(task.error||'').toLowerCase();
    if(error.includes('codex login')||error.includes('connecte codex'))return 'L’agent n’a pas pu se connecter. Aucun changement appliqué.';
    if(error.includes('tests serveur')||error.includes('vérification'))return 'Les vérifications ont échoué. Le changement reste à examiner.';
    if(error.includes('conflit')||error.includes('dépôt a changé'))return 'Le projet a changé pendant la mission. Le changement reste à examiner.';
    return 'La mission s’est arrêtée avant l’application du changement.';
  }
  if(task.status==='queued')return 'Le travail attend son démarrage.';
  if(task.status==='running')return 'L’agent travaille sur le changement.';
  if(task.status==='waiting_approval')return 'Le changement attend une décision.';
  if(codeChangeState(task)==='no_change'&&!task.result.already_present)return 'L’agent n’a pas trouvé de changement fiable à faire.';
  const raw=task.result.plain_summary||task.result.summary||task.result.text?.split(/\n\s*\n/)[0]||'';
  const clean=raw.replace(/[`*_#]/g,'').replace(/\s+/g,' ').trim();
  return clean.length>180?clean.slice(0,177).replace(/\s+\S*$/,'')+'…':clean||'Le compte rendu est disponible dans la mission.';
}

async function api<T>(path: string, payload?: object): Promise<T> {
  const response = await fetch(path, {
    credentials: "same-origin",
    method: payload ? "POST" : "GET",
    headers: payload ? { "Content-Type": "application/json", "X-MarketDesk-City": "1" } : undefined,
    body: payload ? JSON.stringify(payload) : undefined,
    cache: "no-store",
  });
  let data: Record<string, unknown> = {};
  try { data = await response.json() as Record<string, unknown>; } catch { /* readable fallback below */ }
  if (!response.ok) throw new Error(String(data.detail || `Erreur HTTP ${response.status}`));
  return data as T;
}

function App(): React.ReactElement {
  const [notificationView,setNotificationView]=useState({filter:"all",agent:""});
  const [missionFilter,setMissionFilter]=useState("active");
  const [missionSection,setMissionSection]=useState<'follow'|'launch'|'projects'>('follow');
  const [codeHistory,setCodeHistory]=useState<CodingHistory|null>(null);
  const [codePeriod,setCodePeriod]=useState('month');
  const [codeVisibleCount,setCodeVisibleCount]=useState(12);
  const [codeAgent,setCodeAgent]=useState('all');
  const [codeAssignee,setCodeAssignee]=useState('job_hunter');
  const [codeHistoryError,setCodeHistoryError]=useState('');
  const [codeRequest,setCodeRequest]=useState('');
  const [codeActionBusy,setCodeActionBusy]=useState(false);
  const [codeActionNotice,setCodeActionNotice]=useState('');
  const [resultTaskId,setResultTaskId]=useState<string|null>(null);
  const [resultTaskDetail,setResultTaskDetail]=useState<Task|null>(null);
  const [commandQuery,setCommandQuery]=useState("");
  useEffect(()=>{if(!resultTaskId)return;const close=(event:KeyboardEvent)=>{if(event.key==="Escape")setResultTaskId(null);};window.addEventListener("keydown",close);return()=>window.removeEventListener("keydown",close);},[resultTaskId]);
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [internshipHighlight, setInternshipHighlight] = useState<InternshipHighlight | null>(null);
  const [selectedId, setSelectedId] = useState("");
  const [workflowTemplate, setWorkflowTemplate] = useState("careers_outreach");
  const [workflowFocus, setWorkflowFocus] = useState("");
  const [workflowPriority, setWorkflowPriority] = useState(1);
  const [workflowName, setWorkflowName] = useState("Contacts et brouillons");
  const [workflowSteps, setWorkflowSteps] = useState<WorkflowStepDraft[]>([
    {id:"contacts",agent_id:"networker",description:"Identifier les contacts importés pertinents",depends_on:[]},
    {id:"draft",agent_id:"outreach_agent",description:"Préparer un brouillon pour le contact le plus pertinent",depends_on:["contacts"]},
  ]);
  const [editingWorkflowId, setEditingWorkflowId] = useState("");
  const [workflowDefinitions, setWorkflowDefinitions] = useState<WorkflowDefinition[]>([]);
  const [memoryEntries, setMemoryEntries] = useState<MemoryEntry[]>([]);
  const [memoryQuery, setMemoryQuery] = useState("");
  const [memoryTitle, setMemoryTitle] = useState("");
  const [memoryContent, setMemoryContent] = useState("");
  const [memoryBusy, setMemoryBusy] = useState(false);
  const [mission, setMission] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [openedTaskId, setOpenedTaskId] = useState<string | null>(null);
  const [retryNotice,setRetryNotice]=useState('');
  const [windowMode, setWindowMode] = useState<"none"|"agent"|"agents"|"missions"|"code"|"activity"|"contacts"|"chat"|"internships"|"settings">("none");
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [chatInput, setChatInput] = useState("");
  const [chatBusy, setChatBusy] = useState(false);
  const [chatStatus, setChatStatus] = useState("");
  const [chatError, setChatError] = useState("");
  const [chatAtBottom,setChatAtBottom]=useState(true);
  const [chatElapsed,setChatElapsed]=useState(0);
  const chatFollow=useRef(true);
  const chatScrollRef = useRef<HTMLDivElement>(null);
  const chatAbort = useRef<AbortController | null>(null);
  const [settings, setSettings] = useState<CitySettings|null>(null);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [settingsBusy, setSettingsBusy] = useState(false);
  const [diagnostics, setDiagnostics] = useState<Integration[]|null>(null);
  const [diagnosticsBusy, setDiagnosticsBusy] = useState(false);
  const [collectionBusy, setCollectionBusy] = useState<"internships"|null>(null);

  const [notificationReadThrough,setNotificationReadThrough]=useState(0);
  const refresh = useCallback(async () => {
    try {
      const [next,notifications]=await Promise.all([api<Snapshot>("/city/api/state"),api<{last_read_event_id:number}>("/city/api/notifications")]);
      setSnapshot({...next,tasks:[...next.tasks,...(next.shared_coding_tasks||[])].sort((a,b)=>b.created_at.localeCompare(a.created_at)),
        events:[...next.events,...(next.shared_coding_events||[])].sort((a,b)=>b.id-a.id)});
      setNotificationReadThrough(notifications.last_read_event_id);
      setError("");
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Impossible de charger MarketDesk City.");
    }
  }, []);

  const loadWorkflowDefinitions = useCallback(async () => {
    try {
      const data = await api<{definitions:WorkflowDefinition[]}>("/city/api/workflows/definitions");
      setWorkflowDefinitions(data.definitions || []);
    } catch (exc) { setError(exc instanceof Error ? exc.message : "Workflows enregistrés indisponibles."); }
  }, []);

  const loadMemory = useCallback(async (query = "") => {
    try {
      const data = await api<{entries:MemoryEntry[]}>("/city/api/memory?q=" + encodeURIComponent(query));
      setMemoryEntries(data.entries || []);
    } catch (exc) { setError(exc instanceof Error ? exc.message : "Mémoire partagée indisponible."); }
  }, []);

  const loadChat = useCallback(async (agentId: string) => {
    setChatError("");
    try {
      const data = await api<{messages:ChatMessage[]}>(`/city/api/chat/${agentId}`);
      if(!chatAbort.current)setChatMessages(data.messages || []);
    } catch (exc) { setChatError(exc instanceof Error ? exc.message : "Historique indisponible."); }
  }, []);

  const loadSettings = useCallback(async () => {
    try { setSettings(await api<CitySettings>("/city/api/settings")); }
    catch (exc) { setError(exc instanceof Error ? exc.message : "Réglages indisponibles."); }
  }, []);

  const loadInternshipHighlight = useCallback(async () => {
    try { setInternshipHighlight(await api<InternshipHighlight>("/city/api/internship-highlight")); }
    catch (exc) { setInternshipHighlight({featured_offer: null, error: exc instanceof Error ? exc.message : "Cache Internships indisponible."}); }
  }, []);

  useEffect(() => {
    refresh();
    const interval = window.setInterval(() => { if (!document.hidden) refresh(); }, 4000);
    const onVisibility = () => { if (!document.hidden) refresh(); };
    document.addEventListener("visibilitychange", onVisibility);
    return () => {
      window.clearInterval(interval);
      document.removeEventListener("visibilitychange", onVisibility);
    };
  }, [refresh]);

  useEffect(() => {
    void loadWorkflowDefinitions();
    void loadMemory();
  }, [loadWorkflowDefinitions, loadMemory]);

  useEffect(() => {
    void loadInternshipHighlight();
    const interval = window.setInterval(() => { if (!document.hidden) void loadInternshipHighlight(); }, 60000);
    return () => window.clearInterval(interval);
  }, [loadInternshipHighlight]);

  useEffect(() => {
    if(windowMode!=='code')return;
    let active=true;
    const load=async()=>{try{const history=await api<CodingHistory>('/city/api/coding-history');if(active){setCodeHistory(history);setCodeHistoryError('');}}
      catch(exc){if(active)setCodeHistoryError(exc instanceof Error?exc.message:'Suivi indisponible.');}};
    void load();
    const interval=window.setInterval(()=>{if(!document.hidden)void load();},15000);
    return()=>{active=false;window.clearInterval(interval);};
  },[windowMode]);

  useEffect(() => {
    void loadChat("desk_manager");
    const interval=window.setInterval(()=>{if(!document.hidden&&!chatAbort.current)void loadChat("desk_manager");},10000);
    return()=>window.clearInterval(interval);
  }, [loadChat]);
  useEffect(() => { if(chatFollow.current)chatScrollRef.current?.scrollTo({top:chatScrollRef.current.scrollHeight}); }, [chatMessages, chatStatus]);
  useEffect(()=>{setChatElapsed(0);if(!chatBusy)return;const timer=window.setInterval(()=>setChatElapsed(seconds=>seconds+1),1000);return()=>window.clearInterval(timer);},[chatBusy]);

  useEffect(() => {
    const publishHeight = () => window.parent.postMessage({
      type: "marketdesk-city-size", height: document.documentElement.scrollHeight,
    }, window.location.origin);
    const observer = new ResizeObserver(publishHeight);
    observer.observe(document.body);
    window.addEventListener("resize", publishHeight);
    window.setTimeout(publishHeight, 100);
    return () => { observer.disconnect(); window.removeEventListener("resize", publishHeight); };
  }, []);

  const deskManager = snapshot?.agents.find(agent => agent.id === "desk_manager") || null;
  const pendingCount = snapshot?.tasks.filter(task=>task.status==="waiting_approval"||isPendingProposal(task)).length||0;
  const activeCount = snapshot?.tasks.filter(task=>task.status==="running"&&agentGroup(task.agent_id)!=='Développement').length||0;
  const codeActiveCount = snapshot?.tasks.filter(task=>task.status==="running"&&agentGroup(task.agent_id)==='Développement').length||0;
  const todayKey = (value: string) => { const date = new Date(value); return Number.isNaN(date.getTime()) ? "" : `${date.getFullYear()}-${String(date.getMonth()+1).padStart(2,"0")}-${String(date.getDate()).padStart(2,"0")}`; };
  const jobTaskToday = snapshot?.tasks.find(task=>(["internship_scout","networker","desk_manager"].includes(task.agent_id))&&task.status==="completed"&&task.finished_at
    &&todayKey(task.finished_at)===todayKey(new Date().toISOString())&&task.result.featured_offer);
  const latestJobTask = snapshot?.tasks.find(task=>(["internship_scout","networker","desk_manager"].includes(task.agent_id)));
  useEffect(() => {
    if (latestJobTask?.status === "completed") void loadInternshipHighlight();
  }, [latestJobTask?.id, latestJobTask?.status, loadInternshipHighlight]);
  const internshipCollectionActive = snapshot?.tasks.some(task=>["internship_scout","desk_manager"].includes(task.agent_id)&&["queued","running","waiting_approval"].includes(task.status)) || false;

  async function launchCollection(kind:"internships"):Promise<void> {
    if (collectionBusy) return;
    setCollectionBusy(kind); setError("");
    try {
      await api(`/city/api/collect/${kind}`, {});
      await refresh();
      await loadInternshipHighlight();
    } catch (exc) { setError(exc instanceof Error ? exc.message : "La collecte n'a pas pu démarrer."); }
    finally { setCollectionBusy(null); }
  }
  function openNotifications(filter="all",agent=""):void {
    setNotificationView({filter,agent});setWindowMode("activity");
  }
  function switchTab(mode:typeof windowMode):void {
    setResultTaskId(null);setResultTaskDetail(null);
    setWindowMode(mode);
  }
  function openAgent(id:string, tab?:"chat"|"missions"|"history"):void {
    setSelectedId(id);
    if(tab==="history"){openNotifications("all",id==="desk_manager"?"":id);return;}
    if(tab==="missions"){setMissionSection('follow');setWindowMode(agentGroup(id)==='Développement'?'code':'missions');return;}
    if(tab==="chat"||id==="desk_manager"){setWindowMode("chat");return;}
    setWindowMode(id==="networker"?"contacts":"agent");
  }
  function inspectCockpitTask(id:string):void {
    const task=snapshot?.tasks.find(t=>t.id===id);if(!task)return;
    if(["completed","failed"].includes(task.status)){showResult(task);return;}
    setSelectedId(task.agent_id);setOpenedTaskId(id);setMissionFilter(task.status==="running"?"active":"pending");setMissionSection('follow');setWindowMode(agentGroup(task.agent_id)==='Développement'?'code':'missions');
  }
  async function openManagerMission(id:string):Promise<void> {
    try {
      const detail=await api<Task>(`/city/api/tasks/${id}`);
      if (['queued','running','waiting_approval'].includes(detail.status) && snapshot?.tasks.some(task=>task.id===id)) {
        inspectCockpitTask(id); return;
      }
      setResultTaskDetail(detail);setResultTaskId(id);setOpenedTaskId(id);setSelectedId(detail.agent_id);setWindowMode('none');
    } catch (exc) {setChatError(exc instanceof Error?exc.message:'Mission indisponible.');}
  }

  async function startWorkflow(event: React.FormEvent): Promise<void> {
    event.preventDefault();
    if (busy || !mission.trim()) return;
    setBusy(true); setError("");
    try {
      await api("/city/api/workflows", {template:workflowTemplate, request:mission.trim(),
        focus:workflowFocus.trim(), priority:workflowPriority});
      setMission(""); await refresh();
    } catch (exc) { setError(exc instanceof Error ? exc.message : "Projet indisponible."); }
    finally { setBusy(false); }
  }

  function updateWorkflowStep(index:number, changes:Partial<WorkflowStepDraft>):void {
    setWorkflowSteps(current=>current.map((step,i)=>i===index?{...step,...changes}:step));
  }
  function addWorkflowStep():void {
    if(workflowSteps.length>=7)return;
    const previous=workflowSteps[workflowSteps.length-1];
    const id="step-"+Date.now().toString(36);
    setWorkflowSteps(current=>{
      const nextAgent=INITIAL_IDS.find(agentId=>agentId!=="desk_manager"&&!current.some(step=>step.agent_id===agentId))||"developer";
      return [...current,{id,agent_id:nextAgent,operation:SPECIALIST_OPERATIONS[nextAgent],description:"Traiter les informations utiles à cette étape",depends_on:previous?[previous.id]:[]}];
    });
  }
  function removeWorkflowStep(index:number):void {
    const removed=workflowSteps[index]?.id;
    setWorkflowSteps(current=>current.filter((_,i)=>i!==index).map(step=>({...step,depends_on:step.depends_on.filter(id=>id!==removed)})));
  }
  function toggleWorkflowDependency(index:number,dependencyId:string):void {
    const step=workflowSteps[index];
    if(!step)return;
    updateWorkflowStep(index,{depends_on:step.depends_on.includes(dependencyId)
      ?step.depends_on.filter(id=>id!==dependencyId):[...step.depends_on,dependencyId]});
  }
  async function saveWorkflowDefinition():Promise<void> {
    if(busy||!workflowName.trim())return;
    setBusy(true);setError("");
    try{
      const data=await api<{definition:WorkflowDefinition}>("/city/api/workflows/definitions",{
        id:editingWorkflowId||undefined,name:workflowName.trim(),steps:workflowSteps.map(step=>({...step,operation:step.operation||SPECIALIST_OPERATIONS[step.agent_id]}))});
      setWorkflowDefinitions(current=>[data.definition,...current.filter(item=>item.id!==data.definition.id)]);
      setEditingWorkflowId(data.definition.id);
    }catch(exc){setError(exc instanceof Error?exc.message:"Enregistrement du workflow impossible.");}
    finally{setBusy(false);}
  }
  async function runSavedWorkflow(definition:WorkflowDefinition):Promise<void> {
    if(busy)return;
    setBusy(true);setError("");
    try{
      await api("/city/api/workflows/definitions/"+encodeURIComponent(definition.id)+"/run",{
        request:definition.name,priority:workflowPriority});
      await refresh();
    }catch(exc){setError(exc instanceof Error?exc.message:"Lancement du workflow impossible.");}
    finally{setBusy(false);}
  }
  function editWorkflowDefinition(definition:WorkflowDefinition):void {
    setWorkflowName(definition.name);setWorkflowSteps(definition.steps);setEditingWorkflowId(definition.id);
  }
  function newWorkflowDefinition():void {
    setWorkflowName("");setEditingWorkflowId("");
    setWorkflowSteps([{id:"engineering",agent_id:"job_hunter",operation:"repository_audit",description:"Auditer le code City",depends_on:[]}]);
  }
  async function searchMemory(event:React.FormEvent):Promise<void> {
    event.preventDefault();await loadMemory(memoryQuery.trim());
  }
  async function saveMemoryEntry(event:React.FormEvent):Promise<void> {
    event.preventDefault();if(memoryBusy)return;setMemoryBusy(true);setError("");
    try{
      await api("/city/api/memory",{title:memoryTitle.trim(),content:memoryContent.trim(),kind:"preference",agent_id:"desk_manager"});
      setMemoryTitle("");setMemoryContent("");await loadMemory(memoryQuery.trim());
    }catch(exc){setError(exc instanceof Error?exc.message:"Enregistrement mémoire impossible.");}
    finally{setMemoryBusy(false);}
  }

  async function workflowAction(id:string, action:"approve"|"cancel"):Promise<void> {
    setBusy(true); setError("");
    try { await api(`/city/api/workflows/${id}/${action}`, {}); await refresh(); }
    catch (exc) { setError(exc instanceof Error ? exc.message : "Action impossible."); }
    finally { setBusy(false); }
  }

  async function cancel(taskId: string): Promise<void> {
    setBusy(true);
    try {
      await api(`/city/api/tasks/${taskId}/cancel`, {});
      await refresh();
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Annulation impossible.");
    } finally { setBusy(false); }
  }

  async function sendChat(event: React.FormEvent): Promise<void> {
    event.preventDefault();
    await sendChatMessage(chatInput);
  }

  async function sendChatMessage(message: string, intent: boolean | string = false): Promise<void> {
    const text = message.trim();
    if (!text || chatBusy || chatAbort.current) return;
    const userMessage: ChatMessage = {role:"user",content:text,created_at:new Date().toISOString()};
    setChatMessages(rows => [...rows,userMessage,{role:"assistant",content:"",created_at:new Date().toISOString()}]);
    setChatInput(""); setChatBusy(true); setChatError(""); chatFollow.current=true; setChatAtBottom(true); setChatStatus("Connexion à l’agent…");
    const abort = new AbortController(); chatAbort.current = abort;
    try {
      const response = await fetch("/city/api/chat/desk_manager", {method:"POST",credentials:"same-origin",signal:abort.signal,
        headers:{"Content-Type":"application/json","X-MarketDesk-City":"1"},
        body:JSON.stringify({message:text,selection:intent?{intent:intent===true?"development_report":intent}:undefined})});
      if (!response.ok) {
        const data = await response.json().catch(()=>({detail:`Erreur HTTP ${response.status}`}));
        throw new Error(String(data.detail || "La conversation n’a pas pu démarrer."));
      }
      if (!response.body) throw new Error("Le flux de réponse est indisponible dans ce navigateur.");
      const reader = response.body.getReader(); const decoder = new TextDecoder(); let buffer = "";
      const handle = (raw: string) => {
        for (const line of raw.split("\n")) {
          if (!line.startsWith("data: ")) continue;
          try {
            const data = JSON.parse(line.slice(6)) as {type:string;text?:string;model?:string;name?:string;status?:ToolReceipt["status"]};
            if (data.type === "tool") {
              const receipt:ToolReceipt={name:data.name||"Service",status:data.status||"completed",text:data.text||""};
              setChatMessages(messages=>{const copy=[...messages], last=copy[copy.length-1];if(last?.role!=="assistant")return messages;
                const receipts=[...(last.tool_calls||[])];let index=-1;
                for(let i=receipts.length-1;i>=0;i--)if(receipts[i].name===receipt.name&&receipts[i].status==="running"){index=i;break;}
                if(index>=0&&receipt.status!=="running")receipts[index]=receipt;else receipts.push(receipt);
                copy[copy.length-1]={...last,tool_calls:receipts};return copy;});
              setChatStatus(receipt.status==="running"?"Action en cours…":"Préparation du bilan…");
            }
            if (data.type === "status") setChatStatus(data.text || "L’agent rédige une réponse…");
            if (data.type === "replace") {
              setChatMessages(rows=>{const copy=[...rows],last=copy[copy.length-1];if(last?.role==='assistant')copy[copy.length-1]={...last,content:data.text||''};return copy;});
            }
            if (data.type === "delta") {
              setChatStatus("");
              setChatMessages(rows => {const copy=[...rows];const last=copy[copy.length-1];if(last?.role === "assistant")copy[copy.length-1]={...last,content:last.content+(data.text||"")};return copy;});
            }
            if (data.type === "error") { setChatError(data.text || "La génération a échoué."); setChatStatus(""); }
            if (data.type === "done") {
              setChatStatus("");
              setChatMessages(rows=>{const copy=[...rows],last=copy[copy.length-1];if(last?.role==='assistant')copy[copy.length-1]={...last,model:data.model};return copy;});
            }
          } catch { /* ignore incomplete event frames */ }
        }
      };
      while (true) { const part=await reader.read(); buffer+=decoder.decode(part.value||new Uint8Array(),{stream:!part.done});
        const frames=buffer.split("\n\n"); buffer=frames.pop()||""; frames.forEach(handle); if(part.done)break; }
      if (buffer.trim()) handle(buffer);
    } catch (exc) {
      if (exc instanceof DOMException && exc.name === "AbortError") setChatError("Réponse interrompue. Les actions déjà exécutées restent enregistrées.");
      else setChatError(exc instanceof Error ? exc.message : "La conversation a échoué.");
      setChatStatus("");
    } finally {
      setChatMessages(messages=>{const copy=[...messages], last=copy[copy.length-1];if(last?.role!=='assistant')return messages;
        copy[copy.length-1]={...last,tool_calls:last.tool_calls?.map(tool=>tool.status==='running'?{...tool,status:'unavailable',text:'Résultat non confirmé. Consulte les missions avant de relancer.'}:tool)};return copy;});
      setChatBusy(false); chatAbort.current=null; void refresh();
    }
  }

  async function clearChat(): Promise<void> {
    if (!window.confirm("Effacer toute la conversation avec Desk Manager ?")) return;
    if (chatBusy) chatAbort.current?.abort();
    try { await api("/city/api/chat/desk_manager/clear",{}); setChatMessages([]);setChatError(""); }
    catch (exc) { setChatError(exc instanceof Error ? exc.message : "Impossible d’effacer l’historique."); }
  }

  async function prepareMorningBriefing(): Promise<void> {
    if (chatBusy) return;
    setChatBusy(true); setChatError("");
    try {
      await api("/city/api/manager/briefing", {});
      await loadChat("desk_manager");
    } catch (exc) { setChatError(exc instanceof Error ? exc.message : "Briefing indisponible."); }
    finally { setChatBusy(false); }
  }

  async function approve(taskId:string):Promise<void> {
    setBusy(true);try{await api(`/city/api/tasks/${taskId}/approve`,{});await refresh();}
    catch(exc){setError(exc instanceof Error?exc.message:"Approbation impossible.");}finally{setBusy(false);}
  }
  async function retry(taskId:string):Promise<void> {
    setBusy(true);try{const response=await api<{task:{id:string;status:string}}>(`/city/api/tasks/${taskId}/retry`,{});setRetryNotice(`Nouvelle tentative créée et placée en file · ID ${response.task.id.slice(0,10)}`);setMissionFilter('pending');setOpenedTaskId(response.task.id);await refresh();}
    catch(exc){setError(exc instanceof Error?exc.message:"Nouvelle tentative impossible.");}finally{setBusy(false);}
  }
  async function checkIntegrations():Promise<void> {
    setDiagnosticsBusy(true);try{const data=await api<{integrations:Integration[]}>('/city/api/diagnostics');setDiagnostics(data.integrations);}
    catch(exc){setError(exc instanceof Error?exc.message:"Diagnostic indisponible.");}finally{setDiagnosticsBusy(false);}
  }
  async function saveSettings(event:React.FormEvent):Promise<void> {
    event.preventDefault();if(!settings)return;setSettingsBusy(true);
    try{const saved=await api<CitySettings>('/city/api/settings',settings);setSettings(saved);setSettingsOpen(false);await refresh();}
    catch(exc){setError(exc instanceof Error?exc.message:"Réglages non enregistrés.");}finally{setSettingsBusy(false);}
  }


  async function reviewProposal(taskId:string,approved:boolean) {
    try {await api(`/city/api/proposals/${taskId}/review`,{approved});await refresh();setError(approved?"Proposition transmise à Jules.":"Proposition refusée.");} catch(error){setError(error instanceof Error?error.message:"Validation impossible.");}
  }
  function showResult(task:Task):void {setResultTaskDetail(null);setResultTaskId(task.id);setOpenedTaskId(task.id);setSelectedId(task.agent_id);setWindowMode(windowMode==='missions'?'missions':'none');}
  async function showCodeResult(task:Task):Promise<void> {
    try {
      const detail=await api<Task>(`/city/api/tasks/${task.id}`);
      setResultTaskDetail(detail);setResultTaskId(task.id);setOpenedTaskId(task.id);setSelectedId(task.agent_id);setWindowMode('code');
    } catch(exc) {setError(exc instanceof Error?exc.message:'Résultat indisponible.');}
  }

  function codePanel():React.ReactElement {
    const tasks=codeHistory?.tasks||[];
    const calendar=new Intl.DateTimeFormat('en-CA',{timeZone:'Europe/Paris',year:'numeric',month:'2-digit',day:'2-digit'});
    const today=calendar.format(new Date());
    const isToday=(value?:string)=>!!value&&Number.isFinite(new Date(value).getTime())&&calendar.format(new Date(value))===today;
    const active=tasks.filter(task=>['queued','running','waiting_approval'].includes(task.status)&&(codeAgent==='all'||task.agent_id===codeAgent));
    const running=active.filter(task=>task.status==='running');
    const outcomes=tasks.filter(task=>!['queued','running','waiting_approval'].includes(task.status)&&(codeAgent==='all'||task.agent_id===codeAgent)&&(codePeriod==='month'||isToday(task.finished_at)));
    const integrated=outcomes.filter(task=>task.status==='completed'&&task.result.integrated===true);
    const other=outcomes.filter(task=>!integrated.includes(task));
    const analyses=other.filter(task=>task.status==='completed');
    const failures=other.filter(task=>['failed','cancelled'].includes(task.status));
    const team=[['job_hunter','Jules','Services City'],['city_ui_engineer','Camille','Interface'],['internships_engineer','Sacha','Internships'],['quality_engineer','Maël','Qualité']];
    const agentName=(id:string)=>snapshot?.agents.find(agent=>agent.id===id)?.name||id;
    const report=codeHistory?.report;
    async function runCodeAction(action:()=>Promise<unknown>,notice:string):Promise<void>{
      if(codeActionBusy)return;
      setCodeActionBusy(true);setCodeActionNotice('');
      try{await action();setCodeHistory(await api<CodingHistory>('/city/api/coding-history'));await refresh();setCodeActionNotice(notice);}
      catch(exc){setCodeActionNotice(exc instanceof Error?exc.message:'La mission n’a pas pu démarrer.');}
      finally{setCodeActionBusy(false);}
    }
    function workCard(task:Task):React.ReactElement {
      const applied=task.status==='completed'&&task.result.integrated===true;
      const status=applied?'Changement appliqué':task.status==='completed'?(task.result.already_present?'Déjà en place':'Analyse seule'):LABELS[task.status];
      const summary=task.result.plain_summary||task.result.summary;
      const activation=task.result.publication_status==='published'?'Publié sur Internships':
        task.result.publication_status==='pushed; awaiting GitHub Pages'?'Déploiement Internships en attente':
        ['blocked','deployment failed'].includes(task.result.publication_status||'')?'Publication Internships bloquée':
        task.result.live===true?'Actif dans City':task.result.live===false?'Activation à confirmer':'Activation non vérifiée';
      if(task.status==='completed')return <article className={`dev-work-card dev-change-row ${applied?'applied':'analysis'}`} key={task.id}>
        <span className={`roster-avatar pixel-agent-avatar ${task.agent_id}`} aria-hidden="true"><i className="agent-sprite"/></span>
        <div className="dev-change-copy"><h4>{summary?codeChangeSummary(task):'Résumé non renseigné — consulte le détail de la mission.'}</h4>
          <div className="dev-change-meta"><strong>{agentName(task.agent_id)}</strong><time>{dateTime(task.finished_at||task.created_at)}</time>
            {task.result.server_checks?.length?<span className="dev-change-check">✓ {task.result.server_checks.length} vérifications</span>:<span>Vérifications non renseignées</span>}
            <span>{applied?activation:status}</span>
          </div>
        </div>
        <button type="button" className="dev-change-open" onClick={()=>void showCodeResult(task)} aria-label={`Voir le détail · ${agentName(task.agent_id)} · ${task.description}`}><span>Détail</span> ↗</button>
      </article>;
      return <article className={`dev-work-card ${task.status} ${applied?'applied':''}`} key={task.id}>
        <div className="dev-work-meta"><span>{agentName(task.agent_id)} · {dateTime(task.finished_at||task.created_at)}</span><span className={`dev-status ${task.status}`}>{status}</span></div>
        <h4>{task.description}</h4>
        <p>{task.error||(task.last_event?.message==='Mission added to queue.'?'Mission enregistrée, en attente de démarrage.':task.last_event?.message)||codeChangeSummary(task)}</p>
        {task.status==='queued'&&task.scheduled_at&&<p className="dev-work-note">Prochaine tentative : {dateTime(task.scheduled_at)}</p>}
        {task.status==='running'&&<p className="dev-work-note">Dernier signe d’activité : {dateTime(task.heartbeat_at||task.last_event?.created_at||task.started_at)}</p>}
        {applied&&<p className="dev-work-note">{activation}</p>}
        {task.result.server_checks?.length?<details className="dev-checks"><summary>Vérifications réussies · {task.result.server_checks.length}</summary><ul>{task.result.server_checks.map((check,index)=><li key={index}>{check}</li>)}</ul></details>:applied&&<p className="dev-work-note">Détail des vérifications non enregistré.</p>}
        {task.result.limitations&&<details className="dev-checks"><summary>Limites et points à vérifier</summary><p>{task.result.limitations}</p></details>}
        <div className="dev-work-actions"><button type="button" className="secondary-button" onClick={()=>void showCodeResult(task)}>Voir le détail</button>{task.status==='failed'&&<button type="button" className="secondary-button" disabled={busy||codeActionBusy} onClick={()=>void runCodeAction(()=>api(`/city/api/tasks/${task.id}/retry`,{}),'Mission relancée. Son état apparaît dans la file de travail.')}>Relancer</button>}</div>
      </article>;
    }
    return <div className="code-team-panel dev-command-center dev-workspace">
      {codeHistoryError&&<p className="error-copy" role="alert">{codeHistoryError} · Les dernières données affichées peuvent être anciennes.</p>}
      {!codeHistory&&!codeHistoryError&&<p role="status">Chargement du travail des agents…</p>}
      {codeActionNotice&&<p className="dev-action-notice" role="status">{codeActionNotice}</p>}
      <div className="dev-journal-toolbar"><div className="dev-filters"><label>Période<select value={codePeriod} onChange={event=>{setCodePeriod(event.target.value);setCodeVisibleCount(12);}}><option value="today">Aujourd’hui</option><option value="month">31 derniers jours</option></select></label><label>Agent<select value={codeAgent} onChange={event=>{setCodeAgent(event.target.value);setCodeVisibleCount(12);}}><option value="all">Toute l’équipe</option>{team.map(([id,name])=><option key={id} value={id}>{name}</option>)}</select></label></div>{report&&<small>Actualisé à {new Intl.DateTimeFormat('fr-FR',{timeZone:'Europe/Paris',timeStyle:'short'}).format(new Date(report.generated_at))} · Paris</small>}</div>
      <section className="dev-journal-stats" aria-label="État du développement"><span className="dev-stat-delivered"><b>{integrated.length}</b> changements appliqués</span><span><i/> <b>{running.length}</b> en cours</span><span><b>{active.length-running.length}</b> en attente</span><span><b>{failures.length}</b> échecs ou annulations</span></section>
      <section className="dev-outcomes"><div className="dev-journal-heading"><div><span className="dev-eyebrow">LE JOURNAL DE L’ÉQUIPE</span><h3>Les dernières améliorations</h3></div><span className="dev-journal-caption">Appliquées au projet · {codePeriod==='today'?"aujourd’hui":'31 derniers jours'}</span></div>{integrated.length?<><div className="dev-change-list">{integrated.slice(0,codeVisibleCount).map((task,index)=>{
        const previous=integrated[index-1];const newDay=!previous||calendar.format(new Date(previous.finished_at||previous.created_at))!==calendar.format(new Date(task.finished_at||task.created_at));
        return <React.Fragment key={task.id}>{newDay&&<div className="dev-change-date">{isToday(task.finished_at)?'Aujourd’hui':new Intl.DateTimeFormat('fr-FR',{timeZone:'Europe/Paris',day:'numeric',month:'long'}).format(new Date(task.finished_at||task.created_at))}</div>}{workCard(task)}</React.Fragment>;
      })}</div>{integrated.length>codeVisibleCount&&<button type="button" className="dev-load-more" onClick={()=>setCodeVisibleCount(count=>count+12)}>Afficher les {Math.min(12,integrated.length-codeVisibleCount)} suivantes <span>· {integrated.length-codeVisibleCount} restantes</span></button>}</>:<p className="dev-empty">Aucun changement appliqué sur cette période. Consulte les missions en cours ci-dessous.</p>}</section>
      <details className="dev-new-mission"><summary>Confier une nouvelle mission</summary><form onSubmit={event=>{event.preventDefault();void runCodeAction(async()=>{await api(`/city/api/develop/${codeAssignee}`,{request:codeRequest});setCodeRequest('');},'Mission enregistrée et ajoutée à la file de travail.');}}><label htmlFor="dev-assignee">Agent</label><select id="dev-assignee" value={codeAssignee} onChange={event=>setCodeAssignee(event.target.value)}>{team.map(([id,name,role])=><option key={id} value={id}>{name} · {role}</option>)}</select><label htmlFor="code-team-request">Le résultat attendu</label><textarea id="code-team-request" minLength={10} maxLength={2000} required rows={3} value={codeRequest} onChange={event=>setCodeRequest(event.target.value)} placeholder="Décris le problème et ce que tu souhaites obtenir…"/><button type="submit" className="primary-button" disabled={codeActionBusy||codeRequest.trim().length<10}>Lancer la mission</button><small>Travail isolé, vérification puis intégration automatique si les contrôles réussissent.</small></form></details>
      <section className="dev-active"><div className="section-heading"><h3>En cours et en attente <span className="dev-count">{active.length}</span></h3></div>{active.length?<div className="dev-work-grid">{active.map(workCard)}</div>:<p className="dev-empty">Aucune mission en cours ou en attente.</p>}</section>
      <details className="dev-history"><summary>Analyses sans modification <span>{analyses.length}</span></summary>{analyses.length?<div className="dev-work-grid">{analyses.map(workCard)}</div>:<p className="dev-empty">Aucune analyse seule sur cette période.</p>}</details>
      <details className="dev-history"><summary>Échecs et annulations <span>{failures.length}</span></summary>{failures.length?<div className="dev-work-grid">{failures.map(workCard)}</div>:<p className="dev-empty">Aucun échec sur cette période.</p>}</details>
    </div>;
  }


  function managerPanel(): React.ReactElement {
    const allTasks = (snapshot?.tasks || []).filter(task=>agentGroup(task.agent_id)!=='Développement');
    const controlTasks = allTasks.filter(t=>missionFilter==="all"||missionFilter==="active"&&['queued','running'].includes(t.status)||missionFilter==="pending"&&(["queued","waiting_approval"].includes(t.status)||isPendingProposal(t))||missionFilter==="completed"&&t.status==="completed"||missionFilter==="failed"&&["failed","cancelled"].includes(t.status));
    const selectedMission=controlTasks.find(task=>task.id===openedTaskId)||controlTasks[0];
    const renderTask = (task:Task) => {
      const assigned = snapshot?.agents.find(agent=>agent.id===task.agent_id)?.name||task.agent_id;
      const dependencies = (task.depends_on||[]).map(id=>snapshot?.tasks.find(item=>item.id===id));
      const needsApproval = task.status === "waiting_approval" && (!task.workflow_id ||
        snapshot?.tasks.find(item=>item.workflow_id===task.workflow_id)?.id === task.id);
      const summary = task.result.summary || task.result.text || task.result.title ||
        (task.result.new_count !== undefined ? `${task.result.new_count} nouvelle(s) offre(s) sur ${task.result.total_count ?? "?"}.` : "");
      return <article className={`mission-record ${task.status} ${openedTaskId===task.id?'mission-highlight':''}`} key={task.id}>
        <div className="mission-record-head"><div><span className="mission-team-label">{agentGroup(task.agent_id)}</span><button className="mission-title" type="button" onClick={()=>{setOpenedTaskId(task.id);setSelectedId(task.agent_id);}}>{task.description}</button><small>{assigned}{task.delegated_by?` / transmis par ${snapshot?.agents.find(agent=>agent.id===task.delegated_by)?.name||task.delegated_by}`:""}</small></div><span className={`task-chip ${task.status}`}>{LABELS[task.status]}</span></div>
        <div className="mission-record-meta"><time>{dateTime(task.created_at)}</time><code title={`Identifiant persistant : ${task.id}`}>#{task.id.slice(0,10)}</code>{(task.retry_count||0)>0&&<span>Tentative {(task.retry_count||0)+1}</span>}{task.retry_of&&<button type="button" className="mission-retry-link" onClick={()=>{setOpenedTaskId(task.retry_of||null);setMissionFilter('failed')}}>Issue de #{task.retry_of.slice(0,10)}</button>}{task.workflow_id&&<span>Projet {task.workflow_id.slice(0,8)}</span>}</div>
        {allTasks.filter(candidate=>candidate.retry_of===task.id).map(candidate=><button key={candidate.id} type="button" className="mission-retry-link" onClick={()=>{setOpenedTaskId(candidate.id);setMissionFilter(['queued','running'].includes(candidate.status)?'active':candidate.status==='failed'?'failed':'completed')}}>↻ Tentative #{candidate.id.slice(0,10)} · {LABELS[candidate.status]} →</button>)}
        {!!dependencies.length&&<div className="mission-dependencies"><b>{dependencies.filter(d=>d?.status==="completed").length}/{dependencies.length} prérequis terminés</b>{dependencies.map((dependency,index)=><span key={task.depends_on?.[index]} title={task.depends_on?.[index]}>{dependency?`${snapshot?.agents.find(agent=>agent.id===dependency.agent_id)?.name||dependency.agent_id} / ${LABELS[dependency.status]}`:`ID ${task.depends_on?.[index].slice(0,10)} indisponible`}</span>)}</div>}
        {task.status==="waiting_approval"&&<p className="mission-record-result">Cette mission attend ta validation avant ex&eacute;cution.</p>}
        {summary&&<p className="mission-record-result">{summary}</p>}
        {["completed","failed"].includes(task.status)&&<button type="button" className="secondary-button result-open" onClick={()=>showResult(task)}>{task.status==="failed"?"Voir l’erreur":"Voir le résultat"} ↗</button>}
        {task.status==="failed"&&<p className="error-copy">{task.error||"La mission a &eacute;chou&eacute; sans d&eacute;tail suppl&eacute;mentaire."}</p>}
        <details className="mission-log"><summary>Étapes, résultat et journal</summary>{task.started_at&&<p>Démarrée · {dateTime(task.started_at)}</p>}{task.finished_at&&<p>Terminée · {dateTime(task.finished_at)}</p>}{(snapshot?.events||[]).filter(e=>e.task_id===task.id).sort((a,b)=>a.id-b.id).map(e=><p key={e.id}><time>{dateTime(e.created_at)}</time> · {e.message}</p>)}{Object.keys(task.result||{}).length>0&&<pre>{JSON.stringify(task.result,null,2)}</pre>}</details>
        <div className="mission-record-actions">
          {needsApproval&&<button type="button" className="primary-button compact-button" disabled={busy} onClick={()=>task.workflow_id?void workflowAction(task.workflow_id,"approve"):void approve(task.id)}>Valider</button>}
          {!task.read_only&&task.status==="failed"&&(!task.workflow_id||(task.retry_count||0)<(task.max_retries||0))&&<button type="button" className="secondary-button compact-button" disabled={busy} onClick={()=>void retry(task.id)}>R&eacute;essayer</button>}
          {!task.read_only&&(task.status==="queued"||task.status==="waiting_approval")&&<button type="button" className="text-button" disabled={busy} onClick={()=>task.workflow_id?void workflowAction(task.workflow_id,"cancel"):void cancel(task.id)}>Annuler</button>}
        </div>
      </article>;
    };
    return <div className="task-panel-content manager-panel" key={missionSection}>
      {missionSection==='follow'&&<section className="mission-control-register"><div className="section-heading"><div><h3>Suivi des missions</h3><small>{allTasks.filter(task=>task.status==="running").length} en cours &middot; {allTasks.filter(task=>task.status==="waiting_approval"||isPendingProposal(task)).length} &agrave; valider</small></div><button type="button" className="secondary-button compact-button" onClick={()=>setMissionSection('launch')}>Nouvelle mission +</button></div>
        {retryNotice&&<div className="mission-retry-notice" role="status">↻ {retryNotice}<button type="button" onClick={()=>setRetryNotice('')} aria-label="Masquer le message">×</button></div>}
        <div className="mission-filters" role="group" aria-label="Filtrer les missions">{[["active","Actives"],["pending","En attente"],["completed","Terminées"],["failed","Erreurs"],["all","Toutes"]].map(([id,label])=><button type="button" key={id} aria-pressed={missionFilter===id} onClick={()=>setMissionFilter(id)}>{label}</button>)}</div>
        {!controlTasks.length?<p className="muted">Aucune mission pour ce filtre.</p>:<div className="mission-follow-layout"><div className="mission-record-list">{controlTasks.map(renderTask)}</div><aside className="mission-detail-sidebar"><span className="mission-team-label">MISSION SÉLECTIONNÉE</span>{selectedMission?<><h3>{selectedMission.description}</h3><p>{selectedMission.result.summary||selectedMission.result.text||selectedMission.error||LABELS[selectedMission.status]}</p><small>{snapshot?.agents.find(agent=>agent.id===selectedMission.agent_id)?.name||selectedMission.agent_id} · {dateTime(selectedMission.finished_at||selectedMission.created_at)}</small>{selectedMission.error&&<p className="error-copy">{selectedMission.error}</p>}{!!selectedMission.result.files?.length&&<><h4>Fichiers modifiés</h4><ul>{selectedMission.result.files.map(file=><li key={file}><code>{file}</code></li>)}</ul></>}{(snapshot?.events||[]).filter(event=>event.task_id===selectedMission.id).slice(-5).map(event=><p className="mission-detail-event" key={event.id}><time>{dateTime(event.created_at)}</time><br/>{event.message}</p>)}<button type="button" className="secondary-button" onClick={()=>showResult(selectedMission)}>Ouvrir le résultat complet →</button></>:<p>Choisis une mission pour afficher son suivi.</p>}</aside></div>}

      </section>}
      {missionSection==='launch'&&<div className="mission-organize">
      <form className="manager-form" onSubmit={startWorkflow}>
        <label>Processus<select value={workflowTemplate} onChange={event=>setWorkflowTemplate(event.target.value)}>
          <option value="careers_outreach">Offres · contacts · brouillon</option>
          <option value="market_learning">Marchés · recherche quantitative</option>
          <option value="source_review">Jules · revue du code</option><option value="interview_training">Axel · préparation aux entretiens</option><option value="innovation_engineering">Nova · innovations</option>
        </select></label>
        <label>Objectif<textarea rows={2} value={mission} maxLength={500} onChange={event=>setMission(event.target.value)} placeholder="Trouver des stages Fixed Income Sales à Paris et préparer une prise de contact"/></label>
        <div className="manager-fields"><label>Thème de recherche<input value={workflowFocus} maxLength={100} onChange={event=>setWorkflowFocus(event.target.value)} placeholder="Fixed Income Sales"/></label>
          <label>Priorité<select value={workflowPriority} onChange={event=>setWorkflowPriority(Number(event.target.value))}><option value={0}>Normale</option><option value={1}>Élevée</option><option value={2}>Urgente</option></select></label></div>
        <button type="submit" className="primary-button" disabled={busy||!mission.trim()}>{busy?"Préparation...":"Lancer le projet"}</button>
      </form>
      <details className="workflow-builder">
        <summary>Workflow personnalisé <span>Créer des étapes ou relancer un scénario enregistré</span></summary>
        <div className="section-heading"><div><h3>Constructeur de workflows</h3><small>Relie les étapes et enregistre ton scénario pour le relancer en un clic.</small></div>
          <button type="button" className="secondary-button compact-button" onClick={newWorkflowDefinition}>Nouveau</button></div>
        <label className="workflow-name-field">Nom du workflow
          <input value={workflowName} maxLength={80} onChange={event=>setWorkflowName(event.target.value)} placeholder="Ex. Recherche Fixed Income puis prise de contact"/>
        </label>
        <div className="workflow-builder-steps">
          {workflowSteps.map((step,index)=><React.Fragment key={step.id}>
            {index>0&&<div className="workflow-connector" aria-hidden="true"><span>↓</span></div>}
            <article className="workflow-builder-step">
              <div className="workflow-builder-top"><span className="workflow-step-number">{String(index+1).padStart(2,"0")}</span>
                <strong>{snapshot?.agents.find(agent=>agent.id===step.agent_id)?.name||step.agent_id}</strong>
                <button type="button" className="text-button" onClick={()=>removeWorkflowStep(index)} disabled={workflowSteps.length<=1} aria-label="Supprimer cette étape">Retirer</button></div>
              <div className="workflow-builder-fields">
                <label>Agent<select value={step.agent_id} onChange={event=>updateWorkflowStep(index,{agent_id:event.target.value,operation:SPECIALIST_OPERATIONS[event.target.value]})}>
                  {INITIAL_IDS.filter(id=>id!=="desk_manager").map(id=><option key={id} value={id}>{snapshot?.agents.find(agent=>agent.id===id)?.name||id}</option>)}
                </select></label>
                <label>Consigne<textarea rows={2} value={step.description} maxLength={240} onChange={event=>updateWorkflowStep(index,{description:event.target.value})}/></label>
              </div>
              {index>0&&<fieldset className="workflow-dependencies"><legend>Cette étape attend</legend>
                {workflowSteps.slice(0,index).map(prior=><label key={prior.id}>
                  <input type="checkbox" checked={step.depends_on.includes(prior.id)} onChange={()=>toggleWorkflowDependency(index,prior.id)}/>
                  <span>{snapshot?.agents.find(agent=>agent.id===prior.agent_id)?.name||prior.agent_id}</span>
                </label>)}
                <small>Décoche tout pour lancer cette étape en parallèle.</small>
              </fieldset>}
            </article>
          </React.Fragment>)}
        </div>
        <div className="workflow-builder-actions">
          <button type="button" className="secondary-button" onClick={addWorkflowStep} disabled={workflowSteps.length>=7}>+ Ajouter une étape</button>
          <button type="button" className="primary-button" onClick={()=>void saveWorkflowDefinition()} disabled={busy||!workflowName.trim()||workflowSteps.some(step=>!step.description.trim())}>
            {busy?"Enregistrement…":editingWorkflowId?"Enregistrer les changements":"Enregistrer le workflow"}
          </button>
        </div>
        {!!workflowDefinitions.length&&<div className="saved-workflows"><strong>Mes workflows enregistrés</strong>
          {workflowDefinitions.map(definition=><article className="saved-workflow" key={definition.id}>
            <div><b>{definition.name}</b><small>{definition.steps.map(step=>snapshot?.agents.find(agent=>agent.id===step.agent_id)?.name||step.agent_id).join(" → ")}</small></div>
            <div className="saved-workflow-actions">
              <button type="button" className="text-button" onClick={()=>editWorkflowDefinition(definition)}>Modifier</button>
              <button type="button" className="primary-button compact-button" disabled={busy} onClick={()=>void runSavedWorkflow(definition)}>Relancer</button>
            </div>
          </article>)}
        </div>}
      </details>
      <details className="memory-center">
        <summary><span>Mémoire partagée</span><small>{memoryEntries.length} élément(s) · compte actuel</small></summary>
        <p className="memory-note">Recherche locale par mots-clés et synonymes, sans appel IA. Les offres gardées en mémoire restent historiques.</p>
        <form className="memory-search" onSubmit={searchMemory}>
          <input value={memoryQuery} maxLength={240} onChange={event=>setMemoryQuery(event.target.value)} placeholder="Rechercher une offre, un contact, une décision…"/>
          <button type="submit" className="secondary-button">Rechercher</button>
        </form>
        <div className="memory-results">{memoryEntries.slice(0,8).map(entry=><article key={entry.id}>
          <div><b>{entry.title}</b><small>{snapshot?.agents.find(agent=>agent.id===entry.agent_id)?.name||entry.agent_id} · {entry.kind} · {dateTime(entry.updated_at)}</small></div>
          <p>{entry.content}</p>
        </article>)}
          {!memoryEntries.length&&<small className="muted">La mémoire se remplit après les missions. Tu peux aussi enregistrer une préférence durable.</small>}
        </div>
        <form className="memory-save" onSubmit={saveMemoryEntry}>
          <label>Préférence à retenir<input value={memoryTitle} maxLength={120} onChange={event=>setMemoryTitle(event.target.value)} placeholder="Ex. Types de postes à privilégier"/></label>
          <label>Détail<textarea rows={2} value={memoryContent} maxLength={1000} onChange={event=>setMemoryContent(event.target.value)} placeholder="Décris une préférence durable pour tes recherches."/></label>
          <button type="submit" className="secondary-button" disabled={memoryBusy||!memoryTitle.trim()||!memoryContent.trim()}>{memoryBusy?"Enregistrement…":"Mémoriser"}</button>
        </form>
      </details>
      </div>}
      {missionSection==='projects'&&<div className="mission-projects-view">
      <section className="manager-projects"><div className="section-heading"><h3>Suivi des projets</h3><span>{snapshot?.workflows.length||0}</span></div>
        {!snapshot?.workflows.length&&<p className="muted">Aucun projet lancé. Les résultats resteront ici après ta prochaine visite.</p>}
        {snapshot?.workflows.map(workflow=><article className="workflow-card" key={workflow.id}>
          <div className="workflow-head"><strong>{workflow.request}</strong><span className={`task-chip ${workflow.status}`}>{LABELS[workflow.status]}</span></div>
          <small><code title={`Identifiant persistant : ${workflow.id}`}>Workflow {workflow.id}</code> &middot; {dateTime(workflow.created_at)} · Priorité {workflow.priority+1}</small>
          <ol className="workflow-steps">{workflow.steps.map(step=><li key={step.id} className={step.status}>
            <span className="workflow-step-top"><b>{snapshot?.agents.find(a=>a.id===step.agent_id)?.name||step.agent_id}</b><span>{LABELS[step.status]}</span></span>
            <small><code title={`Identifiant de tâche : ${step.id}`}>ID {step.id}</code> &middot; {step.description}{step.status==="queued"&&step.depends_on.length?" · attend les étapes précédentes":""}</small>
            {!!step.depends_on.length&&<div className="mission-dependencies"><b>Dépend de</b>{step.depends_on.map(id=>{const parent=snapshot?.tasks.find(task=>task.id===id);return <span key={id} title={id}>{parent?`${snapshot?.agents.find(a=>a.id===parent.agent_id)?.name||parent.agent_id} · ${LABELS[parent.status]}`:`ID ${id.slice(0,10)}`}</span>;})}</div>}
            {step.error&&<p className="error-copy">{step.error}</p>}
            {step.status==="failed"&&step.retry_count<step.max_retries&&<button type="button" className="text-button" disabled={busy} onClick={()=>void retry(step.id)}>Réessayer ({step.retry_count+1}/{step.max_retries})</button>}
          </li>)}</ol>
          {(workflow.status==="queued"||workflow.status==="waiting_approval"||workflow.status==="running")&&<div className="task-actions">
            {workflow.status==="waiting_approval"&&<button type="button" className="primary-button" disabled={busy} onClick={()=>void workflowAction(workflow.id,"approve")}>Approuver</button>}
            <button type="button" className="secondary-button" disabled={busy} onClick={()=>void workflowAction(workflow.id,"cancel")}>Annuler la suite</button></div>}
          {workflow.result.length>0&&<details className="workflow-results"><summary>Voir les résultats réunis</summary>{workflow.result.map((item,index)=><div key={index}>
            <strong>{snapshot?.agents.find(a=>a.id===item.agent_id)?.name||item.agent_id}</strong>
            {item.error?<p>{item.error}</p>:<><p>{item.result.text||item.result.title||"Étape terminée."}</p>
              {item.result.offers?.slice(0,5).map(offer=><a key={offer.url} href={offer.url} target="_blank" rel="noopener noreferrer">{offer.title} · {offer.company}</a>)}
              {item.result.contacts?.slice(0,5).map(contact=><p key={contact.id}>{contact.name} · {contact.company}</p>)}
              {item.result.body&&<pre>{item.result.body}</pre>}</>}</div>)}</details>}
        </article>)}</section>
      </div>}
    </div>;
  }

  const managerChat = <section className="chat-section" aria-label="Conversation avec Desk Manager">
            <div className="manager-chat-toolbar"><div className="manager-queue-summary"><span><b>{(snapshot?.tasks||[]).filter(t=>t.status==='running').length}</b> en cours</span><span><b>{(snapshot?.tasks||[]).filter(t=>['queued','waiting_approval'].includes(t.status)).length}</b> en attente</span><span><b>{(snapshot?.tasks||[]).filter(t=>t.status==='failed').length}</b> échecs récents</span></div><button type="button" className="text-button" onClick={()=>void clearChat()} disabled={chatBusy}>Effacer l’historique</button></div>
            <div className="manager-chat-shortcuts" aria-label="Demandes rapides">{[
              ['Bilan du code','Fais le bilan du développement aujourd’hui : changements intégrés, vérifications, échecs et travaux en attente.','development_report'],
              ['Bilan du jour','Présente le bilan du jour : développement, contacts et stages.','daily_summary'],
              ['Bilan des contacts','Quels sont les derniers résultats de Lina, Clara et Élodie ?','contacts_report'],
              ['Reprendre les missions en attente','Reprends maintenant les missions en attente, jusqu’à huit, en conservant leurs dépendances. Indique ce qui a réellement été remis en file.','resume_pending'],
              ['Relancer les échecs récents','Vérifie les missions récentes en échec et relance celles qui peuvent reprendre, jusqu’à huit. Explique les reprises et les blocages restants.','resume_failed']
            ].map(([label,message,intent])=><button type="button" key={label} disabled={chatBusy||(intent!=='development_report'&&!snapshot?.manager_console_version)} title={intent!=='development_report'&&!snapshot?.manager_console_version?'Disponible après le rechargement de City':''} onClick={()=>void sendChatMessage(message,intent)}>{label}</button>)}<button type="button" disabled={chatBusy} onClick={()=>void prepareMorningBriefing()}>Briefing</button></div>
            {!snapshot?.manager_console_version&&<small className="manager-reload-note">Les nouvelles commandes seront disponibles après le rechargement de City.</small>}
            <details className="manager-mission-overview"><summary>Suivi des missions <span>{(snapshot?.tasks||[]).filter(t=>['running','queued','waiting_approval'].includes(t.status)).length} actives · voir les dernières activités</span></summary>
              <div className="manager-mission-list">{(()=>{
                const tasks=snapshot?.tasks||[];
                const active=tasks.filter(t=>['running','queued','waiting_approval'].includes(t.status))
                  .sort((a,b)=>Number(b.status==='running')-Number(a.status==='running'));
                const recent=tasks.filter(t=>t.status==='failed');
                const shown=[...active.slice(0,4),...recent.slice(0,2)];
                return shown.length?shown.map(task=>{
                  const event=snapshot?.events.find(item=>item.task_id===task.id);
                  const dependencies=(task.depends_on||[]).map(id=>tasks.find(item=>item.id===id));
                  const blocked=dependencies.some(item=>!item||['failed','cancelled'].includes(item.status));
                  const waiting=dependencies.some(item=>item&&item.status!=='completed');
                  const detail=blocked?'Dépendance indisponible à examiner':waiting?'Attend la fin de ses dépendances':
                    task.error||(event?.message==='Mission added to queue.'?'Mission en attente de démarrage.':event?.message)||'Aucune étape détaillée enregistrée.';
                  return <article className="manager-mission-row" key={task.id}><div>
                    <strong>{snapshot?.agents.find(agent=>agent.id===task.agent_id)?.name||task.agent_id} · {LABELS[task.status]}</strong>
                    <span title={task.description}>{task.description}</span><small title={detail}>{detail}</small>
                    <small>{task.scheduled_at?`Prochaine tentative prévue : ${dateTime(task.scheduled_at)}`:task.heartbeat_at?`Dernier signe d’activité : ${dateTime(task.heartbeat_at)}`:event?.created_at?`Dernière activité : ${dateTime(event.created_at)}`:'Horaire de reprise non renseigné.'}</small>
                  </div><button type="button" onClick={()=>void openManagerMission(task.id)}>Ouvrir</button></article>;
                }):<p>Aucune mission active ou en échec récente.</p>;
              })()}</div>
              <button type="button" className="manager-all-missions" onClick={()=>switchTab('missions')}>Voir toutes les missions →</button>
            </details>
            <div className="chat-history" ref={chatScrollRef} aria-live="polite" aria-label="Historique de la conversation" onScroll={event=>{const el=event.currentTarget;chatFollow.current=el.scrollHeight-el.scrollTop-el.clientHeight<80;setChatAtBottom(chatFollow.current);}}>
              {!chatMessages.length&&<div className="chat-empty"><span className="portrait pixel-agent-avatar desk_manager" aria-hidden="true"><i className="agent-sprite"/></span><strong>Que veux-tu faire avancer ?</strong><p>Demande un bilan, une reprise de mission ou un nouveau travail. Les actions et leurs résultats restent dans cette conversation.</p></div>}
              {chatMessages.map((item,index)=><article key={item.id||`${item.created_at}-${index}`} className={`chat-message ${item.role}`}><span className="chat-role"><span className={`message-avatar ${item.role}`}>{item.role==="user"?"T":"D"}</span>{item.role==="user"?"Toi":deskManager?.name||"Desk Manager"}<time>{dateTime(item.created_at)}</time></span>{item.tool_calls?.map((tool,i)=><div key={i} className={`chat-tool-receipt ${tool.status}`}><span aria-hidden="true">{tool.status==="completed"?"✓":tool.status==="running"?"…":"!"}</span><div><strong>{tool.name}</strong><small>{tool.text}</small></div></div>)}{item.content?<MarkdownText text={item.content} onTaskClick={id=>void openManagerMission(id)}/>:chatBusy&&index===chatMessages.length-1?<span className="typing-indicator">Le Desk Manager prépare son retour…</span>:null}{item.model&&<small className="message-model">{item.model}</small>}</article>)}
              {(snapshot?.tasks||[]).filter(t=>t.status==="waiting_approval"||isPendingProposal(t)).map(t=><div className="approval-inline" key={t.id}><strong>Validation requise</strong><p>{t.description}</p><button type="button" onClick={()=>{if(isPendingProposal(t)){showResult(t);}else{setOpenedTaskId(t.id);setMissionFilter("pending");openAgent("desk_manager","missions");}}}>Examiner la proposition →</button></div>)}{chatError&&<p className="chat-error" role="alert">{chatError}</p>}</div>
            {!chatAtBottom&&<button type="button" className="chat-latest" onClick={()=>{chatFollow.current=true;setChatAtBottom(true);chatScrollRef.current?.scrollTo({top:chatScrollRef.current.scrollHeight});}}>Dernier message ↓</button>}
            {chatBusy&&<div className="manager-chat-progress" role="status"><span className="manager-progress-dot"/>{chatStatus||'Rédaction de la réponse…'}<time>{chatElapsed} s</time></div>}
            <form className="chat-composer" onSubmit={sendChat}><label className="sr-only" htmlFor="city-chat-input">Message au Desk Manager</label><textarea id="city-chat-input" rows={2} maxLength={3000} value={chatInput} onChange={event=>setChatInput(event.target.value)} onKeyDown={event=>{if(event.key==="Enter"&&!event.shiftKey){event.preventDefault();if(chatInput.trim()&&!chatBusy)event.currentTarget.form?.requestSubmit();}}} placeholder="D&eacute;cris ce que tu veux confier au Desk Manager..."/>
              <div className="chat-composer-bottom"><small>{chatInput.length}/3000 · Entrée pour envoyer · Maj + Entrée pour une nouvelle ligne</small>{chatBusy?<button type="button" className="secondary-button" onClick={()=>chatAbort.current?.abort()}>Interrompre la réponse</button>:<button type="submit" className="primary-button" disabled={!chatInput.trim()}>Envoyer</button>}</div></form>
          </section>;

  return <div className={`city-app game-app mode-${windowMode}`}>
    <aside className="city-sidebar" aria-label="Navigation principale">
      <button type="button" className="sidebar-brand" onClick={()=>switchTab('none')} aria-label="MarketDesk City, aller à la ville"><span className="city-brand-mark" aria-hidden="true"><i/><i/><i/><i/></span><span><strong>MarketDesk City</strong><small>Salle de marché · Agents IA</small></span></button>
      <span className="sidebar-section-label">TON ESPACE DE TRAVAIL</span>
      <nav className="sidebar-nav">
        <button className={windowMode==='none'||windowMode==='agent'?'active':''} onClick={()=>switchTab('none')}><SidebarIcon name="city"/><span>Ville</span></button>
        <button className={windowMode==='code'?'active':''} onClick={()=>switchTab('code')}><SidebarIcon name="code"/><span>Développement</span>{codeActiveCount>0&&<b>{codeActiveCount}</b>}</button>
        <button className={windowMode==='contacts'?'active':''} onClick={()=>switchTab('contacts')}><SidebarIcon name="contacts"/><span>Contacts</span></button>
        <button className={windowMode==='missions'?'active':''} onClick={()=>switchTab('missions')}><SidebarIcon name="missions"/><span>Missions</span>{activeCount>0&&<b>{activeCount}</b>}</button>
        <button className={windowMode==='agents'?'active':''} onClick={()=>switchTab('agents')}><SidebarIcon name="team"/><span>Équipe</span></button>
        <button className={windowMode==='internships'?'active':''} onClick={()=>switchTab('internships')}><SidebarIcon name="internships"/><span>Stages</span></button>
        <button className={windowMode==='activity'?'active':''} onClick={()=>{setNotificationView({filter:'all',agent:''});switchTab('activity');}}><SidebarIcon name="notifications"/><span>Notifications</span>{pendingCount>0&&<b>{pendingCount}</b>}</button>
        <button className={windowMode==='settings'?'active':''} onClick={()=>{switchTab('settings');setSettingsOpen(true);void loadSettings();}}><SidebarIcon name="settings"/><span>Réglages</span></button>
      </nav>
      <div className="sidebar-bottom"><button type="button" className="sidebar-manager" onClick={()=>switchTab('chat')}><span className="sidebar-manager-avatar" aria-hidden="true">DM</span><span><strong>Desk Manager</strong><small>Parler au coordinateur</small></span><span aria-hidden="true">↗</span></button><span><i className="live-dot"/> City active</span><form action="/logout" method="post"><button type="submit">Quitter</button></form></div>
    </aside>
    <header className="workspace-topbar"><div className="workspace-heading"><span className="workspace-emblem" aria-hidden="true"><SidebarIcon name="city"/></span><div className="workspace-title"><span className="tiny-label">MARKETDESK CITY</span><strong>{({none:'Ville',agent:snapshot?.agents.find(a=>a.id===selectedId)?.name||'Agent',code:'Développement',contacts:'Contacts',missions:'Missions',agents:'Équipe',activity:'Notifications',chat:'Desk Manager',markets:'Marchés',internships:'Stages',settings:'Réglages'} as Record<string,string>)[windowMode]||'MarketDesk City'}</strong></div></div><div className="workspace-activity" aria-label="Activité des missions"><button type="button" onClick={()=>switchTab('missions')}><span className="activity-indicator" aria-hidden="true"/><strong>{snapshot ? activeCount+codeActiveCount : '—'}</strong><span>en cours</span></button><button type="button" onClick={()=>{setNotificationView({filter:'all',agent:''});switchTab('activity');}}><SidebarIcon name="notifications"/><strong>{snapshot ? pendingCount : '—'}</strong><span>à examiner</span></button></div><div className="workspace-meta"><time className="workspace-date" dateTime={new Intl.DateTimeFormat('en-CA',{timeZone:'Europe/Paris',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date())}><span>PARIS</span>{new Intl.DateTimeFormat('fr-FR',{timeZone:'Europe/Paris',weekday:'short',day:'numeric',month:'short'}).format(new Date())}</time><span className="topbar-live"><i className="live-dot"/> EN LIGNE</span></div></header>
    <header className="city-header">
      <div className="city-brand"><span className="city-brand-mark" aria-hidden="true"><i/><i/><i/><i/></span><div><span className="city-kicker">GLOBAL MARKETS · AI AGENTS</span><h1>MarketDesk <em>City</em></h1></div></div>
      <div className="city-header-right"><span className="live-pill"><span className="live-dot"/> CITY ACTIVE</span><span className="city-subtitle">Huit agents et un Desk Manager reliés aux services existants.</span></div>
      <div className="city-header-actions"><button type="button" className="secondary-button" onClick={()=>{setSettingsOpen(true);void loadSettings();}}>R&eacute;glages</button>
        <form action="/logout" method="post" className="city-logout"><button type="submit">Quitter</button></form></div>
    </header>
    <div className="city-dashboard command-center city-full-width">
      <div className="world-column">
        <div className="world-toolbar"><div><span className="tiny-label">MARKETDESK CITY</span><strong>MarketDesk Tower</strong></div>
          <div className="world-controls" aria-label="Navigation du campus">
            <button type="button" className="collection-control jobs-control" title="Hugo recherche les stages publiés aujourd’hui" onClick={()=>void launchCollection("internships")}
              disabled={collectionBusy!==null||internshipCollectionActive} aria-label="Rechercher les nouvelles offres de stage">
              {collectionBusy==="internships"||internshipCollectionActive?"…":"↻"}<span>{internshipCollectionActive?"Recherche en cours":"Stages"}</span></button>
            <button type="button" title="Plein écran" onClick={()=>{const node=document.querySelector(".world-column");if(!document.fullscreenElement)void node?.requestFullscreen();else void document.exitFullscreen();}} aria-label="Plein écran">⛶</button>
          </div></div>
        <div className="world-stage tower-world"><PixelFloorGame agents={snapshot?.agents||[]} tasks={snapshot?.tasks||[]} events={snapshot?.events||[]}
          selectedId={selectedId} onPick={id=>openAgent(id)} onTaskPick={inspectCockpitTask}/>
           <div className="command-topbar"><div className="game-brand-hud"><span className="city-brand-mark" aria-hidden="true"><i/><i/><i/><i/></span><div><strong>MarketDesk City</strong><small>Global Markets &middot; AI Tower</small></div></div>
           <div className="command-search"><span aria-hidden="true">⌕</span><input aria-label="Rechercher un agent ou une mission" placeholder="Rechercher un agent, une mission…" value={commandQuery} onChange={e=>setCommandQuery(e.target.value)}/>{commandQuery.trim()&&<div className="command-search-results">{AGENT_GROUP_LABELS.map(group=>{const agents=(snapshot?.agents||[]).filter(a=>agentGroup(a.id)===group&&(a.name+' '+a.role).toLowerCase().includes(commandQuery.toLowerCase()));return agents.length?<div className="command-result-group" key={group}><strong>{group}</strong>{agents.map(a=><button key={a.id} onClick={()=>{openAgent(a.id);setCommandQuery('');}}>{a.name}<small>{a.role}</small></button>)}</div>:null})}{(snapshot?.tasks||[]).filter(t=>t.description.toLowerCase().includes(commandQuery.toLowerCase())).slice(0,5).map(t=><button key={t.id} onClick={()=>{showResult(t);setCommandQuery("");}}>{t.description}<small>{agentGroup(t.agent_id)} · {LABELS[t.status]}</small></button>)}<button onClick={()=>setCommandQuery("")}>Fermer la recherche</button></div>}</div>
          <nav className="game-hud" aria-label="Espaces MarketDesk City">
            <button type="button" className={windowMode==="none"?"active":""} onClick={()=>switchTab("none")} aria-label="Ville" aria-pressed={windowMode==="none"}><span>Ville</span></button>
             <button type="button" className={windowMode==="agents"?"active":""} onClick={()=>switchTab("agents")} aria-label="Équipe" aria-pressed={windowMode==="agents"}><span>Équipe</span></button>
            <button type="button" className={windowMode==="missions"?"active":""} onClick={()=>switchTab("missions")} aria-label="Missions" aria-pressed={windowMode==="missions"}><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" aria-hidden="true"><rect x="4" y="5" width="16" height="16" rx="2"/><path d="M9 3h6v4H9zM8 12h8M8 16h5"/></svg><span>Missions</span>{activeCount>0&&<b>{activeCount}</b>}</button>
            <button type="button" className={windowMode==="code"?"active":""} onClick={()=>switchTab("code")} aria-label="Développement" aria-pressed={windowMode==="code"}><span>Code</span>{codeActiveCount>0&&<b>{codeActiveCount}</b>}</button>
            <button type="button" className={windowMode==="activity"?"active":""} onClick={()=>{if(windowMode==="activity")switchTab("activity");else{setResultTaskId(null);setResultTaskDetail(null);openNotifications();}}} aria-label="Notifications" aria-pressed={windowMode==="activity"}><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" aria-hidden="true"><path d="M2 12h5l3-8 4 16 3-8h5"/></svg><span>Notifications</span>{(pendingCount>0||(snapshot?.events||[]).some(e=>e.id>notificationReadThrough))&&<b>{Math.max(pendingCount,(snapshot?.events||[]).filter(e=>e.id>notificationReadThrough).length)}</b>}</button>
            <button type="button" className={windowMode==="contacts"?"active":""} onClick={()=>switchTab("contacts")} aria-label="Contacts" aria-pressed={windowMode==="contacts"}><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" aria-hidden="true"><circle cx="9" cy="8" r="3"/><path d="M3 21v-3a6 6 0 0 1 12 0v3M16 5a3 3 0 0 1 0 6M21 21v-3a6 6 0 0 0-4-5"/></svg><span>Contacts</span></button>
            <button type="button" aria-label="Réglages" onClick={()=>{setSettingsOpen(true);void loadSettings();}}><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" aria-hidden="true"><path d="M4 7h16M4 17h16"/><circle cx="9" cy="7" r="3" fill="currentColor"/><circle cx="15" cy="17" r="3" fill="currentColor"/></svg><span>Réglages</span></button>
            <form action="/logout" method="post" className="city-logout"><button type="submit">Quitter</button></form>
           </nav></div>
          <div className="game-status-hud"><i className="live-dot"/> City active <small>{snapshot?.today_completed??0} missions aujourd’hui</small></div>
          <div className="world-hint">S&eacute;lectionne un bureau ou un robot pour ouvrir son espace.</div></div>
        <div className="world-footer"><span><i className="room-dot trading"/> March&eacute;s</span><span><i className="room-dot career"/> Carri&egrave;res</span><span><i className="room-dot lab"/> Laboratoire</span><span className="world-footer-note">Les robots r&eacute;agissent aux missions et transferts r&eacute;els.</span></div>      </div>
    </div>
    {windowMode==="agent"&&<section className="game-popup agent-dialog" role="dialog" aria-label="Fiche de l’agent">
        <Cockpit compact agents={snapshot?.agents||[]} tasks={snapshot?.tasks||[]} events={snapshot?.events||[]} selectedId={selectedId}
          onSelect={id=>setSelectedId(id)} onCollapse={()=>setWindowMode("none")}
          onNotifications={openNotifications} onOpen={inspectCockpitTask}
          onChat={message=>{if(message)setChatInput(message);openAgent("desk_manager","chat");}}
          onContacts={()=>setWindowMode("contacts")} onCancel={id=>api(`/city/api/tasks/${id}/cancel`,{})}
          onLaunch={id=>id==="internship_scout"?api('/city/api/collect/internships',{}):id==="market_analyst"?api('/city/api/collect/markets',{}):id==="job_hunter"?api('/city/api/develop/job_hunter',{}):api(`/city/api/agents/${id}/run`,{})}
          onDevelop={(id,request='')=>api(`/city/api/develop/${id}`,{request})}
          onReview={()=>api('/city/api/jules/review',{})} onCode={request=>api('/city/api/jules/change',{request})} onRefresh={refresh}/>
      </section>}
    {windowMode==="agents"&&<section className="game-popup team-directory" role="dialog" aria-label="Équipe MarketDesk City"><div className="game-popup-heading"><div><strong>Ton équipe</strong><small>Choisis un agent pour voir son activité et lui confier une mission.</small></div><button type="button" onClick={()=>setWindowMode('none')} aria-label="Fermer">×</button></div><div className="team-directory-body">{agentSections(snapshot?.agents||[]).map(({label,agents})=><section className="team-directory-section" data-team={label} key={label}><header><h3>{label}</h3><span>{agents.length} agent{agents.length>1?'s':''}</span></header><div className="team-directory-grid">{agents.map(agent=>{const current=(snapshot?.tasks||[]).find(task=>task.agent_id===agent.id&&['running','queued'].includes(task.status));return <button type="button" className="team-directory-card" key={agent.id} onClick={()=>openAgent(agent.id)}><span className={`roster-avatar pixel-agent-avatar ${agent.id}`} aria-hidden="true"><i className="agent-sprite"/></span><span><strong>{agent.name}</strong><small>{agent.role}</small><em>{current?`${LABELS[current.status]} · ${current.description}`:'Disponible pour une mission'}</em></span><b aria-hidden="true">↗</b></button>})}</div></section>)}</div></section>}
    {windowMode==="chat"&&<ManagerChatWindow onClose={()=>setWindowMode("none")}>{managerChat}</ManagerChatWindow>}
    {windowMode==="contacts"&&<NetworkContactsWindow onClose={()=>setWindowMode("none")} irisStatus={LABELS[snapshot?.agents.find(agent=>agent.id==='outreach_agent')?.status||'idle']} onIrisAction={(name,action)=>{setChatInput(action==='message'?`Demande à Iris de préparer un brouillon adapté pour ${name}. Ne rien envoyer sans ma validation.`:`Demande à Iris de retrouver les brouillons et échanges enregistrés pour ${name}.`);setWindowMode('chat');}}/>}
    {windowMode==="missions"&&<section className="game-popup game-mission-control" role="dialog" aria-label="Missions">
      <div className="game-popup-heading"><div><strong>Missions</strong><small>Activité des agents métier · {activeCount} en cours</small></div><button type="button" onClick={()=>setWindowMode("none")} aria-label="Fermer">&times;</button></div>
      <div className="mission-view-tabs" role="tablist" aria-label="Sections des missions"><button type="button" role="tab" aria-selected={missionSection==='follow'} onClick={()=>setMissionSection('follow')}>Suivi</button><button type="button" role="tab" aria-selected={missionSection==='launch'} onClick={()=>setMissionSection('launch')}>Lancer et organiser</button><button type="button" role="tab" aria-selected={missionSection==='projects'} onClick={()=>setMissionSection('projects')}>Projets <span>{snapshot?.workflows.length||0}</span></button></div>
      {managerPanel()}</section>}
    {windowMode==="code"&&<section className="game-popup game-mission-control game-code-control" role="dialog" aria-label="Équipe de développement"><div className="game-popup-heading"><div><strong>Développement</strong><small>Changements réalisés et état des missions</small></div><button type="button" onClick={()=>setWindowMode('none')} aria-label="Fermer">&times;</button></div>{codePanel()}</section>}
    {windowMode==="activity"&&<NotificationCenter key={`${notificationView.filter}-${notificationView.agent}`} initialFilter={notificationView.filter} initialAgent={notificationView.agent} tasks={snapshot?.tasks||[]} events={snapshot?.events||[]} agents={snapshot?.agents||[]} readThrough={notificationReadThrough}
      onClose={()=>setWindowMode("none")} onOpen={id=>{const task=snapshot?.tasks.find(t=>t.id===id);if(task)showResult(task);else setError("Cette mission n'est plus dans les données chargées.");}}
      onRead={async()=>{const result=await api<{last_read_event_id:number}>("/city/api/notifications/read",{read_through:Math.max(0,...(snapshot?.events||[]).map(e=>e.id))});setNotificationReadThrough(result.last_read_event_id);}}
      onApprove={id=>api(`/city/api/tasks/${id}/approve`,{})}
      onCancel={id=>api(`/city/api/tasks/${id}/cancel`,{})} onReview={(id,approved)=>api(`/city/api/proposals/${id}/review`,{approved})}
      onRetry={id=>api(`/city/api/tasks/${id}/retry`,{})} onRefresh={refresh}/>}
    {windowMode==='internships'&&<section className="game-popup internships-summary-window" role="region" aria-label="Stages"><div className="game-popup-heading"><div><strong>Stages r&eacute;cents</strong><small>{internshipHighlight?.recent_count||0} offres r&eacute;centes sur 7 jours &middot; {internshipHighlight?.total_count||0} suivies</small></div><div className="internships-summary-actions"><button type="button" className="secondary-button compact-button" disabled={collectionBusy!==null||internshipCollectionActive} onClick={()=>void launchCollection('internships')}>{internshipCollectionActive||collectionBusy==='internships'?'Recherche en cours':'Actualiser'}</button><button type="button" onClick={()=>setWindowMode('none')} aria-label="Fermer">&#215;</button></div></div><div className="internships-summary-list"><p className="catalogue-health" role="status"><a href="https://caruanatheo-beep.github.io/Internships-Offres/#offres" target="_blank" rel="noopener noreferrer">{internshipHighlight?.catalog_source==='public'?'Internships en ligne':'Cache de secours'}</a> · {internshipHighlight?.updated_at?dateTime(internshipHighlight.updated_at):'Date inconnue'} · {internshipHighlight?.source_errors||0} alerte(s) de source{internshipHighlight?.catalog_warning&&<span className="error-copy"> · {internshipHighlight.catalog_warning}</span>}</p>{internshipHighlight?.error?<p className="error-copy">{internshipHighlight.error}</p>:internshipHighlight?.recent_offers?.length?internshipHighlight.recent_offers.map(offer=><article className="internship-summary-card" key={offer.url}><div><strong>{offer.company}</strong><span>{offer.published_inferred?'D\u00e9tect\u00e9e le':'Publi\u00e9e le'} {offer.published||'date inconnue'}</span></div><h3>{offer.title}</h3><p>{[offer.kind,offer.location,offer.start_period].filter(Boolean).join(' | ')}</p><a href={/^https?:\/\//i.test(offer.url)?offer.url:undefined} target="_blank" rel="noopener noreferrer">Voir l'offre</a></article>):<div className="internships-summary-empty"><span className="internships-empty-icon" aria-hidden="true"><SidebarIcon name="internships"/></span><strong>Aucune nouvelle offre cette semaine</strong><p>{internshipHighlight?.updated_at?`Dernière actualisation : ${dateTime(internshipHighlight.updated_at)}.`:'Les nouvelles offres apparaîtront après la prochaine recherche.'}</p><button type="button" className="primary-button" disabled={collectionBusy!==null||internshipCollectionActive} onClick={()=>void launchCollection('internships')}>Rechercher de nouvelles offres</button></div>}</div></section>}
    {error&&<div className="city-toast" role="alert"><span>{error}</span><button type="button" onClick={()=>setError("")} aria-label="Fermer">&times;</button></div>}
    {resultTaskId&&<section className={`game-popup mission-results-window ${(resultTaskDetail||snapshot?.tasks.find(t=>t.id===resultTaskId))?.agent_id==='market_analyst'?'market-brief-window':''} ${(resultTaskDetail||snapshot?.tasks.find(t=>t.id===resultTaskId))?.result.branch?'code-results-window':''}`} role="dialog" aria-label="Résultat de mission"><div className="game-popup-heading"><div><strong>Résultat de mission</strong><small>Contributions enregistrées par les agents</small></div><button type="button" onClick={()=>{setResultTaskId(null);setResultTaskDetail(null);}} aria-label="Fermer le résultat">×</button></div><div className="mission-results-body">
      {(()=>{const root=resultTaskDetail||snapshot?.tasks.find(t=>t.id===resultTaskId);if(!root)return <p>Cette mission n’est plus disponible dans les données chargées.</p>;
        const parts=root.workflow_id?(snapshot?.tasks||[]).filter(t=>t.workflow_id===root.workflow_id):[root];
        return <><h2>{root.description}</h2>{parts.map(task=><article className={`mission-result-part ${task.agent_id==='market_analyst'?'market-brief-result':''}`} key={task.id}><header><strong>{snapshot?.agents.find(a=>a.id===task.agent_id)?.name||task.agent_id}</strong><span className={`task-chip ${task.status}`}>{LABELS[task.status]}</span></header><h3>{task.description}</h3><small>{dateTime(task.finished_at||task.created_at)} · ID {task.id}</small>
          {task.error&&<p className="error-copy">{task.error}</p>}
          {!["completed","failed","cancelled"].includes(task.status)&&<p className="muted">Contribution : {LABELS[task.status].toLocaleLowerCase()}.</p>}
          {task.agent_id==='market_analyst'&&task.result.market_data?.length&&<div className="market-brief-heading"><div><span>POINT MARCHÉS</span><strong>{task.result.title||'Brief de marché'}</strong><small>{task.result.market_points??task.result.market_data.length} séries vérifiées · relevé {dateTime(task.result.as_of)}</small></div><span aria-hidden="true">◈</span></div>}
          {task.agent_id==='market_analyst'&&task.result.sentiment&&<div className={`market-sentiment ${task.result.sentiment.label==='Défensif'?'defensive':task.result.sentiment.label==='Constructif'?'constructive':'mixed'}`}><div><span>SENTIMENT DU MARCHÉ</span><strong>{task.result.sentiment.label}</strong></div><div><b>Confiance {task.result.sentiment.confidence}</b><small>{task.result.sentiment.signals.length} signaux observés · {task.result.sentiment.supporting_news.length} titre(s) concordant(s)</small></div></div>}
          {task.agent_id==='market_analyst'&&task.result.market_data?.length&&<div className="market-brief-grid">{task.result.market_data.map(p=><div className="market-brief-kpi" key={p.series_id}><span>{p.label}</span><strong>{new Intl.NumberFormat('fr-FR',{maximumFractionDigits:4}).format(p.value)} <small>{p.unit}</small></strong><small>{p.change_display&&p.change_display!=='N/A'?`${p.change_display} · `:''}{p.observed_at}</small>{p.source_url?.startsWith('https://')&&<a href={p.source_url} target="_blank" rel="noopener noreferrer">Source ↗</a>}</div>)}</div>}
          {task.result.title&&task.agent_id!=='market_analyst'&&<h4>{task.result.title}</h4>}
          {task.result.integrated&&<p className="mission-integration-proof">✓ Changement appliqué au projet local après vérifications{task.result.commit?` · version ${task.result.commit.slice(0,10)}`:''}. Le texte de l’agent ci-dessous a été rédigé avant cette intégration.</p>}
          {task.result.text&&<MarkdownText text={task.result.integrated&&task.result.base_note?task.result.text.replace(`\n\n${task.result.base_note}`,''):task.result.text}/>}
          {task.result.equity&&<EquityChart points={task.result.equity}/>}
          {task.result.branch&&<p>Branche locale : <code>{task.result.branch}</code></p>}
          {task.result.files&&<details><summary>{task.result.files.length} fichier(s) modifié(s)</summary><ul>{task.result.files.map(file=><li key={file}><code>{file}</code></li>)}</ul></details>}
          {task.result.checks&&<details><summary>Commandes exécutées par Codex</summary>{task.result.checks.map((check,i)=><p key={i}><code>{check.command}</code> · code de sortie : {check.exit_code??'inconnu'}</p>)}</details>}
          {task.result.diff&&<details><summary>Voir les modifications{task.result.diff_truncated?' (extrait)':''}</summary><pre className="jules-code-diff"><code>{task.result.diff}</code></pre></details>}
          {task.result.file&&<p>Fichier préparé : <code>{task.result.file}</code></p>}{isPendingProposal(task)&&task.agent_id==="job_hunter"&&!task.result.revision&&<p className="notification-blockage">Cet audit ne contient pas de révision Git. Relance Jules depuis le centre de notifications avant de valider.</p>}
          {isPendingProposal(task)&&<div className="workflow-builder-actions"><button type="button" disabled={task.agent_id==="job_hunter"&&!task.result.revision} onClick={()=>void reviewProposal(task.id,true)}>Valider la proposition</button><button type="button" onClick={()=>void reviewProposal(task.id,false)}>Refuser</button><small>Validation explicite · branche isolée ou transfert à Jules · aucun merge ni service payant.</small></div>}
          {task.result.new_count!==undefined&&<p>{task.result.new_count} nouvelles offres{task.result.total_count!==undefined?` sur ${task.result.total_count} suivies`:""}.</p>}
          {task.agent_id!=='market_analyst'&&task.result.market_data?.map(p=><p key={p.series_id}><strong>{p.label}</strong> {p.value} {p.unit} · {p.observed_at}</p>)}
          {task.result.offers?.map(offer=><article className="result-item" key={offer.url}><a href={/^https?:\/\//i.test(offer.url)?offer.url:undefined} target="_blank" rel="noopener noreferrer">{offer.title} ↗</a><small>{offer.company} · {offer.location||"Lieu non indiqué"}</small></article>)}
          {task.result.contacts?.map(contact=><article className="result-item" key={contact.id}><strong>{contact.name}</strong><p>{contact.role} · {contact.company}</p><small>{contact.verification}</small>{/^https?:\/\//i.test(contact.linkedin_url||"")&&<a href={contact.linkedin_url} target="_blank" rel="noopener noreferrer">Profil LinkedIn ↗</a>}</article>)}
          {task.result.question&&<div className="exercise-card"><strong>Question</strong><MarkdownText text={task.result.question}/><details><summary>Correction</summary><MarkdownText text={task.result.answer||"Correction non disponible."}/></details></div>}
          {task.result.body&&<div className="draft-card"><strong>Objet : {task.result.subject}</strong><p className="result-letter-text">{task.result.body}</p>{task.result.followup&&<details><summary>Relance</summary><p className="result-letter-text">{task.result.followup}</p></details>}<small>Brouillon enregistré · aucun envoi depuis cette fenêtre.</small></div>}
          {task.result.errors?.map((e,i)=><p className="error-copy" key={i}>{e.source} : {e.error}</p>)}
          {task.status==="completed"&&!Object.keys(task.result).length&&<p>Aucun contenu de résultat n’a été enregistré pour cette mission.</p>}
          <details className="mission-log"><summary>Données et journal complets</summary><pre>{JSON.stringify(task.result,null,2)}</pre>{(snapshot?.events||[]).filter(e=>e.task_id===task.id).map(e=><p key={e.id}>{dateTime(e.created_at)} · {e.message}</p>)}</details>
        </article>)}</>;
      })()}
    </div></section>}
    {settingsOpen&&settings&&<div className="settings-backdrop" role="presentation" onMouseDown={event=>{if(event.target===event.currentTarget)setSettingsOpen(false);}}><form className="settings-dialog" role="dialog" aria-modal="true" aria-labelledby="settings-title" onSubmit={saveSettings}>
      <div className="settings-heading"><div><span className="tiny-label">PR&Eacute;F&Eacute;RENCES DU COMPTE</span><h2 id="settings-title">R&eacute;glages MarketDesk City</h2></div><button type="button" className="icon-button" onClick={()=>setSettingsOpen(false)} aria-label="Fermer">&times;</button></div>
      <p>Le Desk Manager utilise Codex avec ton abonnement ChatGPT. Les autres services conservent leur configuration actuelle.</p>
      <div className="settings-model-grid">{INITIAL_IDS.filter(id=>id!=="desk_manager").map(id=><label key={id}>{snapshot?.agents.find(agent=>agent.id===id)?.name||id}<select value={settings.models[id]||"gpt-4o-mini"} onChange={event=>setSettings({...settings,models:{...settings.models,[id]:event.target.value}})}>{(settings.available_models||["gpt-4o-mini"]).map(model=><option key={model}>{model}</option>)}</select></label>)}</div>
<div className="cost-line"><span>Usage IA du compte</span><strong>{snapshot?.api_usage.calls??0} appel(s) API &middot; ${(snapshot?.api_usage.estimated_usd??0).toFixed(4)}</strong><small>Codex utilise les limites de ta connexion ChatGPT.</small></div>
            <section className="diagnostics-section"><div className="section-heading"><h3>Diagnostics des services</h3><button type="button" className="secondary-button" onClick={()=>void checkIntegrations()} disabled={diagnosticsBusy}>{diagnosticsBusy?"V&eacute;rification...":"V&eacute;rifier"}</button></div>{diagnostics&&<div className="integration-list">{diagnostics.map(item=><article className="integration-row" key={item.name}><span className={`integration-dot ${item.status.toLowerCase()}`}/><div><strong>{item.name}</strong><small>{item.source} &middot; {item.access}</small><p>{item.detail}</p></div><b className={`integration-status ${item.status.toLowerCase()}`}>{item.status}</b></article>)}</div>}</section>
      <div className="settings-limits"><label>Plafond quotidien ($)<input type="number" min="0" max="1000" step="0.5" value={settings.daily_limit_usd} onChange={event=>setSettings({...settings,daily_limit_usd:Number(event.target.value)})}/></label><label>Plafond mensuel ($)<input type="number" min="0" max="10000" step="1" value={settings.monthly_limit_usd} onChange={event=>setSettings({...settings,monthly_limit_usd:Number(event.target.value)})}/></label><label>Missions simultan&eacute;es<select value={settings.max_concurrent_tasks} onChange={event=>setSettings({...settings,max_concurrent_tasks:Number(event.target.value)})}>{[1,2,3,4,5,6].map(value=><option key={value} value={value}>{value}</option>)}</select></label></div>
      <label className="settings-checkbox"><input type="checkbox" checked={settings.auto_tasks} onChange={event=>setSettings({...settings,auto_tasks:event.target.checked})}/><span>Lancer les missions d&egrave;s leur ajout ; sinon, demander mon approbation</span></label><small className={settings.codex_chat_available?"provider-ready":"provider-missing"}>{settings.codex_chat_available?"Desk Manager connect&eacute; &agrave; Codex · GPT-6 Luna.":"Desk Manager indisponible : connecte Codex avec codex login sur le serveur City."}</small><small className={settings.api_key_configured?"provider-ready":"provider-missing"}>{settings.api_key_configured?"La cl&eacute; API OpenAI est configur&eacute;e pour les autres services.":"Les services utilisant l’API OpenAI ne sont pas configur&eacute;s."}</small>
      <div className="dialog-actions"><button type="button" className="secondary-button" onClick={()=>setSettingsOpen(false)}>Fermer</button><button type="submit" className="primary-button" disabled={settingsBusy}>{settingsBusy?"Enregistrement...":"Enregistrer"}</button></div>
    </form></div>}
  </div>;
}

createRoot(document.getElementById("root")!).render(<App />);
