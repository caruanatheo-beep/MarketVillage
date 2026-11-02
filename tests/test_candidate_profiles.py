import zipfile
from datetime import date

import pytest

from internships_project import career_agent
from internships_project.candidate_profiles import (ProfileError, extract_cv_text, profile_choices,
                                                    profile_prompt, save_profile)
from internships_project.internships import Opportunity


def test_cv_import_and_named_profiles(tmp_path):
    document = tmp_path / "cv.docx"
    with zipfile.ZipFile(document, "w") as archive:
        archive.writestr("word/document.xml", "<w:document xmlns:w='http://schemas.openxmlformats.org/wordprocessingml/2006/main'>"
                         "<w:body><w:p><w:r><w:t>Fixed Income Sales internship in Paris, "
                         "with Python and market analysis experience, available from May 2027.</w:t>"
                         "</w:r></w:p></w:body></w:document>")
    text = extract_cv_text(str(document))
    assert "Fixed Income Sales" in text
    first, first_id = save_profile({}, None, {"name": "Alex Martin", "source_text": text,
                                            "target_roles": ["Fixed Income Sales"]})
    second, second_id = save_profile(first, None, {"name": "Sam Lee", "source_text": text})
    assert first_id != second_id
    assert [name for name, _ in profile_choices(second)] == ["Alex Martin", "Sam Lee"]
    assert "Métiers : Fixed Income Sales" in profile_prompt(first[first_id])[2]
    with pytest.raises(ProfileError):
        save_profile(second, None, {"name": "alex martin", "source_text": text})
    with pytest.raises(ProfileError):
        save_profile(second, first_id, {"name": "Alex Martin", "source_text": text,
                                        "start_month": "2027-09", "end_month": "2027-04"})


