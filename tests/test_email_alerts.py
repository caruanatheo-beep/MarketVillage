"""No real SMTP traffic: verify the notification decision and retry behavior."""

from dataclasses import replace
from datetime import datetime, timezone
from email.message import EmailMessage

from internships_project import email_alerts, internships, state_store
from internships_project.internships import Opportunity


def _job(title: str, url: str, **changes) -> Opportunity:
    job = Opportunity(
        title=title, company="BNP Paribas", location="Paris", kind="Stage",
        url=url, published="2026-10-28", score=10, source="Employeur",
    )
    return replace(job, **changes)


def _configure(monkeypatch, tmp_path):
    monkeypatch.setattr(state_store, "USER_DB_PATH", tmp_path / "accounts.sqlite3")
    monkeypatch.setenv("INTERNSHIPS_EMAIL_ALERTS_ENABLED", "1")
    monkeypatch.setenv("INTERNSHIPS_ALERT_EMAIL_TO", "test@example.org")
    monkeypatch.setenv("INTERNSHIPS_ALERT_EMAIL_FROM", "alerts@example.org")
    monkeypatch.setenv("INTERNSHIPS_SMTP_HOST", "smtp.example.org")
    monkeypatch.setenv("INTERNSHIPS_SMTP_USERNAME", "smtp-user")
    monkeypatch.setenv("INTERNSHIPS_SMTP_PASSWORD", "smtp-password")
    monkeypatch.setenv("INTERNSHIPS_SMTP_SECURITY", "starttls")


def test_first_collection_is_baseline_then_one_digest_for_new_offers(tmp_path, monkeypatch):
    _configure(monkeypatch, tmp_path)
    sent = []
    monkeypatch.setattr(email_alerts, "_send_message", lambda config, message: sent.append(message))
    old = _job("Sales Intern", "https://example.org/jobs/sales")
    new = _job("Trading Intern", "https://example.org/jobs/trading",
               published_inferred=True)
    assert email_alerts.notify_new_offers([old]) == 0
    assert email_alerts.notify_new_offers([old, new]) == 1
    assert email_alerts.notify_new_offers([old, new]) == 0
    assert len(sent) == 1
    plain = sent[0].get_body(preferencelist=("plain",)).get_content()
    html = sent[0].get_body(preferencelist=("html",)).get_content()
    assert "Trading Intern" in plain
    assert "Détectée le 2026-10-28" in plain
    assert "Sales Intern" not in plain
    assert "Trading Intern" in html
    assert "Voir l’offre" in html
    assert "Sales Intern" not in html


def test_failed_delivery_is_retried_and_other_source_does_not_duplicate(tmp_path, monkeypatch):
    _configure(monkeypatch, tmp_path)
    old = _job("Sales Intern", "https://example.org/jobs/sales")
    new = _job("Trading Intern", "https://example.org/jobs/trading")
    assert email_alerts.notify_new_offers([old]) == 0

    def fails(config, message):
        raise OSError("SMTP unavailable")

    monkeypatch.setattr(email_alerts, "_send_message", fails)
    assert email_alerts.notify_new_offers([old, new]) == 0
    sent = []
    monkeypatch.setattr(email_alerts, "_send_message", lambda config, message: sent.append(message))
    assert email_alerts.notify_new_offers([old, new]) == 1
    mirrored = replace(new, company="BNP Paribas CIB", location="La Défense",
                       url="https://other.example.org/jobs/trading")
    assert email_alerts.notify_new_offers([old, mirrored]) == 0
    assert len(sent) == 1


def test_unverified_jobteaser_link_does_not_trigger_an_alert(tmp_path, monkeypatch):
    _configure(monkeypatch, tmp_path)
    sent = []
    monkeypatch.setattr(email_alerts, "_send_message", lambda config, message: sent.append(message))
    sitemap = _job("Sales Intern", "https://www.jobteaser.com/job-offers/sales",
                   source="JobTeaser · sitemap")
    official = _job("Sales Intern", "https://example.org/jobs/sales")
    assert email_alerts.notify_new_offers([sitemap]) == 0
    assert email_alerts.notify_new_offers([official]) == 0
    assert email_alerts.notify_new_offers([official, sitemap]) == 0
    assert sent == []


