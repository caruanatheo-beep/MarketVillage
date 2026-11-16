"""Local, permanent snapshots of important official research. No model calls."""
from __future__ import annotations

import hashlib
import io
import json
import re
import threading
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

import requests
from pypdf import PdfReader
from pypdf.errors import PdfReadError

from .config import ROOT
from .models import Evidence, ToolResult

ARCHIVE_ROOT = ROOT / "rag_documents" / "permanent"
OFFICIAL_HOSTS = ("federalreserve.gov", "ecb.europa.eu", "bis.org", "imf.org", "bankofengland.co.uk", "boj.or.jp")
IMPORTANT_TERMS = (
    "fomc", "monetary policy", "interest rate", "policy decision", "minutes",
    "economic bulletin", "world economic outlook", "global financial stability",
    "quarterly review", "financial stability report", "inflation outlook",
)


def important_document(title: str) -> bool:
    return any(term in title.casefold() for term in IMPORTANT_TERMS)


def official_url(url: str) -> bool:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    return parsed.scheme == "https" and not parsed.username and not parsed.password and any(
        host == allowed or host.endswith("." + allowed) for allowed in OFFICIAL_HOSTS
    )


class ArticleText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.skip = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "nav", "footer", "header"}:
            self.skip += 1

    def handle_endtag(self, tag):
        if tag in {"script", "style", "nav", "footer", "header"}:
            self.skip = max(0, self.skip - 1)

    def handle_data(self, data):
        if not self.skip and data.strip():
            self.parts.append(data.strip())


