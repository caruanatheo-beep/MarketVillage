type MarketReading = {
  series_id: string;
  label: string;
  value: number;
  unit?: string;
  observed_at?: string;
};

type Offer = {
  title: string;
  company: string;
  location?: string;
  url?: string;
  kind?: string;
  start_period?: string;
  published?: string;
  published_inferred?: boolean;
  source?: string;
  selection_source?: string;
  selection_reason?: string;
};

type MarketResponse = { points?: MarketReading[]; retrieved_at?: string; error?: string };
type InternshipResponse = {
  featured_offer?: Offer | null;
  updated_at?: string;
  total_count?: number;
  source_errors?: number;
  error?: string;
};
type CityTask = {
  id: string;
  agent_id: string;
  status: string;
  finished_at?: string;
  result?: { featured_offer?: Offer | null; total_count?: number; source_errors?: number; updated_at?: string; new_count?: number };
};
type CityState = { tasks?: CityTask[] };

type LiveView = {
  marketPoints: MarketReading[];
  marketError: string;
  marketUpdatedAt: string;
  offer: Offer | null;
  offerCount: number;
  sourceErrors: number;
  internshipError: string;
  internshipUpdatedAt: string;
  status: string;
  busy: "markets" | "internships" | null;
};

const view: LiveView = {
  marketPoints: [], marketError: "", marketUpdatedAt: "", offer: null,
  offerCount: 0, sourceErrors: 0, internshipError: "", internshipUpdatedAt: "",
  status: "", busy: null,
};
const esc = (value: string) => value;

function make<K extends keyof HTMLElementTagNameMap>(tag: K, className = "", text = ""): HTMLElementTagNameMap[K] {
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (text) element.textContent = esc(text);
  return element;
}

async function get<T>(path: string): Promise<T> {
  const response = await fetch(path, { credentials: "same-origin", cache: "no-store" });
  const payload = await response.json().catch(() => ({})) as Record<string, unknown>;
  if (!response.ok) throw new Error(String(payload.detail || payload.error || `Erreur HTTP ${response.status}`));
  return payload as T;
}

function dateKey(value?: string): string {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}

function shortDate(value?: string): string {
  if (!value) return "date indisponible";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : new Intl.DateTimeFormat("fr-FR", {
    day: "numeric", month: "short", year: "numeric",
  }).format(date);
}

function agentOffer(tasks: CityTask[] | undefined): { offer: Offer; finishedAt: string; today: boolean; result: NonNullable<CityTask["result"]> } | null {
  const today = dateKey(new Date().toISOString());
  const completed = [...(tasks || [])]
    .filter(task => task.agent_id === "networker" && task.status === "completed" && task.result?.featured_offer?.title)
    .sort((a, b) => (b.finished_at || "").localeCompare(a.finished_at || ""));
  const selected = completed.find(task => dateKey(task.finished_at) === today) || completed[0];
  const offer = selected?.result?.featured_offer;
  return selected && offer ? { offer, finishedAt: selected.finished_at || "", today: dateKey(selected.finished_at) === today,
    result: selected.result || {} } : null;
}

function safeUrl(value?: string): string {
  try {
    const url = new URL(value || "");
    return url.protocol === "https:" || url.protocol === "http:" ? url.href : "";
  } catch { return ""; }
}

function formatReading(point: MarketReading): string {
  const digits = point.series_id.startsWith("DEX") ? 4 : 2;
  const value = Number(point.value).toLocaleString("fr-FR", { maximumFractionDigits: digits });
  return `${value}${point.unit ? ` ${point.unit}` : ""}`;
}

let root: HTMLDivElement | null = null;
let marketValues: HTMLDivElement;
let marketMeta: HTMLParagraphElement;
let marketStatus: HTMLParagraphElement;
let marketButton: HTMLButtonElement;
let offerTitle: HTMLAnchorElement;
let offerCompany: HTMLParagraphElement;
let offerMeta: HTMLParagraphElement;
let offerMeta2: HTMLParagraphElement;
let offerSource: HTMLParagraphElement;
let offerStatus: HTMLParagraphElement;
let offerButton: HTMLButtonElement;
let offerLink: HTMLAnchorElement;

function setButton(button: HTMLButtonElement, label: string, busy: boolean): void {
  button.textContent = label;
  button.disabled = busy || view.busy !== null;
  button.classList.toggle("is-busy", busy);
}