def test_alerts_stay_disabled_without_explicit_opt_in(tmp_path, monkeypatch):
    _configure(monkeypatch, tmp_path)
    monkeypatch.setenv("INTERNSHIPS_EMAIL_ALERTS_ENABLED", "0")
    sent = []
    monkeypatch.setattr(email_alerts, "_send_message", lambda config, message: sent.append(message))
    assert email_alerts.notify_new_offers([_job("Sales Intern", "https://example.org/jobs/sales")]) == 0
    assert sent == []
    assert not (tmp_path / "accounts.sqlite3").exists()


def test_completed_refresh_calls_alert_handler(tmp_path, monkeypatch):
    job = _job("Sales Intern", "https://example.org/jobs/sales")
    calls = []
    monkeypatch.setattr(internships, "CACHE_PATH", tmp_path / "internships_cache.json")
    monkeypatch.setattr(internships, "_cache", None)
    monkeypatch.setattr(internships, "_last_attempt", None)
    monkeypatch.setattr(internships, "_refresh_previous_jobs", {})
    monkeypatch.setattr(internships, "_force_source_refresh", False)
    monkeypatch.setattr(internships, "_fetch_opportunities", lambda: ([job], []))
    monkeypatch.setattr(email_alerts, "notify_new_offers",
                        lambda jobs, now: calls.append((jobs, now)))
    internships.refresh_opportunities()
    assert len(calls) == 1
    assert calls[0][0][0].url == job.url


def test_smtp_uses_ascii_ehlo_name_when_machine_name_contains_accents(monkeypatch):
    calls = []

    class FakeSMTP:
        def __init__(self, host, port, **kwargs):
            calls.append(kwargs)

        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

        def ehlo(self):
            pass

        def starttls(self, **_):
            pass

        def login(self, *_):
            pass

        def send_message(self, *_args, **_kwargs):
            pass

    monkeypatch.setattr(email_alerts.smtplib, "SMTP", FakeSMTP)
    monkeypatch.setattr(email_alerts.smtplib, "SMTP_SSL", FakeSMTP)
    message = EmailMessage()
    message.set_content("Test")
    for security in ("starttls", "ssl"):
        config = email_alerts.MailConfig(
            recipient="to@example.org", sender="from@example.org",
            host="smtp.example.org", port=587, username="user",
            password="password", security=security,
        )
        email_alerts._send_message(config, message)
    assert [call["local_hostname"] for call in calls] == ["localhost", "localhost"]


def test_html_digest_escapes_offer_data_and_distinguishes_detection():
    job = _job('Sales <script>alert(1)</script>', 'https://example.org/jobs/sales?a=1&b=2',
               company='Bank & Co', published_inferred=True, start_period='',
               family='Sales & Trading')
    message = email_alerts._message([job], 'to@example.org', 'from@example.org')
    html = message.get_body(preferencelist=("html",)).get_content()
    plain = message.get_body(preferencelist=("plain",)).get_content()
    assert 'Bank &amp; Co' in html
    assert '&lt;script&gt;' in html
    assert '<script>' not in html
    assert 'a=1&amp;b=2' in html
    assert 'Détectée le 2026-10-28' in html
    assert 'Début :' not in html
    assert 'https://example.org/jobs/sales?a=1&b=2' in plain


def test_preview_uses_cached_offers_without_changing_alert_history(tmp_path, monkeypatch):
    _configure(monkeypatch, tmp_path)
    cached = [_job(f"Sales Intern {index}", f"https://example.org/jobs/{index}")
              for index in range(4)]
    monkeypatch.setattr(internships, "_read_cache",
                        lambda: (datetime.now(timezone.utc), cached, []))
    sent = []
    monkeypatch.setattr(email_alerts, "_send_message",
                        lambda config, message: sent.append(message))
    assert email_alerts.send_preview_email() == 3
    assert len(sent) == 1
    assert sent[0]["Subject"] == "Aperçu des alertes offres"
    html = sent[0].get_body(preferencelist=("html",)).get_content()
    assert "Sales Intern 0" in html
    assert "Sales Intern 3" not in html
    assert not (tmp_path / "accounts.sqlite3").exists()
