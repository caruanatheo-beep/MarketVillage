from src import dynamic_rag
from src.dynamic_rag import DynamicOfficialRag
from src.models import NewsItem
from src.tools import classify_and_plan


def test_dynamic_rag_ingests_live_official_news(tmp_path, monkeypatch):
    cache = tmp_path / "dynamic_documents.json"
    monkeypatch.setattr(dynamic_rag, "CACHE", cache)
    corpus = DynamicOfficialRag()
    count = corpus.ingest_news([
        NewsItem(
            "Federal Reserve issues FOMC statement",
            "Federal Reserve",
            "2026-09-29 18:00 UTC",
            "https://www.federalreserve.gov/newsevents/pressreleases/monetary20260929a.htm",
            "Monetary-policy decision",
        )
    ])
    assert count == 1
    assert corpus.documents()[0]["institution"] == "Federal Reserve"
    result = corpus.search("Federal Reserve policy")
    assert result.evidence
    assert result.evidence[0].url.startswith("https://www.federalreserve.gov/")
    assert cache.exists()


def test_sales_requests_select_sales_workflow_tool():
    classification, _, tools = classify_and_plan("Prepare my client call and scenario map", 5)
    assert "Sales workflow" in classification
    assert "sales_workflow" in tools
