"""Outreach tests use only local fixtures and a simulated transport."""

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from internships_project import mail_outreach, state_store


@pytest.fixture
def account(tmp_path, monkeypatch):
    monkeypatch.setattr(state_store, "USER_DB_PATH", tmp_path / "accounts.sqlite3")
    return "alice"


def _contact(key="one", **overrides):
    item = {"id": key, "name": "Alex Martin", "role": "Rates Sales", "company": "BNP Paribas",
            "location": "Paris", "linkedin_url": f"https://www.linkedin.com/in/{key}",
            "email": "alex.martin@bnpparibas.com", "template": "BNP Paribas",
            "address_status": "supposée", "subject": "Candidature spontanée",
            "body": "Bonjour, je suis étudiant à SKEMA et recherche un stage en Sales. Cordialement, Alex.",
            "delivery": "brouillon", "conversation": "À contacter", "sent_at": "",
            "followup_days": "7", "followup_due": "", "followup_subject": "Re: Candidature spontanée",
            "followup_body": "Bonjour, je reviens vers vous concernant ma demande. Merci.",
            "auto_followup": False, "approved": False}
    return {**item, **overrides}


def _review(account, keys, cv=None):
    return mail_outreach.review_signature(state_store.load_user_data(account, "mail_contacts"), keys, cv)


def test_templates_are_exactly_scoped_and_initials_are_never_completed(account):
    registry = mail_outreach.templates_for(account)
    entry = mail_outreach.matching_template("BNP Paribas CIB", registry)
    assert entry["documented"] and entry["source_url"] and entry["verified_on"]
    assert mail_outreach.matching_template("BNP Paribas Asset Management", registry) is None
    assert mail_outreach.propose_address("Élodie Martin", entry)[0] == "elodie.martin@bnpparibas.com"
    assert mail_outreach.propose_address("Samir L.", entry)[0] == ""
    assert mail_outreach.propose_address("Anne-Marie Martin", entry)[0] == ""
    assert mail_outreach.propose_address("Cam Trew", registry["Kepler Cheuvreux"])[0] == ""


def test_import_deduplicates_linkedin_urls_and_keeps_accounts_separate(account, monkeypatch):
    extracted = _contact()
    extracted["pdf_hash"] = "hash"
    extracted["filename"] = "profile.pdf"
    monkeypatch.setattr(mail_outreach, "extract_contact", lambda data, filename: dict(extracted))
    candidate = {"target_roles": ["Sales"], "overview": "Étudiant à SKEMA"}
    records, notices = mail_outreach.import_contacts(account,
                                                      [("one.pdf", b"pdf"), ("two.pdf", b"pdf")],
                                                      candidate)
    assert len(records) == 1
    imported = next(iter(records.values()))
    assert imported["email"] == "" and imported["email_status"] == "non_renseigne"
    assert imported["subject"] == imported["body"] == ""
    assert imported["delivery"] == "not_requested"
    assert imported["conversation"] == "Non contacté"
    assert any("déjà" in notice for notice in notices)
    assert state_store.load_user_data("bob", "mail_contacts") == {}


def test_explicit_batch_validation_and_simulated_sending(account, monkeypatch):
    state_store.save_user_data(account, "mail_contacts", {"one": _contact()})
    monkeypatch.setattr(mail_outreach, "_validate_sender", lambda: None)
    sent = []
    monkeypatch.setattr(mail_outreach, "_provider_send",
                        lambda recipient, subject, body, cv: sent.append((recipient, subject, cv)))
    with pytest.raises(ValueError, match="Confirme"):
        mail_outreach.approve_and_start(account, ["one"], None, confirmed=False,
                                        review_token=_review(account, ["one"]))
    assert sent == []
    cv = ("CV.pdf", b"%PDF-1.4")
    assert mail_outreach.approve_and_start(account, ["one"], cv, confirmed=True,
                                           review_token=_review(account, ["one"], cv)) == 1
    mail_outreach._WORKERS[account].join(timeout=3)
    assert sent == [("alex.martin@bnpparibas.com", "Candidature spontanée", ("CV.pdf", b"%PDF-1.4"))]
    item = state_store.load_user_data(account, "mail_contacts")["one"]
    assert item["delivery"] == "envoyé" and item["sent_at"]
    with pytest.raises(ValueError, match="déjà"):
        mail_outreach.approve_and_start(account, ["one"], None, confirmed=True,
                                        review_token=_review(account, ["one"]))


def test_uncertain_delivery_is_not_retried(account, monkeypatch):
    state_store.save_user_data(account, "mail_contacts", {"one": _contact()})
    monkeypatch.setattr(mail_outreach, "_validate_sender", lambda: None)
    calls = []

    def fails(*args):
        calls.append(args)
        raise TimeoutError("No acknowledgement")

    monkeypatch.setattr(mail_outreach, "_provider_send", fails)
    mail_outreach.approve_and_start(account, ["one"], None, confirmed=True,
                                    review_token=_review(account, ["one"]))
    mail_outreach._WORKERS[account].join(timeout=3)
    item = state_store.load_user_data(account, "mail_contacts")["one"]
    assert item["delivery"] == "résultat incertain" and len(calls) == 1
    with pytest.raises(ValueError):
        mail_outreach.approve_and_start(account, ["one"], None, confirmed=True,
                                        review_token=_review(account, ["one"]))


def test_batch_rejects_duplicate_recipient_address(account, monkeypatch):
    state_store.save_user_data(account, "mail_contacts", {
        "one": _contact("one"), "two": _contact("two")})
    monkeypatch.setattr(mail_outreach, "_validate_sender", lambda: None)
    with pytest.raises(ValueError, match="même adresse"):
        mail_outreach.approve_and_start(account, ["one", "two"], None, confirmed=True,
                                        review_token=_review(account, ["one", "two"]))


