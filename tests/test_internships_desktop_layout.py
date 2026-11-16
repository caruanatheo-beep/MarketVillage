"""Check that the internship filter row stays readable on desktop widths."""

from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright


STYLES = Path(__file__).resolve().parents[1] / "Internships" / "internships_project" / "ui_styles.css"


@pytest.mark.parametrize("width,expected_columns", [
    (900, 3), (1024, 3), (1100, 3), (1101, 4), (1150, 4), (1199, 4), (1200, 5),
])
def test_desktop_quick_filters_use_readable_columns(width, expected_columns):
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": width, "height": 800})
        page.set_content(
            '<main id="internships-app"><section id="internship-search-panel">'
            '<div id="internship-quick-filters">'
            '<div>Contrat</div><div>Métier</div><div>Publication ou détection</div>'
            '<div>Début du contrat</div><div id="sort-filter">Trier par</div>'
            '</div></section></main>'
        )
        page.add_style_tag(path=str(STYLES))
        columns = page.locator("#internship-quick-filters").evaluate(
            "element => getComputedStyle(element).gridTemplateColumns.split(' ').length"
        )
        assert columns == expected_columns
        if 1101 <= width <= 1199:
            positions = page.locator("#internship-quick-filters > *").evaluate_all(
                "elements => elements.map(e => { const r=e.getBoundingClientRect(); "
                "return {left:r.left,right:r.right,top:r.top,bottom:r.bottom}; })"
            )
            for first, second in zip(positions, positions[1:]):
                assert first["bottom"] <= second["top"] or first["right"] <= second["left"], positions
            assert positions[-1]["top"] > positions[-2]["top"], positions
        browser.close()


def test_desktop_offer_cards_show_three_lines_for_long_titles():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.set_content(
            '<main id="internships-app"><article class="internship-card" style="width:300px">'
            '<a class="job-card-main"><p class="job-title" style="width:150px">Senior investment banking analyst internship '
            'in corporate finance and global markets for international clients</p></a></article></main>'
        )
        page.add_style_tag(path=str(STYLES))
        title = page.locator(".job-title")
        assert title.evaluate("element => getComputedStyle(element).webkitLineClamp") == "3"
        assert title.evaluate("element => getComputedStyle(element).maxHeight") == "54px"
        browser.close()


def test_offer_card_wraps_contract_deadline_and_tracking_tags_on_desktop():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.set_content(
            '<main id="internships-app"><article class="internship-card" style="width:320px">'
            '<a class="job-card-main"><span class="job-card-header">Company</span>'
            '<strong class="job-title">Stage Sales</strong>'
            '<span class="job-key-facts"><span>Paris</span><span>Septembre 2027</span></span>'
            '<span class="job-card-footer"><span class="job-card-tags">'
            '<span class="job-fact">Stage</span><span class="job-fact">Date limite : 30 juin 2027</span>'
            '<span class="job-fact">Vente institutionnelle</span><span class="job-badge tracked">À candidater</span>'
            '</span><span class="job-card-provenance">Publié le 15 nov. 2026</span></span></a>'
            '</article></main>'
        )
        page.add_style_tag(path=str(STYLES))
        tags = page.locator(".job-card-tags")
        positions = tags.locator(":scope > *").evaluate_all(
            "elements => elements.map(e => {const r=e.getBoundingClientRect();return {top:r.top,bottom:r.bottom};})"
        )
        assert positions[1]["top"] > positions[0]["top"], positions
        footer = page.locator(".job-card-footer")
        facts = page.locator(".job-key-facts")
        assert footer.bounding_box()["height"] > 24
        facts_box = facts.bounding_box()
        footer_box = footer.bounding_box()
        assert facts_box["y"] + facts_box["height"] < footer_box["y"]
        for index in range(4):
            assert tags.locator(":scope > *").nth(index).is_visible()
        browser.close()
