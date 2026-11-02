import json
import os
from datetime import date
from pathlib import Path

import pytest

from internships_project import career_agent
from internships_project.internships import Opportunity


def job(title, url, published, score=100):
    return Opportunity(title, "Société Générale", "Paris", "Stage", url, published,
                       score, "avril 2027", "Sales / Trading / Structuring")


def test_shortlist_excludes_old_dismissed_and_applied_offers():
    jobs = [
        job("FX Sales", "https://example.com/fx", "2026-10-24"),
        job("Rates Trading", "https://example.com/rates", "2026-10-23"),
        job("Equity Sales", "https://example.com/equity", "2026-10-22"),
        job("Credit Trading", "https://example.com/credit", "2026-10-21"),
        job("Old Markets", "https://example.com/old", "2026-09-01"),
    ]
    selected = career_agent.select_candidates(
        jobs, feedback={jobs[1].url: {"verdict": "hors_cible"}},
        tracking={jobs[2].url: {"status": "Postulé"}}, today=date(2026, 10, 25),
    )
    assert [item.url for item in selected] == [jobs[0].url, jobs[3].url]
    assert len(selected) <= 3


def test_profile_is_local_and_candidate_priorities_are_applied(tmp_path, monkeypatch):
    monkeypatch.setattr(career_agent, "PROFILE_PATH", tmp_path / "candidate_profile.txt")
    monkeypatch.setattr(career_agent, "local_state_enabled", lambda: True)
    profile = "Nom : Théo Caruana.\nDisponibilité : mai 2027."
    career_agent.save_candidate_profile(profile)
    assert career_agent.load_candidate_profile().strip() == profile
    assert career_agent.candidate_name(profile) == "Théo Caruana"


def test_linkedin_message_keeps_sender_and_recipient_distinct_for_two_profiles(monkeypatch):
    cases = [
        ("Theo Caruana", "Ben Pattenaude",
         "Theo has 18 months of market-finance internships and is currently studying an MSc Financial Markets & Investments.",
         "Top Skills\nPython, Excel, Bloomberg\nBen Pattenaude\nSales at Banque A; Equity Derivatives at Banque B. " * 2,
         "Your move from Sales into Equity Derivatives is relevant to my markets search."),
        ("Alex Martin", "Nina Patel",
         "Alex targets trading roles and has studied derivatives pricing.",
         "Nina Patel\nTrading at Bank C; Rates products at Bank D. " * 4,
         "Your rates trading experience is relevant to my derivatives studies."),
    ]
    for sender_name, recipient_name, sender_profile, recipient_pdf_text, body in cases:
        recipient_profile = {
            "full_name": recipient_name, "first_name": recipient_name.split()[0],
            "name_confidence": "high", "headline": "Markets professional",
            "main_column_text": recipient_pdf_text, "sidebar_text": "Top Skills",
            "linkedin_pdf_text": recipient_pdf_text,
        }
        captured = []

        def fake_openai_json(name, schema, instructions, payload):
            captured.append((name, schema, instructions, payload))
            return {"body": f"Bonjour {sender_name.split()[0]}, {body}\n\n{recipient_name}",
                    "follow_up_body": "Je reviens sur ma question au sujet de votre expérience. Si vous avez un moment pour y répondre, votre avis m'aiderait."}

        monkeypatch.setattr(career_agent, "_openai_json", fake_openai_json)
        message = career_agent.generate_linkedin_message(
            recipient_profile=recipient_profile,
            candidate_profile=sender_profile,
            candidate_name=sender_name,
            tone="Naturel",
            objective="Demander un conseil",
            language="Fran\u00e7ais",
            message_type="Premier message apr\u00e8s connexion",
        )

        _, schema, instructions, payload = captured[0]
        assert "sender_candidate" in instructions and "recipient_contact" in instructions
        assert "never reverse names" in instructions.casefold()
        assert "call the sender a beginner or minimize their experience" in instructions.casefold()
        assert "do not infer whether a degree is completed or ongoing" in instructions.casefold()
        assert payload["sender_candidate"] == {"name": sender_name, "profile": sender_profile}
        assert payload["recipient_contact"]["linkedin_pdf_text"] == recipient_pdf_text.strip()
        assert payload["recipient_contact"]["full_name"] == recipient_name
        assert "candidate_name" not in payload
        assert message.startswith(f"Bonjour {recipient_name.split()[0]},")
        assert message.endswith(f"\n\n{sender_name.split()[0]}")
        assert body in message
        assert recipient_name not in message.rsplit("\n\n", 1)[-1]
        assert schema["required"] == ["body", "follow_up_body"]