def test_review_invalidated_by_message_or_attachment_change(account, monkeypatch):
    state_store.save_user_data(account, "mail_contacts", {"one": _contact()})
    monkeypatch.setattr(mail_outreach, "_validate_sender", lambda: None)
    token = _review(account, ["one"], ("CV.pdf", b"%PDF-one"))
    with pytest.raises(ValueError, match="changé"):
        mail_outreach.approve_and_start(account, ["one"], ("CV.pdf", b"%PDF-two"),
                                        confirmed=True, review_token=token)
    mail_outreach.update_contact(account, "one", {"body": "Autre message"})
    with pytest.raises(ValueError, match="changé"):
        mail_outreach.approve_and_start(account, ["one"], ("CV.pdf", b"%PDF-one"),
                                        confirmed=True, review_token=token)


def test_send_rejects_attachment_claim_without_cv(account, monkeypatch):
    state_store.save_user_data(account, "mail_contacts", {
        "one": _contact(body="Bonjour, je joins mon CV. Cordialement.")})
    monkeypatch.setattr(mail_outreach, "_validate_sender", lambda: None)
    with pytest.raises(ValueError, match="aucun CV"):
        mail_outreach.approve_and_start(account, ["one"], None, confirmed=True,
                                        review_token=_review(account, ["one"]))


def test_incomplete_identity_and_unknown_format_are_distinguished():
    assert "Identité incomplète" in mail_outreach.contact_blocker({"name": "Samir L", "email": ""})
    assert "Format d'entreprise inconnu" in mail_outreach.contact_blocker({"name": "Samir Lemaire", "email": ""})


def test_supplied_linkedin_pdf_current_job_and_annotation_link():
    pdf = Path.home() / "Downloads" / "Profile (3).pdf"
    if not pdf.is_file():
        pytest.skip("PDF fourni disponible uniquement sur le poste local")
    item = mail_outreach.extract_contact(pdf.read_bytes(), pdf.name)
    assert item["name"] == "Samir L"
    assert item["role"] == "Cross-Asset Structurer"
    assert item["company"] == "Lynceus Partners"
    assert item["location"].startswith("Paris,")
    assert item["linkedin_url"].endswith("samir-l-b9a889b7")
    assert "Natixis" in item["experiences"]
    assert "2019" in item["experiences"]
    assert mail_outreach.propose_address(item["name"], mail_outreach.DEFAULT_TEMPLATES["Natixis"])[0] == ""


def test_mail_prompt_keeps_identities_verified_overlap_and_attachment(monkeypatch):
    from internships_project import career_agent
    captured = {}

    def fake_model(name, schema, instructions, payload):
        captured.update(name=name, instructions=instructions, payload=payload)
        return {"subject": "Candidature spontanée", "body": "Bonjour, candidature.",
                "followup_body": "Bonjour, je reviens sur ma candidature."}

    monkeypatch.setattr(career_agent, "_openai_json", fake_model)
    candidate = {"name": "Camille Test", "source_text": "Étudiant à SKEMA, stage Sales chez Natixis.",
                 "target_roles": ["Sales"], "start_window": "Mai 2027"}
    contact = {"name": "Alex Martin", "role": "Structurer", "company": "Lynceus Partners",
               "experiences": "Lynceus Partners\nStructurer\n2021 - Present\nNatixis\nSales\n2019"}
    mail_outreach.draft_mail(contact, candidate, "Français", cv_attached=False)
    assert captured["name"] == "speculative_mail"
    assert captured["payload"]["recipient"]["name"] == "Alex Martin"
    assert captured["payload"]["shared_employers"] == ["Natixis"]
    assert captured["payload"]["cv_attached"] is False
    assert "only when cv_attached is true" in captured["instructions"]


def test_followup_requires_opt_in_and_stops_after_response(account, monkeypatch):
    yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).date().isoformat()
    initial = _contact(delivery="envoyé", sent_at="2026-10-01T12:00:00+00:00",
                       followup_due=yesterday, conversation="En attente")
    state_store.save_user_data(account, "mail_contacts", {"one": initial})
    monkeypatch.setattr(mail_outreach, "_validate_sender", lambda: None)
    sent = []
    monkeypatch.setattr(mail_outreach, "_provider_send", lambda *args: sent.append(args))
    assert mail_outreach.send_due_followups() == 0
    mail_outreach.update_contact(account, "one", {"auto_followup": True, "conversation": "Réponse"})
    assert mail_outreach.send_due_followups() == 0
    assert sent == []


def test_followup_sends_once_after_explicit_opt_in(account, monkeypatch):
    yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).date().isoformat()
    initial = _contact(delivery="envoyé", sent_at="2026-10-01T12:00:00+00:00",
                       followup_due=yesterday, conversation="En attente", auto_followup=True)
    state_store.save_user_data(account, "mail_contacts", {"one": initial})
    monkeypatch.setattr(mail_outreach, "_validate_sender", lambda: None)
    sent = []
    monkeypatch.setattr(mail_outreach, "_provider_send", lambda *args: sent.append(args))
    monkeypatch.setenv("INTERNSHIPS_MAIL_DELAY_SECONDS", "0")
    # Avoid the production pacing delay in this isolated simulation.
    monkeypatch.setattr(mail_outreach.threading, "Event", lambda: type("NoWait", (), {"wait": lambda self, seconds: None})())
    assert mail_outreach.send_due_followups() == 1
    assert mail_outreach.send_due_followups() == 0
    assert len(sent) == 1 and sent[0][-1] is None
