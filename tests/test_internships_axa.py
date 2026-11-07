import json

from internships_project import internships


def _card(title, slug, *, contract="Stage", location="PARIS - 75", entity="GIE AXA"):
    return (f'<a class="search-results-list__job-link" href="/emploi/paris/{slug}/3441/123">{title}</a>'
            f'<li class="job-location">{location}</li><li class="job-contract">{contract}</li>'
            f'<li class="job-entity">{entity}</li>')


def _detail(title, description):
    posting = {"@type": "JobPosting", "title": title, "datePosted": "2026-11-01",
               "description": description}
    return f'<script type="application/ld+json">{json.dumps(posting)}</script>'


def test_axa_collects_verified_stage_offers_across_pages(monkeypatch):
    pages = {
        1: ('<input class="pagination-current" max="2">'
            + _card("Stage - Investment Strategy and Financial Data Analyst", "investment-strategy")
            + _card("Stage - Health equity analyst", "health-equity")
            + _card("Portfolio Analyst", "portfolio-cdi", contract="CDI")),
        2: (_card("Stage - Portfolio Liquidity Analyst", "portfolio-liquidity")
            + _card("Conseiller Valorisation Automobiles - Stage", "automobiles")),
    }
    details = {
        "investment-strategy": _detail("Stage - Investment Strategy and Financial Data Analyst",
                                       "Suivi des classes d'actifs liquides et données Bloomberg."),
        "portfolio-liquidity": _detail("Stage - Portfolio Liquidity Analyst",
                                      "Portfolio liquidity and market risk analysis."),
    }
    calls = []

    class Response:
        def __init__(self, text):
            self.text = text

        def raise_for_status(self):
            pass

    def get(url, *, params=None, timeout=None):
        calls.append((url, params))
        if params is not None:
            return Response(pages[params.get("p", 1)])
        return Response(details[url.split("/")[-3]])

    monkeypatch.setattr(internships.requests, "get", get)
    jobs = internships._axa_jobs()
    assert {job.title for job in jobs} == {
        "Stage - Investment Strategy and Financial Data Analyst",
        "Stage - Portfolio Liquidity Analyst",
    }
    assert all(job.published == "2026-11-01" and job.kind == "Stage" for job in jobs)
    assert all(job.source == "Site carrière · AXA" and job.url.startswith("https://recrutement.axa.fr/emploi/") for job in jobs)
    assert len(calls) == 4  # Two listing pages and only two relevant details.
