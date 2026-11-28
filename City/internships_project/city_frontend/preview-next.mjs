// Serves the new interface on http://127.0.0.1:7879/city/next/ with made-up data.
// For screenshots only: no login, no database, no agent is contacted.
import { createServer } from "node:http";
import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { dirname, extname, resolve, sep } from "node:path";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "../city_assets/next");
const TYPES = { ".html": "text/html; charset=utf-8", ".js": "text/javascript", ".css": "text/css", ".ttf": "font/ttf" };
const ago = minutes => new Date(Date.now() - minutes * 60000).toISOString();
const ROSTER = [["desk_manager", "Desk Manager", "Coordinateur"], ["market_analyst", "Mira", "Market Analyst"], ["finance_tutor", "Noé", "Quant Research"],
  ["job_hunter", "Jules", "Software Engineer"], ["networker", "Lina", "Networker"], ["securities_scout", "Clara", "Securities Services Scout"],
  ["prime_services_scout", "Élodie", "Prime Services & Clearing Scout"], ["outreach_agent", "Iris", "Outreach Agent"], ["developer", "Axel", "Interview Coach"],
  ["innovation_lab", "Nova", "Innovation Lab"], ["internship_scout", "Hugo", "Internship Scout"], ["city_ui_engineer", "Camille", "UI Engineer"],
  ["internships_engineer", "Sacha", "Sources Engineer"], ["quality_engineer", "Maël", "Quality Engineer"]];
const task = (n, agent_id, status, description, extra = {}) => ({ id: String(n).padStart(32, "a"), agent_id, task_type: "mission", description, status,
  created_at: ago(90 - n), started_at: ago(80 - n), finished_at: ["completed", "failed"].includes(status) ? ago(30 - n) : undefined,
  result: {}, xp_awarded: 0, input_tokens: 0, output_tokens: 0, api_cost_usd: 0, depends_on: [], ...extra });
const tasks = [
  task(1, "market_analyst", "running", "Collecter les données Markets et produire le brief"),
  task(2, "outreach_agent", "waiting_approval", "Préparer un brouillon pour le contact Fixed Income Sales le plus pertinent"),
  task(3, "internship_scout", "running", "Chercher les stages publiés aujourd’hui"),
  task(4, "finance_tutor", "queued", "Backtest momentum 12-1 sur l’Euro Stoxx 50, coûts inclus"),
  task(5, "networker", "completed", "Rechercher les écoles de cinq contacts", { result: { summary: "Cinq écoles retrouvées, trois confirmées par une source publique.", text: "Lina a croisé les profils publics et les annuaires d’anciens.\n\nTrois formations sont confirmées par deux sources ; deux restent à vérifier." } }),
  task(6, "quality_engineer", "failed", "Corriger la reprise des collectes interrompues", { error: "Les vérifications ont échoué : 2 tests en erreur." }),
  task(7, "innovation_lab", "completed", "Veille open source du jeudi", { result: { summary: "Deux propositions documentées.", role_version: 2, approval_required: true } }),
];
const events = tasks.flatMap((item, i) => [{ id: i * 2 + 1, agent_id: item.agent_id, task_id: item.id, status: "queued", message: "Mission ajoutée à la file.", created_at: item.created_at },
  { id: i * 2 + 2, agent_id: item.agent_id, task_id: item.id, status: item.status, message: item.status === "running" ? "Mission démarrée." : "État mis à jour.", created_at: item.started_at }]);
const latest = id => tasks.find(item => item.agent_id === id) || null;
const state = () => ({ agents: ROSTER.map(([id, name, role], i) => ({ id, name, role, area: "", description: "", available: true, xp: 120 + i * 37, level: 2 + (i % 4), level_progress: (i * 0.17) % 1,
  achievements: [], status: latest(id)?.status || "idle", latest: latest(id) })), tasks, events, workflows: [], today_completed: 3, week_completed: 21, manager_console_version: 1,
  api_usage: { calls: 12, estimated_usd: 0.04 } });

createServer(async (request, response) => {
  const url = new URL(request.url, "http://127.0.0.1");
  const json = body => { response.writeHead(200, { "Content-Type": "application/json", "Cache-Control": "no-store" }); response.end(JSON.stringify(body)); };
  if (url.pathname === "/city/api/state") return json(state());
  if (url.pathname === "/city/api/chat/desk_manager") return json({ messages: [{ role: "assistant", content: "Bonsoir. Mira termine le brief de marché, Hugo cherche les stages du jour et Iris attend ta validation pour un brouillon." }] });
  if (url.pathname.startsWith("/city/api/")) return json({});
  const relative = url.pathname.replace(/^\/city\/next\/?/, "") || "index.html", file = resolve(root, relative);
  if (!url.pathname.startsWith("/city/next") || !file.startsWith(root + sep)) { response.writeHead(404); return response.end("Introuvable"); }
  try { const body = await readFile(file); response.writeHead(200, { "Content-Type": TYPES[extname(file)] || "application/octet-stream", "Cache-Control": "no-store" }); response.end(body); }
  catch { response.writeHead(404); response.end("Introuvable"); }
}).listen(7879, "127.0.0.1", () => console.log("Aperçu : http://127.0.0.1:7879/city/next/"));