function render(): void {
  if (!root) return;
  const wanted = ["DGS10", "DGS2", "DEXUSEU", "SP500", "VIXCLS"];
  const points = wanted.map(id => view.marketPoints.find(point => point.series_id === id)).filter((p): p is MarketReading => !!p).slice(0, 4);
  marketValues.replaceChildren();
  for (const point of points) {
    const item = make("div", "city-live-value");
    item.append(make("span", "city-live-value-label", point.label));
    item.append(make("strong", "city-live-value-number", formatReading(point)));
    marketValues.append(item);
  }
  const observedDates = points.map(p => p.observed_at || "").filter(Boolean).sort();
  marketMeta.textContent = points.length
    ? `Observations Markets · ${shortDate(observedDates[observedDates.length - 1])}`
    : "Service Markets · données du cache";
  marketStatus.textContent = view.busy === "markets" ? view.status : (points.length
    ? "Valeurs chargées depuis Markets."
    : view.marketError || "Aucune observation disponible. Lance une collecte via Noé.");
  setButton(marketButton, view.busy === "markets" ? "Mira actualise…" : "Actualiser via Noé", view.busy === "markets");

  const offer = view.offer;
  const url = safeUrl(offer?.url);
  offerTitle.textContent = offer?.title || "";
  offerTitle.href = url || "#";
  offerTitle.hidden = !offer;
  offerTitle.classList.toggle("is-unavailable", !url);
  offerTitle.setAttribute("aria-disabled", String(!url));
  offerCompany.textContent = offer ? `${offer.company} · ${offer.location || "Lieu non indiqué"}`
    : view.internshipError ? "Redémarre City pour lire le cache Internships."
      : "Aucune offre en cache. Lance une collecte avec Jules.";
  offerMeta.textContent = offer ? [offer.kind, offer.start_period ? `Début : ${offer.start_period}` : "Début à confirmer"].filter(Boolean).join(" · ") : "";
  offerMeta2.textContent = offer
    ? offer.published ? (offer.published_inferred ? `Détectée le ${offer.published}` : `Publiée le ${offer.published}`) : "Date de publication inconnue"
    : "";
  offerSource.textContent = offer
    ? `${offer.selection_source === "job_hunter" ? `Collecte Internships · Lina ${offer.selection_reason || ""}` : "Classement actuel d’Internships"}${view.offerCount ? ` · ${view.offerCount} offres` : ""}${view.sourceErrors ? ` · ${view.sourceErrors} sources indisponibles` : ""}`
    : view.internshipError ? "Connexion au cache en attente de redémarrage" : view.internshipUpdatedAt ? `Cache vérifié le ${shortDate(view.internshipUpdatedAt)}` : "";
  offerStatus.textContent = view.busy === "internships" ? view.status
    : offer && !url ? "Lien direct indisponible dans la donnée source." : "";
  offerLink.hidden = !url;
  offerLink.href = url || "#";
  setButton(offerButton, view.busy === "internships" ? "Lina recherche…" : "Actualiser via Lina", view.busy === "internships");
}

function buildOverlay(stage: HTMLElement): void {
  root = make("div", "city-live-data-overlay");
  root.setAttribute("aria-label", "Données réelles des services Markets et Internships");
  const market = make("section", "city-live-data-card city-live-market");
  market.setAttribute("aria-label", "Données Markets");
  const marketHead = make("div", "city-live-card-head");
  const marketHeading = make("h2", "", "Markets · données réelles");
  marketMeta = make("p", "city-live-meta");
  marketHead.append(marketHeading, marketMeta);
  marketValues = make("div", "city-live-market-values");
  marketStatus = make("p", "city-live-status");
  marketButton = make("button", "city-live-action", "Actualiser via Noé");
  marketButton.type = "button";
  marketButton.addEventListener("click", () => { void startCollection("markets"); });
  market.append(marketHead, marketValues, marketStatus, marketButton);

  const jobs = make("section", "city-live-data-card city-live-jobs");
  jobs.setAttribute("aria-label", "Offre prioritaire du service Internships");
  const jobsHead = make("div", "city-live-card-head");
  jobsHead.append(make("h2", "", "Stage à examiner"));
  offerSource = make("p", "city-live-meta");
  jobsHead.append(offerSource);
  offerTitle = make("a", "city-live-offer-title");
  offerTitle.target = "_blank";
  offerTitle.rel = "noopener noreferrer";
  offerTitle.addEventListener("click", event => { if (!safeUrl(view.offer?.url)) event.preventDefault(); });
  offerCompany = make("p", "city-live-company");
  offerMeta = make("p", "city-live-meta city-live-offer-meta");
  offerMeta2 = make("p", "city-live-meta city-live-offer-meta");
  offerStatus = make("p", "city-live-status");
  const actions = make("div", "city-live-actions");
  offerButton = make("button", "city-live-action", "Actualiser via Lina");
  offerButton.type = "button";
  offerButton.addEventListener("click", () => { void startCollection("internships"); });
  offerLink = make("a", "city-live-offer-link", "Voir l’offre ↗");
  offerLink.target = "_blank";
  offerLink.rel = "noopener noreferrer";
  actions.append(offerButton, offerLink);
  jobs.append(jobsHead, offerTitle, offerCompany, offerMeta, offerMeta2, offerStatus, actions);

  root.append(market, jobs);
  stage.append(root);
  render();
}

