from copy import deepcopy
from unittest.mock import Mock

import pytest

from internships_project import email_alerts
from scripts import notify_internships_pages as alerts


def snapshot(*titles):
    return {"updated": "2026-11-11T12:00:00+00:00", "generated": "2026-11-11T12:01:00+00:00",
            "sources": {"checked": 1, "unavailable": 0, "retained": 0},
            "offers": [{"title": title, "company": "BNP Paribas", "location": "Paris", "kind": "Stage",
                        "url": "https://careers.example.com/jobs/" + str(index), "published": "2026-11-11",
                        "date_label": "Publiée le 11 novembre 2026", "start": "avril 2027", "start_month": "2027-04",
                        "family": "Sales", "logo": "", "categories": ["Stages Paris"]}
                       for index, title in enumerate(titles)]}


class FakeLedger:
    def __init__(self):
        self.state = None

    def read(self):
        return deepcopy(self.state)

    def write(self, seen):
        self.state = {"version": 1, "seen": sorted(seen), "updated": "2026-11-11T12:00:00+00:00"}


@pytest.fixture(autouse=True)
def configuration(monkeypatch):
    config = email_alerts.MailConfig("owner@example.com", "alerts@example.com", "smtp.example.com", 465,
                                    "alerts@example.com", "example-password", "ssl")
    monkeypatch.setattr(email_alerts, "_configuration", lambda **kw: config)


def test_baseline_is_silent_then_one_digest_and_no_repeat():
    ledger = FakeLedger()
    send = Mock()
    assert alerts.notify(snapshot("Sales Rates"), ledger, send=send) == 0
    send.assert_not_called()
    assert alerts.notify(snapshot("Sales Rates", "Sales Credit", "Equity Sales"), ledger, send=send) == 2
    send.assert_called_once()
    message = send.call_args.args[1]
    assert "2 nouvelles" in message["Subject"]
    assert "Sales Credit" in message.get_body(preferencelist=("plain",)).get_content()
    assert "Sales Rates" not in message.get_body(preferencelist=("plain",)).get_content()
    assert alerts.notify(snapshot("Sales Rates", "Sales Credit", "Equity Sales"), ledger, send=send) == 0
    assert send.call_count == 1
    assert all(len(key) == 64 for key in ledger.state["seen"])
    assert "owner@example.com" not in str(ledger.state)


def test_failed_email_is_not_recorded_and_can_retry():
    ledger = FakeLedger()
    alerts.notify(snapshot("Sales Rates"), ledger, send=Mock())
    previous = deepcopy(ledger.state)
    with pytest.raises(OSError):
        alerts.notify(snapshot("Sales Rates", "Equity Sales"), ledger, send=Mock(side_effect=OSError("unavailable")))
    assert ledger.state == previous
    assert alerts.notify(snapshot("Sales Rates", "Equity Sales"), ledger, send=Mock()) == 1


def test_same_offer_from_another_source_or_paris_suburb_is_not_new():
    ledger = FakeLedger()
    alerts.notify(snapshot("Sales Rates"), ledger, send=Mock())
    duplicate = snapshot("Sales Rates")
    duplicate["offers"][0].update(company="BNP Paribas CIB", location="La Défense",
                                 url="https://other.example.com/job")
    send = Mock()
    assert alerts.notify(duplicate, ledger, send=send) == 0
    send.assert_not_called()


def test_location_display_change_does_not_send_existing_foreign_offer_again():
    original=snapshot('Sales Rates')
    original['offers'][0].update(location='London, GBR',categories=['Stages International'])
    ledger=FakeLedger()
    alerts.notify(original,ledger,send=Mock())
    normalized=deepcopy(original)
    normalized['offers'][0].update(location='Londres · Royaume-Uni',location_source='London, GBR')
    send=Mock()
    assert alerts.notify(normalized,ledger,send=send)==0
    send.assert_not_called()
    assert alerts.public_offers(normalized).keys()==alerts.public_offers(original).keys()


def test_sitemap_only_jobteaser_links_do_not_trigger_unverified_alerts():
    data = snapshot("Sales Rates")
    data["offers"][0]["url"] = "https://www.jobteaser.com/fr/job-offers/example"
    assert alerts.public_offers(data) == {}


def test_disabling_email_never_uses_delivery_or_ledger(monkeypatch):
    monkeypatch.setattr(email_alerts, "_configuration", lambda **kw: None)
    ledger = Mock()
    assert alerts.notify(snapshot("Sales Rates"), ledger, send=Mock()) == 0
    ledger.read.assert_not_called()
