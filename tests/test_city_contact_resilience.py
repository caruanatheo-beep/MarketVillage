"""Malformed saved records cannot hide usable contacts; no stored data is read."""

import asyncio
from copy import deepcopy
from types import SimpleNamespace

import pytest
from pydantic_ai.models.test import TestModel

from internships_project import city_agents, city_services, state_store


def saved_contacts(monkeypatch, contacts):
    def load(username, kind):
        assert kind == "mail_contacts"
        return contacts if username == "synthetic-owner" else {}

    monkeypatch.setattr(state_store, "load_user_data", load)
    monkeypatch.setattr(state_store, "save_user_data",
                        lambda *args, **kwargs: pytest.fail("Consultation must not write contacts"))


def test_search_paginates_valid_contacts_and_reports_malformed_records(monkeypatch):
    contacts = {str(i): {"name": f"Contact {i:02}", "company": "Crédit Test", "role": "FX"}
                for i in range(14)}
    contacts.update({"null": None, "list": ["FX"], "text": "FX", "number": 42, "flag": True})
    before = deepcopy(contacts)
    saved_contacts(monkeypatch, contacts)

    pages = [city_services.network_contacts("synthetic-owner", "credit FX", page) for page in (1, 2)]

    assert [page["count"] for page in pages] == [12, 2]
    assert [page["has_more"] for page in pages] == [True, False]
    assert all(page["total_matches"] == 14 for page in pages)
    assert len({row["id"] for page in pages for row in page["contacts"]}) == 14
    assert all("5 fiche(s)" in page["warning"] for page in pages)
    assert all(set(row["matched_fields"]) == {"company", "role"}
               for page in pages for row in page["contacts"])
    assert city_services.network_contacts("synthetic-other")["count"] == 0
    assert contacts == before


@pytest.mark.parametrize("contacts,expected_text,warning", [
    ({}, "Aucun contact enregistré.", False),
    ({"broken": None}, "Aucune fiche de contact lisible.", True),
])
def test_empty_and_unreadable_directories_are_distinguished(monkeypatch, contacts, expected_text, warning):
    saved_contacts(monkeypatch, contacts)

    result = city_services.network_contacts("synthetic-owner")

    assert result["contacts"] == []
    assert result["total_matches"] == 0
    assert not result["has_more"]
    assert result["text"].startswith(expected_text)
    assert ("format invalide" in result["warning"]) == warning


@pytest.mark.parametrize("broken", [None, [], "invalid", 42, False])
def test_lina_tools_keep_valid_results_and_explain_unreadable_selected_contact(monkeypatch, broken):
    saved_contacts(monkeypatch, {"valid": {"name": "Synthetic contact"}, "broken": broken})
    agent = city_agents.build_agent("networker", TestModel())
    ctx = SimpleNamespace(deps=city_agents.ChatDeps("synthetic-owner", None))
    search = agent._function_toolset.tools["search_saved_contacts"].function
    read = agent._function_toolset.tools["read_contact_profile"].function

    result = asyncio.run(search(ctx))
    assert result["status"] == "completed"
    assert [row["id"] for row in result["data"]["contacts"]] == ["valid"]
    assert "1 fiche(s)" in result["data"]["warning"]
    result = asyncio.run(read(ctx, "broken"))
    assert result["status"] == "unavailable"
    assert "illisible" in result["reason"]
    assert asyncio.run(read(ctx, "valid"))["data"]["name"] == "Synthetic contact"
    missing = asyncio.run(read(ctx, "missing"))
    assert missing["status"] == "unavailable"
    assert "pas enregistré" in missing["reason"]