def test_profile_rejects_oversized_fields_and_docx_expansion(tmp_path):
    source = "Valid profile information with more than eighty characters. " * 2
    with pytest.raises(ProfileError, match="trop long"):
        save_profile({}, None, {"name": "Alex Martin", "source_text": source,
                                "overview": "x" * 2001})
    document = tmp_path / "large.docx"
    with zipfile.ZipFile(document, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("word/document.xml", "x" * 12_000_001)
    with pytest.raises(ProfileError, match="décompressée"):
        extract_cv_text(str(document))


def test_ai_structures_profile_without_inventing_missing_dates(monkeypatch):
    def fake_model(name, schema, instructions, payload):
        assert name == "candidate_profile"
        assert "N'invente" in instructions
        assert payload["candidate_name"] == "Alex Martin"
        return {"overview": "Étudiant en finance", "experience": ["Stage Sales"],
                "strengths": ["Python"], "target_roles": ["Sales"],
                "locations": ["Paris"], "contracts": ["Stage"],
                "start_month": "été 2027", "end_month": "", "start_window": "Été 2027",
                "constraints": ["Convention à confirmer"]}
    monkeypatch.setattr(career_agent, "_openai_json", fake_model)
    result = career_agent.structure_candidate_profile(
        "Alex Martin", "Étudiant en finance, expérience en salle de marchés, "
        "Python et analyse des marchés financiers. Recherche un stage Sales à Paris pour 2027.")
    assert result["target_roles"] == ["Sales"]
    assert result["start_month"] == ""
    assert result["constraints"] == ["Convention à confirmer"]


def test_ranking_and_drafts_follow_selected_profile():
    jobs = [
        Opportunity("Equity Sales", "Banque", "Paris", "Stage", "https://example.com/sales",
                    "2026-10-24", 100, "mai 2027", "Sales / Trading / Structuring"),
        Opportunity("Quantitative Research", "Banque", "London", "Stage", "https://example.com/quant",
                    "2026-10-24", 100, "mai 2027", "Quant / Research"),
    ]
    profile = {"target_roles": ["Quantitative Research"], "locations": ["London"],
               "contracts": ["Stage"], "start_month": "2027-05", "end_month": "2027-08"}
    ranked = career_agent.rank_candidate_pool(jobs, today=date(2026, 10, 25), profile=profile)
    assert ranked[0].url == jobs[1].url
    drafts = career_agent.save_letter_draft({}, jobs[0].url, {jobs[0].url}, "Alex letter", "alex")
    drafts = career_agent.save_letter_draft(drafts, jobs[0].url, {jobs[0].url}, "Sam letter", "sam")
    assert career_agent.saved_letter(drafts, jobs[0].url, "alex") == "Alex letter"
    assert career_agent.saved_letter(drafts, jobs[0].url, "sam") == "Sam letter"


def test_sales_and_trader_shortlists_use_target_role_not_cv_history(monkeypatch):
    def offer(title, company, suffix, score):
        return Opportunity(title, company, "Paris", "Stage", f"https://example.com/{suffix}",
                           "2026-10-24", score, "juin 2027", "Sales / Trading / Structuring")

    jobs = [offer("Assistant Sales Forex", "Banque A", "sales-a", 100),
            offer("Fixed Income Sales", "Banque B", "sales-b", 85),
            offer("Trading Analyst", "Banque C", "trader-a", 160),
            offer("Junior Trader", "Banque D", "trader-b", 95),
            offer("Quantitative Researcher", "Banque E", "quant", 180)]
    sales = {"target_roles": ["Fixed Income Sales"], "locations": ["Paris"],
             "contracts": ["Stage"]}
    trader = {"target_roles": ["Trader"], "locations": ["Paris"],
              "contracts": ["Stage"]}
    sales_pool = career_agent.rank_candidate_pool(jobs, today=date(2026, 10, 25), profile=sales)
    trader_pool = career_agent.rank_candidate_pool(jobs, today=date(2026, 10, 25), profile=trader)
    assert {job.url for job in sales_pool} == {jobs[0].url, jobs[1].url}
    assert {job.url for job in trader_pool} == {jobs[2].url, jobs[3].url}

    monkeypatch.setattr(career_agent, "job_evidence", lambda job: (job.title, "listing_only"))
    def fake_model(name, schema, instructions, payload):
        assert payload["candidate_profile"] == "CV avec expérience Sales, objectif Trader"
        return {"briefs": [{"url": row["url"], "fit_summary": "Rôle ciblé",
                            "match_points": [], "role_signals": [], "questions_to_check": [],
                            "application_angle": "Candidature ciblée"} for row in payload["jobs"]]}
    monkeypatch.setattr(career_agent, "_openai_json", fake_model)
    briefs = career_agent.generate_briefs(trader_pool, "CV avec expérience Sales, objectif Trader",
                                          candidate_record=trader)
    assert {row["job"].url for row in briefs} == {jobs[2].url, jobs[3].url}
    assert "Correspond à ton métier cible" in career_agent.render_briefs(briefs)


def test_profile_card_formats_confirmed_month_range():
    from internships_project.candidate_profiles import render_profile_card

    card = render_profile_card({"name": "Camille Martin", "target_roles": ["Sales"],
                                "locations": ["Paris"], "contracts": ["Stage"],
                                "start_month": "2027-04", "end_month": "2027-07",
                                "start_window": "2027-04 to 2027-07"})
    assert "Avril à juillet 2027" in card
    assert "2027-04 to 2027-07" not in card


def test_profile_card_keeps_roles_separate_and_escapes_profile_text():
    from internships_project.candidate_profiles import render_profile_card

    card = render_profile_card({"name": "Camille Martin-Durand de la Tour", "target_roles":
                                ["Fixed Income Sales", "FX & Rates", "Structured Products Sales"],
                                "locations": ["Paris", "Londres"], "contracts": ["Stage"]})
    assert card.count('class="profile-role-chip"') == 3
    assert "FX &amp; Rates" in card
    assert "Fixed Income Sales, FX" not in card
    assert "Paris, Londres" in card