def test_linkedin_name_extraction_ignores_top_skills_and_uses_generic_greeting_when_unknown(monkeypatch):
    assert career_agent._linkedin_profile_name("Top Skills\nPython, Excel, Bloomberg") == ""
    monkeypatch.setattr(career_agent, "_openai_json", lambda *args, **kwargs: {
        "body": "Je te contacte au sujet de ton expérience en marchés. Quel conseil donnerais-tu sur ce sujet ?",
        "follow_up_body": "Je reviens sur ma question concernant ton expérience des marchés. Si tu as un moment pour y répondre, merci d'avance.",
    })
    message = career_agent.generate_linkedin_message(
        recipient_profile="Top Skills\nPython, Excel, Bloomberg. " * 8,
        candidate_profile="Profil candidat avec expérience en finance de marché et objectifs professionnels détaillés. " * 2,
        candidate_name="Alex Martin", tone="Naturel", objective="Demander un conseil",
    )
    assert message.startswith("Bonjour,")
    assert not message.startswith("Bonjour Top")
    assert not message.endswith("\n\nAlex Martin")


def test_linkedin_generation_receives_complete_candidate_and_recipient_profiles(monkeypatch):
    from internships_project.candidate_profiles import candidate_profile_context

    full_source = "Detailed candidate CV and education record. " * 650
    record = {
        "name": "Ari Lane", "overview": "Market-finance candidate, MSc in progress.",
        "source_text": full_source,
        "experience": ["Rates sales internship"], "strengths": ["Fixed income"],
        "target_roles": ["Sales"], "locations": ["Paris"], "contracts": ["Stage"],
        "start_window": "April 2027", "start_month": "2027-04", "end_month": "2027-07",
        "constraints": ["No corporate treasury roles"],
    }
    candidate_context = candidate_profile_context(record)
    recipient_pdf_text = "Morgan Lee\n" + "Rates Sales at Bank A. " * 1_200
    recipient_profile = {
        "full_name": "Morgan Lee", "first_name": "Morgan", "name_confidence": "high",
        "headline": "Rates Sales", "main_column_text": recipient_pdf_text,
        "sidebar_text": "", "linkedin_pdf_text": recipient_pdf_text,
    }
    captured = {}

    def fake_openai_json(name, schema, instructions, payload):
        captured.update(payload)
        return {"body": "Je te contacte au sujet de ton parcours en Rates Sales. Quel conseil donnerais-tu sur ce choix de carrière ?",
                "follow_up_body": "Je reviens sur ma question concernant ton parcours en Rates Sales. Si tu as un moment pour y répondre, ton avis m'aiderait."}

    monkeypatch.setattr(career_agent, "_openai_json", fake_openai_json)
    career_agent.generate_linkedin_message(
        recipient_profile=recipient_profile, candidate_profile=candidate_context,
        candidate_name="Ari Lane", tone="Naturel", objective="Demander un conseil",
    )

    assert captured["sender_candidate"]["profile"] == candidate_context
    assert captured["sender_candidate"]["profile"]["source_text"] == full_source.strip()
    assert captured["sender_candidate"]["profile"]["start_month"] == "2027-04"
    assert captured["recipient_contact"]["linkedin_pdf_text"] == recipient_pdf_text.strip()
    assert len(captured["recipient_contact"]["linkedin_pdf_text"]) > 20_000

def test_linkedin_message_rejects_short_pdf_text_before_api(monkeypatch):
    monkeypatch.setattr(career_agent, "_openai_json", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError()))
    try:
        career_agent.generate_linkedin_message(
            "trop court", "Étudiant en finance de marché." * 5, "Théo Caruana",
            "Naturel", "Demander un conseil",
        )
    except career_agent.CareerAgentError as exc:
        assert "PDF" in str(exc)
    else:
        raise AssertionError("Short recipient profile must be rejected before an API call")

    preferred = job("Fixed Income Sales Assistant", "https://example.com/sales", "2026-10-24")
    preferred = career_agent.Opportunity(**{**preferred.__dict__, "start_period": "mai 2027"})
    secondary = job("Market Risk Analyst", "https://example.com/risk", "2026-10-24")
    too_early = job("FX Sales Assistant", "https://example.com/early", "2026-10-24")
    too_early = career_agent.Opportunity(**{**too_early.__dict__, "start_period": "décembre 2026"})
    selected = career_agent.select_candidates([secondary, too_early, preferred], today=date(2026, 10, 25))
    assert [item.url for item in selected] == [preferred.url, secondary.url]
    assert "disponibilité" in " ".join(career_agent.eligibility_checks(
        career_agent.Opportunity(**{**preferred.__dict__, "start_period": "avril 2027"}))).lower()


