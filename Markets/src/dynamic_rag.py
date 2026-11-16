from __future__ import annotations

import json
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

import feedparser
import requests

from .config import ROOT, settings
from .models import Evidence, ToolResult
from .models import NewsItem
from .security import safe_text, safe_url
from .research_archive import ResearchArchive


FEEDS = (
    ("Federal Reserve", "https://www.federalreserve.gov/feeds/s_t_all.xml"),
    ("Federal Reserve", "https://www.federalreserve.gov/feeds/press_monetary.xml"),
    ("European Central Bank", "https://www.ecb.europa.eu/rss/press.html"),
    ("European Central Bank", "https://www.ecb.europa.eu/rss/pub.html"),
    ("Bank of England", "https://www.bankofengland.co.uk/rss/news"),
    ("Bank of Japan", "https://www.boj.or.jp/en/rss/whatsnew.xml"),
    ("BIS", "https://www.bis.org/doclist/bis_fsi_publs.rss"),
    ("BIS", "https://www.bis.org/doclist/cbspeeches.rss"),
)
CACHE = ROOT / "rag_documents" / "dynamic_documents.json"
TOKENS = re.compile(r"[a-z0-9]{2,}")


@dataclass(frozen=True)
class DynamicDocument:
    title: str
    institution: str
    published: str
    url: str
    summary: str
    fetched_at: str

    @property
    def freshness(self) -> str:
        try:
            age = (datetime.now(timezone.utc) - datetime.fromisoformat(self.published.replace("Z", "+00:00"))).days
        except ValueError:
            return "date unavailable"
        return "today" if age <= 0 else "recent" if age <= 7 else "current" if age <= 45 else "archive"


