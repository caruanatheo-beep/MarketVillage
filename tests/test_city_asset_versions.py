"""City page cache versions depend on asset contents, not deployment metadata."""

import os
import re

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from internships_project import city_routes


@pytest.mark.parametrize("changed_asset", ["city.css", "city.js"])
def test_city_refreshes_changed_assets_with_identical_size_and_timestamp(tmp_path, monkeypatch, changed_asset):
    (tmp_path / "city.html").write_text(
        '<link href="/city/city.css"><script src="/city/city.js"></script>',
        encoding="utf-8",
    )
    for name in ("city.css", "city.js"):
        (tmp_path / name).write_bytes(b"old content")
    monkeypatch.setattr(city_routes, "ASSETS", tmp_path)
    app = FastAPI()
    # Page rendering needs neither stored user data nor a running worker.
    city_routes.add_city_routes(app, lambda request: "synthetic-user", None, None)

    def versions(response):
        assert response.status_code == 200
        assert response.headers["cache-control"] == "private, no-store"
        return dict(re.findall(r'/city/(city\.(?:css|js))\?v=([^" ]+)', response.text))

    with TestClient(app) as client:
        before = versions(client.get("/city/"))
        assert set(before) == {"city.css", "city.js"}
        assert versions(client.get("/city/")) == before

        asset = tmp_path / changed_asset
        original = asset.stat()
        asset.write_bytes(b"new content")
        os.utime(asset, ns=(original.st_atime_ns, original.st_mtime_ns))
        assert asset.stat().st_size == original.st_size
        assert asset.stat().st_mtime_ns == original.st_mtime_ns

        after = versions(client.get("/city/"))
        assert after[changed_asset] != before[changed_asset]
        unchanged_asset = "city.js" if changed_asset == "city.css" else "city.css"
        assert after[unchanged_asset] == before[unchanged_asset]

        # The generated URL still serves the updated asset through the usual route.
        response = client.get(f"/city/{changed_asset}?v={after[changed_asset]}")
        assert response.status_code == 200
        assert response.content == b"new content"
