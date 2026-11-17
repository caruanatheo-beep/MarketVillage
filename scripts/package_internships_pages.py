"""Prepare a new public repository without copying secrets or project history."""
from __future__ import annotations

import shutil
import sys
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from project_layout import source_path
from internships_project.public_safety import assert_public, validate_snapshot

FILES = {
    "Internships/internships_project/__init__.py": "internships_project/__init__.py",
    "internships_project/internships.py": "internships_project/internships.py",
    "internships_project/public_safety.py": "internships_project/public_safety.py",
    "internships_project/source_catalog.py": "internships_project/source_catalog.py",
    "internships_project/source_coverage.py": "internships_project/source_coverage.py",
    "internships_project/SOURCES.md": "internships_project/SOURCES.md",
    "internships_project/email_alerts.py": "internships_project/email_alerts.py",
    "scripts/build_internships_pages.py": "scripts/build_internships_pages.py",
    "scripts/internships_refresh_window.py": "scripts/internships_refresh_window.py",
    "scripts/notify_internships_pages.py": "scripts/notify_internships_pages.py",
    "tests/test_pages_export.py": "tests/test_pages_export.py",
    "tests/test_pages_filters.py": "tests/test_pages_filters.py",
    "tests/test_pages_sources.py": "tests/test_pages_sources.py",
    "tests/test_source_catalog.py": "tests/test_source_catalog.py",
    "tests/test_internships_recommended_sources.py": "tests/test_internships_recommended_sources.py",
    "tests/test_internships_nomura.py": "tests/test_internships_nomura.py",
    "tests/test_internships_rbc.py": "tests/test_internships_rbc.py",
    "tests/test_internships_pimco.py": "tests/test_internships_pimco.py",
    "tests/test_internships_murex.py": "tests/test_internships_murex.py",
    "tests/test_internships_tp_icap.py": "tests/test_internships_tp_icap.py",
    "tests/test_internships_refresh_window.py": "tests/test_internships_refresh_window.py",
    "tests/test_pages_email.py": "tests/test_pages_email.py",
    "tests/test_internships_publication_sort.py": "tests/test_internships_publication_sort.py",
    "tests/test_internships_source_browser_repair.py": "tests/test_internships_source_browser_repair.py",
    "tests/test_internships_graduate_coverage.py": "tests/test_internships_graduate_coverage.py",
    "tests/test_internships_deduplication.py": "tests/test_internships_deduplication.py",
    "tests/test_internships_location_display.py": "tests/test_internships_location_display.py",
    "tests/test_internships_candriam_bny.py": "tests/test_internships_candriam_bny.py",
    "tests/test_internships_commerz_standard.py": "tests/test_internships_commerz_standard.py",
    "tests/test_internships_reliability.py": "tests/test_internships_reliability.py",
    "tests/test_internships_offer_metadata.py": "tests/test_internships_offer_metadata.py",
    "tests/test_workday_pagination.py": "tests/test_workday_pagination.py",
    "tests/test_internships_collection_limits.py": "tests/test_internships_collection_limits.py",
    "deploy/github-pages/requirements.txt": "deploy/github-pages/requirements.txt",
    "deploy/github-pages/site/index.html": "deploy/github-pages/site/index.html",
    "deploy/github-pages/site/site.css": "deploy/github-pages/site/site.css",
    "deploy/github-pages/site/app.js": "deploy/github-pages/site/app.js",
    "deploy/github-pages/site/sources.js": "deploy/github-pages/site/sources.js",
    "deploy/github-pages/site/marketdesk-icon.svg": "deploy/github-pages/site/marketdesk-icon.svg",
    "deploy/github-pages/pages.yml": ".github/workflows/pages.yml",
    "deploy/github-pages/README.md": "README.md",
}


def package_repository(output: Path, seed: Path) -> int:
    if output.exists() and any(output.iterdir()):
        raise ValueError("Repository staging directory must be empty")
    files = {target: source_path(source, ROOT) for source, target in FILES.items()}
    files["public_seed.json"] = seed
    validate_snapshot(json.loads(seed.read_bytes()))
    for path in source_path("internships_project/assets/company_logos", ROOT).glob("*.png"):
        files[f"internships_project/assets/company_logos/{path.name}"] = path
    for name, path in files.items():
        if not path.is_file() or path.is_symlink():
            raise ValueError(f"Invalid deployment input: {name}")
        assert_public(path.read_bytes(), name)
    output.mkdir(parents=True, exist_ok=True)
    for name, path in files.items():
        target = output / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
    (output / ".gitignore").write_text(".env\n.env.*\n.collection-cache/\n_site/\n__pycache__/\n.pytest_cache/\n*.pyc\n", encoding="utf-8")
    return len(files) + 1


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/internships-pages-repository")
    parser.add_argument("--seed", type=Path, required=True)
    args = parser.parse_args()
    print(f"Clean public repository prepared: {package_repository(args.output, args.seed)} verified files")