class DynamicOfficialRag:
    """Bounded, persistent RAG catalogue populated only from official feeds."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._documents = self._load()
        self._last_sync = CACHE.stat().st_mtime if CACHE.exists() else 0.0
        self._source_status: dict[str, str] = {}
        self._news_pipeline_count = 0
        self.archive = ResearchArchive()

    def _load(self) -> list[DynamicDocument]:
        try:
            return [DynamicDocument(**item) for item in json.loads(CACHE.read_text(encoding="utf-8"))]
        except (OSError, ValueError, TypeError):
            return []

    @staticmethod
    def _date(entry: object) -> str:
        raw = entry.get("published") or entry.get("updated") or ""
        if raw:
            try:
                parsed = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=timezone.utc)
                return parsed.astimezone(timezone.utc).isoformat()
            except ValueError:
                pass
        try:
            parsed = parsedate_to_datetime(raw)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc).isoformat()
        except (TypeError, ValueError, OverflowError):
            return datetime.now(timezone.utc).isoformat()

    def _persist(self) -> None:
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        temporary = CACHE.with_suffix(".tmp")
        temporary.write_text(
            json.dumps([asdict(item) for item in self._documents], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary.replace(CACHE)

    def _merge(self, discovered: list[DynamicDocument]) -> int:
        with self._lock:
            combined = {item.url: item for item in self._documents}
            combined.update({item.url: item for item in discovered if item.url})
            self._documents = sorted(
                combined.values(), key=lambda item: item.published, reverse=True,
            )[:settings.rag_max_documents]
            self._persist()
            self._last_sync = time.time()
            self.archive.schedule([asdict(item) for item in self._documents])
            return len(self._documents)

    def ingest_news(self, items: list[NewsItem]) -> int:
        """Use the already-working official news pipeline as a resilient RAG input."""
        fetched_at = datetime.now(timezone.utc).isoformat()
        discovered: list[DynamicDocument] = []
        for item in items:
            url = safe_url(item.url)
            if not url:
                continue
            published = item.published
            try:
                parsed = datetime.strptime(published, "%Y-%m-%d %H:%M UTC").replace(tzinfo=timezone.utc)
                published = parsed.isoformat()
            except (TypeError, ValueError):
                published = fetched_at
            discovered.append(DynamicDocument(
                title=safe_text(item.title, 240),
                institution=safe_text(item.source, 100),
                published=published,
                url=url,
                summary=f"{safe_text(item.category, 120)}. Official release indexed from the live news pipeline.",
                fetched_at=fetched_at,
            ))
        self._news_pipeline_count = len(discovered)
        return self._merge(discovered) if discovered else len(self._documents)

    def sync(self, force: bool = False) -> int:
        if not force and time.time() - self._last_sync < settings.rag_sync_seconds:
            self.archive.schedule(self.documents())
            return len(self._documents)
        headers = {"User-Agent": "AI-Sales-Desk-Assistant/3.0 official-research-index"}
        discovered: list[DynamicDocument] = []

        def fetch_feed(institution: str, feed_url: str) -> tuple[str, list[DynamicDocument], str]:
            try:
                response = requests.get(
                    feed_url, headers=headers,
                    timeout=(4, min(settings.request_timeout, 8)),
                )
                response.raise_for_status()
                parsed = feedparser.parse(response.content)
                feed_documents: list[DynamicDocument] = []
                for entry in parsed.entries[:30]:
                    url = safe_url(entry.get("link", ""))
                    if not url:
                        continue
                    summary = safe_text(entry.get("summary", entry.get("description", "")), 1400)
                    feed_documents.append(DynamicDocument(
                        safe_text(entry.get("title", "Official publication"), 240), institution,
                        self._date(entry), url, summary,
                        datetime.now(timezone.utc).isoformat(),
                    ))
                if not feed_documents:
                    return feed_url, [], "empty feed"
                return feed_url, feed_documents, f"{len(feed_documents)} indexed"
            except (requests.RequestException, ValueError) as exc:
                return feed_url, [], type(exc).__name__

        with ThreadPoolExecutor(max_workers=min(6, len(FEEDS))) as pool:
            futures = [pool.submit(fetch_feed, institution, url) for institution, url in FEEDS]
            for future in as_completed(futures):
                feed_url, feed_documents, status = future.result()
                self._source_status[feed_url] = status
                discovered.extend(feed_documents)

        # The News module uses the same official institutions and has its own
        # bounded, concurrent fetch/cache path. Reusing it prevents an empty
        # corpus when a publication-only feed is blocked or has moved.
        try:
            from .news import fetch_official_news
            news_items, _ = fetch_official_news(max_items=20)
            self._news_pipeline_count = len(news_items)
            fetched_at = datetime.now(timezone.utc).isoformat()
            for item in news_items:
                url = safe_url(item.url)
                if not url:
                    continue
                try:
                    published_dt = datetime.strptime(item.published, "%Y-%m-%d %H:%M UTC").replace(tzinfo=timezone.utc)
                    published = published_dt.isoformat()
                except (TypeError, ValueError):
                    published = fetched_at
                discovered.append(DynamicDocument(
                    safe_text(item.title, 240), safe_text(item.source, 100), published, url,
                    f"{safe_text(item.category, 120)}. Official release indexed from the live news pipeline.",
                    fetched_at,
                ))
        except (OSError, ValueError, TypeError):
            pass
        return self._merge(discovered)

    def warm_async(self) -> None:
        threading.Thread(target=self.sync, name="dynamic-official-rag", daemon=True).start()

    def summary(self) -> str:
        healthy = sum(1 for status in self._source_status.values() if "indexed" in status)
        if healthy:
            suffix = f" from {healthy} live feeds"
        elif self._news_pipeline_count:
            suffix = " via the resilient official-news pipeline"
        else:
            suffix = " from persistent cache"
        return f"{len(self._documents)} dynamic official publications indexed{suffix}"

    def sync_status(self) -> str:
        if not self._source_status:
            return "Persistent cache ready; live feeds have not completed yet."
        healthy = sum(1 for status in self._source_status.values() if "indexed" in status)
        if self._news_pipeline_count:
            return (
                f"{len(self._documents)} publications available; resilient official-news pipeline active "
                f"({self._news_pipeline_count} current releases)."
            )
        return f"{healthy}/{len(self._source_status)} official feeds responded; {len(self._documents)} cached publications available."

    def documents(self) -> list[dict[str, str]]:
        with self._lock:
            return [{**asdict(item), "freshness": item.freshness} for item in self._documents]

    def search(self, query: str, limit: int = 7) -> ToolResult:
        query_tokens = set(TOKENS.findall(query.casefold()))
        now = datetime.now(timezone.utc)
        scored: list[tuple[float, DynamicDocument]] = []
        with self._lock:
            documents = list(self._documents)
        for item in documents:
            text_tokens = set(TOKENS.findall(f"{item.title} {item.summary} {item.institution}".casefold()))
            lexical = len(query_tokens & text_tokens) / max(1, len(query_tokens))
            try:
                age = max(0, (now - datetime.fromisoformat(item.published.replace("Z", "+00:00"))).days)
            except ValueError:
                age = 365
            recency = 1 / (1 + age / 14)
            score = lexical * 0.78 + recency * 0.22
            if lexical or age <= 14:
                scored.append((score, item))
        selected = [item for _, item in sorted(scored, key=lambda row: row[0], reverse=True)[:limit]]
        evidence = [Evidence(
            claim=f"{item.title}. {item.summary[:500]}", source=item.institution, url=item.url,
            observation_date=item.published[:10], evidence_type=f"official publication ({item.freshness})",
            confidence="high",
        ) for item in selected]
        warning = [] if evidence else ["The dynamic official corpus has no matching publication yet."]
        return ToolResult("dynamic_official_rag", "\n".join(item.claim for item in evidence), evidence, warning)