class ResearchArchive:
    def __init__(self, root: Path = ARCHIVE_ROOT):
        self.root = root
        self._lock = threading.RLock()
        self._download_lock = threading.Lock()
        self.last_errors: list[str] = []
        self._attempts: dict[str, float] = {}
        self._worker: threading.Thread | None = None

    def schedule(self, documents: list[dict]) -> None:
        with self._lock:
            if self._worker and self._worker.is_alive():
                return
            self._worker = threading.Thread(target=self.retain_important, args=(documents,), daemon=True,
                                            name="permanent-research-archive")
            self._worker.start()

    def documents(self) -> list[dict]:
        with self._lock:
            try:
                items = json.loads((self.root / "manifest.json").read_text(encoding="utf-8"))
                return items if isinstance(items, list) else []
            except (OSError, ValueError):
                return []

    def keep(self, document: dict, automatic: bool = False) -> dict:
        """Save a verified downloadable snapshot; never mark a failed fetch as saved."""
        url = str(document.get("url", ""))
        if not official_url(url):
            raise ValueError("Only HTTPS publications on approved official domains can be retained.")
        with self._download_lock:
            existing = next((item for item in self.documents() if item["url"] == url), None)
            if existing and (self.root / existing["text_file"]).is_file() and (self.root / existing["file"]).is_file():
                return existing
            with requests.Session() as session:
                current_url = url
                for _ in range(5):
                    if not official_url(current_url):
                        raise ValueError("Publication redirected outside approved official domains.")
                    response = session.get(current_url, timeout=(4, 12), stream=True, allow_redirects=False,
                                           headers={"User-Agent": "AI-Sales-Copilot/3.5 (official research archive)"})
                    if response.status_code in {301, 302, 303, 307, 308}:
                        from urllib.parse import urljoin
                        current_url = urljoin(current_url, response.headers.get("Location", ""))
                        response.close()
                        continue
                    break
                else:
                    raise ValueError("Too many redirects while downloading publication.")
                response.raise_for_status()
                parts, size = [], 0
                for part in response.iter_content(65536):
                    size += len(part)
                    if size > 15 * 1024 * 1024:
                        raise ValueError("Publication exceeds the 15 MB archive limit.")
                    parts.append(part)
                payload = b"".join(parts)
                content_type = response.headers.get("Content-Type", "").lower()
            is_pdf = payload.startswith(b"%PDF-")
            if is_pdf:
                try:
                    reader = PdfReader(io.BytesIO(payload))
                    text = "\n\n".join(page.extract_text() or "" for page in reader.pages[:200])
                except (PdfReadError, TypeError, KeyError) as exc:
                    raise ValueError("PDF text could not be extracted; nothing was archived.") from exc
            elif "html" in content_type or payload.lstrip().lower().startswith((b"<!doctype html", b"<html")):
                parser = ArticleText()
                parser.feed(payload.decode("utf-8", errors="replace"))
                text = "\n".join(parser.parts)
            else:
                raise ValueError("Source did not return a PDF or readable publication page.")
            if len(text.strip()) < 200 or any(marker in text[:1000].casefold() for marker in (
                "verify you are human", "access denied", "checking your browser", "just a moment",
            )):
                raise ValueError("No usable publication text was returned; nothing was archived.")
            identity = hashlib.sha256(url.encode()).hexdigest()[:20]
            file_name = identity + (".pdf" if is_pdf else ".txt")
            text_file = identity + ".txt"
            added_at = datetime.now(timezone.utc).isoformat()
            item = {
                "title": str(document.get("title", "Official publication")),
                "institution": str(document.get("institution", "Official source")),
                "published": str(document.get("published", "")),
                "url": url, "added_at": added_at, "file": file_name, "text_file": text_file,
                "format": "PDF" if is_pdf else "TEXT", "automatic": automatic,
                "content_hash": hashlib.sha256(payload).hexdigest(),
            }
            with self._lock:
                self.root.mkdir(parents=True, exist_ok=True)
                if is_pdf:
                    (self.root / file_name).write_bytes(payload)
                (self.root / text_file).write_text(text, encoding="utf-8")
                items = [old for old in self.documents() if old["url"] != url] + [item]
                temporary = self.root / "manifest.tmp"
                temporary.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
                temporary.replace(self.root / "manifest.json")
            return item

    def retain_important(self, documents: list[dict], limit: int = 4) -> int:
        saved = {item["url"] for item in self.documents()}
        import time
        now = time.time()
        candidates = [item for item in documents if important_document(item["title"])
                      and official_url(item["url"]) and item["url"] not in saved
                      and now - self._attempts.get(item["url"], 0) > 21600][:limit]
        self.last_errors = []
        count = 0
        for document in candidates:
            self._attempts[document["url"]] = now
            try:
                self.keep(document, automatic=True)
                count += 1
            except (requests.RequestException, OSError, ValueError) as exc:
                self.last_errors.append(f"{document['title']}: {type(exc).__name__}")
        return count

    def search(self, query: str, limit: int = 4) -> ToolResult:
        terms = set(re.findall(r"[a-z]{3,}", query.casefold())) - {"the", "and", "for", "with", "what", "prepare", "client", "market"}
        candidates = []
        for item in self.documents():
            try:
                text = (self.root / item["text_file"]).read_text(encoding="utf-8")
            except OSError:
                continue
            for start in range(0, min(len(text), 500000), 1000):
                passage = re.sub(r"\s+", " ", text[start:start + 1250]).strip()
                score = len(terms & set(re.findall(r"[a-z]{3,}", passage.casefold())))
                if score:
                    candidates.append((score, item.get("published", ""), item, passage))
        candidates.sort(key=lambda row: (row[0], row[1]), reverse=True)
        evidence = []
        per_document: dict[str, int] = {}
        for _, _, item, passage in candidates:
            if per_document.get(item["url"], 0) >= 2:
                continue
            evidence.append(Evidence(
                claim=f"{item['title']}: {passage}", source=item["institution"], url=item["url"],
                observation_date=item["published"][:10] or "date unavailable",
                evidence_type="permanently retained official publication (dated background)", confidence="high",
            ))
            per_document[item["url"]] = per_document.get(item["url"], 0) + 1
            if len(evidence) >= limit:
                break
        return ToolResult("permanent_research_rag", "\n".join(item.claim for item in evidence), evidence)
