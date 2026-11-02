from src.research_archive import ResearchArchive, important_document, official_url
import pytest


class Response:
    status_code = 200
    headers = {"Content-Type": "text/html"}
    def raise_for_status(self):
        pass
    def iter_content(self, size):
        yield ("<html><body><article>Monetary policy inflation outlook and interest rates. "
               + "Inflation policy evidence and projections. " * 30 + "</article></body></html>").encode()


class Session:
    def __enter__(self):
        return self
    def __exit__(self, *args):
        pass
    def get(self, *args, **kwargs):
        return Response()


def test_retained_content_survives_restart_and_deduplicates(tmp_path, monkeypatch):
    monkeypatch.setattr("src.research_archive.requests.Session", Session)
    archive = ResearchArchive(tmp_path)
    doc = {"title": "Monetary policy decision", "url": "https://www.ecb.europa.eu/press/test.html",
           "institution": "ECB", "published": "2026-09-30"}
    first = archive.keep(doc)
    assert archive.keep(doc)["added_at"] == first["added_at"]
    restarted = ResearchArchive(tmp_path)
    assert len(restarted.documents()) == 1
    assert restarted.search("inflation projections").evidence
    assert (tmp_path / first["file"]).exists()


def test_failed_download_never_marked_saved(tmp_path, monkeypatch):
    monkeypatch.setattr("src.research_archive.requests.Session", Session)
    monkeypatch.setattr(Response, "iter_content", lambda self, size: iter([b"<html>Access denied</html>"]))
    archive = ResearchArchive(tmp_path)
    with pytest.raises(ValueError):
        archive.keep({"url": "https://www.bis.org/test.html"})
    assert archive.documents() == []


def test_selection_and_allowlist():
    assert important_document("FOMC meeting minutes")
    assert not important_document("Weekly website update")
    assert official_url("https://www.imf.org/report.pdf")
    assert not official_url("https://imf.org.attacker.com/report.pdf")
    assert not official_url("http://www.imf.org/report.pdf")


def test_auto_retention_and_cooldown(tmp_path, monkeypatch):
    archive = ResearchArchive(tmp_path)
    calls = []
    def failed(doc, automatic=False):
        calls.append(doc)
        raise ValueError("blocked")
    monkeypatch.setattr(archive, "keep", failed)
    doc = {"title": "FOMC minutes", "url": "https://www.federalreserve.gov/test.html"}
    assert archive.retain_important([doc]) == 0
    archive.retain_important([doc])
    assert len(calls) == 1


def test_pdf_saved_and_retrievable(tmp_path, monkeypatch):
    from reportlab.pdfgen import canvas
    import io
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer)
    for index in range(12):
        pdf.drawString(30, 780 - index * 25, "Inflation projections and monetary policy transmission evidence.")
    pdf.save()
    monkeypatch.setattr("src.research_archive.requests.Session", Session)
    monkeypatch.setattr(Response, "iter_content", lambda self, size: iter([buffer.getvalue()]))
    archive = ResearchArchive(tmp_path)
    saved = archive.keep({"url": "https://www.imf.org/report.pdf", "title": "World economic outlook",
                          "institution": "IMF", "published": "2026-09-01"})
    assert saved["format"] == "PDF"
    assert (tmp_path / saved["file"]).read_bytes().startswith(b"%PDF-")
    assert archive.search("inflation transmission").evidence
