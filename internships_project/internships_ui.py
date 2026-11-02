"""Standalone Gradio interface for the internships project."""

from __future__ import annotations

import base64
import csv
import hashlib
import html
import json
import os
import tempfile
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

import gradio as gr

from .internships import (
    Opportunity, TRACKING_STATUSES, export_tracking, import_tracking, load_opportunities,
    load_delayed_opportunities,
    mark_opened_offer_applied, normalize_status, opportunities_loading, render_opportunities, render_tracking,
    save_tracking, matching_opportunities,
)
from .career_agent import (CareerAgentError, candidate_name, export_letter_pdf,
                           generate_briefs, generate_letter, generate_linkedin_messages,
                           letter_review_flags, load_candidate_profile,
                           rank_candidate_pool, render_briefs, structure_candidate_profile,
                           save_letter_draft, saved_letter, PROFILE_PATH)
from .candidate_profiles import (ProfileError, clean_catalog, extract_cv_text, profile_choices,
                                 candidate_profile_context, extract_linkedin_recipient_profile,
                                 profile_prompt, render_profile_card,
                                 save_profile, selected_profile)
from .state_store import (hydrate_local_state, local_state_enabled, persist_tracking,
                          shared_mode, load_user_data, save_user_data)
from .accounts import admin_username, delete_registered_account, list_accounts
from .llm_usage import llm_user, generation_slot, GenerationLimitError, render_usage_report
from .private_downloads import register_download
from . import mail_outreach

CSS = Path(__file__).with_name('ui_styles.css').read_text(encoding='utf-8')
# New SKEMA emblem published on the school's 2026 brand announcement.
SKEMA_EMBLEM = base64.b64encode(
    (Path(__file__).parent / 'assets' / 'skema_emblem_2026.png').read_bytes()
).decode('ascii')

APP_THEME = gr.themes.Base(primary_hue="purple", secondary_hue="violet", neutral_hue="slate").set(
    body_background_fill="#f7f8fa", body_background_fill_dark="#f7f8fa",
    background_fill_primary="#ffffff", background_fill_primary_dark="#ffffff",
    background_fill_secondary="#f1f3f7", background_fill_secondary_dark="#f1f3f7",
    block_background_fill="#ffffff", block_background_fill_dark="#ffffff",
    block_label_background_fill="#ffffff", block_label_background_fill_dark="#ffffff",
    panel_background_fill="#ffffff", panel_background_fill_dark="#ffffff",
    input_background_fill="#ffffff", input_background_fill_dark="#ffffff",
    input_background_fill_hover="#f8f7fd", input_background_fill_hover_dark="#f8f7fd",
    input_border_color="#dce1e8", input_border_color_dark="#dce1e8",
    border_color_primary="#dfe3e9", border_color_primary_dark="#dfe3e9",
    body_text_color="#17202b", body_text_color_dark="#17202b",
    body_text_color_subdued="#647184", body_text_color_subdued_dark="#647184",
    button_primary_background_fill="#7657d4", button_primary_background_fill_dark="#7657d4",
    button_primary_text_color="#ffffff", button_primary_text_color_dark="#ffffff",
)

OFFER_RETURN_JS = """
const storageKey = 'markets-career-opened-offer-v1';
const toast = element.querySelector('.offer-return-toast');
const title = element.querySelector('.offer-return-title');
const company = element.querySelector('.offer-return-company');
let pending = null;
try { pending = JSON.parse(sessionStorage.getItem(storageKey) || 'null'); } catch (_) {}
function remember() {
  try { sessionStorage.setItem(storageKey, JSON.stringify(pending)); } catch (_) {}
}
function clearPending() {
  pending = null;
  try { sessionStorage.removeItem(storageKey); } catch (_) {}
  toast.hidden = true;
}
function showOnReturn() {
  if (!pending || !pending.away || document.visibilityState !== 'visible') return;
  if (Date.now() - pending.openedAt > 24 * 60 * 60 * 1000) { clearPending(); return; }
  title.textContent = pending.title;
  company.textContent = pending.company;
  toast.hidden = false;
}
document.addEventListener('click', (event) => {
  const link = event.target.closest('a.job-card-main, a.internship-open');
  const card = link?.closest('.internship-card[data-offer-url]');
  if (!card) return;
  const status = card.dataset.trackingStatus;
  if (status && !['À examiner', 'À candidater'].includes(status)) return;
  pending = {url: card.dataset.offerUrl, title: card.dataset.offerTitle,
             company: card.dataset.offerCompany, openedAt: Date.now(), away: false};
  remember();
});
window.addEventListener('blur', () => { if (pending) { pending.away = true; remember(); } });
document.addEventListener('visibilitychange', () => {
  if (document.visibilityState === 'hidden' && pending) { pending.away = true; remember(); }
  if (document.visibilityState === 'visible') setTimeout(showOnReturn, 150);
});
window.addEventListener('focus', () => setTimeout(showOnReturn, 150));
element.addEventListener('click', (event) => {
  if (event.target.closest('[data-offer-return-later]')) { clearPending(); return; }
  if (event.target.closest('[data-offer-return-apply]') && pending) {
    const url = pending.url;
    clearPending();
    trigger('click', {url});
  }
});
showOnReturn();
"""


