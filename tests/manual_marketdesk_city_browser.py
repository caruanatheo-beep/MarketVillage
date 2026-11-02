"""Manual browser smoke check; run against a locally started City server.

Usage: python tests/manual_marketdesk_city_browser.py http://127.0.0.1:7862
No missions are started. Screenshots are written to MARKETDESK_CITY_SCREENSHOT_DIR.
"""

import os
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright


base = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:7862").rstrip("/")
output = Path(os.getenv("MARKETDESK_CITY_SCREENSHOT_DIR", ".pytest_city_tmp"))
output.mkdir(parents=True, exist_ok=True)

with sync_playwright() as playwright:
    browser = playwright.chromium.launch(headless=True)
    for name, width, height in (("desktop", 1440, 900), ("mobile", 390, 844)):
        page = browser.new_page(viewport={"width": width, "height": height}, device_scale_factor=1)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(base + "/city/", wait_until="networkidle", timeout=45000)
        page.locator(".roster-agent").first.wait_for(timeout=30000)
        page.locator(".roster-agent").nth(2).click()
        assert page.locator(".agent-identity h2").inner_text() == "Jules"
        assert page.locator("#phaser-game canvas").count() == 1
        assert page.locator(".roster-agent").count() == 6
        assert not errors, errors
        page.screenshot(path=str(output / f"city_{name}.png"), full_page=True)
        print(name, "OK", "canvas", page.locator("#phaser-game canvas").count(),
              "agents", page.locator(".roster-agent").count())
        page.close()
    browser.close()
