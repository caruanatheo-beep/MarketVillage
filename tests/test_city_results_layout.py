"""Render shipped City styles with synthetic, long mission results only."""

from pathlib import Path
import sys

import pytest

from playwright.sync_api import sync_playwright


CSS = (Path(__file__).resolve().parents[1] / "internships_project" /
       "city_assets" / "city.css").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            channel="msedge" if sys.platform == "win32" else None, headless=True
        )
        try:
            yield browser
        finally:
            browser.close()


@pytest.mark.parametrize("width,height", [(1366, 768), (1024, 768), (1920, 1080)])
@pytest.mark.parametrize("variant", ["code-results-window", "market-brief-window", ""])
def test_results_fit_workspace_and_scroll_without_losing_close_button(browser, width, height, variant):
    page = browser.new_page(viewport={"width": width, "height": height})
    page.set_content('''<main class="game-app">
      <section class="game-popup mission-results-window"
               role="dialog" aria-label="Résultat de mission">
        <div class="game-popup-heading"><div><strong>Résultat de mission</strong>
          <small>Contributions enregistrées par les agents</small></div>
          <button aria-label="Fermer le résultat">×</button></div>
        <div class="mission-results-body"><h2>Résultat de validation</h2>
          <article class="mission-result-part"><pre class="jules-code-diff"></pre>
            <button id="last-action">Voir le détail</button></article></div>
      </section></main>''')
    page.locator(".mission-results-window").evaluate(
        "(e, variant) => { if (variant) e.classList.add(variant); }", variant
    )
    page.add_style_tag(content=CSS)
    page.locator(".jules-code-diff").evaluate(
        "e => e.textContent = ('+ Modification synthétique ' + 'x'.repeat(240) + '\\n').repeat(180)"
    )
    page.locator("#last-action").evaluate(
        "e => e.before(...Array.from({length: 60}, () => {"
        "const p = document.createElement('p'); p.textContent = 'Contribution synthétique'; return p; }))"
    )
    bounds = page.locator(".mission-results-window").bounding_box()
    assert bounds["y"] >= (114 if width <= 1180 else 88)
    assert bounds["y"] + bounds["height"] <= height - 14 + 1
    assert bounds["x"] >= 0
    assert bounds["x"] + bounds["width"] <= width
    close = page.get_by_role("button", name="Fermer le résultat")
    assert close.bounding_box()["height"] >= 29
    assert page.locator(".mission-results-body").evaluate(
        "e => e.scrollHeight > e.clientHeight"
    )
    page.locator("#last-action").scroll_into_view_if_needed()
    action = page.locator("#last-action").bounding_box()
    assert action["y"] + action["height"] <= height - 14
    assert close.bounding_box()["y"] >= bounds["y"]
    assert page.locator(".mission-results-body").evaluate(
        "e => e.scrollWidth <= e.clientWidth"
    )
    page.close()