def build_internships_app() -> gr.Blocks:
    shared = shared_mode()

    def cleared_pdf():
        return gr.HTML("") if shared else gr.File(value=None, visible=False)
    configured = list(json.loads(os.getenv("INTERNSHIPS_USERS_JSON", "{}")).items()) if shared else []
    owner = admin_username(configured) if shared else ""

    def username(request: gr.Request) -> str:
        name = getattr(request, "username", None)
        if shared and not name:
            raise gr.Error("Connecte-toi pour accéder à tes données.")
        return str(name or "")

    def account_opportunities(request: gr.Request, force: bool = False, refresh: bool = True):
        live = load_opportunities(force=force, refresh=refresh)
        if shared and username(request) != owner:
            return load_delayed_opportunities()
        return live

    def persist_personal(kind: str, data: dict, request: gr.Request) -> bool:
        if shared:
            save_user_data(username(request), kind, data)
            return True
        return persist_tracking(data) if kind == "tracking" else False

    def active_profile(catalog: object) -> tuple[str | None, dict | None]:
        """Use one stable profile for this account, including older catalogs."""
        records = clean_catalog(catalog)
        key = next(iter(records), None)
        return key, records.get(key) if key else None

    nav_js = """
const icons = {
  'Offres': '<svg class="career-nav-icon" viewBox="0 0 24 24" aria-hidden="true"><rect x="2.5" y="7" width="19" height="14" rx="2.5"/><path d="M8 7V5a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2M2.5 13h19M10 12.5v2h4v-2"/></svg>',
  'Assistant IA': '<svg class="career-nav-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="m12 2 1.8 5.2L19 9l-5.2 1.8L12 16l-1.8-5.2L5 9l5.2-1.8L12 2ZM19 16l.7 1.8L21.5 18.5l-1.8.7L19 21l-.7-1.8-1.8-.7 1.8-.7L19 16ZM4.5 15l.6 1.4 1.4.6-1.4.6L4.5 19l-.6-1.4-1.4-.6 1.4-.6L4.5 15Z"/></svg>',
  'Mon profil': '<svg class="career-nav-icon" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="8" r="3.5"/><path d="M4.5 21v-2a7.5 7.5 0 0 1 15 0v2H4.5Z"/></svg>',
  'Administration': '<svg class="career-nav-icon" viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="4" width="18" height="17" rx="2"/><path d="M7 9h10M7 13h10M7 17h6"/></svg>'
};
function decorateCareerNav() {
  const app = document.querySelector('#internships-app');
  const nav = [...(app?.querySelectorAll('[role="tablist"]') || [])].find(list => {
    const names = [...list.querySelectorAll('[role="tab"]')].map(tab => tab.textContent.trim());
    return names.includes('Offres') && names.includes('Assistant IA') && names.includes('Mon profil');
  });
  if (!nav) return false;
  nav.classList.add('career-main-nav');
  for (const tab of nav.querySelectorAll('[role="tab"]')) {
    const name = tab.textContent.trim();
    if (icons[name] && !tab.querySelector('.career-nav-icon')) {
      tab.dataset.careerTab = name === 'Offres' ? 'jobs' : name === 'Assistant IA' ? 'assistant' : name === 'Administration' ? 'admin' : 'profile';
      tab.insertAdjacentHTML('afterbegin', icons[name]);
    }
  }
  return true;
}
if (!decorateCareerNav()) requestAnimationFrame(decorateCareerNav);
const careerNavObserver = new MutationObserver(decorateCareerNav);
careerNavObserver.observe(document.querySelector('#internships-app') || document.body,
  {childList: true, subtree: true});
"""
    favicon_path = Path(__file__).parent / "assets" / "skema_emblem_2026.png"
    with gr.Blocks(analytics_enabled=False, title='Offres · Marchés financiers') as app_blocks:
        with gr.Column(elem_id="internships-app"):
            legacy_profile = "" if shared else load_candidate_profile()
            legacy_name = candidate_name(legacy_profile) or "Mon profil"
            initial_catalog = ({"legacy": {"name": legacy_name, "source_text": legacy_profile,
                                           "overview": "", "experience": [], "strengths": [],
                                           "target_roles": [], "locations": [], "contracts": [],
                                           "start_month": "", "end_month": "", "start_window": "",
                                           "constraints": []}} if legacy_profile and not shared else {})
            profiles_state = (gr.State({}) if shared else gr.BrowserState(
                default_value=initial_catalog, storage_key="ai-sales-desk-candidate-profiles-v1",
                secret="ai-sales-desk-candidate-profiles-local-v1"))
            if shared:
                old_profiles = gr.BrowserState(default_value={},
                    storage_key="ai-sales-desk-candidate-profiles-v1",
                    secret="ai-sales-desk-candidate-profiles-local-v1")
                old_tracking = gr.BrowserState(default_value={},
                    storage_key="ai-sales-desk-internships-v1",
                    secret="ai-sales-desk-local-tracking-v1")
                old_feedback = gr.BrowserState(default_value={},
                    storage_key="ai-sales-desk-internships-feedback-v1",
                    secret="ai-sales-desk-local-feedback-v1")
                old_drafts = gr.BrowserState(default_value={},
                    storage_key="ai-sales-desk-internships-agent-drafts-v1",
                    secret="ai-sales-desk-agent-drafts-v1")
            offer_return_toast = gr.HTML(
                '<aside class="offer-return-toast" hidden role="status" aria-live="polite">'
                '<span class="offer-return-eyebrow">Offre consultée</span>'
                '<strong class="offer-return-title"></strong>'
                '<span class="offer-return-company"></span>'
                '<p>Tu as postulé à cette offre ?</p>'
                '<div class="offer-return-actions">'
                '<button type="button" data-offer-return-later>Plus tard</button>'
                '<button type="button" data-offer-return-apply>Marquer « Postulé »</button>'
                '</div></aside>',
                js_on_load=OFFER_RETURN_JS, elem_id="offer-return-notification",
            )
            gr.HTML(
                '<div class="career-masthead" aria-label="À propos du projet">'
                '<div class="career-masthead-brand">'
                '<a class="skema-brand" href="https://www.skema.edu/fr/la-marque-skema-business-school" '
                'target="_blank" rel="noopener noreferrer" aria-label="SKEMA Business School — nouvelle identité">'
                f'<span class="skema-emblem"><img src="data:image/png;base64,{SKEMA_EMBLEM}" alt="" /></span>'
                '<span class="skema-wordmark"><strong>SKEMA</strong><small>BUSINESS SCHOOL</small></span></a>'
                '</div>'
                '<div class="career-masthead-identity">'
                '<span class="career-masthead-course">MSc Financial Markets &amp; Investments</span>'
                '<span class="career-masthead-author">Théo Caruana</span>'
                '</div>'
                '</div>',
                elem_id="career-masthead",
            )
            with gr.Tabs(elem_id="primary-navigation", selected="offres") as primary_tabs:
                with gr.Tab("Offres", id="offres"):
                    gr.HTML(
                        '<header class="internship-hero"><div class="hero-copy">'
                        '<h1>Trouve ton prochain <em>stage</em></h1>'
                        '<p>Les offres en finance de marché, réunies au même endroit.</p>'
                        '</div></header>',
                        js_on_load=nav_js,
                    )
                    with gr.Column(elem_id="internship-search-panel"):
                        with gr.Row(elem_id="internship-search-row"):
                            internship_search = gr.Textbox(
                                label="Rechercher", placeholder="Métier, entreprise ou ville…",
                                show_label=False, container=False, scale=7,
                                elem_id="internship-search-input",
                            )
                            internship_refresh = gr.Button("↻  Actualiser les offres", variant="secondary", scale=1,
                                                           elem_id="internship-refresh")
                        current_month = datetime.now(timezone.utc)
                        month_names = ("Janvier", "Février", "Mars", "Avril", "Mai", "Juin",
                                       "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre")
                        month_choices = [("Toutes dates", "Toutes dates")] + [
                            (f"{month_names[(current_month.month - 1 + step) % 12]} "
                             f"{current_month.year + (current_month.month - 1 + step) // 12}",
                             f"{current_month.year + (current_month.month - 1 + step) // 12:04d}-"
                             f"{(current_month.month - 1 + step) % 12 + 1:02d}")
                            for step in range(24)
                        ]
                        with gr.Row(elem_id="internship-quick-filters"):
                            with gr.Column(elem_id="internship-contract-field"):
                                gr.HTML('<span class="job-filter-label">Type de contrat</span>')
                                internship_category = gr.Dropdown(
                                    [("Tous les contrats", "Toutes"), ("Stages · Paris", "Stages Paris"),
                                     ("Stages · International", "Stages International"),
                                     ("VIE", "VIE"), ("Graduate", "Graduate")],
                                    value="Toutes", label="Type de contrat", show_label=False,
                                    container=False, elem_id="internship-contract-types",
                                )
                            with gr.Column(elem_id="internship-family-field"):
                                gr.HTML('<span class="job-filter-label">Métier</span>')
                                internship_family = gr.Dropdown(
                                    ["Tous métiers", "Capital Markets", "Sales", "Trading / Structuring", "Asset Management", "Quant / Research", "Risk / Support"],
                                    value="Tous métiers", label="Métier", show_label=False, container=False,
                                    elem_id="internship-family",
                                )
                            with gr.Column(elem_id="internship-period-field"):
                                gr.HTML('<span class="job-filter-label">Date de publication</span>')
                                internship_period = gr.Dropdown(
                                    [("Toutes les dates", "all"), ("Aujourd’hui", "daily"),
                                     ("7 derniers jours", "weekly")],
                                    value="all", label="Date de publication", show_label=False,
                                    container=False, elem_id="internship-period",
                                )
                            with gr.Column(elem_id="internship-start-field"):
                                gr.HTML('<span class="job-filter-label">Début du contrat</span>')
                                internship_start = gr.Dropdown(
                                    month_choices, value="Toutes dates", label="Début à partir de",
                                    show_label=False, container=False, elem_id="internship-start",
                                )
                        with gr.Row(elem_id="internship-active-filters", visible=False) as internship_active_filters:
                            internship_query_chip = gr.Button(visible=False, elem_classes="active-filter-chip")
                            internship_contract_chip = gr.Button(visible=False, elem_classes="active-filter-chip")
                            internship_family_chip = gr.Button(visible=False, elem_classes="active-filter-chip")
                            internship_period_chip = gr.Button(visible=False, elem_classes="active-filter-chip")
                            internship_start_chip = gr.Button(visible=False, elem_classes="active-filter-chip")
                            internship_reset_filters = gr.Button("Réinitialiser", visible=False,
                                                                 elem_id="internship-reset-filters")
                        internship_show_hors_cible = gr.State(True)
                    internship_feedback = (gr.State({}) if shared else gr.BrowserState(
                        default_value={}, storage_key="ai-sales-desk-internships-feedback-v1",
                        secret="ai-sales-desk-local-feedback-v1"))
                    with gr.Tabs(elem_id="jobs-sections"):
                        with gr.Tab("Offres"):
                            with gr.Row(elem_id="internship-controls-row"):
                                with gr.Column(elem_id="internship-sort-field"):
                                    internship_sort = gr.Dropdown(
                                        [("Par pertinence", "pertinence"), ("Plus récentes d’abord", "recent")],
                                        value="pertinence", label="Trier les offres", show_label=False,
                                        container=False, elem_id="internship-sort",
                                    )
                            internship_board = gr.HTML(
                                '<div class="calendar-empty">Ouvre cet onglet pour charger les offres publiques.</div>',
                                elem_id="internship-board",
                            )
                            with gr.Row(visible=False, elem_id="internship-pagination") as internship_pagination:
                                internship_previous = gr.Button("Précédent", elem_id="internship-page-previous")
                                internship_page_buttons = [gr.Button(str(number), elem_id=f"internship-page-{number}")
                                                           for number in range(1, 6)]
                                internship_next = gr.Button("Suivant", elem_id="internship-page-next")
                            internship_page = gr.State({"page": 1, "count": 1})
                        with gr.Tab("Mes candidatures"):
                            internship_tracking = (gr.State({}) if shared else gr.BrowserState(
                                default_value={}, storage_key="ai-sales-desk-internships-v1",
                                secret="ai-sales-desk-local-tracking-v1"))
                            with gr.Row(elem_id="application-entry-row"):
                                tracked_offer = gr.Dropdown(label="Offre", choices=[], filterable=True, scale=5)
                                tracked_status = gr.Dropdown(
                                    list(TRACKING_STATUSES), value=TRACKING_STATUSES[0], label="Étape", scale=2,
                                )
                                tracking_save = gr.Button("Enregistrer", variant="primary", scale=1)
                            with gr.Accordion("Notes et dates (facultatif)", open=False):
                                with gr.Row():
                                    tracked_follow_up = gr.Textbox(label="Prochaine action (AAAA-MM-JJ)", scale=2)
                                    tracked_deadline = gr.Textbox(label="Date limite (AAAA-MM-JJ)", scale=2)
                                with gr.Row():
                                    tracked_applied_at = gr.Textbox(label="Postulé le (AAAA-MM-JJ)", scale=2)
                                    tracked_note = gr.Textbox(label="Note et contact", lines=2, scale=4)
                                tracking_remove = gr.Button("Retirer cette offre du suivi")
                            tracking_message = gr.Markdown(
                                "Suivi enregistré dans ton compte." if shared else
                                "Suivi sauvegardé automatiquement sur cet ordinateur."
                                if local_state_enabled() else "Suivi conservé dans ce navigateur."
                            )
                            tracking_view = gr.HTML('<div class="pipeline-empty">Chargement de ton suivi…</div>')
                            with gr.Accordion("Sauvegarder ou restaurer mon suivi", open=False):
                                gr.Markdown("La sauvegarde locale est automatique. Copie ce JSON pour transférer ton suivi vers un autre ordinateur.")
                                tracking_backup = gr.Textbox(label="Sauvegarde JSON", lines=6)
                                with gr.Row():
                                    tracking_export = gr.Button("Afficher la sauvegarde")
                                    tracking_import = gr.Button("Importer cette sauvegarde")

                with gr.Tab("Assistant IA", id="assistant"):
                    with gr.Tabs(elem_id="assistant-subtabs"):
                      with gr.Tab("Candidatures", id="candidatures"):
                        gr.HTML(
                            '<section class="agent-intro"><div>'
                            '<h2>Prépare tes candidatures</h2>'
                            '<p>Analyse les offres et rédige une lettre adaptée à ton profil.</p>'
                            '</div></section>'
                        )
                        with gr.Column(elem_id="agent-start-card"):
                            with gr.Row(elem_id="agent-start-row"):
                                agent_profile_select = gr.Dropdown(
                                    choices=profile_choices(initial_catalog), value=active_profile(initial_catalog)[0],
                                    visible=False, elem_id="agent-profile-select",
                                )
                                agent_scan = gr.Button("Analyser les offres", variant="primary", interactive=False,
                                                       elem_id="agent-scan")
                            gr.Markdown("Ton profil est envoyé à OpenAI uniquement quand tu lances une génération.",
                                        elem_id="agent-privacy-note")
                        with gr.Column(elem_id="agent-empty-state") as agent_empty_state:
                            gr.HTML('<div class="agent-empty"><strong>Commence avec ton profil</strong>'
                                    '<p>Ajoute ton CV et tes préférences pour recevoir des offres adaptées.</p></div>')
                            agent_create_profile = gr.Button("Créer mon profil", variant="primary")
                        agent_profile_card = gr.HTML("")
                        agent_message = gr.Markdown("")
                        agent_briefs = gr.HTML("", elem_id="agent-briefs", js_on_load="""
element.addEventListener('click', (event) => {
  const button = event.target.closest('.agent-prepare-letter');
  if (!button) return;
  trigger('click', {url: button.dataset.offerUrl});
  document.querySelector('#agent-workspace')?.scrollIntoView({behavior: 'smooth', block: 'start'});
});
""")
                        agent_selection = gr.State([])
                        agent_drafts = (gr.State({}) if shared else gr.BrowserState(
                            default_value={}, storage_key="ai-sales-desk-internships-agent-drafts-v1",
                            secret="ai-sales-desk-agent-drafts-v1"))
                        with gr.Column(elem_id="agent-workspace", visible=False) as agent_workspace:
                            gr.HTML('<h3 class="agent-letter-title">Ta lettre de motivation</h3>')
                            with gr.Row(elem_id="agent-letter-row"):
                                with gr.Column(elem_id="agent-offer-field"):
                                    gr.HTML('<label class="agent-field-label" for="agent-offer">Offre pour la lettre</label>')
                                    agent_offer = gr.Dropdown(label="Offre pour la lettre", show_label=False,
                                                              container=False, choices=[], scale=4,
                                                              elem_id="agent-offer")
                                with gr.Column(elem_id="agent-language-field"):
                                    gr.HTML('<span class="agent-field-label">Langue</span>')
                                    agent_language = gr.Radio(["Français", "English"], value="Français",
                                                              label="Langue", show_label=False, container=False, scale=2,
                                                              elem_id="agent-letter-language")
                                with gr.Column(elem_id="agent-letter-action"):
                                    agent_letter_button = gr.Button("Préparer la lettre", variant="primary", scale=1,
                                                                    elem_id="agent-letter-button")
                            gr.HTML('<label class="agent-field-label agent-editor-label" for="agent-letter">Ta lettre — modifiable avant export</label>')
                            agent_letter = gr.Textbox(label="Ta lettre — modifiable avant export", show_label=False,
                                                      container=False, lines=11, elem_id="agent-letter")
                            agent_review = gr.Markdown("", elem_id="agent-review")
                            with gr.Row(elem_id="agent-export-row"):
                                agent_save_draft = gr.Button("Sauvegarder le brouillon", scale=1, elem_id="agent-save-draft")
                                agent_pdf_button = gr.Button("Exporter en PDF", scale=1, interactive=False,
                                                             elem_id="agent-pdf-button")
                            agent_pdf = (gr.HTML("", elem_id="agent-pdf-file") if shared else
                                         gr.File(label="Fichier PDF", interactive=False, visible=False,
                                                 elem_id="agent-pdf-file"))
                      with gr.Tab("Messages LinkedIn", id="messages-linkedin") as linkedin_tab:
                        gr.Markdown("Ton profil s\u00e9lectionn\u00e9 est l\u2019exp\u00e9diteur ; ce PDF est celui de la personne que tu contactes.", elem_id="linkedin-intro", elem_classes=["linkedin-intro"])
                        linkedin_initial_profile = active_profile(initial_catalog)[1]
                        linkedin_profile_card = gr.HTML(
                            render_profile_card(linkedin_initial_profile), elem_id="linkedin-profile-card",
                        )
                        with gr.Column(elem_id="linkedin-message-card"):
                            gr.HTML('<div class="linkedin-upload-label">Profil du destinataire (PDF)</div>')
                            linkedin_pdf = gr.File(
                                label="Profil du destinataire (PDF)", show_label=False,
                                file_types=[".pdf"], file_count="single", type="filepath",
                                height=118, elem_id="linkedin-pdf",
                            )
                            with gr.Row(visible=False, elem_id="linkedin-uploaded-row") as linkedin_uploaded_row:
                                linkedin_pdf_details = gr.HTML("", elem_id="linkedin-pdf-details")
                                linkedin_pdf_remove = gr.Button("Supprimer", variant="secondary",
                                                                elem_id="linkedin-pdf-remove")
                            linkedin_recipient_state = gr.State({})
                            with gr.Row(visible=False, elem_id="linkedin-recipient-identity-row") as linkedin_identity_row:
                                linkedin_recipient_name = gr.Textbox(
                                    label="Destinataire identifié : Prénom Nom (modifiable)", value="", lines=1, max_lines=1,
                                    placeholder="Laisse vide si le prénom est incertain",
                                    elem_id="linkedin-recipient-name",
                                )
                            with gr.Row(elem_id="linkedin-select-row"):
                                linkedin_tone = gr.Dropdown(
                                    ["Professionnel", "Naturel", "Direct et concis"],
                                    value="Naturel", label="Ton", elem_id="linkedin-tone",
                                )
                                linkedin_objective = gr.Dropdown(
                                    ["Demander un conseil", "\u00c9changer sur son parcours",
                                     "Se renseigner sur une opportunit\u00e9"],
                                    value="Demander un conseil", label="Objectif",
                                    elem_id="linkedin-objective",
                                )
                            with gr.Row(elem_id="linkedin-option-row"):
                                linkedin_language = gr.Radio(
                                    ["Fran\u00e7ais", "English"], value="Fran\u00e7ais",
                                    label="Langue", elem_id="linkedin-language",
                                )
                                linkedin_type = gr.Radio(
                                    ["Invitation", "Apr\u00e8s connexion"],
                                    value="Invitation", label="Format", elem_id="linkedin-format",
                                )
                            linkedin_context = gr.Textbox(
                                label="Pr\u00e9cision facultative", lines=2, max_lines=3,
                                placeholder="Un sujet ou une question \u00e0 pr\u00e9ciser...",
                                elem_id="linkedin-context",
                            )
                            with gr.Row(elem_id="linkedin-generate-row"):
                                linkedin_generate = gr.Button(
                                    "G\u00e9n\u00e9rer le message", variant="primary",
                                    elem_id="linkedin-generate",
                                )
                                linkedin_status = gr.Markdown(
                                    "Ton profil complet et le texte extrait du PDF sont transmis \u00e0 OpenAI uniquement au clic.",
                                    elem_id="linkedin-status",
                                )
                            with gr.Column(visible=False, elem_id="linkedin-result") as linkedin_result:
                                linkedin_message = gr.Textbox(
                                    label="Message modifiable", lines=5, max_lines=8,
                                    elem_id="linkedin-message",
                                )
                                linkedin_copy = gr.Button(
                                    "Copier le message", variant="secondary", elem_id="linkedin-copy",
                                    interactive=False,
                                )
                                gr.HTML('<div class="linkedin-copy-hint">Modifie le texte avant de le copier ou de le régénérer.</div>')
                                gr.Markdown("### Ta relance", elem_id="linkedin-followup-heading")
                                linkedin_followup = gr.Textbox(
                                    label="Brouillon de relance modifiable", lines=3, max_lines=5,
                                    elem_id="linkedin-followup-message",
                                )
                                linkedin_followup_copy = gr.Button(
                                    "Copier la relance", variant="secondary", elem_id="linkedin-followup-copy",
                                    interactive=False,
                                )
                                gr.Markdown(
                                    "À utiliser après une à deux semaines sans réponse. Après une invitation, attends l’acceptation avant d’envoyer cette relance si tu n’as pas d’autre canal de contact.",
                                    elem_id="linkedin-followup-note",
                                )
                            linkedin_copy.click(
                                None, inputs=[linkedin_message], outputs=[],
                                js="(text) => { if (!text) return; if (navigator.clipboard && window.isSecureContext) navigator.clipboard.writeText(text); else { const area=document.createElement('textarea'); area.value=text; document.body.appendChild(area); area.select(); document.execCommand('copy'); area.remove(); } }",
                            )
                            linkedin_followup_copy.click(
                                None, inputs=[linkedin_followup], outputs=[],
                                js="(text) => { if (!text) return; if (navigator.clipboard && window.isSecureContext) navigator.clipboard.writeText(text); else { const area=document.createElement('textarea'); area.value=text; document.body.appendChild(area); area.select(); document.execCommand('copy'); area.remove(); } }",
                            )
                      with gr.Tab("Mail", id="mail") as mail_tab:
                        gr.HTML('<section class="mail-intro"><h2>Candidatures spontanées</h2>'
                                '<p>Importe des profils LinkedIn, prépare tes messages et valide chaque adresse avant envoi.</p></section>')
                        with gr.Column(elem_id="mail-import-card"):
                            mail_profile_card = gr.HTML(render_profile_card(active_profile(initial_catalog)[1]))
                            mail_seed_status = gr.Markdown("Les contacts du fichier fourni seront enregistrés dans ton espace Mail.")
                            mail_pdf = gr.File(label="Profils LinkedIn (PDF)", file_types=[".pdf"],
                                               file_count="multiple", type="filepath", height=118,
                                               elem_id="mail-pdf")
                            mail_import_button = gr.Button("Importer les contacts", variant="primary")
                            mail_import_status = gr.Markdown("Aucun message n'est envoyé lors de l'import.")
                        with gr.Column(elem_id="mail-editor-card", visible=False) as mail_editor_card:
                            mail_contact = gr.Dropdown(label="Contact à préparer", choices=[],
                                                       elem_id="mail-contact")
                            with gr.Row():
                                mail_name = gr.Textbox(label="Nom complet", lines=1, elem_id="mail-name")
                                mail_role = gr.Textbox(label="Poste actuel", lines=1)
                            with gr.Row():
                                mail_company = gr.Textbox(label="Entreprise actuelle", lines=1)
                                mail_location = gr.Textbox(label="Localisation", lines=1)
                            with gr.Row():
                                mail_desk = gr.Textbox(label="Desk / catégorie", lines=1)
                                mail_external_id = gr.Textbox(label="Identifiant source (lecture seule)", lines=1, interactive=False)
                            with gr.Row():
                                mail_source_type = gr.Textbox(label="Type de source", lines=1)
                                mail_source_url = gr.Textbox(label="Source", lines=1)
                            with gr.Row():
                                mail_research_date = gr.Textbox(label="Date de recherche", lines=1)
                                mail_last_verified = gr.Textbox(label="Dernière vérification réelle", lines=1)
                            with gr.Row():
                                mail_verification_status = gr.Dropdown(["À vérifier", "Partiellement vérifié", "Vérifié"],
                                                                       value="À vérifier", label="Vérification")
                                mail_contract_status = gr.Dropdown(["Non confirmé", "Stage", "VIE", "Graduate", "CDI", "CDD", "Autre"],
                                                                   value="Non confirmé", label="Contrat")
                                mail_outreach_status = gr.Dropdown(["Non contacté", "Contacté", "À recontacter", "Ne pas contacter"],
                                                                   value="Non contacté", label="Prospection")
                            mail_source_notes = gr.Textbox(label="Notes d’origine", lines=3, max_lines=5)
                            mail_linkedin = gr.Textbox(label="Profil LinkedIn", lines=1)
                            with gr.Row():
                                mail_template = gr.Dropdown(label="Format d'adresse", choices=list(mail_outreach.DEFAULT_TEMPLATES),
                                                            value=None, allow_custom_value=False)
                                mail_email = gr.Textbox(label="Adresse supposée ou saisie manuellement", lines=1,
                                                        elem_id="mail-email")
                                mail_email_status = gr.Dropdown(["non_renseigne", "supposée", "publiée", "vérifiée"],
                                                                value="non_renseigne", label="État de l’adresse")
                            mail_address_note = gr.Markdown("Une adresse proposée n'est jamais une boîte vérifiée.")
                            with gr.Row():
                                mail_experiences = gr.Textbox(label="Expériences du contact (corrigeables)", lines=3)
                                mail_education = gr.Textbox(label="Formations du contact (corrigeables)", lines=3)
                            with gr.Row():
                                mail_language = gr.Dropdown(["Français", "English"], value="Français", label="Langue")
                                mail_followup_days = gr.Dropdown(["7", "14"], value="14", label="Relance à préparer après (jours)")
                            mail_auto_followup = gr.Checkbox(
                                label="Envoyer automatiquement une relance à l'échéance si aucune réponse ou refus n'a été enregistré",
                                value=False)
                            with gr.Column(elem_classes=["mail-draft-section"]):
                                mail_subject = gr.Textbox(label="Objet", lines=1, elem_id="mail-subject")
                                mail_body = gr.Textbox(label="Message", lines=5, elem_id="mail-body")
                            with gr.Column(elem_classes=["mail-draft-section"]):
                                mail_followup_subject = gr.Textbox(label="Objet de relance", lines=1)
                                mail_followup_body = gr.Textbox(label="Relance", lines=3)
                            with gr.Row():
                                mail_save = gr.Button("Enregistrer ce contact", variant="secondary")
                                mail_generate = gr.Button("Générer le mail", variant="primary")
                            mail_editor_status = gr.Markdown("")
                        with gr.Accordion("Formats d'adresses supposés", open=False, elem_id="mail-templates"):
                            mail_template_info = gr.Markdown("")
                            with gr.Row():
                                template_institution = gr.Textbox(label="Établissement", lines=1)
                                template_domain = gr.Textbox(label="Domaine", lines=1)
                            with gr.Row():
                                template_pattern = gr.Dropdown(["{prenom}.{nom}", "{initiale_prenom}{nom}",
                                                                "{prenom}{nom}", "{prenom}_{nom}"],
                                                               label="Format", value="{prenom}.{nom}")
                                template_aliases = gr.Textbox(label="Filiales exactes (séparées par virgules)", lines=1)
                            template_source = gr.Textbox(label="Référence publique (optionnelle ; non vérifiée automatiquement)", lines=1)
                            template_save = gr.Button("Enregistrer le format", variant="secondary")
                            template_status = gr.Markdown("")
                        with gr.Column(elem_id="mail-batch-card", visible=False) as mail_batch_card:
                            gr.Markdown("### Revue du lot")
                            mail_batch = gr.CheckboxGroup(label="Contacts à envoyer", choices=[], elem_id="mail-batch")
                            mail_cv = gr.File(label="CV à joindre à ce lot (PDF, facultatif)",
                                              file_types=[".pdf"], file_count="single", type="filepath",
                                              height=112, elem_id="mail-cv")
                            mail_review_state = gr.State("")
                            mail_batch_review = gr.HTML("")
                            mail_confirm = gr.Checkbox(label="J'ai relu chaque message, adresse supposée et pièce jointe ; je valide l'envoi de ce lot.",
                                                       elem_id="mail-confirm")
                            with gr.Row():
                                mail_send = gr.Button("Envoyer le lot validé", variant="primary", interactive=False)
                                mail_pause = gr.Button("Mettre en pause", variant="secondary", visible=False)
                                mail_resume = gr.Button("Reprendre", variant="secondary", visible=False)
                                mail_cancel = gr.Button("Annuler le reste", variant="secondary", visible=False)
                            mail_batch_status = gr.Markdown("Cadence et plafond configurables côté serveur. Aucun envoi automatique des relances.")
                        with gr.Column(elem_id="mail-dashboard-card"):
                            gr.Markdown("### Suivi des contacts")
                            mail_counts = gr.HTML("")
                            with gr.Row():
                                mail_filter = gr.Textbox(label="Filtrer", placeholder="Nom, entreprise, statut…", lines=1)
                                mail_refresh = gr.Button("Actualiser le suivi", variant="secondary")
                            with gr.Row():
                                mail_company_filter = gr.Dropdown(choices=mail_outreach.seed_filter_options("company"), value="Toutes", label="Banque / établissement", allow_custom_value=True)
                                mail_desk_filter = gr.Dropdown(choices=mail_outreach.seed_filter_options("desk"), value="Toutes", label="Desk", allow_custom_value=True)
                                mail_location_filter = gr.Dropdown(choices=mail_outreach.seed_filter_options("location"), value="Toutes", label="Localisation", allow_custom_value=True)
                            with gr.Row():
                                mail_source_filter = gr.Dropdown(choices=mail_outreach.seed_filter_options("source_type"), value="Toutes", label="Type de source", allow_custom_value=True)
                                mail_verification_filter = gr.Dropdown(["Toutes", "À vérifier", "Partiellement vérifié", "Vérifié"], value="Toutes", label="Vérification")
                                mail_outreach_filter = gr.Dropdown(["Toutes", "Non contacté", "Contacté", "À recontacter", "Ne pas contacter", "En attente", "Réponse", "Refus"], value="Toutes", label="Prospection")
                            mail_table = gr.Dataframe(
                                headers=["Nom", "Poste", "Entreprise", "Localisation", "Desk", "Source",
                                         "Vérification", "Contrat", "Adresse", "État adresse", "Statut", "Dernier envoi",
                                         "Prochaine relance"],
                                interactive=False, wrap=False, visible=False, elem_id="mail-table")
                            mail_mobile_cards = gr.HTML("", elem_id="mail-mobile-cards")
                            with gr.Row():
                                mail_export_button = gr.Button("Exporter les contacts en CSV", variant="secondary")
                                mail_export_file = gr.File(label="Export CSV", visible=False, interactive=False)
                            mail_export_link = gr.HTML("")
                            mail_detail_select = gr.Dropdown(label="Contact à consulter ou mettre à jour", choices=[],
                                                             elem_id="mail-detail-select")
                            mail_detail = gr.HTML("", elem_id="mail-detail")
                            with gr.Column(visible=False, elem_id="mail-status-editor") as mail_status_editor:
                                with gr.Row():
                                    mail_conversation = gr.Dropdown(["Non contact\u00e9", "\u00c0 contacter", "En attente", "R\u00e9ponse", "Refus",
                                                                     "Erreur d\u00e9finitive"], label="Statut de conversation")
                                    mail_notes = gr.Textbox(label="Notes", lines=1)
                                mail_status_save = gr.Button("Mettre à jour le suivi", variant="secondary")
                                mail_status_feedback = gr.Markdown("", elem_id="mail-status-feedback")
                            gr.Markdown("Marque les réponses, refus et erreurs définitives manuellement. Aucune synchronisation de boîte ni pixel de suivi.")
                        mail_timer = gr.Timer(value=5, active=True)
                with gr.Tab("Mon profil", id="profil") as profile_tab:
                    gr.HTML(
                        '<section class="profile-intro">'
                        '<h2>Ton profil</h2>'
                        '<p>Ajoute ton CV et tes préférences pour personnaliser ta recherche.</p>'
                        '</section>'
                    )
                    profile_select = gr.Dropdown(
                        choices=profile_choices(initial_catalog), value=active_profile(initial_catalog)[0],
                        visible=False, elem_id="profile-select",
                    )
                    if shared:
                        with gr.Accordion("Importer mes données de ce navigateur", open=False):
                            gr.Markdown("Si tu utilisais déjà l’application dans ce navigateur, transfère tes profils, candidatures et brouillons vers ton compte connecté. Tes données déjà enregistrées restent prioritaires en cas de conflit.")
                            import_browser_data = gr.Button("Importer dans mon compte")
                            import_browser_message = gr.Markdown("")
                    with gr.Column(elem_id="profile-cv-card", elem_classes=["profile-section-card"]):
                        gr.HTML('<div class="profile-section-heading"><h3>Ton CV</h3>'
                                '<p>Ajoute un CV ou décris ton parcours pour créer ton profil.</p></div>')
                        with gr.Column(elem_classes=["profile-field"]):
                            gr.HTML('<div class="profile-field-label">Nom du profil</div>')
                            profile_name = gr.Textbox(label="Nom du profil", value="", lines=1, max_lines=1,
                                                      placeholder="Prénom Nom", container=False,
                                                      elem_id="profile-name")
                        with gr.Row(elem_id="profile-source-row"):
                            with gr.Column(elem_id="profile-upload-column"):
                                gr.HTML('<div class="profile-upload-caption"><strong>Importer ton CV</strong>'
                                        '<span>PDF, Word ou texte</span></div>')
                                profile_cv = gr.UploadButton(
                                    "Choisir un fichier",
                                    file_types=[".pdf", ".docx", ".txt", ".md"],
                                    type="filepath", size="sm", elem_id="profile-cv-upload",
                                )
                                profile_cv_text = gr.State("")
                            with gr.Column(elem_id="profile-summary-column"):
                                gr.HTML('<div class="profile-field-label">Résumé du parcours</div>')
                                profile_source = gr.Textbox(
                                    label="Résumé du parcours", value="", lines=5, max_lines=5,
                                    container=False,
                                    placeholder="Formation, expériences, compétences, objectifs et disponibilité. L’import du CV peut compléter ce résumé.",
                                )
                        profile_analyze = gr.Button("Analyser mon CV ou mon résumé", variant="primary",
                                                    elem_id="profile-analyze")
                        profile_status = gr.Markdown("Indique ton nom et ajoute un CV ou un résumé.",
                                                     elem_id="profile-status")
                    with gr.Column(elem_id="profile-experience-card", elem_classes=["profile-section-card"]):
                        gr.HTML('<div class="profile-section-heading"><h3>Ton parcours</h3>'
                                '<p>Relis les informations extraites et complète-les si besoin.</p></div>')
                        with gr.Column(elem_classes=["profile-field"]):
                            gr.HTML('<div class="profile-field-label">Résumé professionnel</div>')
                            profile_overview = gr.Textbox(label="Résumé professionnel", lines=3, max_lines=4,
                                                          container=False)
                        with gr.Row(elem_id="profile-experience-row"):
                            with gr.Column(elem_classes=["profile-field"]):
                                gr.HTML('<div class="profile-field-label">Tes expériences</div>')
                                profile_experience = gr.Textbox(label="Tes expériences", lines=4, max_lines=5,
                                                                 container=False, placeholder="Une expérience par ligne")
                            with gr.Column(elem_classes=["profile-field"]):
                                gr.HTML('<div class="profile-field-label">Tes compétences</div>')
                                profile_strengths = gr.Textbox(label="Tes compétences", lines=4, max_lines=5,
                                                                container=False, placeholder="Une compétence par ligne")
                    with gr.Column(elem_id="profile-search-card", elem_classes=["profile-section-card"]):
                        gr.HTML('<div class="profile-section-heading"><h3>Ta recherche</h3>'
                                '<p>Précise les offres et la période qui t’intéressent.</p></div>')
                        with gr.Row(elem_id="profile-target-row"):
                            with gr.Column(elem_classes=["profile-field"]):
                                gr.HTML('<div class="profile-field-label">Métiers recherchés</div>')
                                profile_roles = gr.Textbox(label="Métiers recherchés", placeholder="Sales, Trading, Quant…",
                                                           lines=1, max_lines=1, scale=2, container=False,
                                                           elem_id="profile-roles")
                            with gr.Column(elem_classes=["profile-field"]):
                                gr.HTML('<div class="profile-field-label">Lieux souhaités</div>')
                                profile_locations = gr.Textbox(label="Lieux souhaités", placeholder="Paris, Londres…",
                                                               lines=1, max_lines=1, scale=2, container=False,
                                                               elem_id="profile-locations")
                            with gr.Column(elem_classes=["profile-field"]):
                                gr.HTML('<div class="profile-field-label">Contrats</div>')
                                profile_contracts = gr.Textbox(label="Contrats", placeholder="Stage, VIE, Graduate",
                                                               lines=1, max_lines=1, scale=1, container=False,
                                                               elem_id="profile-contracts")
                        gr.HTML('<div class="profile-availability-heading"><strong>Disponibilités</strong>'
                                '<span>Indique les mois au plus tôt et au plus tard (AAAA-MM).</span></div>')
                        with gr.Row(elem_id="profile-dates-row"):
                            with gr.Column(elem_classes=["profile-field"]):
                                gr.HTML('<div class="profile-field-label">Au plus tôt</div>')
                                profile_start_month = gr.Textbox(label="Au plus tôt", placeholder="AAAA-MM", scale=1,
                                                                 lines=1, max_lines=1, container=False,
                                                                 elem_id="profile-start-month")
                            with gr.Column(elem_classes=["profile-field"]):
                                gr.HTML('<div class="profile-field-label">Au plus tard</div>')
                                profile_end_month = gr.Textbox(label="Au plus tard", placeholder="AAAA-MM", scale=1,
                                                               lines=1, max_lines=1, container=False,
                                                               elem_id="profile-end-month")
                        with gr.Column(elem_classes=["profile-field"]):
                            gr.HTML('<div class="profile-field-label">Précision facultative sur ta disponibilité</div>')
                            profile_start = gr.Textbox(label="Précision facultative sur ta disponibilité",
                                                       placeholder="Ex. disponible dès mai 2027", lines=1, max_lines=1,
                                                       container=False, elem_id="profile-start-window")
                        with gr.Column(elem_classes=["profile-field"]):
                            gr.HTML('<div class="profile-field-label">Informations à compléter</div>')
                            profile_constraints = gr.Textbox(label="Informations à compléter", lines=3, max_lines=4,
                                                             container=False, placeholder="Un point par ligne")
                        profile_save = gr.Button("Enregistrer les modifications", variant="secondary",
                                                 elem_id="profile-save")
                        profile_delete_confirm = gr.Checkbox(
                            label="Je confirme la suppression de mon profil enregistré.", value=False,
                            elem_id="profile-delete-confirm",
                        )
                        profile_delete = gr.Button("Supprimer mon profil", variant="secondary",
                                                   elem_id="profile-delete")
                        profile_save_status = gr.Markdown("", elem_id="profile-save-status")
                    profile_preview = gr.HTML("")

                if shared:
                    with gr.Tab("Administration", id="administration", visible=False) as admin_tab:
                        gr.HTML('<section class="profile-intro"><h2>Administration</h2>'
                                '<p>Comptes créés et consommation de l’assistant IA.</p></section>')
                        admin_refresh = gr.Button("Actualiser le rapport", variant="primary", size="sm", elem_id="admin-refresh")
                        with gr.Column(elem_id="account-admin-panel"):
                            gr.HTML('<div class="account-admin-heading"><h3>Comptes de l’application</h3>'
                                    '<p>Supprimer un compte bloque aussi définitivement son identifiant. Les comptes initiaux se gèrent dans la configuration du serveur.</p></div>')
                            account_admin_list = gr.HTML("")
                            with gr.Row(elem_id="account-delete-row"):
                                account_to_delete = gr.Dropdown(
                                    label="Compte inscrit à supprimer", choices=[],
                                    value=None, elem_id="account-delete-select",
                                )
                                admin_delete = gr.Button("Supprimer et bloquer l’identifiant", variant="secondary",
                                                         elem_id="account-delete-button")
                            admin_delete_confirm = gr.Checkbox(
                                label="Je confirme la suppression de son accès et de ses données, et le blocage définitif de son identifiant.",
                                value=False, elem_id="account-delete-confirm",
                            )
                            admin_delete_message = gr.Markdown("", elem_id="account-delete-message")
                        with gr.Column(elem_id="usage-admin-panel"):
                            gr.HTML('<div class="account-admin-heading"><h3>Coûts de l’API IA</h3>'
                                    '<p>Suivi par compte, par usage et par appel.</p></div>')
                            admin_usage_html = gr.HTML("")

            gr.HTML(
                '<footer class="career-credit">Un projet de <strong>Théo Caruana</strong>'
                '<span aria-hidden="true">·</span> Développé avec Codex '
                '<span aria-hidden="true">·</span> <a href="/confidentialite" target="_blank" rel="noopener">Confidentialité</a></footer>',
                elem_id="career-credit",
            )


        def offer_choices(jobs: list[Opportunity], state: dict | None):
            entries = state if isinstance(state, dict) else {}
            tracked = [
                (f"{normalize_status(entry.get('status'))} · {entry.get('company', '')} · {str(entry.get('title', 'Offre'))[:65]}", url)
                for url, entry in reversed(list(entries.items())[-100:])
                if isinstance(url, str) and url.startswith("https://") and isinstance(entry, dict)
            ]
            saved_urls = {url for _, url in tracked}
            published = [(f"{job.company} · {job.title[:75]}", job.url)
                         for job in jobs if job.url not in saved_urls]
            return tracked + published

        def show_internships(category: str, query: str, family: str, earliest: str,
                             tracking: dict, feedback: dict, show_hors_cible: bool, period: str, sort_by: str,
                             force: bool = False, request: gr.Request = None, page: int = 1,
                             refresh: bool = True):
            jobs, errors, updated = account_opportunities(request, force=force, refresh=refresh)
            filtered = matching_opportunities(
                jobs, category, query, family, earliest, tracking=tracking,
                hide_dismissed=True, weekly=period == "weekly", daily=period == "daily",
                sort_by=sort_by,
            )
            page_count = max(1, (len(filtered) + 49) // 50)
            page = max(1, min(int(page), page_count))
            page_state = {"page": page, "count": page_count}
            page_controls = pagination_updates(page, page_count)
            return (
                render_opportunities(
                    jobs, errors, updated, category, query, family, earliest, tracking=tracking,
                    hide_dismissed=True,
                    refreshing=opportunities_loading() and (not shared or username(request) == owner),
                    daily=period == "daily", weekly=period == "weekly",
                    feedback=feedback, show_hors_cible=show_hors_cible, sort_by=sort_by,
                    delayed_updates=shared and username(request) != owner,
                    page=page, page_size=50,
                ),
                gr.Dropdown(choices=offer_choices(jobs, tracking), value=None),
                render_tracking(tracking, jobs),
                page_state, *page_controls,
            )

        internship_inputs = [
            internship_category, internship_search, internship_family, internship_start, internship_tracking,
            internship_feedback, internship_show_hors_cible,
            internship_period, internship_sort,
        ]
        internship_outputs = [internship_board, tracked_offer, tracking_view, internship_page,
                              internship_pagination, *internship_page_buttons,
                              internship_previous, internship_next]

        def pagination_updates(page: int, page_count: int):
            start_page = max(1, min(page - 2, page_count - 4))
            number_updates = [
                gr.Button(value=str(number), visible=number <= page_count,
                          interactive=number <= page_count,
                          variant="primary" if number == page else "secondary")
                for number in range(start_page, start_page + 5)
            ]
            return [gr.Row(visible=page_count > 1), *number_updates,
                    gr.Button(value="Précédent", interactive=page > 1),
                    gr.Button(value="Suivant", interactive=page < page_count)]

        def show_requested_page(page: int, category: str, query: str, family: str, earliest: str,
                                tracking: dict, feedback: dict, show_hors_cible: bool,
                                period: str, sort_by: str, request: gr.Request):
            try:
                target = max(1, int(page))
            except (TypeError, ValueError):
                target = 1
            return show_internships(category, query, family, earliest, tracking, feedback,
                                    show_hors_cible, period, sort_by, request=request,
                                    page=target, refresh=False)

        def navigate_relative(amount: int, current: dict, *args):
            current_page = int((current or {}).get("page", 1))
            page_count = int((current or {}).get("count", 1))
            start_page = max(1, min(current_page - 2, page_count - 4))
            target = (max(1, min(page_count, current_page + amount)) if amount in {-1, 1}
                      else min(page_count, start_page + amount - 100))
            category, query, family, earliest, tracking, feedback, show_hors_cible, period, sort_by, request = args
            return show_requested_page(target, category, query, family, earliest, tracking,
                                       feedback, show_hors_cible, period, sort_by, request)

        def previous_page(current: dict, category: str, query: str, family: str, earliest: str,
                          tracking: dict, feedback: dict, show_hors_cible: bool, period: str,
                          sort_by: str, request: gr.Request):
            return navigate_relative(-1, current, category, query, family, earliest, tracking,
                                     feedback, show_hors_cible, period, sort_by, request)

        def next_page(current: dict, category: str, query: str, family: str, earliest: str,
                      tracking: dict, feedback: dict, show_hors_cible: bool, period: str,
                      sort_by: str, request: gr.Request):
            return navigate_relative(1, current, category, query, family, earliest, tracking,
                                     feedback, show_hors_cible, period, sort_by, request)

        def numbered_page(slot: int):
            def select(current: dict, category: str, query: str, family: str, earliest: str,
                       tracking: dict, feedback: dict, show_hors_cible: bool, period: str,
                       sort_by: str, request: gr.Request):
                return navigate_relative(100 + slot, current, category, query, family, earliest, tracking,
                                         feedback, show_hors_cible, period, sort_by, request)
            return select

        scroll_after_page_change = "() => { document.querySelector('#internship-board .results-overview')?.scrollIntoView({behavior: 'smooth', block: 'start'}); }"
        internship_previous.click(
            previous_page,
            inputs=[internship_page, *internship_inputs], outputs=internship_outputs,
            queue=False, show_progress="hidden",
        ).then(None, js=scroll_after_page_change)
        for slot, button in enumerate(internship_page_buttons):
            button.click(
                numbered_page(slot),
                inputs=[internship_page, *internship_inputs], outputs=internship_outputs,
                queue=False, show_progress="hidden",
            ).then(None, js=scroll_after_page_change)
        internship_next.click(
            next_page,
            inputs=[internship_page, *internship_inputs], outputs=internship_outputs,
            queue=False, show_progress="hidden",
        ).then(None, js=scroll_after_page_change)

        filter_controls = [internship_search, internship_category, internship_family,
                           internship_period, internship_start]
        filter_chips = [internship_query_chip, internship_contract_chip, internship_family_chip,
                        internship_period_chip, internship_start_chip]
        chip_outputs = [internship_active_filters, *filter_chips, internship_reset_filters]

        def update_filter_chips(query: str, category: str, family: str, period: str, earliest: str):
            active = [
                (bool(query.strip()), f"Recherche : {query.strip()}  ×"),
                (category != "Toutes", f"{dict([('Toutes', 'Tous les contrats'), ('Stages Paris', 'Stages · Paris'), ('Stages International', 'Stages · International'), ('VIE', 'VIE'), ('Graduate', 'Graduate')]).get(category, category)}  ×"),
                (family != "Tous métiers", f"{family}  ×"),
                (period != "all", f"{dict([('daily', 'Aujourd’hui'), ('weekly', '7 derniers jours')]).get(period, period)}  ×"),
                (earliest != "Toutes dates", f"Début : {next((label for label, value in month_choices if value == earliest), earliest)}  ×"),
            ]
            visible = any(enabled for enabled, _ in active)
            return (gr.update(visible=visible),
                    *(gr.update(value=label, visible=enabled) for enabled, label in active),
                    gr.update(visible=visible))

        for control in filter_controls:
            control.change(update_filter_chips, inputs=filter_controls, outputs=chip_outputs,
                           queue=False, show_progress="hidden")

        defaults = ["", "Toutes", "Tous métiers", "all", "Toutes dates"]
        for chip, control, default in zip(filter_chips, filter_controls, defaults):
            chip.click(lambda value=default: value, outputs=control, queue=False).then(
                show_internships, inputs=internship_inputs, outputs=internship_outputs,
            ).then(update_filter_chips, inputs=filter_controls, outputs=chip_outputs, queue=False)
        internship_reset_filters.click(
            lambda: defaults, outputs=filter_controls, queue=False,
        ).then(
            show_internships, inputs=internship_inputs, outputs=internship_outputs,
        ).then(
            update_filter_chips, inputs=filter_controls, outputs=chip_outputs, queue=False,
        )

        def hydrate_state(tracking: dict, feedback: dict, request: gr.Request):
            if shared:
                account = username(request)
                return (load_user_data(account, "tracking"),
                        load_user_data(account, "feedback"),
                        clean_catalog(load_user_data(account, "profiles")),
                        load_user_data(account, "drafts"))
            try:
                saved_tracking, saved_feedback = hydrate_local_state(tracking, feedback)
            except OSError:
                gr.Warning("Sauvegarde locale inaccessible ; le suivi reste disponible dans ce navigateur.")
                saved_tracking, saved_feedback = tracking or {}, feedback or {}
            return saved_tracking, saved_feedback, gr.skip(), gr.skip()

        hydration_event = app_blocks.load(
            hydrate_state, inputs=[internship_tracking, internship_feedback],
            outputs=[internship_tracking, internship_feedback, profiles_state, agent_drafts],
        ).then(show_internships, inputs=internship_inputs, outputs=internship_outputs)
        if shared:
            def account_overview(request: gr.Request):
                if username(request) != owner:
                    return gr.update(visible=False), "", "", gr.Dropdown(choices=[], value=None)
                entries = list_accounts(configured)
                rows = "".join(
                    '<div class="account-admin-row"><strong>' + html.escape(name)
                    + '</strong><span>' + html.escape(kind) + '</span><time>'
                    + html.escape(created[:10] if created else "Compte initial") + '</time></div>'
                    for name, kind, created in entries
                )
                accounts_html = (
                    f'<div class="account-admin-count">{len(entries)} compte(s)</div>'
                    f'<div class="account-admin-rows">{rows}</div>'
                )
                deletable = [(name, name) for name, kind, _ in entries if kind == "Inscription"]
                return (gr.update(visible=True), accounts_html, render_usage_report(),
                        gr.Dropdown(choices=deletable, value=None))

            app_blocks.load(account_overview, outputs=[admin_tab, account_admin_list,
                                                       admin_usage_html, account_to_delete],
                            queue=False, show_progress="hidden")
            admin_refresh.click(account_overview,
                                outputs=[admin_tab, account_admin_list, admin_usage_html,
                                         account_to_delete], queue=False)

            def remove_account(target: str, confirmed: bool, request: gr.Request):
                if username(request) != owner:
                    raise gr.Error("Seul l’administrateur peut supprimer un compte.")
                if not confirmed:
                    raise gr.Error("Confirme la suppression avant de continuer.")
                try:
                    delete_registered_account(target, configured)
                except ValueError as exc:
                    raise gr.Error(str(exc)) from exc
                return (f"Le compte **{html.escape(target)}** et ses données ont été supprimés ; "
                        "cet identifiant est désormais bloqué pour toute nouvelle inscription."), False

            admin_delete.click(
                remove_account, inputs=[account_to_delete, admin_delete_confirm],
                outputs=[admin_delete_message, admin_delete_confirm],
            ).then(account_overview,
                   outputs=[admin_tab, account_admin_list, admin_usage_html,
                            account_to_delete])
        internship_category.change(
            show_internships, inputs=internship_inputs, outputs=internship_outputs
        )
        internship_search.submit(
            show_internships, inputs=internship_inputs, outputs=internship_outputs
        )
        internship_family.change(
            show_internships, inputs=internship_inputs, outputs=internship_outputs
        )
        internship_start.change(
            show_internships, inputs=internship_inputs, outputs=internship_outputs
        )
        internship_period.change(
            show_internships, inputs=internship_inputs, outputs=internship_outputs
        )
        internship_sort.change(
            show_internships, inputs=internship_inputs, outputs=internship_outputs
        )
        def manual_refresh(category: str, query: str, family: str, earliest: str,
                           tracking: dict, feedback: dict, show_hors_cible: bool,
                           period: str, sort_by: str, page: dict, request: gr.Request):
            current_page = int((page or {}).get("page", 1))
            return show_internships(category, query, family, earliest, tracking,
                                    feedback, show_hors_cible, period, sort_by, True, request, current_page)

        internship_refresh.click(
            manual_refresh,
            inputs=[*internship_inputs, internship_page], outputs=internship_outputs,
        )
        internship_timer = gr.Timer(value=10, active=True)
        def refresh_internship_timer(category: str, query: str, family: str, earliest: str,
                                     tracking: dict, feedback: dict, show_hors_cible: bool,
                                     period: str, sort_by: str, selected: str,
                                     page: dict, request: gr.Request):
            rendered = show_internships(
                category, query, family, earliest, tracking, feedback, show_hors_cible,
                period, sort_by, request=request, page=int((page or {}).get("page", 1)),
            )
            jobs, _, _ = account_opportunities(request)
            choices = offer_choices(jobs, tracking)
            urls = {url for _, url in choices}
            return (rendered[0], gr.Dropdown(choices=choices, value=selected if selected in urls else None),
                    rendered[2], *rendered[3:])

        internship_timer.tick(
            refresh_internship_timer, inputs=[*internship_inputs, tracked_offer, internship_page],
            outputs=internship_outputs,
            queue=False, show_progress="hidden",
        )

        def load_tracking_fields(url: str, tracking: dict, request: gr.Request):
            entry = (tracking or {}).get(url, {}) if isinstance(tracking, dict) else {}
            jobs, _, _ = account_opportunities(request)
            job = next((item for item in jobs if item.url == url), None)
            return (normalize_status(entry.get("status")), entry.get("note", ""),
                    entry.get("deadline") or (job.deadline if job else ""),
                    entry.get("follow_up", ""), entry.get("applied_at", ""))

        tracked_offer.change(
            load_tracking_fields, inputs=[tracked_offer, internship_tracking],
            outputs=[tracked_status, tracked_note, tracked_deadline, tracked_follow_up, tracked_applied_at],
        )

        def update_tracking(url: str, status: str, note: str, deadline: str, follow_up: str,
                            applied_at: str,
                            tracking: dict, request: gr.Request, remove: bool = False):
            jobs, _, _ = account_opportunities(request)
            current = next((job for job in jobs if job.url == url), None)
            state = tracking if isinstance(tracking, dict) else {}

            def response(updated: dict, message: str, selected: str | None):
                return (updated, gr.Dropdown(choices=offer_choices(jobs, updated), value=selected),
                        render_tracking(updated, jobs), message)

            if not url:
                return response(state, "Sélectionne une offre.", None)
            if remove:
                updated = dict(state)
                updated.pop(url, None)
                try:
                    persist_personal("tracking", updated, request)
                except OSError:
                    gr.Warning("Suppression enregistrée dans ce navigateur ; sauvegarde locale inaccessible.")
                return response(updated, "Offre retirée du suivi.", None)
            if current is None:
                entry = state.get(url)
                if not isinstance(entry, dict):
                    return response(state, "Cette offre n'est plus dans les sources. Sélectionne une offre publiée.", None)
                current = Opportunity(
                    title=str(entry.get("title") or "Offre"), company=str(entry.get("company") or ""),
                    location=str(entry.get("location") or ""), kind="Stage", url=url,
                    published="", score=0,
                )
            updated = save_tracking(state, current, status, note, deadline, follow_up, applied_at)
            try:
                saved_locally = persist_personal("tracking", updated, request)
            except OSError:
                saved_locally = False
                gr.Warning("Suivi enregistré dans ce navigateur ; sauvegarde locale inaccessible.")
            message = ("Suivi enregistré dans ton compte." if shared and saved_locally else
                       "Suivi sauvegardé automatiquement sur cet ordinateur." if saved_locally
                       else "Suivi enregistré dans ce navigateur.")
            return response(updated, message, url)

        tracking_inputs = [tracked_offer, tracked_status, tracked_note, tracked_deadline,
                           tracked_follow_up, tracked_applied_at, internship_tracking]
        tracking_outputs = [internship_tracking, tracked_offer, tracking_view, tracking_message]

        def confirm_opened_offer(category: str, query: str, family: str, earliest: str,
                                 tracking: dict, feedback: dict,
                                 show_hors_cible: bool, period: str, sort_by: str,
                                 page: int, evt: gr.EventData, request: gr.Request):
            url = str(getattr(evt, "url", "") or "")
            jobs, _, _ = account_opportunities(request)
            updated, changed = mark_opened_offer_applied(tracking, jobs, url)
            if changed:
                try:
                    persist_personal("tracking", updated, request)
                except OSError:
                    gr.Warning("Candidature enregistrée dans ce navigateur ; sauvegarde locale inaccessible.")
                gr.Info("Offre ajoutée à Mes candidatures avec le statut « Postulé ».")
            else:
                gr.Warning("Cette offre est déjà suivie ou n’est plus dans les offres disponibles.")
            rendered = show_internships(
                category, query, family, earliest, updated,
                feedback, show_hors_cible, period, sort_by, request=request,
                page=int((page or {}).get("page", 1)),
            )
            choices = offer_choices(jobs, updated)
            selected = url if changed and any(choice_url == url for _, choice_url in choices) else None
            return (updated, rendered[0], gr.Dropdown(choices=choices, value=selected),
                    rendered[2], "Candidature ajoutée au statut Postulé." if changed else "Aucune modification du suivi.")

        offer_return_toast.click(
            confirm_opened_offer, inputs=[*internship_inputs, internship_page],
            outputs=[internship_tracking, internship_board, tracked_offer, tracking_view, tracking_message],
        )
        tracking_save.click(update_tracking, inputs=tracking_inputs, outputs=tracking_outputs)
        def remove_tracking(url: str, status: str, note: str, deadline: str,
                            follow_up: str, applied_at: str, tracking: dict,
                            request: gr.Request):
            return update_tracking(url, status, note, deadline, follow_up,
                                   applied_at, tracking, request, True)

        tracking_remove.click(
            remove_tracking,
            inputs=tracking_inputs, outputs=tracking_outputs,
        )
        tracking_export.click(export_tracking, inputs=[internship_tracking], outputs=[tracking_backup])

        def restore_tracking(payload: str, state: dict, request: gr.Request):
            updated, message = import_tracking(payload, state)
            if updated != (state or {}):
                try:
                    persist_personal("tracking", updated, request)
                except OSError:
                    gr.Warning("Import visible dans ce navigateur ; sauvegarde locale inaccessible.")
            jobs, _, _ = account_opportunities(request)
            return (updated, gr.Dropdown(choices=offer_choices(jobs, updated), value=None),
                    render_tracking(updated, jobs), message)

        tracking_import.click(
            restore_tracking, inputs=[tracking_backup, internship_tracking],
            outputs=tracking_outputs,
        )

        profile_editor = [profile_name, profile_source, profile_overview, profile_experience,
                          profile_strengths, profile_roles, profile_locations, profile_contracts,
                          profile_start, profile_start_month, profile_end_month, profile_constraints]

        def lines(values: object) -> str:
            return "\n".join(str(item) for item in values) if isinstance(values, list) else ""

        def items(value: str) -> list[str]:
            return [item.strip() for item in value.replace(",", "\n").splitlines() if item.strip()][:12]

        def editor_values(record: dict | None):
            record = record or {}
            return (record.get("name", ""), record.get("source_text", ""), record.get("overview", ""),
                    lines(record.get("experience")), lines(record.get("strengths")),
                    lines(record.get("target_roles")), lines(record.get("locations")),
                    lines(record.get("contracts")), record.get("start_window", ""),
                    record.get("start_month", ""), record.get("end_month", ""),
                    lines(record.get("constraints")))

        def choose_profile(key: str, catalog: dict):
            record = selected_profile(catalog, key)
            return (*editor_values(record), render_profile_card(record) if record else "",
                    "Profil chargé. Modifie les champs puis enregistre si nécessaire." if record else "Crée un profil pour commencer.", "")

        profile_tab.select(
            lambda catalog: (gr.Dropdown(value=active_profile(catalog)[0]),
                             *editor_values(active_profile(catalog)[1]), None, "",
                             render_profile_card(active_profile(catalog)[1]) if active_profile(catalog)[1] else "",
                             "Modifie ton profil puis enregistre." if active_profile(catalog)[1]
                             else "Indique ton nom et ajoute un CV ou un résumé.", ""),
            inputs=[profiles_state],
            outputs=[profile_select, *profile_editor, profile_cv, profile_cv_text, profile_preview,
                     profile_status, profile_save_status],
        )
        profile_cv.upload(
            lambda file_path: _extract_upload(file_path),
            inputs=[profile_cv], outputs=[profile_status, profile_cv_text],
        )

        def _extract_upload(file_path: str | None):
            if not file_path:
                return "Aucun CV sélectionné.", ""
            try:
                text = extract_cv_text(file_path)
                return f"CV lu et supprimé du stockage temporaire ({Path(file_path).suffix.upper()}). Tu peux lancer l’analyse.", text
            except ProfileError as exc:
                return str(exc), ""
            finally:
                try:
                    Path(file_path).unlink(missing_ok=True)
                except (OSError, TypeError):
                    pass

        def catalog_updates(catalog: dict, key: str):
            choices = profile_choices(catalog)
            return (catalog, gr.Dropdown(choices=choices, value=key),
                    gr.Dropdown(choices=choices, value=key))

        def analyze_profile(key: str, name: str, source: str, cv_text: str,
                            catalog: dict, request: gr.Request):
            try:
                if len(source or "") > 30_000 or len(cv_text or "") > 30_000:
                    raise ProfileError("Le CV et le résumé dépassent 30 000 caractères.")
                combined = "\n\n".join(part for part in (source.strip(), cv_text) if part)
                if len(combined) > 30_000:
                    raise ProfileError("Le CV et le résumé dépassent 30 000 caractères.")
                with llm_user(username(request) if shared else "local"), generation_slot():
                    record = structure_candidate_profile(name, combined)
                updated, selected = save_profile(catalog, active_profile(catalog)[0], record)
                if shared:
                    save_user_data(username(request), "profiles", updated)
            except (ProfileError, CareerAgentError, GenerationLimitError) as exc:
                raise gr.Error(str(exc)) from exc
            return (*catalog_updates(updated, selected), *editor_values(record), None, "",
                    render_profile_card(record),
                    "Profil analysé et enregistré dans ton compte. Relis les informations extraites." if shared
                    else "Profil analysé et enregistré dans ce navigateur. Relis les informations extraites.",
                    render_profile_card(record), "", gr.Button(interactive=True),
                    gr.Column(visible=False))

        profile_analyze.click(
            analyze_profile,
            inputs=[profile_select, profile_name, profile_source, profile_cv_text, profiles_state],
            outputs=[profiles_state, profile_select, agent_profile_select, *profile_editor,
                     profile_cv, profile_cv_text, profile_preview, profile_status, agent_profile_card,
                     profile_save_status, agent_scan, agent_empty_state],
            time_limit=105, show_progress="minimal",
        )

        def save_profile_edits(key: str, catalog: dict, name: str, source: str, overview: str,
                               experience: str, strengths: str, roles: str, locations: str,
                               contracts: str, start: str, start_month: str, end_month: str,
                               constraints: str, request: gr.Request):
            record = {"name": name, "source_text": source, "overview": overview,
                      "experience": items(experience), "strengths": items(strengths),
                      "target_roles": items(roles), "locations": items(locations),
                      "contracts": items(contracts), "start_window": start.strip(),
                      "start_month": start_month.strip(), "end_month": end_month.strip(),
                      "constraints": items(constraints)}
            try:
                updated, selected = save_profile(catalog, active_profile(catalog)[0], record)
                if shared:
                    save_user_data(username(request), "profiles", updated)
            except ProfileError as exc:
                raise gr.Error(str(exc)) from exc
            return (*catalog_updates(updated, selected), render_profile_card(record),
                    "Modifications enregistrées dans ton compte." if shared else
                    "Modifications enregistrées dans ce navigateur.", render_profile_card(record),
                    gr.Button(interactive=True), gr.Column(visible=False))

        profile_save.click(
            save_profile_edits, inputs=[profile_select, profiles_state, *profile_editor],
            outputs=[profiles_state, profile_select, agent_profile_select,
                     profile_preview, profile_save_status, agent_profile_card,
                     agent_scan, agent_empty_state],
        )

        def delete_profile(key: str, catalog: dict, confirmed: bool, request: gr.Request):
            account = username(request) if shared else ""
            if not confirmed:
                raise gr.Error("Coche la confirmation avant de supprimer ton profil.")
            if mail_outreach.batch_active(account or "local"):
                raise gr.Error("Annule le lot de mails et attends la fin de l'envoi en cours avant de supprimer ton profil.")
            records = clean_catalog(catalog)
            selected = key if key in records else active_profile(records)[0]
            if not selected:
                raise gr.Error("Aucun profil enregistré à supprimer.")
            records.pop(selected, None)
            if shared:
                save_user_data(account, "profiles", records)
            from .private_downloads import remove_user_downloads
            remove_user_downloads(account or "local")
            if not shared:
                PROFILE_PATH.unlink(missing_ok=True)
            save_user_data(account or "local", "ai_cache", {})
            save_user_data(account or "local", "mail_contacts", {})
            save_user_data(account or "local", "mail_templates", {})
            empty = editor_values(None)
            return (records, gr.Dropdown(choices=profile_choices(records), value=None),
                    gr.Dropdown(choices=profile_choices(records), value=None), *empty, None, "",
                    "", "Profil supprimé. Le CV importé avait déjà été effacé après sa lecture.",
                    "", "", gr.Button(interactive=False), gr.Column(visible=True),
                    gr.Button(interactive=False), gr.Dropdown(choices=[], value=None), [],
                    "Ton profil a été supprimé.", "", cleared_pdf(),
                    gr.Button(interactive=False), gr.Column(visible=False))

        profile_delete.click(
            delete_profile,
            inputs=[profile_select, profiles_state, profile_delete_confirm],
            outputs=[profiles_state, profile_select, agent_profile_select, *profile_editor,
                     profile_cv, profile_cv_text, profile_preview, profile_save_status,
                     agent_profile_card, agent_briefs, agent_scan,
                     agent_empty_state, agent_letter_button, agent_offer, agent_selection,
                     agent_message, agent_letter, agent_pdf, agent_pdf_button, agent_workspace],
        )

        def hydrate_profiles(catalog: dict):
            records = clean_catalog(catalog)
            key, record = active_profile(records)
            return (gr.Dropdown(choices=profile_choices(records), value=key),
                    gr.Dropdown(choices=profile_choices(records), value=key),
                    *editor_values(record), render_profile_card(record) if record else "",
                    render_profile_card(record) if record else "",
                    gr.Button(interactive=bool(record)), gr.Column(visible=not bool(record)))

        hydration_event.then(
            hydrate_profiles, inputs=[profiles_state],
            outputs=[profile_select, agent_profile_select, *profile_editor,
                     profile_preview, agent_profile_card, agent_scan, agent_empty_state],
        )

        def update_linkedin_profile_card(profile_id: str, catalog: dict):
            return render_profile_card(selected_profile(catalog, profile_id))

        profiles_state.change(
            update_linkedin_profile_card, inputs=[agent_profile_select, profiles_state],
            outputs=[linkedin_profile_card], queue=False, show_progress="hidden",
        )
        agent_profile_select.change(
            update_linkedin_profile_card, inputs=[agent_profile_select, profiles_state],
            outputs=[linkedin_profile_card], queue=False, show_progress="hidden",
        )
        linkedin_tab.select(
            update_linkedin_profile_card, inputs=[agent_profile_select, profiles_state],
            outputs=[linkedin_profile_card], queue=False, show_progress="hidden",
        )

        if shared:
            def migrate_browser_data(previous_profiles: dict, previous_tracking: dict,
                                     previous_feedback: dict, previous_drafts: dict,
                                     request: gr.Request):
                account = username(request)
                values = {
                    "profiles": clean_catalog(previous_profiles),
                    "tracking": import_tracking(export_tracking(previous_tracking), {})[0],
                    "feedback": previous_feedback if isinstance(previous_feedback, dict) else {},
                    "drafts": previous_drafts if isinstance(previous_drafts, dict) else {},
                }
                merged = {}
                for kind, older in values.items():
                    current = load_user_data(account, kind)
                    merged[kind] = ({**current, **{key: value for key, value in older.items()
                                                  if key not in current}}
                                    if kind == "profiles" else {**older, **current})
                    save_user_data(account, kind, merged[kind])
                choices = profile_choices(clean_catalog(merged["profiles"]))
                key, _ = active_profile(merged["profiles"])
                return (merged["profiles"], merged["tracking"], merged["feedback"],
                        merged["drafts"], gr.Dropdown(choices=choices, value=key),
                        gr.Dropdown(choices=choices, value=key),
                        "Import terminé. Tes données sont enregistrées dans ton compte.")

            import_browser_data.click(
                migrate_browser_data,
                inputs=[old_profiles, old_tracking, old_feedback, old_drafts],
                outputs=[profiles_state, internship_tracking, internship_feedback,
                         agent_drafts, profile_select, agent_profile_select,
                         import_browser_message],
            ).then(hydrate_profiles, inputs=[profiles_state],
                   outputs=[profile_select, agent_profile_select, *profile_editor,
                            profile_preview, agent_profile_card, agent_scan,
                            agent_empty_state]).then(
                show_internships, inputs=internship_inputs, outputs=internship_outputs)

        def reset_agent_for_profile(key: str, catalog: dict):
            record = selected_profile(catalog, key)
            return (render_profile_card(record) if record else "", "",
                    gr.Dropdown(choices=[], value=None), [],
                    "Analyse en cours…" if record else "", "", cleared_pdf(),
                    gr.Button(interactive=bool(record)),
                    gr.Column(visible=not bool(record)), gr.Column(visible=bool(record)),
                    gr.Button(interactive=False))

        def analyze_career_matches(profile_id: str, catalog: dict, feedback: dict, tracking: dict,
                                   request: gr.Request):
            record = selected_profile(catalog, profile_id)
            if not record:
                return ("", gr.Dropdown(choices=[], value=None), [], "", "", cleared_pdf(),
                        gr.Column(visible=False), gr.Button(interactive=False))
            if not record.get("target_roles"):
                return ('<div class="agent-empty">Metier cible manquant dans ce profil.</div>',
                        gr.Dropdown(choices=[], value=None), [],
                        "Renseigne les metiers recherches dans Mon profil, puis relance l'analyse.", "",
                        cleared_pdf(), gr.Column(visible=False), gr.Button(interactive=False))
            _, profile, goals = profile_prompt(record)
            jobs, _, _ = account_opportunities(request)
            candidate_pool = rank_candidate_pool(jobs, {}, tracking, profile=record)
            if not candidate_pool:
                return (render_briefs([]), gr.Dropdown(choices=[], value=None), [],
                        "Aucune offre recente et non postulee dans les sources actuelles. Actualise les offres puis reessaie.",
                        "", cleared_pdf(), gr.Column(visible=False), gr.Button(interactive=False))
            try:
                account = username(request) if shared else "local"
                cache_key = hashlib.sha256(json.dumps(
                    {"cache_version": 1, "model": os.getenv("INTERNSHIPS_AI_MODEL", "gpt-4o"),
                     "profile": record, "goals": goals,
                     "jobs": [asdict(job) for job in candidate_pool[:6]]},
                    ensure_ascii=False, sort_keys=True, default=str,
                ).encode("utf-8")).hexdigest()
                cache = load_user_data(account, "ai_cache")
                cached = cache.get(cache_key) if isinstance(cache, dict) else None
                if (isinstance(cached, dict) and
                        datetime.now(timezone.utc).timestamp() - float(cached.get("saved_at", 0)) < 24 * 3600):
                    current_jobs = {job.url: job for job in candidate_pool}
                    briefs = [{"job": current_jobs[item["url"]],
                               "evidence_quality": item["evidence_quality"],
                               "brief": item["brief"], "candidate_record": record}
                              for item in cached.get("briefs", [])
                              if isinstance(item, dict) and item.get("url") in current_jobs]
                else:
                    with llm_user(account), generation_slot():
                        briefs = generate_briefs(candidate_pool, profile, goals, candidate_record=record)
                    cache[cache_key] = {
                        "saved_at": datetime.now(timezone.utc).timestamp(),
                        "briefs": [{"url": item["job"].url,
                                    "evidence_quality": item["evidence_quality"],
                                    "brief": item["brief"]} for item in briefs],
                    }
                    if len(cache) > 10:
                        cache = dict(sorted(cache.items(), key=lambda item: item[1].get("saved_at", 0))[-10:])
                    save_user_data(account, "ai_cache", cache)
            except (CareerAgentError, GenerationLimitError) as exc:
                return ('<div class="agent-empty">Analyse interrompue.</div>',
                        gr.Dropdown(choices=[], value=None), [], str(exc), "",
                        cleared_pdf(), gr.Column(visible=False), gr.Button(interactive=False))
            if not briefs:
                return (render_briefs([]), gr.Dropdown(choices=[], value=None), [],
                        "Les annonces classees ne sont plus accessibles. Actualise les offres puis reessaie.",
                        "", cleared_pdf(), gr.Column(visible=False), gr.Button(interactive=False))
            selected = [row["job"] for row in briefs]
            choices = [(f"{job.company} - {job.title[:75]}", job.url) for job in selected]
            return (render_briefs(briefs), gr.Dropdown(choices=choices, value=selected[0].url),
                    [asdict(job) for job in selected],
                    f"{len(selected)} offre(s) analysee(s). Choisis une offre pour preparer ta lettre.", "",
                    cleared_pdf(), gr.Column(visible=True), gr.Button(interactive=False))

        def linkedin_cached_pdf_path(file_path: str | None) -> Path:
            if not file_path:
                raise ProfileError("Importe le PDF LinkedIn de la personne à contacter.")
            path = Path(file_path).resolve(strict=True)
            cache_root = Path(linkedin_pdf.GRADIO_CACHE).resolve()
            try:
                path.relative_to(cache_root)
            except ValueError as exc:
                raise ProfileError("Le fichier PDF importé n’est plus disponible. Importe-le de nouveau.") from exc
            if not path.is_file() or path.suffix.casefold() != ".pdf":
                raise ProfileError("Sélectionne un fichier PDF valide.")
            return path

        def render_linkedin_file_row(path: Path) -> str:
            size = path.stat().st_size
            readable_size = (f"{size / 1_000_000:.1f} Mo" if size >= 1_000_000
                             else f"{max(1, round(size / 1_000))} Ko")
            return (
                '<div class="linkedin-file-chip">'
                '<span class="linkedin-pdf-icon" aria-hidden="true">PDF</span>'
                '<span class="linkedin-file-copy"><strong>' + html.escape(path.name) + '</strong>'
                '<small>' + readable_size + ' · fichier temporaire de cette session</small></span>'
                '</div>'
            )

        def empty_linkedin_result_updates():
            return ("", "", gr.Column(visible=False),
                    gr.Button(interactive=False), gr.Button(interactive=False))

        def load_linkedin_recipient(file_path: str | None):
            path = None
            try:
                path = linkedin_cached_pdf_path(file_path)
                if path.stat().st_size > 8_000_000:
                    raise ProfileError("Le PDF dépasse la taille maximale de 8 Mo.")
                recipient = extract_linkedin_recipient_profile(path.read_bytes())
                identified = str(recipient.get("full_name") or "") if recipient.get("name_confidence") == "high" else ""
                note = ("Profil analysé. Vérifie ou corrige le nom avant de générer les messages."
                        if identified else
                        "Profil analysé. Le nom reste incertain : laisse le champ vide pour une salutation sans prénom.")
                return (gr.update(visible=False), render_linkedin_file_row(path), gr.Row(visible=True),
                        gr.Textbox(value=identified, visible=True), gr.Row(visible=True), recipient, note,
                        *empty_linkedin_result_updates())
            except (ProfileError, OSError, ValueError) as exc:
                try:
                    if path and path.is_file():
                        return (gr.update(visible=False), render_linkedin_file_row(path), gr.Row(visible=True),
                                gr.Textbox(value="", visible=False), gr.Row(visible=False), {}, str(exc),
                                *empty_linkedin_result_updates())
                except (OSError, ValueError):
                    pass
                return (gr.update(visible=True), "", gr.Row(visible=False),
                        gr.Textbox(value="", visible=False), gr.Row(visible=False), {}, str(exc),
                        *empty_linkedin_result_updates())

        def clear_linkedin_recipient(file_path: str | None):
            try:
                path = linkedin_cached_pdf_path(file_path)
                path.unlink(missing_ok=True)
            except (ProfileError, OSError, ValueError):
                pass
            return (gr.File(value=None, visible=True), "", gr.Row(visible=False),
                    gr.Textbox(value="", visible=False), gr.Row(visible=False), {},
                    "Le PDF a été retiré. Tu peux en importer un autre.",
                    *empty_linkedin_result_updates())

        linkedin_pdf.upload(
            load_linkedin_recipient, inputs=[linkedin_pdf],
            outputs=[linkedin_pdf, linkedin_pdf_details, linkedin_uploaded_row,
                     linkedin_recipient_name, linkedin_identity_row, linkedin_recipient_state, linkedin_status,
                     linkedin_message, linkedin_followup, linkedin_result, linkedin_copy, linkedin_followup_copy],
            queue=False, show_progress="hidden",
        )
        linkedin_pdf_remove.click(
            clear_linkedin_recipient, inputs=[linkedin_pdf],
            outputs=[linkedin_pdf, linkedin_pdf_details, linkedin_uploaded_row,
                     linkedin_recipient_name, linkedin_identity_row, linkedin_recipient_state, linkedin_status,
                     linkedin_message, linkedin_followup, linkedin_result, linkedin_copy, linkedin_followup_copy],
            queue=False, show_progress="hidden",
        )

        def create_linkedin_message(recipient: dict, recipient_name: str, profile_id: str,
                                    catalog: dict, tone: str, objective: str,
                                    extra_context: str, language: str, message_type: str,
                                    request: gr.Request):
            try:
                record = selected_profile(catalog, profile_id)
                if not record:
                    raise CareerAgentError("Complète d’abord ton profil dans Mon profil.")
                if not isinstance(recipient, dict) or len(str(recipient.get("linkedin_pdf_text") or "")) < 80:
                    raise ProfileError("Importe le PDF LinkedIn de la personne à contacter.")
                name = str(record.get("name") or "").strip()
                complete_candidate_profile = candidate_profile_context(record)
                account = username(request) if shared else "local"
                with llm_user(account), generation_slot():
                    message, followup = generate_linkedin_messages(
                        recipient, complete_candidate_profile, name, tone, objective,
                        extra_context, language, message_type,
                        recipient_name_override=recipient_name,
                    )
                status = "Les deux brouillons sont prêts. Relis-les et adapte-les avant de les envoyer."
                return (message, followup, status, gr.Column(visible=True),
                        gr.Button(interactive=True), gr.Button(interactive=True))
            except (CareerAgentError, ProfileError, GenerationLimitError, TimeoutError) as exc:
                return (gr.skip(), gr.skip(), str(exc), gr.skip(), gr.skip(), gr.skip())
            except Exception as exc:
                status = f"La génération a échoué ({type(exc).__name__}). Vérifie la connexion puis réessaie."
                return (gr.skip(), gr.skip(), status, gr.skip(), gr.skip(), gr.skip())

        linkedin_generate.click(
            create_linkedin_message,
            inputs=[linkedin_recipient_state, linkedin_recipient_name, agent_profile_select,
                    profiles_state, linkedin_tone, linkedin_objective, linkedin_context,
                    linkedin_language, linkedin_type],
            outputs=[linkedin_message, linkedin_followup, linkedin_status,
                     linkedin_result, linkedin_copy, linkedin_followup_copy],
            time_limit=105, show_progress="minimal",
        )

        def mail_owner(request: gr.Request) -> str:
            return username(request) if shared else "local"

        def mail_choices(records: dict):
            return [(f"{item.get('name') or 'Identité à compléter'} · {item.get('company') or 'Entreprise à compléter'}", key)
                    for key, item in records.items()]

        def mail_filter_values(company="Toutes", desk="Toutes", location="Toutes", source="Toutes",
                               verification="Toutes", outreach="Toutes"):
            return {"company": company or "Toutes", "desk": desk or "Toutes",
                    "location": location or "Toutes", "source": source or "Toutes",
                    "verification": verification or "Toutes", "outreach": outreach or "Toutes"}

        def mail_summary(account: str, filter_text: str = "", filters: dict | None = None):
            rows, counts = mail_outreach.dashboard(account, filter_text or "", filters)
            plural = {"contact": "contacts", "envoi": "envois", "r\u00e9ponse": "r\u00e9ponses", "erreur": "erreurs",
                      "relance": "relances", "\u00e0 v\u00e9rifier": "\u00e0 v\u00e9rifier", "profil v\u00e9rifi\u00e9": "profils v\u00e9rifi\u00e9s",
                      "sans adresse": "sans adresse", "adresse suppos\u00e9e": "adresses suppos\u00e9es",
                      "adresse publi\u00e9e": "adresses publi\u00e9es", "adresse v\u00e9rifi\u00e9e": "adresses v\u00e9rifi\u00e9es",
                      "non contact\u00e9": "non contact\u00e9s"}
            chips = "".join(f'<span class="mail-counter"><strong>{value}</strong> {html.escape(label if value == 1 else plural.get(label, label))}</span>'
                            for label, value in counts.items())
            mobile = "".join(
                '<article class="mail-mobile-item"><strong>' + html.escape(str(row[0])) + '</strong>'
                '<span>' + html.escape(str(row[1]) + ' · ' + str(row[2])) + '</span>'
                '<span>' + html.escape(str(row[3] or "Lieu non renseign\u00e9") + ' · ' + str(row[4] or "Desk \u00e0 pr\u00e9ciser")) + '</span>'
                '<span>' + html.escape(str(row[8] or "Adresse absente") + ' · ' + str(row[6] or "\u00c0 v\u00e9rifier")) + '</span>'
                '<small>' + html.escape(str(row[10]) + ' · Envoi : ' + str(row[11] or "—") +
                ' · Relance : ' + str(row[12] or "—")) + '</small></article>' for row in rows)
            return rows, f'<div class="mail-counters">{chips}</div>', mobile
        def cached_mail_pdf(file_path: str, component: gr.File) -> tuple[str, bytes]:
            if not file_path:
                raise ValueError("Sélectionne un PDF.")
            path = Path(file_path).resolve(strict=True)
            try:
                path.relative_to(Path(component.GRADIO_CACHE).resolve())
            except ValueError as exc:
                raise ValueError("Le PDF doit être importé depuis cette session.") from exc
            if path.suffix.casefold() != ".pdf" or path.stat().st_size > 8_000_000:
                raise ValueError("Importe un PDF de 8 Mo maximum.")
            data = path.read_bytes()
            if not data.startswith(b"%PDF-"):
                raise ValueError("Le fichier importé n'est pas un PDF valide.")
            return path.name, data

        def refresh_mail(filter_text: str, company: str, desk: str, location: str, source: str,
                         verification: str, outreach: str, request: gr.Request):
            account = mail_owner(request)
            records = load_user_data(account, "mail_contacts")
            filters = mail_filter_values(company, desk, location, source, verification, outreach)
            rows, counts, mobile = mail_summary(account, filter_text, filters)
            available = [(f"{item.get('name')} · {item.get('email')}", key)
                         for key, item in records.items() if item.get("delivery") == "brouillon"
                         and not mail_outreach.contact_blocker(item)]
            return (gr.Dropdown(choices=mail_choices(records)), gr.CheckboxGroup(choices=available),
                    gr.Dataframe(value=rows, visible=bool(rows)), counts, gr.Column(visible=bool(available)),
                    gr.Dropdown(choices=mail_choices(records)), mobile)

        def initialize_mail(filter_text: str, company: str, desk: str, location: str, source: str,
                            verification: str, outreach: str, request: gr.Request):
            account = mail_owner(request)
            _, tally = mail_outreach.import_seed_contacts(account)
            result = refresh_mail(filter_text, company, desk, location, source, verification, outreach, request)
            summary = (f"Répertoire Paris : {tally['read']} lignes lues, {tally['created']} créées, "
                       f"{tally['matched']} rapprochées, {tally['conflicts']} conflits, {tally['rejected']} rejetées. "
                       "Import sans adresse e-mail, génération, brouillon ni envoi. "
                       "Les postes et contrats restent à vérifier.")
            if tally["reasons"]:
                summary += " Détail : " + " · ".join(tally["reasons"][:5])
            return (*result, summary)

        mail_filters = [mail_company_filter, mail_desk_filter, mail_location_filter,
                        mail_source_filter, mail_verification_filter, mail_outreach_filter]
        mail_filter_inputs = [mail_filter, *mail_filters]
        mail_tab.select(initialize_mail, inputs=mail_filter_inputs,
                        outputs=[mail_contact, mail_batch, mail_table, mail_counts, mail_batch_card,
                                 mail_detail_select, mail_mobile_cards, mail_seed_status], queue=False)
        mail_refresh.click(refresh_mail, inputs=mail_filter_inputs,
                           outputs=[mail_contact, mail_batch, mail_table, mail_counts, mail_batch_card,
                                    mail_detail_select, mail_mobile_cards], queue=False)
        mail_filter.change(refresh_mail, inputs=mail_filter_inputs,
                           outputs=[mail_contact, mail_batch, mail_table, mail_counts, mail_batch_card,
                                    mail_detail_select, mail_mobile_cards], queue=False)
        for mail_filter_component in mail_filters:
            mail_filter_component.change(refresh_mail, inputs=mail_filter_inputs,
                                         outputs=[mail_contact, mail_batch, mail_table, mail_counts, mail_batch_card,
                                                  mail_detail_select, mail_mobile_cards], queue=False)

        def refresh_mail_stats(filter_text: str, company: str, desk: str, location: str, source: str,
                               verification: str, outreach: str, request: gr.Request):
            filters = mail_filter_values(company, desk, location, source, verification, outreach)
            rows, counts, mobile = mail_summary(mail_owner(request), filter_text, filters)
            return gr.Dataframe(value=rows, visible=bool(rows)), counts, mobile

        mail_timer.tick(refresh_mail_stats, inputs=mail_filter_inputs,
                        outputs=[mail_table, mail_counts, mail_mobile_cards],
                        queue=False, show_progress="hidden")
        def import_mail_pdfs(paths: list[str] | None, profile_id: str, catalog: dict,
                             filter_text: str, company: str, desk: str, location: str, source: str,
                             verification: str, outreach: str, request: gr.Request):
            record = selected_profile(catalog, profile_id)
            if not record:
                return gr.skip(), gr.skip(), gr.skip(), gr.skip(), gr.skip(), gr.skip(), gr.skip(), "Complète d'abord Mon profil."
            try:
                files = [cached_mail_pdf(path, mail_pdf) for path in (paths or [])[:20]]
                if not files:
                    raise ValueError("Ajoute au moins un profil LinkedIn PDF.")
                records, notices = mail_outreach.import_contacts(mail_owner(request), files, record)
                filters = mail_filter_values(company, desk, location, source, verification, outreach)
                rows, counts, mobile = mail_summary(mail_owner(request), filter_text, filters)
                available = [(f"{item.get('name')} · {item.get('email')}", key)
                             for key, item in records.items() if item.get("delivery") == "brouillon"
                             and not mail_outreach.contact_blocker(item)]
                return (gr.Dropdown(choices=mail_choices(records), value=next(reversed(records), None)),
                        gr.CheckboxGroup(choices=available), gr.Dataframe(value=rows, visible=bool(rows)), counts,
                        gr.Column(visible=bool(available)), gr.Dropdown(choices=mail_choices(records)),
                        mobile, "\n\n".join(notices))
            except (ValueError, OSError, ProfileError) as exc:
                return gr.skip(), gr.skip(), gr.skip(), gr.skip(), gr.skip(), gr.skip(), gr.skip(), str(exc)

        mail_import_button.click(import_mail_pdfs,
                                 inputs=[mail_pdf, agent_profile_select, profiles_state, *mail_filter_inputs],
                                 outputs=[mail_contact, mail_batch, mail_table, mail_counts, mail_batch_card,
                                          mail_detail_select, mail_mobile_cards, mail_import_status], time_limit=60)

        def select_mail_contact(key: str, request: gr.Request):
            item = load_user_data(mail_owner(request), "mail_contacts").get(key, {})
            return (gr.Column(visible=bool(item)), item.get("name", ""), item.get("role", ""), item.get("company", ""),
                    item.get("location", ""), item.get("desk", ""), item.get("external_id", ""),
                    item.get("source_type", ""), item.get("source_url", ""), item.get("research_date", ""),
                    item.get("last_verified_at", ""), item.get("verification_status", "\u00c0 v\u00e9rifier"),
                    item.get("contract_type", "Non confirm\u00e9"), item.get("outreach_status", "Non contact\u00e9"),
                    item.get("source_notes", ""), item.get("linkedin_url", ""), item.get("template") or None,
                    item.get("email", ""), item.get("email_status", "non_renseigne"),
                    (mail_outreach.contact_blocker(item) or f"Adresse {item.get('address_status', 'inconnue')} · {item.get('relevance', '')}"),
                    item.get("experiences", ""), item.get("education", ""), item.get("language", "Fran\u00e7ais"),
                    str(item.get("followup_days", 14)), bool(item.get("auto_followup", False)),
                    item.get("subject", ""), item.get("body", ""), item.get("followup_subject", ""),
                    item.get("followup_body", ""), item.get("conversation", "Non contact\u00e9"), item.get("notes", ""))
        mail_contact.change(select_mail_contact, inputs=[mail_contact],
                            outputs=[mail_editor_card, mail_name, mail_role, mail_company, mail_location, mail_desk,
                                     mail_external_id, mail_source_type, mail_source_url, mail_research_date,
                                     mail_last_verified, mail_verification_status, mail_contract_status,
                                     mail_outreach_status, mail_source_notes, mail_linkedin, mail_template, mail_email,
                                     mail_email_status, mail_address_note, mail_experiences, mail_education, mail_language,
                                     mail_followup_days, mail_auto_followup, mail_subject, mail_body,
                                     mail_followup_subject, mail_followup_body, mail_conversation, mail_notes], queue=False)
        def show_mail_detail(key: str, request: gr.Request):
            item = load_user_data(mail_owner(request), "mail_contacts").get(key, {})
            if not item:
                return "", "Non contact\u00e9", "", gr.Column(visible=False)
            linkedin_url = str(item.get("linkedin_url") or "")
            source_url = str(item.get("source_url") or "")
            seed_source_url = str(item.get("seed_source_url") or "")
            linkedin_link = (f'<a href="{html.escape(linkedin_url, quote=True)}" target="_blank" rel="noopener">Profil individuel ↗</a>'
                             if mail_outreach._LINKEDIN.fullmatch(linkedin_url) else "Lien individuel non renseigné")
            source_link = (f'<a href="{html.escape(source_url, quote=True)}" target="_blank" rel="noopener">Ouvrir la source ↗</a>'
                           if source_url.startswith(("https://", "http://")) else "Source non renseignée")
            seed_source_link = (f'<a href="{html.escape(seed_source_url, quote=True)}" target="_blank" rel="noopener">Source du répertoire ↗</a>'
                                if seed_source_url.startswith(("https://", "http://")) and seed_source_url != source_url else "")
            detail = (f'<div class="mail-contact-detail"><strong>{html.escape(item.get("name") or "Identité à compléter")}</strong>'
                      f'<span>Identifiant : {html.escape(item.get("external_id") or "contact importé")}</span>'
                      f'<span>{html.escape(item.get("company") or "Employeur à vérifier")} · {html.escape(item.get("role") or "Poste à vérifier")}</span>'
                      f'<span>{html.escape(item.get("location") or "Lieu à confirmer")} · Desk : {html.escape(item.get("desk") or "à préciser")}</span>'
                      f'<span>Profil : {html.escape(item.get("verification_status") or "À vérifier")} · Contrat : {html.escape(item.get("contract_type") or "Non confirmé")}</span>'
                      f'<span>Source ({html.escape(item.get("source_type") or "type inconnu")}) : {source_link}</span>'
                      f'<span>{seed_source_link}</span>'
                      f'<span>Recherche : {html.escape(item.get("research_date") or "date inconnue")} · Vérification réelle : {html.escape(item.get("last_verified_at") or "non effectuée")}</span>'
                      f'<span>{linkedin_link}</span><span>Adresse : {html.escape(item.get("email_status") or "non renseignée")}</span>'
                      f'<p>{html.escape(item.get("source_notes") or "Aucune note d’origine.")}</p></div>')
            return detail, item.get("conversation", "Non contacté"), item.get("notes", ""), gr.Column(visible=True)
        mail_detail_select.change(show_mail_detail, inputs=[mail_detail_select],
                                  outputs=[mail_detail, mail_conversation, mail_notes, mail_status_editor], queue=False)

        def select_mail_row(filter_text: str, company: str, desk: str, location: str, source: str,
                            verification: str, outreach: str, evt: gr.SelectData, request: gr.Request):
            account = mail_owner(request)
            records = load_user_data(account, "mail_contacts")
            filters = mail_filter_values(company, desk, location, source, verification, outreach)
            query = (filter_text or "").casefold()
            ordered = sorted(records.items(), key=lambda pair: (str(pair[1].get("company") or "").casefold(),
                             str(pair[1].get("name") or "").casefold(), str(pair[1].get("external_id") or pair[0])))
            keys = []
            conversation_states = {"\u00c0 contacter", "En attente", "R\u00e9ponse", "Refus", "Erreur d\u00e9finitive"}
            for key, item in ordered:
                if query and query not in " ".join(str(v) for v in item.values()).casefold():
                    continue
                values = {"company": item.get("company", ""), "desk": item.get("desk", ""),
                          "location": item.get("location", ""), "source": item.get("source_type") or item.get("seed_source_type", ""),
                          "verification": item.get("verification_status", ""),
                          "outreach": item.get("outreach_status", item.get("conversation", ""))}
                matches = all(not value or value == "Toutes" or value.casefold() == str(
                    item.get("conversation", "") if field == "outreach" and value in conversation_states
                    else values.get(field) or "").casefold() for field, value in filters.items())
                if matches:
                    keys.append(key)
            index = evt.index[0] if isinstance(evt.index, (tuple, list)) else evt.index
            return keys[index] if isinstance(index, int) and 0 <= index < len(keys) else None
        mail_table.select(select_mail_row, inputs=mail_filter_inputs, outputs=[mail_detail_select], queue=False)

        def export_mail_contacts(request: gr.Request):
            account = mail_owner(request)
            records = load_user_data(account, "mail_contacts")
            fields = ["external_id", "first_name", "last_name", "name", "company", "role", "desk",
                      "location", "linkedin_url", "source_type", "source_url", "source_notes", "research_date",
                      "seed_external_id", "seed_source_type", "seed_source_url", "seed_source_notes", "seed_research_date",
                      "last_verified_at", "verification_status", "contract_type", "outreach_status", "email",
                      "email_status", "address_status", "template", "conversation", "sent_at", "followup_due", "notes"]
            directory = Path(tempfile.mkdtemp(prefix="internships-mail-export-"))
            path = directory / "contacts_marches_paris.csv"
            with path.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=fields, delimiter=";", extrasaction="ignore")
                writer.writeheader()
                for item in records.values():
                    writer.writerow({field: item.get(field, "") for field in fields})
            if shared:
                register_download(account, str(path))
                return gr.File(value=None, visible=False), (
                    '<a class="mail-export-link" href="/private-download">Télécharger l’export CSV Excel-compatible</a>')
            return gr.File(value=str(path), visible=True), ""

        mail_export_button.click(export_mail_contacts, outputs=[mail_export_file, mail_export_link], queue=False)

        def propose_mail_address(name: str, template_name: str, request: gr.Request):
            entry = mail_outreach.templates_for(mail_owner(request)).get(template_name)
            address, warning = mail_outreach.propose_address(name, entry)
            source = (f" · <a href='{html.escape(entry['source_url'], quote=True)}' target='_blank'>Exemple public</a>"
                      f" ({entry['verified_on']})" if entry and entry.get("documented") else "")
            return address, f"{html.escape(warning)}{source}"

        mail_template.input(propose_mail_address, inputs=[mail_name, mail_template],
                            outputs=[mail_email, mail_address_note], queue=False)

        mail_editor_fields = [mail_name, mail_role, mail_company, mail_location, mail_desk, mail_source_type,
                              mail_source_url, mail_research_date, mail_last_verified, mail_verification_status,
                              mail_contract_status, mail_outreach_status, mail_source_notes, mail_linkedin,
                              mail_template, mail_email, mail_email_status, mail_experiences, mail_education,
                              mail_language, mail_followup_days, mail_auto_followup, mail_subject, mail_body,
                              mail_followup_subject, mail_followup_body]

        def save_mail_editor(key: str, name: str, role: str, company: str, location: str, desk: str,
                             source_type: str, source_url: str, research_date: str, last_verified_at: str,
                             verification_status: str, contract_type: str, outreach_status: str,
                             source_notes: str, linkedin_url: str, template: str, email: str, email_status: str,
                             experiences: str, education: str, language: str, followup_days: str,
                             auto_followup: bool, subject: str, body: str, followup_subject: str,
                             followup_body: str, request: gr.Request):
            fields = dict(zip(("name", "role", "company", "location", "desk", "source_type", "source_url",
                               "research_date", "last_verified_at", "verification_status", "contract_type",
                               "outreach_status", "source_notes", "linkedin_url", "template", "email",
                               "email_status", "experiences", "education", "language", "followup_days",
                               "auto_followup", "subject", "body", "followup_subject", "followup_body"),
                              (name, role, company, location, desk, source_type, source_url, research_date,
                               last_verified_at, verification_status, contract_type, outreach_status, source_notes,
                               linkedin_url, template, email, email_status, experiences, education, language,
                               followup_days, auto_followup, subject, body, followup_subject, followup_body)))
            try:
                mail_outreach.update_contact(mail_owner(request), key, fields)
                return "Fiche enregistrée. Les sources et données de suivi sont conservées.", False, ""
            except ValueError as exc:
                return str(exc), False, ""

        mail_save.click(save_mail_editor, inputs=[mail_contact, *mail_editor_fields],
                        outputs=[mail_editor_status, mail_confirm, mail_review_state]).then(
            refresh_mail, inputs=mail_filter_inputs,
            outputs=[mail_contact, mail_batch, mail_table, mail_counts, mail_batch_card, mail_detail_select,
                     mail_mobile_cards], queue=False)
        def generate_mail(key: str, profile_id: str, catalog: dict, language: str, cv_path: str | None,
                          request: gr.Request):
            try:
                candidate = selected_profile(catalog, profile_id)
                if not candidate or not key:
                    raise ValueError("Choisis ton profil et un contact importé.")
                account = mail_owner(request)
                contact = load_user_data(account, "mail_contacts").get(key)
                if not contact:
                    raise ValueError("Contact introuvable.")
                if cv_path:
                    cached_mail_pdf(cv_path, mail_cv)
                with llm_user(account), generation_slot():
                    subject, body, followup = mail_outreach.draft_mail(contact, candidate, language,
                                                                       cv_attached=bool(cv_path))
                mail_outreach.update_contact(account, key, {"subject": subject, "body": body,
                                                            "followup_subject": "Re: " + subject,
                                                            "followup_body": followup, "language": language})
                return subject, body, "Re: " + subject, followup, "Brouillons générés et enregistrés. Relis-les avant l'envoi.", False, ""
            except (ValueError, OSError, CareerAgentError, GenerationLimitError) as exc:
                return gr.skip(), gr.skip(), gr.skip(), gr.skip(), str(exc), False, ""

        mail_generate.click(generate_mail, inputs=[mail_contact, agent_profile_select,
                                                   profiles_state, mail_language, mail_cv],
                            outputs=[mail_subject, mail_body, mail_followup_subject,
                                     mail_followup_body, mail_editor_status, mail_confirm, mail_review_state],
                            time_limit=105, show_progress="minimal").then(
            refresh_mail, inputs=mail_filter_inputs,
            outputs=[mail_contact, mail_batch, mail_table, mail_counts, mail_batch_card, mail_detail_select,
                     mail_mobile_cards], queue=False)

        def save_mail_format(institution, domain, pattern, aliases, source, request: gr.Request):
            try:
                mail_outreach.save_template(mail_owner(request), institution, domain, pattern,
                                            aliases or "", source or "")
                return (gr.Dropdown(choices=list(mail_outreach.templates_for(mail_owner(request)))),
                        "Format enregistré pour ton compte. L'exemple public reste non vérifié jusqu'à revue.")
            except ValueError as exc:
                return gr.skip(), str(exc)

        template_save.click(save_mail_format,
                            inputs=[template_institution, template_domain, template_pattern,
                                    template_aliases, template_source],
                            outputs=[mail_template, template_status])

        def review_mail_batch(keys: list[str] | None, cv_path: str | None, request: gr.Request):
            records = load_user_data(mail_owner(request), "mail_contacts")
            try:
                cv = cached_mail_pdf(cv_path, mail_cv) if cv_path else None
            except (ValueError, OSError) as exc:
                return f'<p>{html.escape(str(exc))}</p>', "", False, gr.Button(interactive=False)
            cards = []
            for key in (keys or [])[:10]:
                item = records.get(key)
                if not item:
                    continue
                cards.append('<article class="mail-review-item"><strong>' +
                             html.escape(item.get("name") or "Identité incomplète") +
                             '</strong><span>Adresse supposée : ' + html.escape(item.get("email") or "manquante") +
                             '</span><span>Objet : ' + html.escape(item.get("subject") or "manquant") +
                             '</span><p>' + html.escape(item.get("body") or "Message manquant").replace("\n", "<br>") +
                             '</p><span>CV joint : ' + html.escape(cv[0] if cv else "aucun") + '</span></article>')
            token = mail_outreach.review_signature(records, keys or [], cv) if cards else ""
            return ("".join(cards) or '<p>Choisis des contacts avec une adresse pour revoir le lot.</p>',
                    token, False, gr.Button(interactive=bool(cards)))

        mail_batch.change(review_mail_batch, inputs=[mail_batch, mail_cv],
                          outputs=[mail_batch_review, mail_review_state, mail_confirm, mail_send], queue=False)
        mail_cv.change(review_mail_batch, inputs=[mail_batch, mail_cv],
                       outputs=[mail_batch_review, mail_review_state, mail_confirm, mail_send], queue=False)
        for field in (mail_name, mail_email, mail_subject, mail_body, mail_followup_subject, mail_followup_body):
            field.input(lambda: ("", False), outputs=[mail_review_state, mail_confirm], queue=False)
            field.change(lambda: ("", False), outputs=[mail_review_state, mail_confirm], queue=False)

        def mail_batch_actions(request: gr.Request):
            account = mail_owner(request)
            active = mail_outreach.batch_active(account)
            paused = mail_outreach.batch_paused(account)
            return (gr.Button(visible=active and not paused),
                    gr.Button(visible=active and paused), gr.Button(visible=active))

        def send_mail_batch(keys: list[str] | None, cv_path: str | None,
                            confirmed: bool, review_token: str, selected_key: str,
                            name: str, email: str, subject: str, body: str, request: gr.Request):
            try:
                if selected_key in (keys or []):
                    saved = load_user_data(mail_owner(request), "mail_contacts").get(selected_key, {})
                    if any(str(saved.get(field) or "").strip() != str(value or "").strip()
                           for field, value in (("name", name), ("email", email),
                                                ("subject", subject), ("body", body))):
                        raise ValueError("Des modifications ne sont pas enregistrées. Enregistre le contact, puis relis le lot.")
                cv = cached_mail_pdf(cv_path, mail_cv) if cv_path else None
                count = mail_outreach.approve_and_start(mail_owner(request), keys or [], cv,
                                                        confirmed=confirmed, review_token=review_token)
                return (f"Lot de {count} contact(s) lancé. Le suivi se met à jour automatiquement.", False,
                        *mail_batch_actions(request), gr.Button(interactive=False))
            except (ValueError, OSError) as exc:
                return str(exc), False, *mail_batch_actions(request), gr.Button(interactive=True)

        mail_send.click(send_mail_batch, inputs=[mail_batch, mail_cv, mail_confirm, mail_review_state,
                                                 mail_contact, mail_name, mail_email, mail_subject, mail_body],
                        outputs=[mail_batch_status, mail_confirm, mail_pause, mail_resume, mail_cancel,
                                 mail_send], time_limit=30)

        def pause_mail_batch(request: gr.Request):
            mail_outreach.pause_batch(mail_owner(request))
            return "Lot mis en pause après l'envoi éventuellement déjà commencé.", *mail_batch_actions(request)

        mail_pause.click(pause_mail_batch, outputs=[mail_batch_status, mail_pause, mail_resume, mail_cancel], queue=False)

        def resume_mail_batch(request: gr.Request):
            mail_outreach.resume_batch(mail_owner(request))
            return "Envoi du lot repris.", *mail_batch_actions(request)

        mail_resume.click(resume_mail_batch, outputs=[mail_batch_status, mail_pause, mail_resume, mail_cancel], queue=False)

        def cancel_mail_batch(request: gr.Request):
            mail_outreach.cancel_batch(mail_owner(request))
            return ("Arrêt demandé. Un envoi déjà commencé peut encore se terminer ; les suivants sont annulés.",
                    *mail_batch_actions(request))

        mail_cancel.click(cancel_mail_batch, outputs=[mail_batch_status, mail_pause, mail_resume, mail_cancel], queue=False)
        mail_timer.tick(mail_batch_actions, outputs=[mail_pause, mail_resume, mail_cancel],
                        queue=False, show_progress="hidden")

        def save_mail_status(key: str, conversation: str, notes: str, request: gr.Request):
            try:
                mail_outreach.update_contact(mail_owner(request), key,
                                             {"conversation": conversation, "notes": notes})
                return "Suivi enregistré."
            except ValueError as exc:
                return str(exc)

        mail_status_save.click(save_mail_status, inputs=[mail_detail_select, mail_conversation, mail_notes],
                               outputs=[mail_status_feedback]).then(
            refresh_mail, inputs=mail_filter_inputs,
            outputs=[mail_contact, mail_batch, mail_table, mail_counts, mail_batch_card, mail_detail_select,
                     mail_mobile_cards], queue=False)

        def update_mail_profile_card(profile_id: str, catalog: dict):
            return render_profile_card(selected_profile(catalog, profile_id))

        mail_tab.select(update_mail_profile_card, inputs=[agent_profile_select, profiles_state],
                        outputs=[mail_profile_card], queue=False)

        agent_scan.click(
            analyze_career_matches,
            inputs=[agent_profile_select, profiles_state, internship_feedback, internship_tracking],
            outputs=[agent_briefs, agent_offer, agent_selection, agent_message, agent_letter, agent_pdf,
                     agent_workspace, agent_pdf_button],
            time_limit=105, show_progress="minimal",
        )

        def select_recommendation(rows: list[dict], evt: gr.EventData):
            url = str(getattr(evt, "url", "") or "")
            choices = [(f"{row.get('company', '')} - {str(row.get('title', ''))[:75]}", row["url"])
                       for row in (rows or []) if isinstance(row, dict) and row.get("url")]
            valid_url = url if any(choice[1] == url for choice in choices) else None
            return gr.Dropdown(choices=choices, value=valid_url), gr.Column(visible=bool(valid_url))

        agent_profile_select.input(
            reset_agent_for_profile, inputs=[agent_profile_select, profiles_state],
            outputs=[agent_profile_card, agent_briefs, agent_offer, agent_selection,
                     agent_message, agent_letter, agent_pdf, agent_scan,
                     agent_empty_state, agent_workspace, agent_pdf_button],
        ).then(
            analyze_career_matches,
            inputs=[agent_profile_select, profiles_state, internship_feedback, internship_tracking],
            outputs=[agent_briefs, agent_offer, agent_selection, agent_message, agent_letter,
                     agent_pdf, agent_workspace, agent_pdf_button],
            time_limit=105, show_progress="minimal",
        )
        agent_create_profile.click(lambda: gr.Tabs(selected="profil"), outputs=[primary_tabs])

        def prepare_career_letter(url: str, rows: list[dict], profile_id: str,
                                  catalog: dict, language: str, current_letter: str,
                                  request: gr.Request):
            row = next((item for item in (rows or []) if isinstance(item, dict) and item.get("url") == url), None)
            if row is None:
                message = "Cette offre n’a pas été reliée à la sélection. Choisis-la dans le menu puis réessaie."
                return gr.skip(), message, "", cleared_pdf(), gr.Button(interactive=bool((current_letter or "").strip()))
            record = selected_profile(catalog, profile_id)
            if not record:
                return gr.skip(), "Crée ton profil dans Mon profil avant de rédiger une lettre.", "", cleared_pdf(), gr.Button(interactive=bool((current_letter or "").strip()))
            try:
                name, profile, goals = profile_prompt(record)
                job = Opportunity(**row)
                with llm_user(username(request) if shared else "local"), generation_slot():
                    letter = generate_letter(job, profile, name, goals, language)
                if not letter or not letter.strip():
                    raise CareerAgentError("Le modèle a renvoyé une lettre vide. Réessaie dans un instant.")
                checks = "\n".join(f"- {item}" for item in letter_review_flags(job, letter, record))
            except Exception as exc:
                if isinstance(exc, (CareerAgentError, GenerationLimitError)):
                    message = str(exc)
                elif isinstance(exc, TimeoutError):
                    message = "La rédaction a dépassé le délai maximal. Réessaie dans un instant."
                else:
                    message = (f"La rédaction a échoué ({type(exc).__name__}). Tes modifications sont conservées ; "
                               "vérifie la connexion au modèle puis réessaie.")
                return gr.skip(), message, "", cleared_pdf(), gr.Button(interactive=bool((current_letter or "").strip()))
            return (letter, "Brouillon prêt. Relis et ajuste les faits avant l’envoi.",
                    (f"### À vérifier avant l’envoi\n\n{checks}" if checks else ""),
                    cleared_pdf(), gr.Button(interactive=True))

        def start_letter_generation():
            return ("Rédaction en cours…", gr.Button(value="Rédaction en cours…", interactive=False))

        def finish_letter_generation():
            return gr.Button(value="Préparer la lettre", interactive=True)

        agent_briefs.click(
            select_recommendation, inputs=[agent_selection], outputs=[agent_offer, agent_workspace],
        ).then(
            start_letter_generation, outputs=[agent_message, agent_letter_button], show_progress="hidden",
        ).then(
            prepare_career_letter,
            inputs=[agent_offer, agent_selection, agent_profile_select, profiles_state, agent_language,
                    agent_letter],
            outputs=[agent_letter, agent_message, agent_review, agent_pdf, agent_pdf_button],
            time_limit=105, show_progress="minimal",
        ).then(finish_letter_generation, outputs=[agent_letter_button], show_progress="hidden")

        agent_letter_button.click(
            start_letter_generation, outputs=[agent_message, agent_letter_button], show_progress="hidden",
        ).then(
            prepare_career_letter,
            inputs=[agent_offer, agent_selection, agent_profile_select, profiles_state, agent_language,
                    agent_letter],
            outputs=[agent_letter, agent_message, agent_review, agent_pdf, agent_pdf_button],
            time_limit=105, show_progress="minimal",
        ).then(
            finish_letter_generation, outputs=[agent_letter_button], show_progress="hidden",
        )

        def restore_agent_draft(url: str, drafts: dict, profile_id: str):
            letter = saved_letter(drafts, url, profile_id)
            if letter:
                return (letter, "Brouillon enregistré retrouvé. Tu peux le modifier ou le régénérer.", "",
                        gr.Button(interactive=bool(letter.strip())), cleared_pdf())
            return "", "Sélectionne cette offre puis prépare ta lettre.", "", gr.Button(interactive=False), cleared_pdf()

        agent_offer.input(
            restore_agent_draft, inputs=[agent_offer, agent_drafts, agent_profile_select],
            outputs=[agent_letter, agent_message, agent_review, agent_pdf_button, agent_pdf],
        )

        def update_export_state(letter: str):
            return gr.Button(interactive=bool((letter or "").strip())), cleared_pdf()

        agent_letter.input(update_export_state, inputs=[agent_letter], outputs=[agent_pdf_button, agent_pdf],
                           show_progress="hidden")

        def save_agent_draft(url: str, rows: list[dict], letter: str, drafts: dict,
                             profile_id: str, request: gr.Request):
            urls = {row.get("url") for row in (rows or []) if isinstance(row, dict)}
            try:
                updated = save_letter_draft(drafts, url, urls, letter, profile_id)
                if shared:
                    save_user_data(username(request), "drafts", updated)
            except CareerAgentError as exc:
                return drafts or {}, str(exc)
            return updated, ("Brouillon enregistré dans ton compte pour cette offre." if shared else
                             "Brouillon enregistré dans ce navigateur pour cette offre.")

        agent_save_draft.click(
            save_agent_draft, inputs=[agent_offer, agent_selection, agent_letter,
                                      agent_drafts, agent_profile_select],
            outputs=[agent_drafts, agent_message],
        )

        def download_career_letter(letter: str, url: str, rows: list[dict],
                                   profile_id: str, catalog: dict, language: str,
                                   request: gr.Request):
            row = next((item for item in (rows or []) if isinstance(item, dict) and item.get("url") == url), None)
            try:
                if row is None:
                    raise CareerAgentError("Sélectionne une offre avant l’export PDF.")
                record = selected_profile(catalog, profile_id) or {}
                path = export_letter_pdf(letter, str(row.get("company") or ""),
                                         candidate=str(record.get("name") or ""),
                                         job_title=str(row.get("title") or ""), language=language,
                                         candidate_record=record)
                register_download(username(request) if shared else "local", path)
                if shared:
                    return (f'<a class="private-pdf-download" href="/private-download" '
                            'rel="noopener">Télécharger le PDF · lien privé, valable 1 heure</a>',
                            "PDF prêt à télécharger.")
                return gr.File(value=path, visible=True), "PDF prêt à télécharger."
            except Exception as exc:
                message = str(exc) if isinstance(exc, CareerAgentError) else (
                    "La mise en page du PDF a échoué. Vérifie le texte de la lettre puis réessaie."
                )
                return cleared_pdf(), f"Export impossible : {message}"

        agent_pdf_button.click(
            download_career_letter, inputs=[agent_letter, agent_offer, agent_selection,
                                            agent_profile_select, profiles_state, agent_language],
            outputs=[agent_pdf, agent_message],
        )
        app_blocks.favicon_path = str(favicon_path)
        return app_blocks