def test_briefs_use_only_selected_jobs_and_report_evidence_quality(monkeypatch):
    selected = [job("FX Sales", "https://example.com/fx", "2026-10-24")]
    monkeypatch.setattr(career_agent, "job_evidence", lambda item: ("Visible listing facts", "listing_only"))

    def fake_model(name, schema, instructions, payload):
        assert payload["jobs"][0]["url"] == selected[0].url
        assert payload["jobs"][0]["evidence"] == "Visible listing facts"
        assert payload["jobs"][0]["evidence_quality"] == "listing_only"
        assert payload["jobs"][0]["profile_match"]["classification"] == "À examiner selon ton objectif"
        assert "N'invente" in instructions
        return {"briefs": [{"url": selected[0].url, "fit_summary": "Bon alignement",
                            "match_points": ["FX"], "role_signals": [],
                            "questions_to_check": ["Date de début"],
                            "application_angle": "Mettre en avant le stage FX"}]}

    monkeypatch.setattr(career_agent, "_openai_json", fake_model)
    result = career_agent.generate_briefs(selected, "Étudiant en finance, expérience FX")
    assert result[0]["evidence_quality"] == "listing_only"
    assert "Date de début" in career_agent.render_briefs(result)


def test_closed_offer_is_replaced_and_employers_are_diversified(monkeypatch):
    jobs = [job("FX Sales", f"https://example.com/{index}", "2026-10-24") for index in range(4)]
    jobs[2] = Opportunity(**{**jobs[2].__dict__, "company": "BNP Paribas"})
    jobs[3] = Opportunity(**{**jobs[3].__dict__, "company": "Natixis"})
    monkeypatch.setattr(career_agent, "job_evidence",
                        lambda item: ("Listing", "unavailable") if item.url == jobs[0].url else ("Listing", "listing_only"))

    def fake_model(name, schema, instructions, payload):
        urls = [item["url"] for item in payload["jobs"]]
        assert jobs[0].url not in urls
        assert urls == [jobs[1].url, jobs[2].url, jobs[3].url]
        return {"briefs": [{"url": url, "fit_summary": "Fit", "match_points": [],
                             "role_signals": [], "questions_to_check": [],
                             "application_angle": "Angle"} for url in urls]}

    monkeypatch.setattr(career_agent, "_openai_json", fake_model)
    briefs = career_agent.generate_briefs(jobs, "Profil de test")
    assert [item["job"].url for item in briefs] == [jobs[1].url, jobs[2].url, jobs[3].url]
    assert "Stage" in career_agent.render_briefs(briefs)
    assert "Résumé fondé sur les seules métadonnées" in career_agent.render_briefs(briefs)


def test_brief_labels_inferred_date_and_secondary_role_without_inventing_start():
    from dataclasses import replace

    offer = replace(job("FO Controls on Fixed Income", "https://example.com/controls", "2026-10-25"),
                    start_period="", published_inferred=True)
    rendered = career_agent.render_briefs([{
        "job": offer, "evidence_quality": "listing_only",
        "candidate_record": {"target_roles": ["Fixed Income Sales"]},
        "brief": {"fit_summary": "Le titre mentionne Fixed Income.", "match_points": [],
                  "role_signals": ["Mission non confirmée"], "questions_to_check": [],
                  "application_angle": "Relie ton expérience Sales au produit mentionné."},
    }])
    assert "Piste secondaire pour ton objectif" in rendered
    assert "Détectée 2026-10-25" in rendered
    assert "Début à confirmer" in rendered
    assert "Mission non confirmée" not in rendered
    assert "Publiée aujourd’hui" not in rendered


def test_product_target_changes_ranking_and_explains_secondary_offer():
    profile = {"target_roles": ["Fixed Income Sales"], "locations": ["Paris"],
               "contracts": ["Stage"], "start_month": "2027-04", "end_month": "2027-09"}
    fixed = job("Fixed Income Sales Assistant", "https://example.com/fixed", "2026-10-24", score=80)
    fx = job("FX Sales Assistant", "https://example.com/fx", "2026-10-24", score=160)
    controls = job("FO Controls on Fixed Income", "https://example.com/controls", "2026-10-24")
    ranked = career_agent.rank_candidate_pool([fx, controls, fixed], today=date(2026, 10, 25), profile=profile)
    assert ranked[0].url == fixed.url
    assert fx in ranked and controls in ranked
    assert career_agent.profile_match_details(fixed, profile)[0] == "Correspond à ton métier cible"
    label, reasons, checks = career_agent.profile_match_details(fx, profile)
    assert label == "Piste secondaire pour ton objectif"
    assert any("FX" in check and "Fixed Income" in check for check in checks)
    assert any("Paris" in reason for reason in reasons)
    assert career_agent.profile_match_details(controls, profile)[0] == "Piste secondaire pour ton objectif"
    assert "Publiée" not in " ".join(reasons + checks)