async function loadFeeds(): Promise<void> {
  const [marketResult, internshipResult, stateResult] = await Promise.allSettled([
    get<MarketResponse>("/city/api/market-snapshot"),
    get<InternshipResponse>("/city/api/internship-highlight"),
    get<CityState>("/city/api/state"),
  ]);
  if (marketResult.status === "fulfilled") {
    view.marketPoints = marketResult.value.points || [];
    view.marketError = marketResult.value.error || "";
    view.marketUpdatedAt = marketResult.value.retrieved_at || "";
  } else view.marketError = marketResult.reason instanceof Error ? marketResult.reason.message : "Markets indisponible.";
  let cacheOffer: Offer | null = null;
  if (internshipResult.status === "fulfilled") {
    const data = internshipResult.value;
    cacheOffer = data.featured_offer || null;
    view.offerCount = data.total_count || 0;
    view.sourceErrors = data.source_errors || 0;
    view.internshipError = data.error || "";
    view.internshipUpdatedAt = data.updated_at || "";
  } else {
    const message = internshipResult.reason instanceof Error ? internshipResult.reason.message : "Internships indisponible.";
    view.internshipError = /404|not found/i.test(message)
      ? "Cache Internships direct activé après redémarrage de MarketDesk City."
      : message;
  }
  if (stateResult.status === "fulfilled") {
    const result = agentOffer(stateResult.value.tasks);
    view.offer = result
      ? { ...result.offer, selection_source: "job_hunter",
          selection_reason: `${result.today ? "aujourd’hui" : `le ${shortDate(result.finishedAt)}`} · ${result.result.new_count ?? 0} nouvelles offres` }
      : cacheOffer;
    if (result) {
      view.offerCount = result.result.total_count || view.offerCount;
      view.sourceErrors = result.result.source_errors ?? view.sourceErrors;
      view.internshipUpdatedAt = result.result.updated_at || view.internshipUpdatedAt;
    }
  } else view.offer = cacheOffer;
  if (!view.offer && view.internshipError && !/après redémarrage/i.test(view.internshipError)) {
    view.internshipError = `Lecture Internships indisponible : ${view.internshipError}`;
  }
  render();
}

async function startCollection(kind: "markets" | "internships"): Promise<void> {
  if (view.busy) return;
  view.busy = kind;
  view.status = kind === "markets" ? "Noé lance la collecte Markets…" : "Lina lance la collecte Internships…";
  render();
  try {
    const response = await fetch(`/city/api/collect/${kind}`, {
      method: "POST", credentials: "same-origin", cache: "no-store",
      headers: { "Content-Type": "application/json", "X-MarketDesk-City": "1" }, body: "{}",
    });
    const data = await response.json() as { detail?: string; task?: CityTask };
    if (!response.ok) throw new Error(data.detail || `Collecte refusée (${response.status}).`);
    const taskId = data.task?.id;
    if (taskId) await waitForCollection(kind, taskId);
    else {
      view.status = "Une collecte est déjà en cours.";
      await loadFeeds();
    }
  } catch (error) {
    view.status = error instanceof Error ? error.message : "La collecte n’a pas pu démarrer.";
  } finally {
    view.busy = null;
    render();
  }
}

async function waitForCollection(kind: "markets" | "internships", taskId: string): Promise<void> {
  for (let attempt = 0; attempt < 60; attempt++) {
    await new Promise(resolve => window.setTimeout(resolve, 3000));
    const state = await get<CityState>("/city/api/state");
    const task = (state.tasks || []).find(item => item.id === taskId);
    if (!task) continue;
    if (task.status === "completed") {
      view.status = kind === "markets" ? "Collecte Markets terminée." : "Collecte Internships terminée.";
      await loadFeeds();
      return;
    }
    if (["failed", "cancelled"].includes(task.status)) {
      view.status = kind === "markets" ? "Collecte Markets interrompue. Consulte les détails de Noé." : "Collecte Internships interrompue. Consulte les détails de Lina.";
      return;
    }
    render();
  }
  view.status = "Collecte toujours en cours ; le suivi continue dans Missions.";
}

function mountIfNeeded(): void {
  if ((window as Window & { __marketdeskNativePanels?: boolean }).__marketdeskNativePanels || root) return;
  const stage = document.querySelector<HTMLElement>(".world-stage.tower-world");
  if (!stage) { window.setTimeout(mountIfNeeded, 300); return; }
  buildOverlay(stage);
  void loadFeeds();
  window.setInterval(() => { if (!document.hidden && !view.busy) void loadFeeds(); }, 60000);
}

window.setTimeout(mountIfNeeded, 250);
