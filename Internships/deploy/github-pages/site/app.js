"use strict";
const $ = (id) => document.getElementById(id);
const controls = ["search", "category", "family", "period", "start"];
const selects = controls.slice(1);
// Short, shareable query keys for each control.
const urlKeys = {search: "q", category: "contrat", family: "metier", period: "publication", start: "debut"};
const normalize = (s) => String(s || "").normalize("NFKD").replace(/\p{M}/gu, "").toLowerCase().replace(/[^\p{L}\p{N}]+/gu, " ").trim();
let offers = [], shown = 0;
let sortMode = "rank";
let resultsAnimation;
const reduceMotion = matchMedia("(prefers-reduced-motion: reduce)");
const touchScreen = matchMedia("(pointer: coarse)").matches;
const sheetLayout = matchMedia("(max-width: 760px)");
const size = 50;
const filterViews = new Map();
let openFilter = null;
const initialQuery = new URLSearchParams(location.search);
let pendingQuery = initialQuery;
function enhanceFilter(select) {
  const field = select.parentElement;
  const trigger = document.createElement("button"), value = document.createElement("span");
  const chevron = document.createElement("span"), menu = document.createElement("div");
  trigger.type = "button"; trigger.id = select.id + "-trigger"; trigger.className = "filter-trigger";
  value.id = select.id + "-value"; chevron.className = "filter-chevron"; chevron.setAttribute("aria-hidden", "true");
  trigger.append(value, chevron);
  menu.id = select.id + "-menu"; menu.className = "filter-menu"; menu.hidden = true;
  menu.setAttribute("role", "listbox"); menu.setAttribute("aria-labelledby", select.id + "-label");
  trigger.setAttribute("role", "combobox"); trigger.setAttribute("aria-haspopup", "listbox");
  trigger.setAttribute("aria-expanded", "false"); trigger.setAttribute("aria-controls", menu.id);
  trigger.setAttribute("aria-labelledby", select.id + "-label " + value.id);
  $(select.id + "-label").htmlFor = trigger.id;
  field.append(trigger, menu); select.hidden = true;
  let active = 0, typed = "", typedAt = 0;
  const isOpen = () => !menu.hidden;
  function highlight(index, scroll = true) {
    active = Math.max(0, Math.min(index, menu.children.length - 1));
    for (const [i, option] of [...menu.children].entries()) option.classList.toggle("is-highlighted", i === active);
    if (isOpen() && menu.children[active]) {
      trigger.setAttribute("aria-activedescendant", menu.children[active].id);
      if (scroll) menu.children[active].scrollIntoView({block:"nearest"});
    }
  }
  function close() {
    menu.hidden = true; trigger.setAttribute("aria-expanded", "false");
    trigger.removeAttribute("aria-activedescendant"); field.classList.remove("is-open");
    if (openFilter === api) openFilter = null;
    typed = "";
  }
  function sync() {
    value.textContent = select.selectedOptions[0]?.textContent || "";
    trigger.classList.toggle("is-selected", Boolean(select.value));
    for (const [i, option] of [...menu.children].entries()) option.setAttribute("aria-selected", String(i === select.selectedIndex));
  }
  function choose(index) {
    select.selectedIndex = index; close(); sync();
    select.dispatchEvent(new Event("change", {bubbles:true})); trigger.focus();
  }
  function open() {
    if (openFilter) openFilter.close();
    menu.hidden = false; trigger.setAttribute("aria-expanded", "true"); field.classList.add("is-open");
    menu.style.maxHeight = "";
    const box = field.getBoundingClientRect(), height = menu.getBoundingClientRect().height;
    // Keep the 6px menu gap and an 8px viewport margin.
    const below = window.innerHeight - box.bottom - 14, above = box.top - 14;
    const opensUp = below < height && above > below;
    menu.classList.toggle("opens-up", opensUp);
    menu.style.maxHeight = Math.max(0, Math.min(height, opensUp ? above : below)) + "px";
    openFilter = api; highlight(select.selectedIndex);
  }
  function refresh() {
    close(); menu.replaceChildren();
    for (const [i, option] of [...select.options].entries()) {
      const item = document.createElement("div"); item.id = select.id + "-option-" + i;
      item.className = "filter-option"; item.setAttribute("role", "option"); item.textContent = option.textContent;
      item.addEventListener("click", () => choose(i));
      item.addEventListener("pointermove", () => highlight(i, false)); menu.append(item);
    }
    sync();
  }
  const api = {close, sync, refresh};
  trigger.addEventListener("click", () => isOpen() ? close() : open());
  trigger.addEventListener("keydown", (event) => {
    if (event.key === "Tab") {close(); return;}
    if (event.key === "Escape") {if (isOpen()) event.preventDefault(); close(); return;}
    if (["ArrowDown", "ArrowUp", "Home", "End", "Enter", " "].includes(event.key)) {
      event.preventDefault();
      const wasOpen = isOpen(); if (!wasOpen) open();
      if (event.key === "Home") highlight(0);
      else if (event.key === "End") highlight(menu.children.length - 1);
      else if (wasOpen && ["Enter", " "].includes(event.key)) choose(active);
      else if (wasOpen) highlight(active + (event.key === "ArrowDown" ? 1 : -1));
    } else if (event.key.length === 1 && !event.ctrlKey && !event.metaKey && !event.altKey) {
      event.preventDefault(); if (!isOpen()) open();
      typed = Date.now() - typedAt > 700 ? event.key : typed + event.key; typedAt = Date.now();
      const choices = [...select.options];
      const match = choices.findIndex(option => normalize(option.textContent).startsWith(normalize(typed)));
      if (match >= 0) highlight(match);
    }
  });
  filterViews.set(select.id, api); refresh();
}
document.addEventListener("pointerdown", (event) => {
  if (openFilter && !event.target.closest(".filter-field.is-open")) openFilter.close();
});
function safeLink(value) {
  try { const u = new URL(value); return u.protocol === "https:" && !u.username && !u.password ? u.href : null; }
  catch { return null; }
}
function parisToday() {
  return new Intl.DateTimeFormat("en-CA", {timeZone: "Europe/Paris", year: "numeric", month: "2-digit", day: "2-digit"}).format(new Date());
}
function relativeDate(published, today) {
  const days = Math.round((Date.parse(today + "T12:00:00Z") - Date.parse(published + "T12:00:00Z")) / 86400000);
  if (!Number.isFinite(days) || days < 0) return {text: "", fresh: false};
  if (days === 0) return {text: "Nouveau · aujourd’hui", fresh: true};
  if (days === 1) return {text: "Nouveau · hier", fresh: true};
  if (days < 60) return {text: `Il y a ${days} j`, fresh: false};
  return {text: `Il y a ${Math.floor(days / 30)} mois`, fresh: false};
}
// Variants differ only by a trailing parenthesis (language, class…); everything else must match.
const baseTitle = (title) => {
  const base = title.replace(/\s*\([^()]*\)\s*$/u, "").replace(/[\s,;:–-]+$/u, "").trim();
  return base !== title.trim() && base.length >= 8 ? base : "";
};
function groupVariants(list) {
  const groups = new Map(), result = [];
  for (const job of list) {
    const base = baseTitle(job.title);
    const key = [job.company, normalize(base), job.location, job.start, job.kind].join("|");
    const group = base && groups.get(key);
    if (group) { group.variants.push(job); continue; }
    const entry = {job, base, variants: [job]};
    if (base) groups.set(key, entry);
    result.push(entry);
  }
  return result;
}
function filteredOffers() {
  const terms = normalize($("search").value).split(/\s+/).filter(Boolean);
  const today = parisToday();
  const week = new Date(today + "T12:00:00Z"); week.setUTCDate(week.getUTCDate() - 6);
  const first = week.toISOString().slice(0,10);
  const selected = offers.filter((j) => terms.every((t) => normalize(j.title + " " + j.company + " " + j.location + " " + (j.location_source || "")).includes(t))
    && (!$("category").value || j.categories.includes($("category").value))
    && (!$("family").value || j.family === $("family").value)
    && (!$("start").value || j.start_month && j.start_month >= $("start").value)
    && (!$("period").value || $("period").value === "daily" && j.published === today
      || $("period").value === "weekly" && j.published >= first && j.published <= today));
  if (sortMode === "recent") selected.sort((a,b) => b.published.localeCompare(a.published));
  return groupVariants(selected);
}
function activeFilters() {
  const active = [];
  const search = $("search").value.trim();
  if (search) active.push({id: "search", label: "« " + search + " »"});
  for (const id of selects) if ($(id).value) active.push({id, label: $(id).selectedOptions[0]?.textContent || $(id).value});
  return active;
}
function clearControl(id) {
  if (id === "search") $("search").value = "";
  else $(id).selectedIndex = 0;
}
function writeUrl() {
  const params = new URLSearchParams();
  for (const id of controls) { const value = $(id).value.trim(); if (value) params.set(urlKeys[id], value); }
  if (sortMode !== "rank") params.set("tri", "recent");
  const query = params.toString();
  const target = location.pathname + (query ? "?" + query : "") + location.hash;
  if (target !== location.pathname + location.search + location.hash) {
    try { history.replaceState(history.state, "", target); } catch { /* Sandboxed previews may refuse URL updates. */ }
  }
}
function renderActiveFilters(active, total) {
  const bar = $("active-filters");
  bar.hidden = !active.length;
  const fragment = document.createDocumentFragment();
  for (const filter of active) {
    const chip = document.createElement("button");
    chip.type = "button"; chip.className = "filter-chip";
    chip.setAttribute("aria-label", "Retirer le filtre " + filter.label);
    const text = document.createElement("span"); text.textContent = filter.label;
    const mark = document.createElement("span"); mark.setAttribute("aria-hidden", "true"); mark.textContent = "×";
    chip.append(text, mark);
    chip.addEventListener("click", () => { clearControl(filter.id); changed(true); ($("active-filters").querySelector("button") || $("search")).focus(); });
    fragment.append(chip);
  }
  if (active.length > 1) {
    const reset = document.createElement("button");
    reset.type = "button"; reset.className = "filter-reset"; reset.textContent = "Tout effacer";
    reset.addEventListener("click", () => { resetFilters(); $("search").focus(); });
    fragment.append(reset);
  }
  bar.replaceChildren(fragment);
  const count = active.filter(filter => filter.id !== "search").length;
  $("filters-count").hidden = !count; $("filters-count").textContent = String(count);
  $("filters-toggle").setAttribute("aria-label", count ? `Filtres, ${count} actif${count > 1 ? "s" : ""}` : "Filtres");
  $("sheet-apply").textContent = total ? `Voir ${total} offre${total > 1 ? "s" : ""}` : "Aucune offre";
}
function resetFilters() {
  for (const id of controls) clearControl(id);
  changed(true);
}
function fillCard(entry, today) {
  const j = entry.job, href = safeLink(j.url); if (!href) return null;
  const card = $("offer-template").content.firstElementChild.cloneNode(true);
  const grouped = entry.variants.length > 1;
  const title = grouped ? entry.base : j.title;
  const link = card.querySelector(".card-link"); link.href = href; link.textContent = title;
  card.querySelector("h3").title = title;
  const kindLabel = j.kind === "Graduate" && /\b(?:junior|jr)\b/i.test(j.title) && !/\bgraduates?\b/i.test(j.title) ? "Junior" : j.kind;
  for (const [selector, value] of [[".company",j.company],[".kind",kindLabel],[".location",j.location],[".start",j.start],[".family",j.family]]) {
    const node = card.querySelector(selector); node.textContent = value; node.title = value;
  }
  card.querySelector(".kind").dataset.kind = kindLabel;
  const date = card.querySelector(".date"), relative = relativeDate(j.published, today);
  date.textContent = relative.text || j.date_label; date.title = j.date_label;
  date.classList.toggle("is-new", relative.fresh);
  const img = card.querySelector("img"), initials = card.querySelector(".initials");
  initials.textContent = j.company.split(/\s+/).slice(0,2).map(s=>s[0] || "").join("").toUpperCase();
  img.hidden = true;
  if (/^logos\/[a-zA-Z0-9._-]+\.png$/.test(j.logo)) {
    img.loading = "eager";
    img.onload = () => { img.hidden = false; initials.hidden = true; };
    img.src = j.logo;
  }
  if (grouped) {
    const details = card.querySelector(".card-variants"), list = details.querySelector("ul");
    details.hidden = false;
    const summary = details.querySelector("summary");
    summary.textContent = "+" + (entry.variants.length - 1);
    summary.title = entry.variants.length + " variantes de cette offre";
    summary.setAttribute("aria-label", "Voir les " + entry.variants.length + " variantes de " + title);
    for (const variant of entry.variants) {
      const url = safeLink(variant.url); if (!url) continue;
      const item = document.createElement("li"), anchor = document.createElement("a");
      anchor.href = url; anchor.target = "_blank"; anchor.rel = "noopener noreferrer"; anchor.referrerPolicy = "no-referrer";
      anchor.textContent = variant.title.slice(entry.base.length).replace(/^[\s,;:–-]+/u, "").replace(/^\((.*)\)$/s, "$1") || variant.title;
      anchor.title = variant.title;
      item.append(anchor); list.append(item);
    }
    details.addEventListener("toggle", () => {
      if (details.open) for (const other of document.querySelectorAll(".card-variants[open]")) if (other !== details) other.open = false;
    });
  }
  return card;
}
function render(animateResults = false, append = false) {
  for (const view of filterViews.values()) view.sync();
  for (const button of $("sort-options").querySelectorAll("button")) {
    button.setAttribute("aria-pressed", String(button.dataset.sort === sortMode));
  }
  const entries = filteredOffers(), today = parisToday();
  const previous = append ? shown : 0;
  shown = Math.min(entries.length, Math.max(size, append ? shown + size : shown || size));
  const fragment = document.createDocumentFragment();
  for (const entry of entries.slice(previous, shown)) {
    const card = fillCard(entry, today); if (card) fragment.append(card);
  }
  const grid = $("offers");
  resultsAnimation?.cancel();
  resultsAnimation = undefined;
  if (append) grid.append(fragment); else grid.replaceChildren(fragment);
  grid.removeAttribute("aria-busy");
  if (animateResults && !append && !reduceMotion.matches && grid.firstElementChild && grid.animate) {
    resultsAnimation = grid.animate(
      [{opacity: .72, transform: "translateY(3px)"}, {opacity: 1, transform: "none"}],
      {duration: 170, easing: "ease-out"},
    );
  }
  const total = entries.length;
  $("count").textContent = total ? `${total} offre${total > 1 ? "s" : ""}` : "Aucune offre pour ces critères";
  $("shown").textContent = total > shown ? `${shown} affichées sur ${total}` : "";
  $("more").hidden = total <= shown;
  $("more").textContent = `Afficher ${Math.min(size, total - shown)} offres de plus`;
  renderActiveFilters(activeFilters(), total);
  writeUrl();
}
function changed(animate) {
  shown = 0;
  render(animate);
}
function options(id, pairs) {
  $(id).replaceChildren($(id).options[0]);
  for (const [value,label] of pairs) { const o = document.createElement("option"); o.value = value; o.textContent = label; $(id).append(o); }
  filterViews.get(id)?.refresh();
}
function applyQuery(ids) {
  for (const id of ids) {
    const value = pendingQuery.get(urlKeys[id]);
    if (value === null) continue;
    if (id === "search") $("search").value = value.slice(0, 120);
    else if ([...$(id).options].some(option => option.value === value)) $(id).value = value;
  }
}
let loading = false;
async function load() {
  if (loading) return;
  loading = true;
  try {
    const response = await fetch("offers.json", {cache: "no-cache", credentials: "omit"});
    if (!response.ok) throw new Error("load");
    const data = await response.json();
    if (!Array.isArray(data.offers)) throw new Error("schema");
    offers = data.offers;
    const family = $("family").value, start = $("start").value;
    options("family", [...new Set(offers.map(j=>j.family).filter(Boolean))].sort().map(v=>[v,v]));
    const months = new Set(offers.map(j=>j.start_month).filter(Boolean));
    const now = new Date();
    for (let n=0;n<24;n++) months.add(new Date(Date.UTC(now.getFullYear(),now.getMonth()+n,1)).toISOString().slice(0,7));
    options("start", [...months].sort().map(v=>[v,new Intl.DateTimeFormat("fr-FR",{month:"long",year:"numeric",timeZone:"UTC"}).format(new Date(v+"-01T12:00:00Z"))]));
    $("family").value = family; $("start").value = start;
    if ($("family").selectedIndex < 0) $("family").selectedIndex = 0;
    if ($("start").selectedIndex < 0) $("start").selectedIndex = 0;
    if (pendingQuery) { applyQuery(["family", "start"]); pendingQuery = null; }
    const s = data.sources;
    $("updated").textContent = "Actualisé le " + new Intl.DateTimeFormat("fr-FR", {day:"numeric",month:"short",hour:"2-digit",minute:"2-digit",timeZone:"Europe/Paris"}).format(new Date(data.updated)) + (s.unavailable || s.partial || s.retained ? " · Certaines sources à vérifier" : "");
    $("updated").title = `Heure de Paris · ${s.checked} sources · ${s.unavailable} sources indisponibles · ${s.partial || 0} collectes partielles · ${s.retained} sources avec offres conservées`;
    $("message").textContent = ""; render();
  } catch {
    $("message").textContent = "Impossible de charger les nouvelles données. Réessaie dans un instant. Les offres déjà affichées sont conservées.";
    if (!offers.length) { $("offers").replaceChildren(); $("offers").removeAttribute("aria-busy"); }
  }
  finally { loading = false; }
}
// Bottom sheet for filters on phones; the same panel stays inline on wider screens.
const panel = $("filter-panel"), backdrop = $("sheet-backdrop"), toggle = $("filters-toggle");
const sheetOpen = () => panel.classList.contains("is-open");
function openSheet() {
  panel.classList.add("is-open"); backdrop.hidden = false; document.body.classList.add("sheet-open");
  panel.setAttribute("role", "dialog"); panel.setAttribute("aria-modal", "true");
  toggle.setAttribute("aria-expanded", "true"); $("filters-close").focus();
}
function closeSheet(returnFocus = true) {
  if (!sheetOpen()) return;
  if (openFilter) openFilter.close();
  panel.classList.remove("is-open"); backdrop.hidden = true; document.body.classList.remove("sheet-open");
  panel.removeAttribute("role"); panel.removeAttribute("aria-modal");
  toggle.setAttribute("aria-expanded", "false");
  if (returnFocus) toggle.focus({preventScroll:true});
}
toggle.addEventListener("click", () => sheetOpen() ? closeSheet() : openSheet());
$("filters-close").addEventListener("click", () => closeSheet());
$("sheet-apply").addEventListener("click", () => { closeSheet(); $("count").scrollIntoView({block:"nearest"}); });
$("sheet-reset").addEventListener("click", () => resetFilters());
backdrop.addEventListener("click", () => closeSheet());
sheetLayout.addEventListener("change", () => closeSheet(false));
document.addEventListener("keydown", (event) => {
  if (event.key !== "Escape" || event.defaultPrevented) return;
  const variants = document.querySelector(".card-variants[open]");
  if (variants) { variants.open = false; variants.querySelector("summary").focus(); return; }
  if (sheetOpen()) closeSheet();
});
document.addEventListener("click", (event) => {
  for (const details of document.querySelectorAll(".card-variants[open]")) if (!details.contains(event.target)) details.open = false;
});
for (const id of controls) {
  $(id).addEventListener(id === "search" ? "input" : "change", () => changed(id !== "search"));
}
for (const button of $("sort-options").querySelectorAll("button")) {
  button.addEventListener("click", () => {sortMode=button.dataset.sort;changed(true);});
}
$("more").addEventListener("click", () => {
  const next = $("offers").children.length;
  render(false, true);
  $("offers").children[next]?.querySelector(".card-link")?.focus({preventScroll:true});
});
applyQuery(["search", "category", "period"]);
if (initialQuery.get("tri") === "recent") sortMode = "recent";
if (!touchScreen) for (const id of selects) enhanceFilter($(id));
load();
setInterval(() => { if (!document.hidden) load(); }, 5 * 60 * 1000);
document.addEventListener("visibilitychange", () => { if (!document.hidden) load(); });
window.addEventListener("pageshow", event => { if (event.persisted) load(); });
