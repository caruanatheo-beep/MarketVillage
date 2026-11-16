"use strict";
(() => {
  const byId = id => document.getElementById(id);
  const form = byId("source-request-form"), fields = byId("source-request-fields");
  const status = byId("source-request-status"), submit = byId("source-submit");
  const endpointPattern = /^https:\/\/marketdesk-source-suggestions\.source-suggestions\.workers\.dev\/suggestions$/;
  let catalog = [], category = "", endpoint = "", loaded = false, loading = false, sending = false;
  async function loadSuggestions() {
    if (!endpoint) return;
    byId("proposed-sources").hidden = false;
    try {
      const response = await fetch(endpoint, {cache:"no-cache", credentials:"omit", referrerPolicy:"no-referrer"});
      if (!response.ok) throw new Error("proposals");
      const data = await response.json();
      if (!Array.isArray(data.suggestions)) throw new Error("proposals");
      const fragment = document.createDocumentFragment();
      for (const proposal of data.suggestions.slice(0,100)) {
        const url = safeLink(proposal.url); if (!url || typeof proposal.company !== "string") continue;
        const card = byId("source-template").content.firstElementChild.cloneNode(true);
        card.querySelector("h3").textContent = proposal.company;
        card.querySelector(".source-type").textContent = "À étudier";
        card.querySelector("img").hidden = true;
        card.querySelector(".initials").textContent = proposal.company.slice(0,1).toUpperCase();
        card.querySelector(".source-link").href = url;
        card.querySelector(".source-link").setAttribute("aria-label", "Consulter la source proposée : " + proposal.company);
        card.querySelector("details").hidden = true;
        if (typeof proposal.reason === "string" && proposal.reason) {
          const text = document.createElement("p"); text.className = "source-reason";
          text.textContent = proposal.reason; card.append(text);
        }
        fragment.append(card);
      }
      byId("proposed-list").replaceChildren(fragment);
      byId("proposed-status").textContent = data.suggestions.length ? "" : "Aucune proposition en attente. Un site manque ? Propose-le ci-contre.";
    } catch {
      byId("proposed-status").textContent = "Les propositions ne peuvent pas être chargées pour le moment.";
    }
  }
  function addedRecently(value, now = new Date()) {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(value || "")) return false;
    const parts = new Intl.DateTimeFormat("en-CA", {timeZone:"Europe/Paris", year:"numeric", month:"2-digit", day:"2-digit"}).formatToParts(now);
    const field = type => parts.find(part => part.type === type).value;
    const today = Date.UTC(+field("year"), +field("month") - 1, +field("day"));
    const earliest = today - 6 * 86400000;
    const added = Date.parse(value + "T00:00:00Z");
    return Number.isFinite(added) && new Date(added).toISOString().slice(0, 10) === value && added >= earliest && added <= today;
  }
  function renderSources() {
    const terms = normalize(byId("source-search").value).split(/\s+/).filter(Boolean);
    const selected = catalog.filter(source => (!category || source.category === category)
      && terms.every(term => normalize(source.name + " " + source.category + " " + source.feeds.map(feed => feed.name).join(" ")).includes(term)));
    const recent = selected.filter(source => addedRecently(source.added_on))
      .sort((a,b) => b.added_on.localeCompare(a.added_on) || a.name.localeCompare(b.name, "fr"));
    const others = selected.filter(source => !addedRecently(source.added_on));
    const fragment = document.createDocumentFragment();
    for (const source of [...recent, ...others]) {
      if (recent.length && (source === recent[0] || source === others[0])) {
        const heading = document.createElement("h3"); heading.className = "source-group-title";
        heading.textContent = source === recent[0] ? "Ajoutées ces 7 derniers jours" : "Autres sources";
        const count = document.createElement("span"); count.textContent = String(source === recent[0] ? recent.length : others.length);
        heading.append(count); fragment.append(heading);
      }
      const url = safeLink(source.url); if (!url) continue;
      const card = byId("source-template").content.firstElementChild.cloneNode(true);
      card.querySelector("h3").textContent = source.name;
      card.querySelector("h3").title = source.name;
      card.querySelector(".source-type").textContent = source.category;
      const link = card.querySelector(".source-link"); link.href = url;
      link.setAttribute("aria-label", "Consulter le site carrière : " + source.name);
      if (addedRecently(source.added_on)) {
        card.classList.add("is-new-source");
        link.setAttribute("aria-label", link.getAttribute("aria-label") + ", ajoutée ces 7 derniers jours");
      }
      const initials = card.querySelector(".initials"), image = card.querySelector("img");
      initials.textContent = source.name.split(/\s+/).slice(0, 2).map(word => word[0] || "").join("").toUpperCase();
      image.hidden = true;
      if (/^logos\/[a-zA-Z0-9._-]+\.png$/.test(source.logo)) {
        image.onload = () => {image.hidden = false; initials.hidden = true;}; image.src = source.logo;
      }
      const feeds = [...new Map(source.feeds.filter(feed => safeLink(feed.url)).map(feed => [safeLink(feed.url),feed])).values()];
      const details = card.querySelector("details"); details.hidden = feeds.length < 2;
      card.classList.toggle("has-feeds", !details.hidden);
      const summary = details.querySelector("summary");
      summary.textContent = feeds.length + " sites";
      summary.setAttribute("aria-label", "Afficher les " + feeds.length + " sites carrière de " + source.name);
      details.addEventListener("toggle", () => {
        if (details.open) for (const other of document.querySelectorAll(".source-feeds[open]")) if (other !== details) other.open = false;
      });
      for (const feed of feeds) {
        const href = safeLink(feed.url); if (!href) continue;
        const item = document.createElement("li"), anchor = document.createElement("a");
        anchor.textContent = feed.name; anchor.href = href; anchor.target = "_blank";
        anchor.rel = "noopener noreferrer"; anchor.referrerPolicy = "no-referrer"; item.append(anchor);
        details.querySelector("ul").append(item);
      }
      fragment.append(card);
    }
    byId("source-list").replaceChildren(fragment);
    byId("source-count").textContent = selected.length + " source" + (selected.length > 1 ? "s" : "") + " référencée" + (selected.length > 1 ? "s" : "");
    byId("sources-message").textContent = selected.length ? "" : "Aucune source ne correspond à cette recherche.";
    for (const button of document.querySelectorAll(".source-categories button")) button.setAttribute("aria-pressed", String(button.dataset.category === category));
  }
  async function loadSources() {
    if (loaded || loading) return;
    loading = true;
    try {
      const response = await fetch("sources.json", {cache:"no-cache", credentials:"omit"});
      if (!response.ok) throw new Error("catalog");
      const data = await response.json();
      if (!Array.isArray(data.sources)) throw new Error("catalog");
      catalog = data.sources;
      endpoint = typeof data.request_endpoint === "string" && endpointPattern.test(data.request_endpoint) ? data.request_endpoint : "";
      fields.disabled = !endpoint;
      status.textContent = endpoint ? "" : "L’envoi des suggestions est en cours d’activation.";
      loaded = true; renderSources(); loadSuggestions();
    } catch {
      byId("source-count").textContent = "Sources";
      byId("sources-message").textContent = "Le catalogue ne peut pas être chargé pour le moment. Réessaie en revenant sur cet onglet.";
    } finally {loading = false;}
  }
  function showView() {
    const sources = ["#sources", "#proposer-source"].includes(location.hash);
    byId("offers-view").hidden = sources; byId("sources-view").hidden = !sources;
    byId("nav-offers").toggleAttribute("aria-current", !sources);
    byId("nav-sources").toggleAttribute("aria-current", sources);
    byId(sources ? "nav-sources" : "nav-offers").setAttribute("aria-current", "page");
    document.title = (sources ? "Sources" : "Offres") + " · MarketDesk";
    if (openFilter) openFilter.close();
    if (sources) loadSources();
  }
  byId("suggest-source").addEventListener("click", () => {
    byId("proposer-source").scrollIntoView({block:"start"});
    if (!fields.disabled) byId("source-name").focus({preventScroll:true});
  });
  byId("source-search").addEventListener("input", renderSources);
  for (const button of document.querySelectorAll(".source-categories button")) button.addEventListener("click", () => {category = button.dataset.category; renderSources();});
  for (const input of form.querySelectorAll("input,textarea")) input.addEventListener("input", () => input.setCustomValidity(""));
  form.addEventListener("submit", async event => {
    event.preventDefault();
    if (sending || !endpoint || !form.reportValidity()) return;
    if (form.elements.organization_fax.value) {status.textContent = "Le formulaire n’a pas pu être validé."; return;}
    const name = byId("source-name").value.trim(), url = byId("source-url").value.trim();
    const reason = byId("source-reason").value.trim();
    try {
      const parsed = new URL(url);
      if (parsed.protocol !== "https:" || parsed.username || parsed.password || !parsed.hostname.includes(".")
          || /^(?:[\d.]+|localhost)$/.test(parsed.hostname) || /\.(?:local|internal)$/.test(parsed.hostname)
          || [...parsed.searchParams.keys()].some(key => /^(?:key|api_key|token|password|secret|authorization)$/i.test(key))) throw new Error("url");
    } catch {
      byId("source-url").setCustomValidity("Indique un lien public en https, sans identifiant ni mot de passe.");
      byId("source-url").reportValidity(); return;
    }
    if (name.length < 2) {byId("source-name").setCustomValidity("Indique le nom de l’entreprise ou de l’organisme."); byId("source-name").reportValidity(); return;}
    sending = true; submit.disabled = true; submit.textContent = "Envoi en cours…";
    status.textContent = ""; status.classList.remove("is-error");
    const controller = new AbortController(), timer = setTimeout(() => controller.abort(), 15000);
    try {
      const response = await fetch(endpoint, {method:"POST", credentials:"omit", referrerPolicy:"no-referrer", signal:controller.signal,
        headers:{"Content-Type":"application/json", "Accept":"application/json"},
        body:JSON.stringify({company:name, url, reason, honey:""})});
      const result = await response.json();
      if (!response.ok || result.success !== true) throw new Error("delivery");
      form.reset(); status.textContent = "Ta suggestion a été enregistrée. Merci !"; loadSuggestions();
    } catch {
      status.classList.add("is-error"); status.textContent = "L’envoi n’a pas abouti. Ta saisie est conservée : réessaie dans un instant.";
    } finally {
      clearTimeout(timer); sending = false; submit.disabled = false; submit.textContent = "Envoyer la suggestion ↗";
    }
  });
  window.addEventListener("hashchange", showView); showView();
  const announcement = byId("sources-announcement"), announcementKey = "marketdesk.sources-announcement.v1";
  let announcementDismissed = false;
  try { announcementDismissed = localStorage.getItem(announcementKey) === "dismissed"; } catch { /* Storage may be disabled. */ }
  announcement.hidden = announcementDismissed;
  function dismissAnnouncement() {
    announcement.hidden = true;
    try { localStorage.setItem(announcementKey, "dismissed"); } catch { /* Keep dismissal effective for this page. */ }
  }
  byId("announcement-close").addEventListener("click", () => {
    dismissAnnouncement();
    document.querySelector('.primary-nav [aria-current="page"]').focus({preventScroll:true});
  });
  byId("announcement-discover").addEventListener("click", () => {
    dismissAnnouncement();
    byId("nav-sources").focus({preventScroll:true});
  });
  document.addEventListener("click", event => {
    for (const details of document.querySelectorAll(".source-feeds[open]")) if (!details.contains(event.target)) details.open = false;
  });
  document.addEventListener("keydown", event => {
    if (event.key === "Escape") for (const details of document.querySelectorAll(".source-feeds[open]")) {
      details.open = false; details.querySelector("summary").focus();
    }
  });
})();