def test_quant_target_is_distinguished_from_sales():
    quant = job("Quantitative Research Intern", "https://example.com/quant", "2026-10-24")
    sales = job("Equity Sales Intern", "https://example.com/sales", "2026-10-24")
    profile = {"target_roles": ["Quantitative Research"], "locations": ["Paris"],
               "contracts": ["Stage"]}
    ranked = career_agent.rank_candidate_pool([sales, quant], today=date(2026, 10, 25), profile=profile)
    assert ranked[0].url == quant.url
    assert career_agent.profile_match_details(quant, profile)[0] == "Correspond à ton métier cible"
    assert career_agent.profile_match_details(sales, profile)[0] != "Correspond à ton métier cible"


def test_job_evidence_marks_404_as_unavailable(monkeypatch):
    class Response:
        status_code = 404

    monkeypatch.setattr(career_agent.requests, "get", lambda *args, **kwargs: Response())
    _, quality = career_agent.job_evidence(job("FX Sales", "https://jobs.smartrecruiters.com/Bank/missing", "2026-10-24"))
    assert quality == "unavailable"


def test_job_evidence_does_not_fetch_untrusted_urls(monkeypatch):
    def fail_if_requested(*args, **kwargs):
        raise AssertionError("untrusted URL must not be fetched")
    monkeypatch.setattr(career_agent.requests, "get", fail_if_requested)
    _, quality = career_agent.job_evidence(job("FX Sales", "https://example.com/private", "2026-10-24"))
    assert quality == "listing_only"


def test_job_evidence_distinguishes_restricted_access_from_temporary_errors(monkeypatch):
    class Response:
        def __init__(self, status_code):
            self.status_code = status_code
        def raise_for_status(self):
            if self.status_code >= 400:
                raise career_agent.requests.HTTPError()
    monkeypatch.setattr(career_agent.requests, "get", lambda *args, **kwargs: Response(403))
    _, restricted = career_agent.job_evidence(job("FX Sales", "https://jobs.smartrecruiters.com/Bank/restricted", "2026-10-24"))
    assert restricted == "access_limited"
    monkeypatch.setattr(career_agent.requests, "get", lambda *args, **kwargs: Response(503))
    _, temporary = career_agent.job_evidence(job("FX Sales", "https://jobs.smartrecruiters.com/Bank/temporary", "2026-10-24"))
    assert temporary == "temporary_error"


def test_english_letter_and_review_flags(monkeypatch):
    offer = job("Fixed Income Sales", "https://example.com/fixed", "2026-10-24")
    monkeypatch.setattr(career_agent, "job_evidence", lambda item: ("Visible facts", "listing_only"))

    def fake_model(name, schema, instructions, payload):
        assert payload["letter_language"] == "English"
        assert "polished English" in instructions
        assert "exactement quatre paragraphes" in instructions
        return {"subject": "Application for Fixed Income Sales", "salutation": "Dear Hiring Team,",
                "paragraphs": ["I am interested in this position.", "My experience is relevant.",
                               "I can contribute to the desk.", "I would welcome a conversation."],
                "closing": "Yours faithfully,"}

    monkeypatch.setattr(career_agent, "_openai_json", fake_model)
    letter = career_agent.generate_letter(offer, "SKEMA student", "Théo Caruana", language="English")
    assert "Subject : Application - Fixed Income Sales" in letter
    assert "Subject : Subject :" not in letter
    assert "Dear Hiring Team," in letter
    assert "convention" in " ".join(career_agent.letter_review_flags(offer, letter)).lower()


