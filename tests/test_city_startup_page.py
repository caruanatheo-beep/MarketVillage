"""Check the City startup page without reading stored account data."""

import re

import pytest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from internships_project.city_routes import add_city_routes


def test_city_explains_disabled_javascript_and_keeps_normal_startup():
    app = FastAPI()
    add_city_routes(app, lambda request: "synthetic-user", None, None)
    with TestClient(app) as client:
        response = client.get("/city/")
    assert response.status_code == 200
    match = re.search(r"<noscript>(.*?)</noscript>", response.text, re.DOTALL)
    assert match is not None
    fallback = match.group(1)
    assert "JavaScript est désactivé" in fallback
    assert "Active-le dans ton navigateur" in fallback
    assert "recharge cette page" in fallback
    # The loading indicator is hidden only when the noscript fallback is active.
    assert "#root { display: none; }" in fallback
    normal_startup = response.text.replace(match.group(0), "")
    assert "display: none" not in normal_startup
    assert '<div id="root">' in normal_startup
    assert re.search(r'<script defer src="/city/city.js\?v=[a-f0-9]+" onerror="[^"]+"></script>', normal_startup)


@pytest.mark.parametrize("bundle_fails", [False, True])
@pytest.mark.parametrize("viewport", [{"width": 1366, "height": 768}, {"width": 1920, "height": 1080}, {"width": 390, "height": 844}])
def test_city_bundle_failure_offers_reload_and_recovers(bundle_fails, viewport, tmp_path):
    """Exercise the served fallback in a browser, using only synthetic responses."""
    playwright = pytest.importorskip("playwright.sync_api")
    app = FastAPI()
    add_city_routes(app, lambda request: "synthetic-user", None, None)
    with TestClient(app) as client:
        html = client.get("/city/").text
        css = client.get("/city/city.css").text

    with playwright.sync_playwright() as runtime:
        try:
            browser = runtime.chromium.launch(headless=True)
        except playwright.Error as exc:
            pytest.skip(f"Navigateur Chromium local indisponible : {exc}")
        try:
            page = browser.new_page(viewport=viewport)
            failing = bundle_fails

            def respond(route):
                path = route.request.url.split("?", 1)[0]
                if path == "http://city.test/city/":
                    route.fulfill(content_type="text/html", body=html)
                elif path == "http://city.test/city/city.css":
                    route.fulfill(content_type="text/css", body=css)
                elif path == "http://city.test/city/city.js":
                    if failing:
                        route.abort("failed")
                    else:
                        route.fulfill(content_type="text/javascript", body=(
                            "document.getElementById('root').textContent = 'City prête';"
                        ))
                else:
                    # No image, external service or real user data.
                    route.fulfill(status=404, body="")

            page.route("**/*", respond)
            page.goto("http://city.test/city/")
            if bundle_fails:
                playwright.expect(page.get_by_role("alert")).to_contain_text(
                    "City n’a pas pu charger son interface")
                playwright.expect(page.get_by_text("Ouverture de MarketDesk City…")).to_have_count(0)
                message = page.get_by_role("alert")
                button = page.get_by_role("button", name="Recharger City")
                playwright.expect(button).to_be_visible()
                card = message.bounding_box()
                action = button.bounding_box()
                assert 0 <= card["x"] < card["x"] + card["width"] <= viewport["width"]
                assert 0 <= card["y"] < card["y"] + card["height"] <= viewport["height"]
                assert action["height"] >= 44
                paragraph = message.locator("p").bounding_box()
                assert 0 <= action["y"] - (paragraph["y"] + paragraph["height"]) <= 32
                assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
                # Keep a synthetic render for visual inspection without any user data.
                page.screenshot(path=str(tmp_path / "city-load-error.png"), full_page=True)
                failing = False
                button.focus()
                page.keyboard.press("Enter")
            playwright.expect(page.locator("#root")).to_have_text("City prête")
            playwright.expect(page.get_by_role("alert")).to_have_count(0)
            playwright.expect(page.get_by_role("button", name="Recharger City")).to_have_count(0)
        finally:
            browser.close()
