"""The redesigned City interface is served under /city/next/, behind the same login."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from internships_project import city_routes


def _client(user):
    app = FastAPI()
    city_routes.add_city_routes(app, lambda request: user, None, None)
    return TestClient(app)


def test_next_page_and_assets_are_served_with_versions_and_types():
    with _client("synthetic-user") as client:
        page = client.get("/city/next/")
        assert page.status_code == 200
        assert page.headers["cache-control"] == "private, no-store"
        assert "/city/next/app.js?v=" in page.text and "/city/next/app.css?v=" in page.text
        assert client.get("/city/next/app.js").headers["content-type"].startswith("text/javascript")
        assert client.get("/city/next/app.css").headers["content-type"].startswith("text/css")
        assert client.get("/city/next/fonts/Jersey15.ttf").headers["content-type"] == "font/ttf"


def test_next_assets_stay_inside_their_folder_and_original_page_is_untouched():
    with _client("synthetic-user") as client:
        assert client.get("/city/next/..%2Fcity.js").status_code == 404
        assert client.get("/city/next/missing.js").status_code == 404
        assert client.get("/city/").status_code == 200
        assert client.get("/city/city.css").status_code == 200


def test_next_interface_requires_login():
    with _client(None) as client:
        assert client.get("/city/next/").status_code == 401
        assert client.get("/city/next/app.js").status_code == 401
