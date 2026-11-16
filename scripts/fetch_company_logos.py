"""Bundle official company favicons as small PNGs; never called by the web app.

Run from the repository root with the project's Python environment. Existing
logos are kept; passing host names restricts acquisition to those configured hosts.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from html.parser import HTMLParser
from io import BytesIO
import json
from pathlib import Path
import sys
from urllib.parse import urljoin

import requests
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from internships_project.internships import COMPANY_ICON_HOSTS, COMPANY_LOGO_DIR


class IconLinks(HTMLParser):
    def __init__(self):
        super().__init__()
        self.urls = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "link" and "icon" in attrs.get("rel", "").lower() and attrs.get("href"):
            self.urls.append(attrs["href"])


def download(url):
    with requests.get(url, timeout=(6, 12), stream=True) as response:
        response.raise_for_status()
        data = bytearray()
        for chunk in response.iter_content(65536):
            data.extend(chunk)
            if len(data) > 2_000_000:
                raise ValueError("Image/page too large")
        return bytes(data), response.url


def png_bytes(data):
    with Image.open(BytesIO(data)) as original:
        if original.width * original.height > 4_000_000:
            raise ValueError("Image dimensions too large")
        original.load()
        image = original.convert("RGBA")
        image.thumbnail((96, 96), Image.Resampling.LANCZOS)
        output = BytesIO()
        image.save(output, format="PNG", optimize=True)
        return output.getvalue()


def fetch(host):
    path = COMPANY_LOGO_DIR / f"{host}.png"
    if path.exists():
        return host, None
    home = f"https://{host}/"
    candidates = []
    try:
        page, final_url = download(home)
        parser = IconLinks()
        parser.feed(page.decode("utf-8", errors="replace"))
        candidates = [urljoin(final_url, href) for href in reversed(parser.urls)]
    except (requests.RequestException, ValueError):
        pass
    candidates.append(urljoin(home, "favicon.ico"))
    for url in dict.fromkeys(candidates):
        if not url.startswith("https://"):
            continue
        try:
            data, final_url = download(url)
            payload = png_bytes(data)
            path.write_bytes(payload)
            print(host, "stored", flush=True)
            return host, {"url": final_url, "downloaded_at": datetime.now(timezone.utc).isoformat()}
        except (requests.RequestException, ValueError, OSError):
            continue
    print(host, "unavailable", flush=True)
    return host, None


def main():
    configured = set(COMPANY_ICON_HOSTS.values())
    selected = set(sys.argv[1:]) or configured
    if not selected <= configured:
        raise SystemExit("Only configured official company hosts are accepted")
    COMPANY_LOGO_DIR.mkdir(parents=True, exist_ok=True)
    manifest = COMPANY_LOGO_DIR / "sources.json"
    sources = json.loads(manifest.read_text(encoding="utf-8")) if manifest.exists() else {}
    with ThreadPoolExecutor(max_workers=4) as pool:
        for host, result in pool.map(fetch, sorted(selected)):
            if result:
                sources[host] = result
    manifest.write_text(json.dumps(sources, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(len(sources), "official logos stored")


if __name__ == "__main__":
    main()
