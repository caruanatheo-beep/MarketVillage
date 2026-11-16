"""Offers-only interface: no AI, profile, tracking, mail or upload callbacks."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import gradio as gr

from .internships import (_display_offer_date, load_opportunities, matching_opportunities,
                          opportunities_loading, render_opportunities)
from .internships_theme import SKEMA_EMBLEM


def show_offers(category, query, family, earliest, period, sort_by, page=1):
    # Visits and filters read the snapshot; only the scheduler performs collections.
    jobs, errors, updated = load_opportunities(refresh=False)
    options = dict(weekly=period == "weekly", daily=period == "daily", sort_by=sort_by)
    count = len(matching_opportunities(jobs, category, query, family, earliest, **options))
    pages = max(1, (count + 49) // 50)
    page = max(1, min(int(page), pages))
    return (
        render_opportunities(jobs, errors, updated, category, query, family, earliest,
                             refreshing=opportunities_loading(), page=page, **options),
        page, f"Page {page} / {pages}",
        gr.Button(interactive=page > 1), gr.Button(interactive=page < pages),
    )


def build_offers_app() -> gr.Blocks:
    with gr.Blocks(analytics_enabled=False, title="Offres · Marchés financiers") as app:
        with gr.Column(elem_id="internships-app"):
            gr.HTML(f'<div class="career-masthead"><div class="career-masthead-brand">'
                    f'<span class="skema-brand"><span class="skema-emblem"><img src="data:image/png;base64,{SKEMA_EMBLEM}" alt=""></span>'
                    '<span class="skema-wordmark"><strong>SKEMA</strong><small>BUSINESS SCHOOL</small></span></span></div>'
                    '<div>Stages · VIE · Graduate</div></div>', elem_id="career-masthead")
            gr.HTML('<header class="internship-hero"><div class="hero-copy">'
                    '<h1>Les opportunités de <em>marché</em></h1>'
                    '<p>Banques, sociétés de gestion et services titres.</p></div></header>')
            with gr.Column(elem_id="internship-search-panel"):
                with gr.Row(elem_id="internship-search-row"):
                    query = gr.Textbox(placeholder="Métier, entreprise ou ville…", label="Rechercher", show_label=False, container=False, scale=7)
                    reload_button = gr.Button("Recharger", scale=1)
                with gr.Row(elem_id="internship-quick-filters"):
                    with gr.Column(elem_id="internship-contract-field"):
                        gr.HTML('<span class="job-filter-label">Type de contrat</span>')
                        category = gr.Dropdown([("Tous les contrats", "Toutes"), ("Stages · Paris", "Stages Paris"),
                                                ("Stages · International", "Stages International"),
                                                ("VIE", "VIE"), ("Graduate", "Graduate")],
                                               value="Toutes", label="Type de contrat", show_label=False, container=False)
                    with gr.Column(elem_id="internship-family-field"):
                        gr.HTML('<span class="job-filter-label">Métier</span>')
                        family = gr.Dropdown(["Tous métiers", "Capital Markets", "Sales", "Trading / Structuring",
                                              "Asset Management", "Quant / Research", "Risk / Support"],
                                             value="Tous métiers", label="Métier", show_label=False, container=False)
                    with gr.Column(elem_id="internship-period-field"):
                        gr.HTML('<span class="job-filter-label">Publication ou détection</span>')
                        period = gr.Dropdown([("Toutes les dates", "all"), ("Aujourd’hui", "daily"),
                                              ("7 derniers jours", "weekly")], value="all", label="Publication ou détection", show_label=False, container=False)
                    now = datetime.now(timezone.utc)
                    months = [("Toutes dates", "Toutes dates")] + [
                        (_display_offer_date(f"{now.year + (now.month - 1 + n) // 12:04d}-{(now.month - 1 + n) % 12 + 1:02d}"),
                         f"{now.year + (now.month - 1 + n) // 12:04d}-{(now.month - 1 + n) % 12 + 1:02d}")
                        for n in range(24)]
                    with gr.Column(elem_id="internship-start-field"):
                        gr.HTML('<span class="job-filter-label">Début du contrat</span>')
                        earliest = gr.Dropdown(months, value="Toutes dates", label="Début à partir de", show_label=False, container=False)
                    with gr.Column(elem_id="internship-sort-field"):
                        gr.HTML('<span class="job-filter-label">Trier par</span>')
                        sort_by = gr.Dropdown([("Pertinence", "pertinence"), ("Plus récentes", "recent")],
                                              value="pertinence", label="Trier par", show_label=False, container=False)
            gr.Markdown("Collectes automatiques à **8 h, 13 h et 18 h**, heure de Paris. "
                        "« Recharger » affiche les dernières offres enregistrées.")
            board = gr.HTML(elem_id="internship-board")
            with gr.Row(elem_id="internship-pagination"):
                previous = gr.Button("Précédent")
                page_label = gr.Markdown("Page 1")
                next_button = gr.Button("Suivant")
            page = gr.State(1)
            gr.HTML('<footer class="career-credit"><a href="/confidentialite">Confidentialité</a></footer>')
        inputs = [category, query, family, earliest, period, sort_by]
        outputs = [board, page, page_label, previous, next_button]
        app.load(show_offers, inputs=inputs, outputs=outputs, api_visibility="private")
        reload_button.click(show_offers, inputs=inputs, outputs=outputs, api_visibility="private")
        query.input(show_offers, inputs=inputs, outputs=outputs, trigger_mode="always_last",
                    show_progress="hidden", api_visibility="private")
        for control in (category, family, earliest, period, sort_by):
            control.change(show_offers, inputs=inputs, outputs=outputs, api_visibility="private")

        def before(*args):
            return show_offers(*args[:-1], page=args[-1] - 1)

        def after(*args):
            return show_offers(*args[:-1], page=args[-1] + 1)

        previous.click(before, inputs=[*inputs, page], outputs=outputs, api_visibility="private")
        next_button.click(after, inputs=[*inputs, page], outputs=outputs, api_visibility="private")
        app.favicon_path = str(Path(__file__).parent / "assets" / "skema_emblem_2026.png")
    return app