def test_french_letter_uses_formal_address_and_normalized_role(monkeypatch):
    offer = job("Stage - 6 mois - Assistant Sales F/H", "https://example.com/sales", "2026-10-25")
    monkeypatch.setattr(career_agent, "job_evidence", lambda item: ("Annonce avec missions explicites", "full_description"))

    def fake_model(name, schema, instructions, payload):
        assert payload["letter_language"] == "Français"
        assert "vouvoie toujours le recruteur" in instructions
        assert payload["candidate_name"] == "Théo Caruana"
        return {"subject": "ignored by design", "salutation": "Madame, Monsieur,",
                "paragraphs": ["Première expérience en lien avec l'annonce.",
                               "Deuxième expérience en lien avec les missions.",
                               "Compétences appliquées au contexte du poste.",
                               "Motivation précise pour cette équipe.\nThéo Caruana"],
                "closing": "Je vous prie d’agréer, Madame, Monsieur, mes salutations distinguées."}

    monkeypatch.setattr(career_agent, "_openai_json", fake_model)
    letter = career_agent.generate_letter(offer, "Expérience Sales avérée", "Théo Caruana")
    assert "Objet : Candidature - Assistant Sales" in letter
    assert letter.endswith("Théo Caruana")
    assert letter.count("Théo Caruana") == 2
    assert offer.title == "Stage - 6 mois - Assistant Sales F/H"


def test_draft_is_kept_per_offer_and_requires_selected_offer():
    first = "https://example.com/first"
    second = "https://example.com/second"
    drafts = career_agent.save_letter_draft({}, first, {first, second}, "Edited first letter")
    drafts = career_agent.save_letter_draft(drafts, second, {first, second}, "Edited second letter")
    assert career_agent.saved_letter(drafts, first) == "Edited first letter"
    assert career_agent.saved_letter(drafts, second) == "Edited second letter"
    try:
        career_agent.save_letter_draft(drafts, "https://example.com/unknown", {first, second}, "Text")
    except career_agent.CareerAgentError:
        pass
    else:
        raise AssertionError("An unrelated offer must not receive a saved draft")


def test_openai_request_uses_structured_output_without_storing_profile(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-only-key")
    captured = {}

    class Response:
        status_code = 200

        def json(self):
            return {"output": [{"type": "message", "content": [
                {"type": "output_text", "text": json.dumps({"ok": True})}
            ]}]}

    def fake_post(url, **kwargs):
        captured.update(kwargs)
        assert url == "https://api.openai.com/v1/responses"
        return Response()

    monkeypatch.setattr(career_agent.requests, "post", fake_post)
    assert career_agent._openai_json("test", {"type": "object"}, "instructions", {"profile": "private"}) == {"ok": True}
    assert captured["json"]["store"] is False
    assert captured["json"]["text"]["format"]["type"] == "json_schema"
    assert captured["json"]["input"] == '{"profile": "private"}'


def test_export_letter_pdf_preserves_edited_content():
    path = career_agent.export_letter_pdf(
        "Prénom Nom\n\nObjet : Stage en Trading\n\nMadame, Monsieur,\n\nTexte modifié par le candidat.",
        "Banque Test",
        candidate="Prénom Nom", job_title="Stage en Trading",
    )
    with open(path, "rb") as output:
        assert output.read(4) == b"%PDF"


def test_document_title_normalization_does_not_change_offer_title():
    offer = job("Stage - 6 mois - Assistant Syndication Obligataire F/H",
                "https://example.com/dcm", "2026-10-25")
    assert career_agent.normalize_job_title_for_documents(offer.title) == "Assistant Syndication Obligataire"
    assert offer.title == "Stage - 6 mois - Assistant Syndication Obligataire F/H"


def test_pdf_export_uses_profile_name_language_and_current_editor_text():
    from pypdf import PdfReader

    for language, expected_name, label in (
        ("Français", "Theo_Caruana_LM_Societe_Generale.pdf", "Objet"),
        ("English", "Theo_Caruana_CL_Societe_Generale.pdf", "Subject"),
    ):
        salutation = "Dear Hiring Team," if language == "English" else "Madame, Monsieur,"
        edited = "Edited text in the editor." if language == "English" else "Texte modifié dans l’éditeur."
        signoff = "Yours faithfully," if language == "English" else "Veuillez agréer mes salutations distinguées."
        letter = ("Théo Caruana\n\nSociété Générale\n\n26 October 2026\n\n"
                  f"{label} : Application - Assistant Sales\n\n"
                  f"{salutation}\n\n{edited}\n\n{signoff}\n\nThéo Caruana")
        path = career_agent.export_letter_pdf(
            letter, "Société Générale", candidate="Théo Caruana",
            job_title="Stage - Assistant Sales F/H", language=language,
        )
        assert path.split("\\")[-1] == expected_name
        text = "\n".join(page.extract_text() or "" for page in PdfReader(path).pages)
        assert edited in text
        assert "Théo Caruana" in text
        assert label + ": Application - Assistant Sales" in text
        assert "**" not in text and "```" not in text
