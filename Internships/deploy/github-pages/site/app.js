"use strict";
const $ = (id) => document.getElementById(id);
const controls = ["search", "category", "family", "period", "start"];
const normalize = (s) => String(s || "").normalize("NFKD").replace(/\p{M}/gu, "").toLowerCase().replace(/[^\p{L}\p{N}]+/gu, " ").trim();
let offers = [], page = 1;
let sortMode = "rank";
const size = 50;
const filterViews = new Map();
let openFilter = null;
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
    // Keep the 6px menu gap and an 8px viewport margin, including below the announcement.
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
function render() {
  for (const view of filterViews.values()) view.sync();
  const terms = normalize($("search").value).split(/\s+/).filter(Boolean);
  const today = new Intl.DateTimeFormat("en-CA", {timeZone: "Europe/Paris", year: "numeric", month: "2-digit", day: "2-digit"}).format(new Date());
  const week = new Date(today + "T12:00:00Z"); week.setUTCDate(week.getUTCDate() - 6);
  const first = week.toISOString().slice(0,10);
  let selected = offers.filter((j) => terms.every((t) => normalize(j.title + " " + j.company + " " + j.location + " " + (j.location_source || "")).includes(t))
    && (!$("category").value || j.categories.includes($("category").value))
    && (!$("family").value || j.family === $("family").value)
    && (!$("start").value || j.start_month && j.start_month >= $("start").value)
    && (!$("period").value || $("period").value === "daily" && j.published === today
      || $("period").value === "weekly" && j.published >= first && j.published <= today));
  for (const button of $("sort-options").querySelectorAll("button")) {
    button.setAttribute("aria-pressed", String(button.dataset.sort === sortMode));
  }
  if (sortMode === "recent") selected.sort((a,b) => b.published.localeCompare(a.published));
  const pages = Math.max(1, Math.ceil(selected.length / size)); page = Math.min(page, pages);
  const fragment = document.createDocumentFragment();
  for (const j of selected.slice((page-1)*size, page*size)) {
    const href = safeLink(j.url); if (!href) continue;
    const card = $("offer-template").content.firstElementChild.cloneNode(true); card.href = href;
    const kindLabel = j.kind === "Graduate" && /\b(?:junior|jr)\b/i.test(j.title) && !/\bgraduates?\b/i.test(j.title) ? "Junior" : j.kind;
    for (const [selector, value] of [[".company",j.company],["h3",j.title],[".kind",kindLabel],[".location",j.location],[".start",j.start],[".family",j.family],[".date",j.date_label]]) {
      const node = card.querySelector(selector); node.textContent = value; node.title = value;
    }
    const img = card.querySelector("img"), initials = card.querySelector(".initials");
    initials.textContent = j.company.split(/\s+/).slice(0,2).map(s=>s[0] || "").join("").toUpperCase();
    img.hidden = true;
    if (/^logos\/[a-zA-Z0-9._-]+\.png$/.test(j.logo)) {
      img.loading = "eager";
      img.onload = () => { img.hidden = false; initials.hidden = true; };
      img.src = j.logo;
    }
    fragment.append(card);
  }
  $("offers").replaceChildren(fragment);
  $("count").textContent = selected.length ? `Offres ${(page-1)*size+1}–${Math.min(page*size,selected.length)} sur ${selected.length}` : "Aucune offre pour ces critères";
  $("page").textContent = `Page ${page} / ${pages}`;
  $("previous").disabled = page <= 1; $("next").disabled = page >= pages;
}
function options(id, pairs) {
  $(id).replaceChildren($(id).options[0]);
  for (const [value,label] of pairs) { const o = document.createElement("option"); o.value = value; o.textContent = label; $(id).append(o); }
  filterViews.get(id)?.refresh();
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
    const s = data.sources;
    $("updated").textContent = "Actualisé le " + new Intl.DateTimeFormat("fr-FR", {day:"numeric",month:"short",hour:"2-digit",minute:"2-digit",timeZone:"Europe/Paris"}).format(new Date(data.updated)) + (s.unavailable || s.partial || s.retained ? " · Certaines sources à vérifier" : "");
    $("updated").title = `Heure de Paris · ${s.checked} sources · ${s.unavailable} sources indisponibles · ${s.partial || 0} collectes partielles · ${s.retained} sources avec offres conservées`;
    $("message").textContent = ""; render();
  } catch { $("message").textContent = "Impossible de charger les nouvelles données. Réessaie dans un instant. Les offres déjà affichées sont conservées."; }
  finally { loading = false; }
}
for (const id of controls) $(id).addEventListener(id === "search" ? "input" : "change", () => {page=1;render();});
for (const button of $("sort-options").querySelectorAll("button")) {
  button.addEventListener("click", () => {sortMode=button.dataset.sort;page=1;render();});
}
$("previous").addEventListener("click",()=>{page--;render();$("count").scrollIntoView({block:"start"});});
$("next").addEventListener("click",()=>{page++;render();$("count").scrollIntoView({block:"start"});});
for (const id of controls.slice(1)) enhanceFilter($(id));
load();
setInterval(() => { if (!document.hidden) load(); }, 5 * 60 * 1000);
document.addEventListener("visibilitychange", () => { if (!document.hidden) load(); });
window.addEventListener("pageshow", event => { if (event.persisted) load(); });
