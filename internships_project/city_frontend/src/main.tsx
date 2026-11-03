import React, { useCallback, useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import { type AgentStatus } from "./types";
import { PixelFloorGame } from "./PixelFloorGame";
import "./liveDashboard";
import {NetworkContactsWindow} from "./NetworkContacts";
import {ManagerChatWindow} from "./ManagerChatWindow";
import {NotificationCenter} from "./NotificationCenter";
import {Cockpit} from "./Cockpit";
import {isPendingProposal} from "./notifications";

// The standalone fallback panel is only used by the currently deployed bundle.
// New frontend builds render these same live feeds directly in the game canvas.
(window as Window & { __marketdeskNativePanels?: boolean }).__marketdeskNativePanels = true;

type Offer = { title: string; company: string; location: string; url: string; kind?: string; start_period?: string;
  published?: string; published_inferred?: boolean; source?: string; selection_source?: "job_hunter"|"internships_cache";
  selection_reason?: string; detected_at?: string; total_offers?: number; tracker_updated_at?: string };
type MarketReading = { series_id: string; label: string; value: number; unit: string; observed_at: string; change?: number | null; change_display?: string; source_url?: string };
type MarketSnapshot = { points: MarketReading[]; retrieved_at?: string; error?: string };
type InternshipHighlight = { featured_offer: Offer | null; updated_at?: string; total_count?: number; source_errors?: number; error?: string };
type Result = { title?: string; text?: string; summary?: string; market_points?: number; question?: string; answer?: string; subject?: string; body?: string;
  sentiment?: {label:string;confidence:string;explanation:string;signals:string[];supporting_news:{title:string;url:string;source:string;published:string}[]};
  followup?: string; new_count?: number; total_count?: number; priority_count?: number; source_errors?: number;
  updated_at?: string; as_of?: string; market_data?: MarketReading[]; featured_offer?: (Offer & { detected_at?: string; selection_reason?: string }) | null;
  offers?: Offer[]; contacts?: {id:string;name:string;role:string;company:string;verification:string;linkedin_url:string}[];
  equity?: {date:string;value:number}[]; approval_required?:boolean; branch?:string; role_version?:number; review_decision?:string; revision?:string; blockage?:string; file?:string;
  files?:string[];diff?:string;diff_truncated?:boolean;checks?:{command:string;exit_code:number|null}[];
  errors?: {source:string;status:string;error:string}[]; contact?: {name?:string;company?:string}; };
type Task = {
  id: string; agent_id: string; task_type: string; description: string; status: AgentStatus;
  created_at: string; started_at?: string; finished_at?: string; result: Result;
  error?: string; xp_awarded: number; input_tokens: number; output_tokens: number; api_cost_usd: number;
  workflow_id?: string; priority?: number; retry_count?: number; max_retries?: number; depends_on?: string[];
  delegated_by?: string;
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
  xp: number; level: number; level_progress: number; achievements: string[];
  status: AgentStatus; latest: Task | null;
};
type Event = { id:number; agent_id: string; task_id: string; status: string; message: string; created_at: string };
type ChatMessage = { id?: number; role: "user" | "assistant"; content: string; model?: string; created_at?: string; tool_calls?:ToolReceipt[] };
type ToolReceipt = {name:string;status:"running"|"completed"|"unavailable"|"failed";text:string};
type CitySettings = { provider: string; models: Record<string,string>; daily_limit_usd: number; monthly_limit_usd: number;
  max_concurrent_tasks: number; auto_tasks: boolean; available_models?: string[]; api_key_configured?: boolean };
type Integration = { name: string; status: "Connected" | "Unavailable" | "Error"; source: string; detail: string;
  last_sync: string; access: string; separate_process: boolean };
type Snapshot = {
  agents: Agent[]; tasks: Task[]; events: Event[]; workflows: Workflow[]; today_completed: number; week_completed: number;
  api_usage: { input_tokens: number; output_tokens: number; estimated_usd: number; calls: number; unknown_costs: number; note: string;
    by_agent: Record<string,{calls:number;estimated_usd:number;unknown:number}> };
  workspace: { profiles: { id: string; name: string }[]; contacts: { id: string; name: string; company: string; email: string }[] };
};

const LABELS: Record<string, string> = {
  idle: "Disponible", queued: "En attente", running: "Au travail", waiting_approval: "Validation requise",
  completed: "Terminée", failed: "Échec", cancelled: "Annulée",
};
const SPECIALIST_OPERATIONS:Record<string,string> = {job_hunter:"repository_audit",finance_tutor:"quant_report",developer:"daily_questions",innovation_lab:"innovation_review",internship_scout:"refresh_internships"};
const INITIAL_IDS = ["desk_manager", "market_analyst", "finance_tutor", "job_hunter", "networker", "outreach_agent", "developer", "innovation_lab", "internship_scout"];

function MarkdownText({text}: {text:string}): React.ReactElement {
  const inline = (value:string) => value
    .replace(/\\\(|\\\)|\\\[|\\\]/g, "")
    .replace(/\\(?:text|mathrm)\{([^{}]*)\}/g, "$1")
    .replace(/\\times/g, "×").replace(/\\cdot/g, "·").replace(/\\%/g, "%")
    .split(/(\[[^\]]+\]\(https?:\/\/[^\s)]+\)|\*\*[^*]+\*\*|`[^`]+`|https?:\/\/[^\s)]+)/g).map((part,index) => {
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
    day: "numeric", month: "short", hour: "2-digit", minute: "2-digit",
  }).format(date);
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
  const [panelCollapsed,setPanelCollapsed]=useState(false);
  const [panelWidth,setPanelWidth]=useState(340);
  const [notificationView,setNotificationView]=useState({filter:"all",agent:""});
  const [missionFilter,setMissionFilter]=useState("active");
  const [resultTaskId,setResultTaskId]=useState<string|null>(null);
  const [launchingSite,setLaunchingSite]=useState<string|null>(null);
  const [siteError,setSiteError]=useState("");
  const [commandQuery,setCommandQuery]=useState("");
  useEffect(()=>{if(!resultTaskId)return;const close=(event:KeyboardEvent)=>{if(event.key==="Escape")setResultTaskId(null);};window.addEventListener("keydown",close);return()=>window.removeEventListener("keydown",close);},[resultTaskId]);
  const resizeStart=useRef<{x:number;width:number}|null>(null);
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [marketSnapshot, setMarketSnapshot] = useState<MarketSnapshot | null>(null);
  const [internshipHighlight, setInternshipHighlight] = useState<InternshipHighlight | null>(null);
  const [selectedId, setSelectedId] = useState("desk_manager");
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
  const [windowMode, setWindowMode] = useState<"none"|"agent"|"agents"|"missions"|"activity"|"contacts"|"chat">("agent");
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [chatInput, setChatInput] = useState("");
  const [chatBusy, setChatBusy] = useState(false);
  const [chatStatus, setChatStatus] = useState("");
  const [chatError, setChatError] = useState("");
  const [chatTools, setChatTools] = useState<ToolReceipt[]>([]);
  const chatScrollRef = useRef<HTMLDivElement>(null);
  const chatAbort = useRef<AbortController | null>(null);
  const [settings, setSettings] = useState<CitySettings|null>(null);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [settingsBusy, setSettingsBusy] = useState(false);
  const [diagnostics, setDiagnostics] = useState<Integration[]|null>(null);
  const [diagnosticsBusy, setDiagnosticsBusy] = useState(false);
  const [collectionBusy, setCollectionBusy] = useState<"markets"|"internships"|null>(null);

  const [notificationReadThrough,setNotificationReadThrough]=useState(0);
  const refresh = useCallback(async () => {
    try {
      const [next,notifications]=await Promise.all([api<Snapshot>("/city/api/state"),api<{last_read_event_id:number}>("/city/api/notifications")]);
      setSnapshot(next);
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

  const loadMarketSnapshot = useCallback(async () => {
    try { setMarketSnapshot(await api<MarketSnapshot>("/city/api/market-snapshot")); }
    catch (exc) { setMarketSnapshot({points: [], error: exc instanceof Error ? exc.message : "Données de marché indisponibles."}); }
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
    void loadMarketSnapshot();
    const interval = window.setInterval(() => { if (!document.hidden) void loadMarketSnapshot(); }, 300000);
    return () => window.clearInterval(interval);
  }, [loadMarketSnapshot]);

  useEffect(() => {
    void loadInternshipHighlight();
    const interval = window.setInterval(() => { if (!document.hidden) void loadInternshipHighlight(); }, 60000);
    return () => window.clearInterval(interval);
  }, [loadInternshipHighlight]);

  useEffect(() => {
    void loadChat("desk_manager");
    const interval=window.setInterval(()=>{if(!document.hidden&&!chatAbort.current)void loadChat("desk_manager");},10000);
    return()=>window.clearInterval(interval);
  }, [loadChat]);
  useEffect(() => { if(!chatMessages.length)return; chatScrollRef.current?.scrollTo({top:chatScrollRef.current.scrollHeight,behavior:"smooth"}); }, [chatMessages, chatStatus]);

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
  const activeCount = snapshot?.tasks.filter(task=>task.status==="running").length||0;
  const todayKey = (value: string) => { const date = new Date(value); return Number.isNaN(date.getTime()) ? "" : `${date.getFullYear()}-${String(date.getMonth()+1).padStart(2,"0")}-${String(date.getDate()).padStart(2,"0")}`; };
  const marketTask = snapshot?.tasks.find(task=>["market_analyst","finance_tutor"].includes(task.agent_id)&&task.status==="completed"&&task.result.market_data?.length);
  const marketTaskIsNewer = Boolean(marketTask?.result.as_of && (!marketSnapshot?.retrieved_at
    || Date.parse(marketTask.result.as_of) > Date.parse(marketSnapshot.retrieved_at)));
  const marketPoints = marketTaskIsNewer ? marketTask!.result.market_data! : marketSnapshot?.points || marketTask?.result.market_data || [];
  const marketRetrievedAt = marketTaskIsNewer ? marketTask!.result.as_of! : marketSnapshot?.retrieved_at || marketTask?.result.as_of || "";
  const jobTaskToday = snapshot?.tasks.find(task=>(["internship_scout","networker","desk_manager"].includes(task.agent_id))&&task.status==="completed"&&task.finished_at
    &&todayKey(task.finished_at)===todayKey(new Date().toISOString())&&task.result.featured_offer);
  const latestJobTask = snapshot?.tasks.find(task=>(["internship_scout","networker","desk_manager"].includes(task.agent_id)));
  useEffect(() => {
    if (latestJobTask?.status === "completed") void loadInternshipHighlight();
  }, [latestJobTask?.id, latestJobTask?.status, loadInternshipHighlight]);
  const agentFeaturedOffer = jobTaskToday?.result.featured_offer
    ? {...jobTaskToday.result.featured_offer, selection_source: "job_hunter" as const}
    : null;
  const cachedFeaturedOffer = internshipHighlight?.featured_offer
    ? {...internshipHighlight.featured_offer, total_offers: internshipHighlight.total_count,
       tracker_updated_at: internshipHighlight.updated_at}
    : null;
  const recentJobOffers = (snapshot?.tasks || [])
    .filter(task=>(["internship_scout","networker","desk_manager"].includes(task.agent_id))&&task.status==="completed")
    .sort((a,b)=>Date.parse(b.finished_at||b.created_at)-Date.parse(a.finished_at||a.created_at))
    .flatMap(task=>[
      ...(task.result.featured_offer ? [{...task.result.featured_offer, selection_source:"job_hunter" as const}] : []),
      ...(task.result.offers || []).map(offer=>({...offer, selection_source:"job_hunter" as const})),
    ]);
  const featuredOffers: Offer[] = [];
  const seenOfferUrls = new Set<string>();
  for (const offer of [agentFeaturedOffer, cachedFeaturedOffer, ...recentJobOffers]) {
    if (!offer?.url || seenOfferUrls.has(offer.url)) continue;
    seenOfferUrls.add(offer.url);
    featuredOffers.push(offer);
    if (featuredOffers.length === 12) break;
  }
  const marketCollectionActive = snapshot?.tasks.some(task=>["market_analyst","finance_tutor"].includes(task.agent_id)&&["queued","running","waiting_approval"].includes(task.status)) || false;
  const internshipCollectionActive = snapshot?.tasks.some(task=>["internship_scout","desk_manager"].includes(task.agent_id)&&["queued","running","waiting_approval"].includes(task.status)) || false;

  async function launchCollection(kind:"markets"|"internships"):Promise<void> {
    if (collectionBusy) return;
    setCollectionBusy(kind); setError("");
    try {
      await api(`/city/api/collect/${kind}`, {});
      await refresh();
    } catch (exc) { setError(exc instanceof Error ? exc.message : "La collecte n'a pas pu démarrer."); }
    finally { setCollectionBusy(null); }
  }
  function openNotifications(filter="all",agent=""):void {
    setNotificationView({filter,agent});setWindowMode("activity");
  }
  function openAgent(id:string, tab?:"chat"|"missions"|"history"):void {
    setPanelCollapsed(false);setSelectedId(id);
    if(tab==="history"){openNotifications("all",id==="desk_manager"?"":id);return;}
    if(tab==="missions"){setWindowMode("missions");return;}
    if(tab==="chat"||id==="desk_manager"){setWindowMode("chat");return;}
    setWindowMode(id==="networker"?"contacts":"agent");
  }
  function inspectCockpitTask(id:string):void {
    const task=snapshot?.tasks.find(t=>t.id===id);if(!task)return;
    if(["completed","failed"].includes(task.status)){showResult(task);return;}
    setSelectedId(task.agent_id);setOpenedTaskId(id);setMissionFilter(task.status==="running"?"active":"pending");setWindowMode("missions");
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
    const text = chatInput.trim();
    if (!text || chatBusy || chatAbort.current) return;
    const userMessage: ChatMessage = {role:"user",content:text,created_at:new Date().toISOString()};
    setChatMessages(rows => [...rows,userMessage,{role:"assistant",content:"",created_at:new Date().toISOString()}]);
    setChatInput(""); setChatBusy(true); setChatError(""); setChatTools([]); setChatStatus("Connexion à l’agent…");
    const abort = new AbortController(); chatAbort.current = abort;
    try {
      const response = await fetch("/city/api/chat/desk_manager", {method:"POST",credentials:"same-origin",signal:abort.signal,
        headers:{"Content-Type":"application/json","X-MarketDesk-City":"1"},
        body:JSON.stringify({message:text})});
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
              setChatTools(rows=>{let index=-1;for(let i=rows.length-1;i>=0;i--){if(rows[i].name===receipt.name&&rows[i].status==="running"){index=i;break;}}
                if(index>=0&&receipt.status!=="running"){const copy=[...rows];copy[index]=receipt;return copy;}
                return [...rows,receipt];});
              setChatStatus(receipt.status==="running"?"Lecture du service…":"Rédaction de la réponse…");
            }
            if (data.type === "status") setChatStatus(data.text || "L’agent rédige une réponse…");
            if (data.type === "delta") {
              setChatStatus("");
              setChatMessages(rows => {const copy=[...rows];const last=copy[copy.length-1];if(last?.role === "assistant")copy[copy.length-1]={...last,content:last.content+(data.text||"")};return copy;});
            }
            if (data.type === "error") { setChatError(data.text || "La génération a échoué."); setChatStatus(""); }
            if (data.type === "done") setChatStatus("");
          } catch { /* ignore incomplete event frames */ }
        }
      };
      while (true) { const part=await reader.read(); buffer+=decoder.decode(part.value||new Uint8Array(),{stream:!part.done});
        const frames=buffer.split("\n\n"); buffer=frames.pop()||""; frames.forEach(handle); if(part.done)break; }
      if (buffer.trim()) handle(buffer);
    } catch (exc) {
      if (!(exc instanceof DOMException && exc.name === "AbortError")) setChatError(exc instanceof Error ? exc.message : "La conversation a échoué.");
      setChatStatus("");
    } finally { setChatBusy(false); chatAbort.current=null; void refresh(); }
  }

  async function clearChat(): Promise<void> {
    if (!window.confirm("Effacer toute la conversation avec Desk Manager ?")) return;
    if (chatBusy) chatAbort.current?.abort();
    try { await api("/city/api/chat/desk_manager/clear",{}); setChatMessages([]);setChatTools([]);setChatError(""); }
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
    setBusy(true);try{await api(`/city/api/tasks/${taskId}/retry`,{});await refresh();}
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

  async function openLocalSite(kind:"markets"|"internships"):Promise<void> {
    if(launchingSite)return;
    const tab=window.open("about:blank","_blank");
    if(!tab){setSiteError("Autorise l’ouverture d’un nouvel onglet pour accéder au site.");return;}
    tab.opener=null;
    tab.document.title=`Ouverture de ${kind === "markets"?"Markets":"Internships"}`;
    tab.document.body.textContent="Démarrage du site local… Cet onglet s’ouvrira dès qu’il sera prêt.";
    setLaunchingSite(kind);setSiteError("");
    const controller=new AbortController();const timer=window.setTimeout(()=>controller.abort(),70000);
    try {
      const response=await fetch(`/city/api/local-apps/${kind}`,{method:"POST",credentials:"same-origin",headers:{"X-MarketDesk-City":"1"},signal:controller.signal});
      const data=await response.json();
      if(!response.ok)throw new Error(data.detail||"Impossible de démarrer ce site.");
      const target=new URL(data.url);
      if(target.protocol!=="http:"||target.hostname!=="127.0.0.1")throw new Error("Adresse locale invalide.");
      if(!tab.closed)tab.location.replace(target.href);
    } catch(error) {
      const message=error instanceof Error&&error.name!=="AbortError"?error.message:"Le démarrage prend trop de temps. Réessaie dans quelques instants.";
      setSiteError(message);if(!tab.closed)tab.document.body.textContent=message;
    } finally {window.clearTimeout(timer);setLaunchingSite(null);}
  }

  async function reviewProposal(taskId:string,approved:boolean) {
    try {await api(`/city/api/proposals/${taskId}/review`,{approved});await refresh();setError(approved?"Proposition transmise à Jules.":"Proposition refusée.");} catch(error){setError(error instanceof Error?error.message:"Validation impossible.");}
  }
  function showResult(task:Task):void {setResultTaskId(task.id);setOpenedTaskId(task.id);setSelectedId(task.agent_id);setWindowMode("none");}

  function managerPanel(): React.ReactElement {
    const allTasks = snapshot?.tasks || [];
    const activeTasks = allTasks.filter(task=>["queued","running","waiting_approval"].includes(task.status));
    const recentTasks = allTasks.filter(task=>!["queued","running","waiting_approval"].includes(task.status)).slice(0,5);
    const controlTasks = allTasks.filter(t=>missionFilter==="all"||missionFilter==="active"&&t.status==="running"||missionFilter==="pending"&&(["queued","waiting_approval"].includes(t.status)||isPendingProposal(t))||missionFilter==="completed"&&t.status==="completed"||missionFilter==="failed"&&["failed","cancelled"].includes(t.status));
    const renderTask = (task:Task) => {
      const assigned = snapshot?.agents.find(agent=>agent.id===task.agent_id)?.name||task.agent_id;
      const dependencies = (task.depends_on||[]).map(id=>allTasks.find(item=>item.id===id));
      const needsApproval = task.status === "waiting_approval" && (!task.workflow_id ||
        allTasks.find(item=>item.workflow_id===task.workflow_id)?.id === task.id);
      const summary = task.result.summary || task.result.text || task.result.title ||
        (task.result.new_count !== undefined ? `${task.result.new_count} nouvelle(s) offre(s) sur ${task.result.total_count ?? "?"}.` : "");
      return <article className={`mission-record ${task.status} ${openedTaskId===task.id?'mission-highlight':''}`} key={task.id}>
        <div className="mission-record-head"><div><button className="mission-title" type="button" onClick={()=>{setOpenedTaskId(task.id);setSelectedId(task.agent_id);}}>{task.description}</button><small>{assigned}{task.delegated_by?` / transmis par ${snapshot?.agents.find(agent=>agent.id===task.delegated_by)?.name||task.delegated_by}`:""}</small></div><span className={`task-chip ${task.status}`}>{LABELS[task.status]}</span></div>
        <div className="mission-record-meta"><code title={`Identifiant persistant : ${task.id}`}>ID {task.id}</code><time>{dateTime(task.created_at)}</time>{task.workflow_id&&<span>Projet {task.workflow_id.slice(0,8)}</span>}</div>
        {!!dependencies.length&&<div className="mission-dependencies"><b>{dependencies.filter(d=>d?.status==="completed").length}/{dependencies.length} prérequis terminés</b>{dependencies.map((dependency,index)=><span key={task.depends_on?.[index]} title={task.depends_on?.[index]}>{dependency?`${snapshot?.agents.find(agent=>agent.id===dependency.agent_id)?.name||dependency.agent_id} / ${LABELS[dependency.status]}`:`ID ${task.depends_on?.[index].slice(0,10)} indisponible`}</span>)}</div>}
        {task.status==="waiting_approval"&&<p className="mission-record-result">Cette mission attend ta validation avant ex&eacute;cution.</p>}
        {summary&&<p className="mission-record-result">{summary}</p>}
        {["completed","failed"].includes(task.status)&&<button type="button" className="secondary-button result-open" onClick={()=>showResult(task)}>{task.status==="failed"?"Voir l’erreur":"Voir le résultat"} ↗</button>}
        {task.status==="failed"&&<p className="error-copy">{task.error||"La mission a &eacute;chou&eacute; sans d&eacute;tail suppl&eacute;mentaire."}</p>}
        <details className="mission-log"><summary>Étapes, résultat et journal</summary>{task.started_at&&<p>Démarrée · {dateTime(task.started_at)}</p>}{task.finished_at&&<p>Terminée · {dateTime(task.finished_at)}</p>}{(snapshot?.events||[]).filter(e=>e.task_id===task.id).sort((a,b)=>a.id-b.id).map(e=><p key={e.id}><time>{dateTime(e.created_at)}</time> · {e.message}</p>)}{Object.keys(task.result||{}).length>0&&<pre>{JSON.stringify(task.result,null,2)}</pre>}</details>
        <div className="mission-record-actions">
          {needsApproval&&<button type="button" className="primary-button compact-button" disabled={busy} onClick={()=>task.workflow_id?void workflowAction(task.workflow_id,"approve"):void approve(task.id)}>Valider</button>}
          {task.status==="failed"&&(!task.workflow_id||(task.retry_count||0)<(task.max_retries||0))&&<button type="button" className="secondary-button compact-button" disabled={busy} onClick={()=>void retry(task.id)}>R&eacute;essayer</button>}
          {(task.status==="queued"||task.status==="waiting_approval")&&<button type="button" className="text-button" disabled={busy} onClick={()=>task.workflow_id?void workflowAction(task.workflow_id,"cancel"):void cancel(task.id)}>Annuler</button>}
        </div>
      </article>;
    };
    return <div className="task-panel-content manager-panel">
      
      <section className="mission-control-register"><div className="section-heading"><div><h3>Registre des missions</h3><small>{allTasks.filter(task=>task.status==="running").length} en cours &middot; {allTasks.filter(task=>task.status==="waiting_approval"||isPendingProposal(task)).length} &agrave; valider</small></div></div>
        <div className="mission-filters" role="group" aria-label="Filtrer les missions">{[["active","Actives"],["pending","En attente"],["completed","Terminées"],["failed","Erreurs"],["all","Toutes"]].map(([id,label])=><button type="button" key={id} aria-pressed={missionFilter===id} onClick={()=>setMissionFilter(id)}>{label}</button>)}</div>
        {!controlTasks.length?<p className="muted">Aucune mission pour ce filtre.</p>:<div className="mission-record-list">{controlTasks.map(renderTask)}</div>}

      </section>
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
      <section className="workflow-builder">
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
      </section>
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
      <section className="manager-activity"><h3>Activité des agents</h3>{snapshot?.events.slice(0,8).map((event,index)=><p key={`${event.task_id}-${event.status}-${index}`}><b>{snapshot.agents.find(a=>a.id===event.agent_id)?.name||event.agent_id}</b><span>{event.message}</span><time>{dateTime(event.created_at)}</time></p>)}{!snapshot?.events.length&&<small>Aucune mission enregistrée.</small>}</section>
      <section className="manager-costs"><h3>Coûts IA par agent</h3>{INITIAL_IDS.map(id=>{const usage=snapshot?.api_usage.by_agent[id];return usage?<p key={id}>{snapshot?.agents.find(a=>a.id===id)?.name}: {usage.calls} appel(s) · {usage.estimated_usd.toFixed(4)} $ {usage.unknown?`· ${usage.unknown} coût(s) inconnus`:""}</p>:null})}<small>Estimations des chats City et des brouillons du Manager. Les services sans coût relevé restent hors total.</small></section>
    </div>;
  }

  const managerChat = <section className="chat-section" aria-label="Conversation avec Desk Manager">
            <div className="chat-heading"><div><h3>Desk Manager</h3><small>{"Décris ton objectif ; Desk Manager le répartit entre les agents."}</small></div><button type="button" className="text-button" onClick={()=>void prepareMorningBriefing()} disabled={chatBusy}>Briefing du matin</button><button type="button" className="text-button" onClick={()=>void clearChat()} disabled={chatBusy}>Effacer</button></div>
            <div className="chat-history" ref={chatScrollRef} aria-live="polite">
              {chatTools.map((tool,index)=><div key={`${tool.name}-${index}`} className={`chat-tool-receipt ${tool.status}`}><span aria-hidden="true">{tool.status==="completed"?"OK":tool.status==="running"?"…":"!"}</span><div><strong>{tool.status==="running"?"Outil en cours":"Outil consulté"} : {tool.name}</strong><small>{tool.text}</small></div></div>)}{!chatMessages.length&&<div className="chat-empty"><span className="portrait pixel-agent-avatar desk_manager" aria-hidden="true"><i className="agent-sprite"/></span><strong>Commence une conversation</strong><p>Pose ta question au Desk Manager. L'historique est sauvegard&eacute; sur ton compte.</p><div className="mission-suggestions">{["Prépare un brief des marchés","Trouve des stages adaptés à mon profil","Identifie des contacts et prépare des brouillons"].map(text=><button type="button" key={text} onClick={()=>{setChatInput(text);document.getElementById('city-chat-input')?.focus();}}>{text} ↗</button>)}</div></div>}
              {chatMessages.map((item,index)=><article key={item.id||`${item.created_at}-${index}`} className={`chat-message ${item.role}`}><span className="chat-role"><span className={`message-avatar ${item.role}`}>{item.role==="user"?"T":"D"}</span>{item.role==="user"?"Toi":deskManager?.name||"Desk Manager"}<time>{dateTime(item.created_at)}</time></span>{item.tool_calls?.map((tool,i)=><div key={i} className={`chat-tool-receipt ${tool.status}`}><span aria-hidden="true">{tool.status==="completed"?"OK":"!"}</span><div><strong>{tool.name}</strong><small>{tool.text}</small></div></div>)}{item.content?<MarkdownText text={item.content}/>:chatBusy?<span className="typing-indicator">R&eacute;ponse en cours...</span>:null}{item.model&&<small className="message-model">{item.model}</small>}</article>)}
              {chatBusy&&<p className="processing-state" role="status">● ● ● Le Manager traite ta demande…</p>}{(snapshot?.tasks||[]).filter(t=>t.status==="waiting_approval"||isPendingProposal(t)).map(t=><div className="approval-inline" key={t.id}><strong>Validation requise</strong><p>{t.description}</p><button type="button" onClick={()=>{if(isPendingProposal(t)){showResult(t);}else{setOpenedTaskId(t.id);setMissionFilter("pending");openAgent("desk_manager","missions");}}}>Examiner la proposition →</button></div>)}{chatStatus&&<p className="chat-status" role="status">{chatStatus}</p>}{chatError&&<p className="chat-error" role="alert">{chatError}</p>}</div>
            <form className="chat-composer" onSubmit={sendChat}><label className="sr-only" htmlFor="city-chat-input">Message au Desk Manager</label><textarea id="city-chat-input" rows={3} maxLength={3000} value={chatInput} disabled={chatBusy} onChange={event=>setChatInput(event.target.value)} onKeyDown={event=>{if(event.key==="Enter"&&!event.shiftKey){event.preventDefault();if(chatInput.trim()&&!chatBusy)event.currentTarget.form?.requestSubmit();}}} placeholder="D&eacute;cris ce que tu veux confier au Desk Manager..."/>
              <div className="chat-composer-bottom"><small>{chatInput.length}/3000 caract&egrave;res &middot; appel IA &agrave; l'envoi</small>{chatBusy?<button type="button" className="secondary-button" onClick={()=>chatAbort.current?.abort()}>Arr&ecirc;ter</button>:<button type="submit" className="primary-button" disabled={!chatInput.trim()}>Envoyer</button>}</div></form>
          </section>;

  return <div className={`city-app game-app mode-${windowMode}`}>
    <header className="city-header">
      <div className="city-brand"><span className="city-brand-mark" aria-hidden="true"><i/><i/><i/><i/></span><div><span className="city-kicker">GLOBAL MARKETS · AI AGENTS</span><h1>MarketDesk <em>City</em></h1></div></div>
      <div className="city-header-right"><span className="live-pill"><span className="live-dot"/> CITY ACTIVE</span><span className="city-subtitle">Huit agents et un Desk Manager reliés aux services existants.</span></div>
      <div className="city-header-actions"><button type="button" className="secondary-button" onClick={()=>{setSettingsOpen(true);void loadSettings();}}>R&eacute;glages</button>
        <form action="/logout" method="post" className="city-logout"><button type="submit">Quitter</button></form></div>
    </header>
    <div className={`city-dashboard command-center ${panelCollapsed?"console-collapsed":""}`} style={{"--console-width":`${panelWidth}px`} as React.CSSProperties}>
      <div className="world-column">
        <div className="world-toolbar"><div><span className="tiny-label">MARKETDESK CITY</span><strong>MarketDesk Tower</strong></div>
          <div className="world-controls" aria-label="Navigation du campus">
            <button type="button" className="collection-control markets-control" title="Noé collecte les données Markets sans ouvrir Gradio" onClick={()=>void launchCollection("markets")}
              disabled={collectionBusy!==null||marketCollectionActive} aria-label="Actualiser les données de marché">
              {collectionBusy==="markets"||marketCollectionActive?"…":"↻"}<span>{marketCollectionActive?"Marchés en cours":"Marchés"}</span></button>
            <button type="button" className="collection-control jobs-control" title="Hugo recherche les stages publiés aujourd’hui" onClick={()=>void launchCollection("internships")}
              disabled={collectionBusy!==null||internshipCollectionActive} aria-label="Rechercher les nouvelles offres de stage">
              {collectionBusy==="internships"||internshipCollectionActive?"…":"↻"}<span>{internshipCollectionActive?"Recherche en cours":"Stages"}</span></button>
            <button type="button" title="Plein écran" onClick={()=>{const node=document.querySelector(".world-column");if(!document.fullscreenElement)void node?.requestFullscreen();else void document.exitFullscreen();}} aria-label="Plein écran">⛶</button>
          </div></div>
        <div className="world-stage tower-world"><PixelFloorGame agents={snapshot?.agents||[]} tasks={snapshot?.tasks||[]} events={snapshot?.events||[]}
          selectedId={selectedId} onPick={id=>openAgent(id)} marketPoints={marketPoints} marketRetrievedAt={marketRetrievedAt}
          marketError={marketSnapshot?.error} internshipError={internshipHighlight?.error} featuredOffers={featuredOffers}/>
          <div className="game-brand-hud"><span className="city-brand-mark" aria-hidden="true"><i/><i/><i/><i/></span><div><strong>MarketDesk City</strong><small>Global Markets &middot; AI Tower</small></div></div>
          <div className="command-search"><span aria-hidden="true">⌕</span><input aria-label="Rechercher un agent ou une mission" placeholder="Rechercher un agent, une mission…" value={commandQuery} onChange={e=>setCommandQuery(e.target.value)}/>{commandQuery.trim()&&<div className="command-search-results">{(snapshot?.agents||[]).filter(a=>(a.name+" "+a.role).toLowerCase().includes(commandQuery.toLowerCase())).map(a=><button key={a.id} onClick={()=>{openAgent(a.id);setCommandQuery("");}}>{a.name}<small>{a.role}</small></button>)}{(snapshot?.tasks||[]).filter(t=>t.description.toLowerCase().includes(commandQuery.toLowerCase())).slice(0,5).map(t=><button key={t.id} onClick={()=>{showResult(t);setCommandQuery("");}}>{t.description}<small>{LABELS[t.status]}</small></button>)}<button onClick={()=>setCommandQuery("")}>Fermer la recherche</button></div>}</div>
          <nav className="game-hud" aria-label="Commandes MarketDesk City">
            <button type="button" className={windowMode==="missions"?"active":""} onClick={()=>setWindowMode(windowMode==="missions"?"none":"missions")} aria-label="Missions" aria-pressed={windowMode==="missions"}><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" aria-hidden="true"><rect x="4" y="5" width="16" height="16" rx="2"/><path d="M9 3h6v4H9zM8 12h8M8 16h5"/></svg><span>Missions</span>{activeCount>0&&<b>{activeCount}</b>}</button>
            <button type="button" className={windowMode==="activity"?"active":""} onClick={()=>{if(windowMode==="activity")setWindowMode("none");else openNotifications();}} aria-label="Notifications" aria-pressed={windowMode==="activity"}><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" aria-hidden="true"><path d="M2 12h5l3-8 4 16 3-8h5"/></svg><span>Notifications</span>{(pendingCount>0||(snapshot?.events||[]).some(e=>e.id>notificationReadThrough))&&<b>{Math.max(pendingCount,(snapshot?.events||[]).filter(e=>e.id>notificationReadThrough).length)}</b>}</button>
            <button type="button" className={windowMode==="contacts"?"active":""} onClick={()=>setWindowMode(windowMode==="contacts"?"none":"contacts")} aria-label="Contacts" aria-pressed={windowMode==="contacts"}><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" aria-hidden="true"><circle cx="9" cy="8" r="3"/><path d="M3 21v-3a6 6 0 0 1 12 0v3M16 5a3 3 0 0 1 0 6M21 21v-3a6 6 0 0 0-4-5"/></svg><span>Contacts</span></button>
            <button type="button" aria-label="Réglages" onClick={()=>{setSettingsOpen(true);void loadSettings();}}><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" aria-hidden="true"><path d="M4 7h16M4 17h16"/><circle cx="9" cy="7" r="3" fill="currentColor"/><circle cx="15" cy="17" r="3" fill="currentColor"/></svg><span>Réglages</span></button>
            <form action="/logout" method="post" className="city-logout"><button type="submit">Quitter</button></form>
          </nav>
          <div className="game-status-hud"><i className="live-dot"/> City active <small>{snapshot?.today_completed??0} missions aujourd’hui</small></div>
          <div className="world-hint">S&eacute;lectionne un bureau ou un robot pour ouvrir son espace.</div></div>
        <div className="world-footer"><span><i className="room-dot trading"/> March&eacute;s</span><span><i className="room-dot career"/> Carri&egrave;res</span><span><i className="room-dot lab"/> Laboratoire</span><span className="world-footer-note">Les robots r&eacute;agissent aux missions et transferts r&eacute;els.</span></div>      </div>
      {panelCollapsed&&<button className="console-reopen" onClick={()=>setPanelCollapsed(false)} aria-label="Ouvrir le centre de commande">☰ Command Center</button>}
      <aside className="agent-panel command-console" aria-label="Centre de commande">
        <div className="console-resizer" role="separator" aria-label="Largeur du panneau" aria-orientation="vertical" aria-valuenow={panelWidth} aria-valuemin={340} aria-valuemax={600} tabIndex={0}
          onKeyDown={e=>{if(e.key==="ArrowLeft"||e.key==="ArrowRight"){e.preventDefault();setPanelWidth(w=>Math.max(340,Math.min(600,w+(e.key==="ArrowLeft"?20:-20))));}}}
          onPointerDown={e=>{resizeStart.current={x:e.clientX,width:panelWidth};e.currentTarget.setPointerCapture(e.pointerId);}}
          onPointerMove={e=>{if(resizeStart.current)setPanelWidth(Math.max(340,Math.min(600,resizeStart.current.width+resizeStart.current.x-e.clientX)));}}
          onPointerUp={()=>{resizeStart.current=null;}} onPointerCancel={()=>{resizeStart.current=null;}}/>
        <Cockpit agents={snapshot?.agents||[]} tasks={snapshot?.tasks||[]} events={snapshot?.events||[]} selectedId={selectedId}
          onSelect={id=>{setSelectedId(id);setPanelCollapsed(false);setWindowMode("agent");}} onCollapse={()=>setPanelCollapsed(true)}
          onNotifications={openNotifications} onOpen={inspectCockpitTask}
          onChat={message=>{if(message)setChatInput(message);openAgent("desk_manager","chat");}}
          onContacts={()=>setWindowMode("contacts")} onCancel={id=>api(`/city/api/tasks/${id}/cancel`,{})}
          onLaunch={id=>id==="internship_scout"?api('/city/api/collect/internships',{}):id==="market_analyst"?api('/city/api/collect/markets',{}):api(`/city/api/agents/${id}/run`,{})}
          onReview={()=>api('/city/api/jules/review',{})} onCode={request=>api('/city/api/jules/change',{request})} onRefresh={refresh}
          onSite={kind=>void openLocalSite(kind)} siteBusy={!!launchingSite} siteError={siteError}/>

      </aside>
    </div>
    {windowMode==="chat"&&<ManagerChatWindow onClose={()=>setWindowMode("agent")}>{managerChat}</ManagerChatWindow>}
    {windowMode==="contacts"&&<NetworkContactsWindow onClose={()=>setWindowMode("agent")}/>}
    {windowMode==="missions"&&<section className="game-popup game-mission-control" aria-label="Mission Control">
      <div className="game-popup-heading"><div><strong>Mission Control</strong><small>{activeCount} en cours &middot; {pendingCount} à valider</small></div><button type="button" onClick={()=>setWindowMode("none")} aria-label="Fermer">&times;</button></div>
      {managerPanel()}</section>}
    {windowMode==="activity"&&<NotificationCenter key={`${notificationView.filter}-${notificationView.agent}`} initialFilter={notificationView.filter} initialAgent={notificationView.agent} tasks={snapshot?.tasks||[]} events={snapshot?.events||[]} agents={snapshot?.agents||[]} readThrough={notificationReadThrough}
      onClose={()=>setWindowMode("agent")} onOpen={id=>{const task=snapshot?.tasks.find(t=>t.id===id);if(task)showResult(task);else setError("Cette mission n'est plus dans les données chargées.");}}
      onRead={async()=>{const result=await api<{last_read_event_id:number}>("/city/api/notifications/read",{read_through:Math.max(0,...(snapshot?.events||[]).map(e=>e.id))});setNotificationReadThrough(result.last_read_event_id);}}
      onRelaunch={()=>api("/city/api/agents/job_hunter/run",{})} onCodeRequest={request=>api('/city/api/jules/change',{request})} onCodexReview={()=>api('/city/api/jules/review',{})} onApprove={id=>api(`/city/api/tasks/${id}/approve`,{})}
      onCancel={id=>api(`/city/api/tasks/${id}/cancel`,{})} onReview={(id,approved)=>api(`/city/api/proposals/${id}/review`,{approved})}
      onRetry={id=>api(`/city/api/tasks/${id}/retry`,{})} onRefresh={refresh}/>}
    {error&&<div className="city-toast" role="alert"><span>{error}</span><button type="button" onClick={()=>setError("")} aria-label="Fermer">&times;</button></div>}
    {resultTaskId&&<section className={`game-popup mission-results-window ${snapshot?.tasks.find(t=>t.id===resultTaskId)?.agent_id==='market_analyst'?'market-brief-window':''}`} role="dialog" aria-label="Résultat de mission"><div className="game-popup-heading"><div><strong>Résultat de mission</strong><small>Contributions enregistrées par les agents</small></div><button type="button" onClick={()=>setResultTaskId(null)} aria-label="Fermer le résultat">×</button></div><div className="mission-results-body">
      {(()=>{const root=snapshot?.tasks.find(t=>t.id===resultTaskId);if(!root)return <p>Cette mission n’est plus disponible dans les données chargées.</p>;
        const parts=root.workflow_id?(snapshot?.tasks||[]).filter(t=>t.workflow_id===root.workflow_id):[root];
        return <><h2>{root.description}</h2>{parts.map(task=><article className={`mission-result-part ${task.agent_id==='market_analyst'?'market-brief-result':''}`} key={task.id}><header><strong>{snapshot?.agents.find(a=>a.id===task.agent_id)?.name||task.agent_id}</strong><span className={`task-chip ${task.status}`}>{LABELS[task.status]}</span></header><h3>{task.description}</h3><small>{dateTime(task.finished_at||task.created_at)} · ID {task.id}</small>
          {task.error&&<p className="error-copy">{task.error}</p>}
          {!["completed","failed","cancelled"].includes(task.status)&&<p className="muted">Contribution : {LABELS[task.status].toLocaleLowerCase()}.</p>}
          {task.agent_id==='market_analyst'&&task.result.market_data?.length&&<div className="market-brief-heading"><div><span>POINT MARCHÉS</span><strong>{task.result.title||'Brief de marché'}</strong><small>{task.result.market_points??task.result.market_data.length} séries vérifiées · relevé {dateTime(task.result.as_of)}</small></div><span aria-hidden="true">◈</span></div>}
          {task.agent_id==='market_analyst'&&task.result.sentiment&&<div className={`market-sentiment ${task.result.sentiment.label==='Défensif'?'defensive':task.result.sentiment.label==='Constructif'?'constructive':'mixed'}`}><div><span>SENTIMENT DU MARCHÉ</span><strong>{task.result.sentiment.label}</strong></div><div><b>Confiance {task.result.sentiment.confidence}</b><small>{task.result.sentiment.signals.length} signaux observés · {task.result.sentiment.supporting_news.length} titre(s) concordant(s)</small></div></div>}
          {task.agent_id==='market_analyst'&&task.result.market_data?.length&&<div className="market-brief-grid">{task.result.market_data.map(p=><div className="market-brief-kpi" key={p.series_id}><span>{p.label}</span><strong>{new Intl.NumberFormat('fr-FR',{maximumFractionDigits:4}).format(p.value)} <small>{p.unit}</small></strong><small>{p.change_display&&p.change_display!=='N/A'?`${p.change_display} · `:''}{p.observed_at}</small>{p.source_url?.startsWith('https://')&&<a href={p.source_url} target="_blank" rel="noopener noreferrer">Source ↗</a>}</div>)}</div>}
          {task.result.title&&task.agent_id!=='market_analyst'&&<h4>{task.result.title}</h4>}{task.result.text&&<MarkdownText text={task.result.text}/>}
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
      <p>La cl&eacute; du fournisseur reste sur le serveur. Choisis le mod&egrave;le par agent et tes limites de d&eacute;penses.</p>
      <div className="settings-model-grid">{INITIAL_IDS.map(id=><label key={id}>{snapshot?.agents.find(agent=>agent.id===id)?.name||id}<select value={settings.models[id]||"gpt-4o-mini"} onChange={event=>setSettings({...settings,models:{...settings.models,[id]:event.target.value}})}>{(settings.available_models||["gpt-4o-mini"]).map(model=><option key={model}>{model}</option>)}</select></label>)}</div>
<div className="cost-line"><span>Usage IA du compte</span><strong>{snapshot?.api_usage.calls??0} appel(s) API &middot; ${(snapshot?.api_usage.estimated_usd??0).toFixed(4)}</strong><small>Codex utilise les limites de ta connexion ChatGPT.</small></div>
            <section className="diagnostics-section"><div className="section-heading"><h3>Diagnostics des services</h3><button type="button" className="secondary-button" onClick={()=>void checkIntegrations()} disabled={diagnosticsBusy}>{diagnosticsBusy?"V&eacute;rification...":"V&eacute;rifier"}</button></div>{diagnostics&&<div className="integration-list">{diagnostics.map(item=><article className="integration-row" key={item.name}><span className={`integration-dot ${item.status.toLowerCase()}`}/><div><strong>{item.name}</strong><small>{item.source} &middot; {item.access}</small><p>{item.detail}</p></div><b className={`integration-status ${item.status.toLowerCase()}`}>{item.status}</b></article>)}</div>}</section>
      <div className="settings-limits"><label>Plafond quotidien ($)<input type="number" min="0" max="1000" step="0.5" value={settings.daily_limit_usd} onChange={event=>setSettings({...settings,daily_limit_usd:Number(event.target.value)})}/></label><label>Plafond mensuel ($)<input type="number" min="0" max="10000" step="1" value={settings.monthly_limit_usd} onChange={event=>setSettings({...settings,monthly_limit_usd:Number(event.target.value)})}/></label><label>Missions simultan&eacute;es<select value={settings.max_concurrent_tasks} onChange={event=>setSettings({...settings,max_concurrent_tasks:Number(event.target.value)})}>{[1,2,3,4,5,6].map(value=><option key={value} value={value}>{value}</option>)}</select></label></div>
      <label className="settings-checkbox"><input type="checkbox" checked={settings.auto_tasks} onChange={event=>setSettings({...settings,auto_tasks:event.target.checked})}/><span>Lancer les missions d&egrave;s leur ajout ; sinon, demander mon approbation</span></label><small className={settings.api_key_configured?"provider-ready":"provider-missing"}>{settings.api_key_configured?"OpenAI est configur&eacute; c&ocirc;t&eacute; serveur.":"OPENAI_API_KEY n'est pas configur&eacute;e sur le serveur."}</small>
      <div className="dialog-actions"><button type="button" className="secondary-button" onClick={()=>setSettingsOpen(false)}>Fermer</button><button type="submit" className="primary-button" disabled={settingsBusy}>{settingsBusy?"Enregistrement...":"Enregistrer"}</button></div>
    </form></div>}
  </div>;
}

createRoot(document.getElementById("root")!).render(<App />);


