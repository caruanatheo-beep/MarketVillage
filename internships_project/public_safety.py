"""Fail closed before exporting public files. Never print matched credentials."""
import os
import re
import ipaddress
from datetime import datetime
from urllib.parse import parse_qsl, urlsplit

PUBLIC_FIELDS = {"title", "company", "location", "kind", "url", "published", "date_label",
                 "start", "start_month", "family", "logo", "categories"}

SECRET = re.compile(
    rb"(?:(?<![A-Za-z0-9])sk-(?:proj-|svcacct-|ant-)?[A-Za-z0-9_-]{20,}"
    rb"|AIza[A-Za-z0-9_-]{30,}|gh[pousr]_[A-Za-z0-9]{30,}"
    rb"|github_pat_[A-Za-z0-9_]{30,}|hf_[A-Za-z0-9]{25,}"
    rb"|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)"
)


def assert_public(payload: bytes, label: str) -> None:
    if SECRET.search(payload):
        raise ValueError(f"Publication refused: possible credential in {label}")
    for name, value in os.environ.items():
        if len(value) >= 8 and any(word in name.upper() for word in ("API_KEY", "API_TOKEN", "SECRET_KEY", "PASSWORD", "SMTP_USERNAME", "EMAIL_TO", "EMAIL_FROM")):
            if value.encode() in payload:
                raise ValueError(f"Publication refused: environment credential in {label}")


def public_job_url(value: str) -> str:
    parsed = urlsplit(value)
    host = (parsed.hostname or "").lower()
    if (parsed.scheme != "https" or parsed.username or parsed.password
            or parsed.port not in (None, 443) or not host or "." not in host
            or host in {"localhost", "metadata.google.internal"}
            or host.endswith((".local", ".internal"))
            or re.fullmatch(r"[\d.]+", host)):
        raise ValueError("Publication refused: invalid public offer URL")
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        raise ValueError("Publication refused: IP address in offer URL")
    sensitive = {"key", "api_key", "apikey", "token", "access_token", "secret", "password", "authorization", "signature"}
    if any(name.lower() in sensitive for name, _ in parse_qsl(parsed.query)):
        raise ValueError("Publication refused: credential-like offer URL parameter")
    assert_public(value.encode(), "offer URL")
    return value


def company_logo_path(name: str) -> bool:
    return bool(re.fullmatch(r'internships_project/assets/company_logos/[a-z0-9]+(?:[.-][a-z0-9]+)*\.png',name))


def validate_snapshot(data: dict) -> None:
    if set(data) != {"updated", "generated", "sources", "offers"}:
        raise ValueError("Publication refused: unexpected snapshot fields")
    if set(data["sources"]) - {"partial"} != {"checked", "unavailable", "retained"}:
        raise ValueError("Publication refused: unexpected diagnostic fields")
    if any(type(value) is not int or value < 0 for value in data["sources"].values()):
        raise ValueError("Publication refused: invalid diagnostic count")
    for record in data["offers"]:
        if set(record) - {"discovered_at", "location_source"} != PUBLIC_FIELDS:
            raise ValueError("Publication refused: unexpected offer fields")
        for name in set(record) - {"categories"}:
            if not isinstance(record[name], str) or len(record[name]) > 2000:
                raise ValueError("Publication refused: invalid public field")
        public_job_url(record["url"])
        if "discovered_at" in record:
            observed = datetime.fromisoformat(record["discovered_at"])
            if observed.tzinfo is None:
                raise ValueError("Publication refused: discovery timestamp needs a timezone")
        if not isinstance(record["categories"], list) or any(value not in {"Stages Paris", "Stages International", "VIE", "Graduate"} for value in record["categories"]):
            raise ValueError("Publication refused: invalid category")
