"""Check the City startup page without reading stored account data."""

import re

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
    assert re.search(r'<script defer src="/city/city.js\?v=[a-f0-9]+"></script>', normal_startup)
