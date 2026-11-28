"""Capture the new interface from the preview server (preview-next.mjs) at 1920x1080.

Usage: python shots_next.py <output directory>
"""
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

out = Path(sys.argv[1] if len(sys.argv) > 1 else "artifacts/redesign")
out.mkdir(parents=True, exist_ok=True)


def click_agent(page, agent_id, y):
    """Sweeps the row until the scene reports the agent under the cursor, then clicks."""
    for x in range(200, 1760, 12):
        page.mouse.move(x, y)
        page.wait_for_timeout(40)
        if page.evaluate("document.querySelector('.scene canvas').dataset.hover") == agent_id:
            page.mouse.click(x, y)
            return True
    return False


with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 1920, "height": 1080})
    errors = []
    page.on("pageerror", lambda exc: errors.append(str(exc)))
    page.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else None)
    page.goto("http://127.0.0.1:7879/city/next/")
    page.wait_for_selector(".hotbar")
    page.wait_for_timeout(2500)
    page.screenshot(path=out / "01-toit-head-markets.png")
    page.wait_for_timeout(9000)
    page.screenshot(path=out / "02-vie.png")
    click_agent(page, "market_analyst", 915)
    page.wait_for_timeout(500)
    page.screenshot(path=out / "03-fiche-agent.png")
    page.keyboard.press("Escape")
    page.keyboard.press("3")
    page.wait_for_timeout(500)
    page.screenshot(path=out / "04-missions.png")
    page.keyboard.press("Escape")
    click_agent(page, "desk_manager", 630)
    page.wait_for_timeout(600)
    page.screenshot(path=out / "05-dialogue.png")
    page.keyboard.press("Escape")
    page.keyboard.press("-")
    page.keyboard.press("-")
    page.wait_for_timeout(1200)
    page.screenshot(path=out / "06-immeuble-entier.png")
    browser.close()
print("\n".join(errors) or "Aucune erreur dans la console.")
