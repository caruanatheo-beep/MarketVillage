"""Export only allowlisted public offer fields to an isolated static directory."""
from __future__ import annotations

import argparse
import json
import hashlib
import os
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from internships_project import internships as jobs
from internships_project.public_safety import assert_public, public_job_url, validate_snapshot
from internships_project.source_catalog import public_source_catalog, validate_source_catalog


def build_site(output: Path, *, collect: bool = False, force: bool = False) -> int:
    if output.exists() and any(output.iterdir()):
        raise ValueError("Build directory must be empty; existing files are never published implicitly")
    if collect:
        seed = ROOT / "public_seed.json"
        if seed.is_file():
            seed_bytes = seed.read_bytes()
            assert_public(seed_bytes, "public seed")
            previous = json.loads(seed_bytes)
            validate_snapshot(previous)
            baseline = [jobs.Opportunity(
                title=j["title"], company=j["company"], location=j.get("location_source", j["location"]), kind=j["kind"],
                url=public_job_url(j["url"]), published=j["published"], score=max(0, 1000-i),
                start_period=j["start"], family=j["family"],
                published_inferred=j["date_label"].startswith("Détectée"),
                source="JobTeaser · sitemap" if urlparse(j["url"]).hostname in {"jobteaser.com", "www.jobteaser.com"} else "Employeur",
            ) for i, j in enumerate(previous["offers"])]
            seed_date = datetime.fromisoformat(previous["updated"])
            jobs._remember_opportunity_snapshot(seed_date, baseline, [], baseline=True)
            if not jobs.CACHE_PATH.exists():
                jobs._write_cache(seed_date, baseline, [])
        offers, _, updated = jobs.refresh_opportunities(force=force, notify_email=False, fail_if_busy=True)
    else:
        offers, _, updated = jobs.load_opportunities(refresh=False)
    if not offers:
        raise ValueError("No offers available; preserve the previous deployment")
    categories = ("Stages Paris", "Stages International", "VIE", "Graduate")
    records = []
    logos = {}
    def company_logo(company: str) -> str:
        host = jobs.COMPANY_ICON_HOSTS.get(jobs._canonical_company(company), "")
        logo = jobs.COMPANY_LOGO_DIR / f"{host}.png"
        icon = ""
        if host and logo.is_file() and not logo.is_symlink() and logo.read_bytes().startswith(b"\x89PNG\r\n\x1a\n"):
            icon = f"logos/{logo.name}"
            logos[icon] = logo
        return icon
    for job in jobs.matching_opportunities(offers):
        # No description, profile, tracking, raw error, token or account data.
        records.append({
            "title": jobs._display_offer_title(job.title, job.location), "company": job.company,
            "location": jobs._display_offer_location(job.location), "location_source": job.location or "Non précisé", "kind": job.kind,
            "url": public_job_url(job.url), "published": job.published,
            "date_label": ("Détectée le " if job.published_inferred else "Publiée le ") + jobs._display_offer_date(job.published),
            "start": jobs._display_offer_date(job.start_period), "start_month": jobs.start_month(job.start_period) or "",
            "family": job.family, "logo": company_logo(job.company),
            "categories": [category for category in categories if jobs.matching_opportunities([job], category)],
        })
    checks = jobs.source_checks()
    partial = {name for name, check in checks.items() if check.get('status') == 'stale'
               and (check.get('cache_status') == 'partial' or
                    str(check.get('error') or '').startswith('collecte incomplète'))}
    if collect:
        for name, check in checks.items():
            if check.get("status") in {"error", "stale"} or name.startswith("BNP Paribas") or name == "ODDO BHF":
                diagnostic = json.dumps({"source": name, **{key: check.get(key) for key in
                    ("status", "count", "error", "cache_status")}}, ensure_ascii=True)
                assert_public(diagnostic.encode(), "source diagnostic")
                print("Source diagnostic: " + diagnostic, flush=True)
    payload = json.dumps({"updated": updated.isoformat(), "generated": datetime.now(timezone.utc).isoformat(),
                          "sources": {"checked": len(checks),
                                      "unavailable": sum(c.get("status") == "error" for c in checks.values()),
                                      "partial": len(partial),
                                      "retained": sum(c.get("status") == "stale" and name not in partial for name, c in checks.items())},
                          "offers": records}, ensure_ascii=False, separators=(",", ":")).encode()
    assert_public(payload, "offers.json")
    validate_snapshot(json.loads(payload))
    endpoint = os.getenv("SOURCE_REQUEST_ENDPOINT", "").strip()
    catalog = {"updated": updated.isoformat(), "sources": public_source_catalog(),
               "request_endpoint": endpoint}
    for source in catalog["sources"]:
        source["logo"] = company_logo(source["name"])
    validate_source_catalog(catalog)
    sources_payload = json.dumps(catalog, ensure_ascii=False, separators=(",", ":")).encode()
    assert_public(sources_payload, "sources.json")
    assets = {name: ROOT / "deploy/github-pages/site" / name for name in ("index.html", "site.css", "app.js", "sources.js", "marketdesk-icon.svg")}
    assets.update(logos)
    # Validate every byte before creating the publish directory.
    for name, path in assets.items():
        if path.is_symlink():
            raise ValueError("Symlink in public assets")
        assert_public(path.read_bytes(), name)
    output.mkdir(parents=True, exist_ok=True)
    for name, path in assets.items():
        target = output / name
        target.parent.mkdir(parents=True, exist_ok=True)
        if name == "index.html":
            document = path.read_text(encoding="utf-8")
            for asset in ("site.css", "app.js", "sources.js"):
                version = hashlib.sha256(assets[asset].read_bytes()).hexdigest()[:12]
                document = document.replace(f'"{asset}"', f'"{asset}?v={version}"')
            if endpoint:
                document = document.replace("connect-src 'self';", "connect-src 'self' https://marketdesk-source-suggestions.source-suggestions.workers.dev;")
            assert_public(document.encode(), "index.html")
            target.write_text(document, encoding="utf-8")
        else:
            shutil.copyfile(path, target)
    (output / "offers.json").write_bytes(payload)
    (output / "sources.json").write_bytes(sources_payload)
    (output / ".nojekyll").touch()
    return len(records)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "_site")
    parser.add_argument("--collect", action="store_true")
    parser.add_argument("--force", action="store_true", help="Recheck source caches during a manual collection")
    args = parser.parse_args()
    if args.force and not args.collect:
        parser.error("--force requires --collect")
    print(f"Static site built: {build_site(args.output, collect=args.collect, force=args.force)} public offers")
