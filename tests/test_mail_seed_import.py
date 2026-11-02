"""Persistence and idempotence checks for the supplied Paris contacts dataset."""

import csv

import pytest

from internships_project import mail_outreach, state_store


@pytest.fixture
def account(tmp_path, monkeypatch):
    monkeypatch.setattr(state_store, "USER_DB_PATH", tmp_path / "accounts.sqlite3")
    return "seed-test"


def test_seed_dataset_is_single_source_complete_and_starts_uncontacted(account, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Contact seed must not propose addresses, draft, or send mail")

    monkeypatch.setattr(mail_outreach, "propose_address", forbidden)
    monkeypatch.setattr(mail_outreach, "draft_mail", forbidden)
    monkeypatch.setattr(mail_outreach, "_provider_send", forbidden)

    contacts, tally = mail_outreach.import_seed_contacts(account)
    persisted = state_store.load_user_data(account, "mail_contacts")
    imported = [item for item in persisted.values() if item.get("seed_dataset") == "contacts_50_paris"]

    assert tally["read"] == tally["created"] == 50
    assert tally["matched"] == tally["conflicts"] == tally["rejected"] == 0
    assert len(imported) == 50
    assert len({item["external_id"] for item in imported}) == 50
    assert all(item["verification_status"] == "À vérifier" for item in imported)
    assert all(item["conversation"] == item["outreach_status"] == "Non contacté" for item in imported)
    assert all(item["contract_type"] == "Non confirmé" for item in imported)
    assert all(item["email"] == "" and item["email_status"] == "non_renseigne" for item in imported)
    assert all(item["last_verified_at"] == "" and item["subject"] == item["body"] == "" for item in imported)
    assert all(item["source_url"] and item["source_type"] and item["source_notes"] for item in imported)
    assert len([item for item in imported if item["company"] == "Citi"]) == 3
    assert len({item["source_url"] for item in imported if item["company"] == "Citi"}) == 1
    assert len(contacts) == 50


def test_second_import_is_idempotent_and_preserves_manual_changes_and_history(account):
    contacts, first = mail_outreach.import_seed_contacts(account)
    assert first["created"] == 50
    key = next(key for key, item in contacts.items() if item.get("external_id") == "PARIS-MKT-001")
    mail_outreach.update_contact(account, key, {
        "name": "Théo Levi (corrigé)", "location": "Paris (confirmé manuellement)",
        "verification_status": "Vérifié", "last_verified_at": "2026-10-29",
        "contract_type": "CDI", "email": "theo.levi@example.org", "email_status": "publiée",
        "conversation": "En attente", "subject": "Objet sauvegardé", "body": "Brouillon conservé",
    })
    records = state_store.load_user_data(account, "mail_contacts")
    records[key]["sent_at"] = "2026-10-28T12:00:00+00:00"
    records[key]["followup_due"] = "2026-11-11"
    records[key]["send_history"] = [{"at": "2026-10-28", "result": "simulation"}]
    state_store.save_user_data(account, "mail_contacts", records)

    _, second = mail_outreach.import_seed_contacts(account)
    saved = state_store.load_user_data(account, "mail_contacts")
    item = saved[key]

    assert second["read"] == second["matched"] == 50
    assert second["unchanged"] == 49
    assert second["created"] == second["rejected"] == 0
    assert second["conflicts"] == 1
    assert item["name"] == "Théo Levi (corrigé)"
    assert item["location"] == "Paris (confirmé manuellement)"
    assert item["verification_status"] == "Vérifié" and item["last_verified_at"] == "2026-10-29"
    assert item["contract_type"] == "CDI" and item["email"] == "theo.levi@example.org"
    assert item["email_status"] == "publiée" and item["conversation"] == "En attente"
    assert item["subject"] == "Objet sauvegardé" and item["body"] == "Brouillon conservé"
    assert item["sent_at"] == "2026-10-28T12:00:00+00:00"
    assert item["followup_due"] == "2026-11-11" and item["send_history"] == [{"at": "2026-10-28", "result": "simulation"}]
    assert len([row for row in saved.values() if row.get("seed_dataset") == "contacts_50_paris"]) == 50


def test_seed_filters_and_excel_compatible_source_data(account):
    mail_outreach.import_seed_contacts(account)
    all_rows, counts = mail_outreach.dashboard(account)
    citi_rows, _ = mail_outreach.dashboard(account, filters={"company": "Citi"})
    paris_rows, _ = mail_outreach.dashboard(account, filters={"location": "Paris"})
    verified_rows, _ = mail_outreach.dashboard(account, filters={"verification": "Vérifié"})

    assert len(all_rows) == 50
    assert len(citi_rows) == 3
    assert len(paris_rows) == 34
    assert verified_rows == []
    assert counts["à vérifier"] == counts["sans adresse"] == counts["non contacté"] == 50
    assert all(len(row) == 13 for row in all_rows)


def test_seed_matches_existing_linkedin_contact_without_overwriting_it(account):
    with mail_outreach.SEED_CONTACTS_PATH.open("r", encoding="utf-8-sig", newline="") as source:
        row = next(csv.DictReader(source, delimiter=";"))
    key = "existing-contact"
    state_store.save_user_data(account, "mail_contacts", {key: {
        "id": key, "name": f"{row['first_name']} {row['last_name']}", "role": row["job_title"],
        "company": row["company"], "linkedin_url": row["source_url"], "location": "Lieu corrigé",
        "email": "contact@example.org", "email_status": "publiée", "subject": "Objet manuel",
        "body": "Brouillon manuel", "delivery": "brouillon", "conversation": "En attente",
        "notes": "Note privée", "sent_at": "2026-10-28", "send_history": [{"id": "historic"}],
    }})

    records, first = mail_outreach.import_seed_contacts(account)
    item = records[key]
    assert first["created"] == 49 and first["matched"] == 1
    assert first["conflicts"] == 1 and first["rejected"] == 0
    assert item["external_id"] == row["id"]
    assert item["email"] == "contact@example.org" and item["email_status"] == "publiée"
    assert item["subject"] == "Objet manuel" and item["body"] == "Brouillon manuel"
    assert item["delivery"] == "brouillon" and item["conversation"] == "En attente"
    assert item["location"] == "Lieu corrigé" and item["notes"] == "Note privée"
    assert item["sent_at"] == "2026-10-28" and item["send_history"] == [{"id": "historic"}]
    assert item["source_url"] == row["source_url"]

    _, second = mail_outreach.import_seed_contacts(account)
    assert second["created"] == 0 and second["matched"] == 50 and second["unchanged"] == 49
    assert second["conflicts"] == 1


def test_duplicate_identity_normalization_is_only_used_for_matching():
    assert mail_outreach._contact_identity_key("Élodie Martin", "SG CIB") == (
        mail_outreach._contact_identity_key("elodie martin", "Société Générale")[0], "societe generale")
    assert mail_outreach._contact_identity_key("Alex Smith", "BNP Paribas CIB") == (
        "alex smith", "bnp paribas")

