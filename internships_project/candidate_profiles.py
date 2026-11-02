"""Private browser-side candidate profiles and CV text extraction."""

from __future__ import annotations

import html
from io import BytesIO
from datetime import datetime
from statistics import median
import re
import uuid
import zipfile
from pathlib import Path
from xml.etree import ElementTree


MAX_CV_BYTES = 8_000_000
MAX_PROFILE_TEXT = 30_000
MAX_LINKEDIN_PROFILE_TEXT = 60_000
MAX_LINKEDIN_PROFILE_PAGES = 30
MAX_PROFILES = 20


class ProfileError(ValueError):
    """A short, user-facing profile validation error."""


def extract_pdf_bytes_text(data: bytes | bytearray | None) -> str:
    """Extract a bounded amount of text from an uploaded PDF without persisting it."""
    if not data:
        raise ProfileError("Importe le PDF LinkedIn de la personne à contacter.")
    if len(data) > MAX_CV_BYTES:
        raise ProfileError("Le PDF dépasse la taille maximale de 8 Mo.")
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise ProfileError("Installe pypdf pour lire les profils PDF.") from exc
    try:
        reader = PdfReader(BytesIO(data))
        if reader.is_encrypted:
            raise ProfileError("Ce PDF est protégé par un mot de passe et ne peut pas être lu.")
        if len(reader.pages) > MAX_LINKEDIN_PROFILE_PAGES:
            raise ProfileError("Le PDF dépasse 30 pages. Exporte uniquement les pages utiles du profil.")
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
    except ProfileError:
        raise
    except Exception as exc:
        raise ProfileError("Ce PDF n’a pas pu être lu. Essaie un PDF texte non protégé.") from exc
    text = re.sub(r"[ \t]+", " ", text).strip()
    if len(text) > MAX_LINKEDIN_PROFILE_TEXT:
        raise ProfileError("Le profil LinkedIn dépasse 60 000 caractères de texte lisible.")
    if len(text) < 80:
        raise ProfileError("Le PDF ne contient pas assez de texte lisible. Essaie un autre export LinkedIn.")
    return text


def _linkedin_name_shape(value: str) -> bool:
    words = str(value or "").strip(" .,:;|\t").split()
    if not 2 <= len(words) <= 4:
        return False
    token = re.compile(r"^[^\W\d_]+(?:[-'’][^\W\d_]+)*$", re.UNICODE)
    return all(token.fullmatch(word) and (word[0].isupper() or word.isupper()) for word in words)


def _linkedin_pdf_lines(fragments: list[dict], page_width: float) -> list[dict]:
    """Rebuild visual text lines and separate columns from PDF fragment geometry."""
    rows: list[dict] = []
    for fragment in sorted(fragments, key=lambda item: (item["top"], item["x"])):
        matching_row = None
        for row in reversed(rows[-4:]):
            tolerance = max(2.0, min(6.0, max(fragment["size"], row["size"]) * 0.42))
            if abs(row["top"] - fragment["top"]) <= tolerance:
                matching_row = row
                break
        if matching_row is None:
            matching_row = {"top": fragment["top"], "size": fragment["size"], "items": []}
            rows.append(matching_row)
        matching_row["items"].append(fragment)
        matching_row["size"] = max(matching_row["size"], fragment["size"])
        matching_row["top"] = min(matching_row["top"], fragment["top"])

    lines = []
    column_gap = max(page_width * 0.075, 28.0)
    for row in rows:
        fragments_in_row = sorted(row["items"], key=lambda item: item["x"])
        column_groups: list[list[dict]] = []
        current: list[dict] = []
        estimated_right = None
        for fragment in fragments_in_row:
            separate_column_start = bool(
                current
                and fragment["x"] - current[-1]["x"] > max(page_width * 0.16, 48.0)
                and fragment["x"] - current[0]["x"] > max(page_width * 0.28, 90.0)
            )
            if current and estimated_right is not None and (
                fragment["x"] - estimated_right > column_gap or separate_column_start
            ):
                column_groups.append(current)
                current = []
                estimated_right = None
            current.append(fragment)
            estimated_right = max(
                estimated_right or fragment["x"],
                fragment["x"] + max(fragment["size"] * 0.45 * len(fragment["text"]), fragment["size"]),
            )
        if current:
            column_groups.append(current)

        for group in column_groups:
            chunks = []
            for fragment in group:
                part = re.sub(r"\s+", " ", fragment["text"]).strip()
                if part and (not chunks or part.casefold() != chunks[-1].casefold()):
                    chunks.append(part)
            text = re.sub(r"\s+", " ", " ".join(chunks)).strip()
            if not text:
                continue
            x_values = [item["x"] for item in group]
            right_values = [
                item["x"] + max(item["size"] * 0.45 * len(item["text"]), item["size"])
                for item in group
            ]
            lines.append({
                "text": text, "x0": min(x_values), "x1": max(right_values),
                "top": row["top"], "size": max(item["size"] for item in group),
                "page": group[0]["page"], "page_height": group[0]["page_height"],
                "page_width": page_width,
            })
    return sorted(lines, key=lambda line: (line["page"], line["top"], line["x0"]))


def _linkedin_column_split(lines: list[dict], page_width: float) -> float | None:
    centers = sorted((line["x0"] + line["x1"]) / 2 for line in lines)
    if len(centers) < 4:
        return None
    best = None
    for index in range(1, len(centers) - 1):
        gap = centers[index] - centers[index - 1]
        left_count, right_count = index, len(centers) - index
        if gap < max(page_width * 0.075, 28.0) or min(left_count, right_count) < 2:
            continue
        score = gap * (min(left_count, right_count) ** 0.5)
        if best is None or score > best[0]:
            best = (score, (centers[index] + centers[index - 1]) / 2)
    return best[1] if best else None


def extract_linkedin_recipient_profile(data: bytes | bytearray | None) -> dict:
    """Extract a LinkedIn PDF into spatially ordered, identity-separated profile data."""
    if not isinstance(data, (bytes, bytearray)) or not data:
        raise ProfileError("Importe le PDF LinkedIn de la personne à contacter.")
    if len(data) > MAX_CV_BYTES:
        raise ProfileError("Le PDF dépasse la taille maximale de 8 Mo.")
    try:
        from pypdf import PdfReader, mult
    except ImportError as exc:
        raise ProfileError("Installe pypdf pour lire les profils PDF.") from exc

    fragments: list[dict] = []
    try:
        reader = PdfReader(BytesIO(data), strict=False)
        if reader.is_encrypted:
            raise ProfileError("Ce PDF est protégé par un mot de passe. Importe une version lisible.")
        if not reader.pages:
            raise ProfileError("Ce PDF ne contient aucune page lisible.")
        if len(reader.pages) > MAX_LINKEDIN_PROFILE_PAGES:
            raise ProfileError("Le PDF dépasse 30 pages. Exporte uniquement les pages utiles du profil.")

        for page_number, page in enumerate(reader.pages):
            page_width = float(page.mediabox.width)
            page_height = float(page.mediabox.height)

            def collect(text, user_matrix, text_matrix, font_dict, font_size):
                raw_text = str(text or "")
                if not raw_text.strip():
                    return
                transform = mult(text_matrix, user_matrix)
                x, y = float(transform[4]), float(transform[5])
                size = abs(float(font_size or 0))
                if size <= 0:
                    return
                for line_number, line_text in enumerate(raw_text.splitlines() or [raw_text]):
                    line_text = line_text.strip()
                    if not line_text:
                        continue
                    baseline = y - line_number * size * 1.15
                    fragments.append({
                        "text": line_text, "x": x, "top": page_height - baseline,
                        "size": size, "page": page_number, "page_height": page_height,
                    })

            page.extract_text(visitor_text=collect)
    except ProfileError:
        raise
    except Exception as exc:
        raise ProfileError("Ce PDF n’a pas pu être lu. Essaie un export LinkedIn contenant du texte sélectionnable.") from exc

    total_text = sum(len(item["text"]) for item in fragments)
    if total_text < 80:
        raise ProfileError("Le PDF ne contient pas assez de texte lisible. Essaie une version avec texte sélectionnable.")
    if total_text > MAX_LINKEDIN_PROFILE_TEXT:
        raise ProfileError("Le texte du profil dépasse 60 000 caractères lisibles.")

    lines_by_page: dict[int, list[dict]] = {}
    page_widths: dict[int, float] = {}
    for fragment in fragments:
        lines_by_page.setdefault(fragment["page"], []).append(fragment)
        page_widths[fragment["page"]] = float(reader.pages[fragment["page"]].mediabox.width)
    lines = []
    for page_number, page_fragments in lines_by_page.items():
        lines.extend(_linkedin_pdf_lines(page_fragments, page_widths[page_number]))
    first_page = [line for line in lines if line["page"] == 0]
    if not first_page:
        raise ProfileError("Le PDF ne contient pas de texte lisible sur sa première page.")

    split = _linkedin_column_split(first_page, page_widths[0])
    font_sizes = [line["size"] for line in lines if line["size"] > 0]
    typical_size = median(font_sizes) if font_sizes else 0
    name_candidates = []
    for line in first_page:
        vertical_position = line["top"] / max(line["page_height"], 1)
        ratio = line["size"] / max(typical_size, 1)
        if vertical_position > 0.42 or ratio < 1.3 or not _linkedin_name_shape(line["text"]):
            continue
        center = (line["x0"] + line["x1"]) / 2
        score = ratio + 0.35 * (1 - vertical_position)
        name_candidates.append((score, ratio, line, center))

    name_candidates.sort(key=lambda item: item[0], reverse=True)
    identified_name = ""
    name_line = None
    confidence = "unknown"
    if name_candidates:
        best_score, best_ratio, best_line, best_center = name_candidates[0]
        runner_up = name_candidates[1][0] if len(name_candidates) > 1 else 0
        if best_ratio >= 1.45 and best_score >= runner_up * 1.12:
            identified_name = best_line["text"].strip(" .,:;|\t")
            name_line = best_line
            confidence = "high"

    main_is_right = True
    if split is not None and name_line is not None:
        main_is_right = ((name_line["x0"] + name_line["x1"]) / 2) >= split

    def is_main_column(line: dict) -> bool:
        if split is None:
            return True
        center = (line["x0"] + line["x1"]) / 2
        return (center >= split) == main_is_right

    main_lines = [line for line in lines if is_main_column(line)]
    sidebar_lines = [line for line in lines if split is not None and not is_main_column(line)]

    headline = ""
    if name_line is not None:
        following = [
            line for line in main_lines
            if line["page"] == 0 and line["top"] > name_line["top"] + 1
            and line["top"] - name_line["top"] <= name_line["page_height"] * 0.16
        ]
        if following:
            headline = min(following, key=lambda line: (line["top"], line["x0"]))["text"]

    main_text = "\n".join(line["text"] for line in main_lines)
    sidebar_text = "\n".join(line["text"] for line in sidebar_lines)
    profile_sections = [
        f"Nom identifié dans l’en-tête : {identified_name}" if identified_name else "Nom non identifié avec certitude",
        f"Titre professionnel proche du nom : {headline}" if headline else "Titre professionnel non identifié",
        "Parcours et contenu de la colonne principale :\n" + main_text,
    ]
    if sidebar_text:
        profile_sections.append("Contact, compétences et éléments de la colonne latérale :\n" + sidebar_text)
    profile_text = "\n\n".join(profile_sections)
    if len(profile_text) > MAX_LINKEDIN_PROFILE_TEXT:
        raise ProfileError("Le profil LinkedIn dépasse 60 000 caractères lisibles.")

    return {
        "full_name": identified_name,
        "first_name": identified_name.split()[0] if identified_name and confidence == "high" else "",
        "name_confidence": confidence,
        "headline": headline,
        "main_column_text": main_text,
        "sidebar_text": sidebar_text,
        "linkedin_pdf_text": profile_text,
    }


def extract_cv_text(file_path: str | None) -> str:
    if not file_path:
        return ""
    path = Path(file_path)
    if not path.is_file() or path.stat().st_size > MAX_CV_BYTES:
        raise ProfileError("Le CV est introuvable ou dépasse 8 Mo.")
    extension = path.suffix.casefold()
    if extension in {".txt", ".md"}:
        text = path.read_text(encoding="utf-8-sig", errors="replace")
    elif extension == ".pdf":
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise ProfileError("Installez pypdf pour importer un CV PDF.") from exc
        try:
            reader = PdfReader(str(path))
            text = "\n".join(page.extract_text() or "" for page in reader.pages[:15])
        except Exception as exc:
            raise ProfileError("Ce PDF n’a pas pu être lu. Essaie un fichier texte.") from exc
    elif extension == ".docx":
        try:
            with zipfile.ZipFile(path) as archive:
                entries = archive.infolist()
                # DOCX is a ZIP container. Bound both entry count and inflated size so
                # a small compressed archive cannot exhaust memory during extraction.
                if len(entries) > 2_000 or sum(item.file_size for item in entries) > 24_000_000:
                    raise ProfileError("Ce document Word dépasse la taille décompressée autorisée.")
                document = next((item for item in entries if item.filename == "word/document.xml"), None)
                if document is None or document.flag_bits & 0x1:
                    raise ProfileError("Ce document Word est incomplet.")
                if document.file_size > 12_000_000:
                    raise ProfileError("Ce document Word dépasse la taille décompressée autorisée.")
                data = archive.read(document)
            root = ElementTree.fromstring(data)
            namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
            text = "\n".join(
                "".join(node.text or "" for node in paragraph.findall(".//w:t", namespace))
                for paragraph in root.findall(".//w:p", namespace)
            )
        except (zipfile.BadZipFile, ElementTree.ParseError, OSError) as exc:
            raise ProfileError("Ce document Word n’a pas pu être lu.") from exc
    else:
        raise ProfileError("Formats acceptés : PDF, DOCX, TXT et MD.")
    text = re.sub(r"[ \t]+", " ", text).strip()[:MAX_PROFILE_TEXT]
    if len(text) < 80:
        raise ProfileError("Le CV ne contient pas assez de texte lisible. Ajoute un résumé manuel.")
    return text


def clean_catalog(value: object) -> dict[str, dict]:
    if not isinstance(value, dict):
        return {}
    result = {}
    for key, record in list(value.items())[:MAX_PROFILES]:
        if isinstance(key, str) and isinstance(record, dict) and isinstance(record.get("name"), str):
            result[key] = record
    return result


def profile_choices(catalog: object) -> list[tuple[str, str]]:
    records = clean_catalog(catalog)
    return sorted(((record["name"], key) for key, record in records.items()),
                  key=lambda item: item[0].casefold())


def save_profile(catalog: object, selected_id: str | None, record: dict) -> tuple[dict, str]:
    records = clean_catalog(catalog)
    if not isinstance(record, dict):
        raise ProfileError("Les informations du profil sont invalides.")
    name = str(record.get("name") or "").strip()[:100]
    if len(name) < 2:
        raise ProfileError("Indique un nom pour ce profil.")
    source_text = str(record.get("source_text") or "").strip()
    if len(source_text) < 80:
        raise ProfileError("Ajoute un CV ou un résumé d’au moins 80 caractères.")
    if len(source_text) > MAX_PROFILE_TEXT:
        raise ProfileError("Le CV ou résumé dépasse la taille maximale autorisée.")
    for field, maximum in (("overview", 2_000), ("start_window", 200)):
        if len(str(record.get(field) or "")) > maximum:
            raise ProfileError("Un des champs du profil est trop long.")
    for field in ("experience", "strengths", "target_roles", "locations", "contracts", "constraints"):
        values = record.get(field, [])
        if isinstance(values, str):
            values = [part.strip() for part in values.replace(",", "\n").splitlines() if part.strip()]
        if not isinstance(values, (list, tuple)) or len(values) > 20 or any(
            not isinstance(item, str) or len(item.strip()) > 300 for item in values
        ):
            raise ProfileError("Un des champs du profil contient trop d’éléments ou un format invalide.")
        record[field] = [item.strip() for item in values if item.strip()]
    for field in ("start_month", "end_month"):
        month = str(record.get(field) or "").strip()
        if month and not re.fullmatch(r"\d{4}-(?:0[1-9]|1[0-2])", month):
            raise ProfileError("Saisissez les mois au format AAAA-MM.")
        record[field] = month
    if record.get("start_month") and record.get("end_month") and record["end_month"] < record["start_month"]:
        raise ProfileError("Le mois de fin doit suivre le mois de début.")
    for key, previous in records.items():
        if previous["name"].casefold() == name.casefold() and key != selected_id:
            raise ProfileError("Un profil porte déjà ce nom. Sélectionne-le pour le modifier.")
    key = selected_id if selected_id in records else uuid.uuid4().hex
    if key not in records and len(records) >= MAX_PROFILES:
        raise ProfileError("Le nombre maximal de profils est atteint.")
    records[key] = {**record, "name": name, "source_text": source_text}
    return records, key


def selected_profile(catalog: object, key: str | None) -> dict | None:
    return clean_catalog(catalog).get(key or "")


def candidate_profile_context(record: dict) -> dict:
    """Return the complete saved candidate profile in a bounded model-ready structure."""
    record = record if isinstance(record, dict) else {}

    def text(field: str, limit: int) -> str:
        return str(record.get(field) or "").strip()[:limit]

    def items(field: str) -> list[str]:
        value = record.get(field, [])
        if isinstance(value, str):
            value = [part.strip() for part in value.replace(",", "\n").splitlines() if part.strip()]
        if not isinstance(value, (list, tuple)):
            return []
        return [str(item).strip()[:300] for item in value[:20] if str(item).strip()]

    return {
        "name": text("name", 100),
        "overview": text("overview", 2_000),
        "source_text": text("source_text", MAX_PROFILE_TEXT),
        "experience": items("experience"),
        "strengths": items("strengths"),
        "target_roles": items("target_roles"),
        "locations": items("locations"),
        "contracts": items("contracts"),
        "start_window": text("start_window", 200),
        "start_month": text("start_month", 7),
        "end_month": text("end_month", 7),
        "constraints": items("constraints"),
    }


def profile_prompt(record: dict) -> tuple[str, str, str]:
    name = str(record.get("name") or "").strip()
    facts = [str(record.get("overview") or "").strip()]
    for field, label in (("experience", "Expériences renseignées"), ("strengths", "Compétences"),
                         ("constraints", "Informations à compléter")):
        values = record.get(field)
        if isinstance(values, list) and values:
            facts.append(label + " : " + "; ".join(str(item) for item in values[:12]))
    facts.append("CV ou résumé source :\n" + str(record.get("source_text") or "")[:MAX_PROFILE_TEXT])
    goals = []
    for field, label in (("target_roles", "Métiers"), ("locations", "Lieux"),
                         ("contracts", "Contrats")):
        values = record.get(field)
        if isinstance(values, list) and values:
            goals.append(label + " : " + ", ".join(str(item) for item in values[:8]))
    if record.get("start_window"):
        goals.append("Période de début : " + str(record["start_window"]))
    if record.get("start_month") or record.get("end_month"):
        goals.append("Disponibilité confirmée : " + str(record.get("start_month") or "")
                     + " à " + str(record.get("end_month") or ""))
    return name, "\n\n".join(part for part in facts if part), "; ".join(goals)


def render_profile_card(record: dict | None) -> str:
    if not record:
        return '<div class="profile-empty">Crée ton profil dans Mon profil pour commencer.</div>'
    icons = {
        "Lieux": '<path d="M12 21s7-5.2 7-11a7 7 0 1 0-14 0c0 5.8 7 11 7 11Z"/><circle cx="12" cy="10" r="2.5"/>',
        "Contrat": '<rect x="3" y="7" width="18" height="14" rx="2"/><path d="M8 7V5a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2M3 12h18"/>',
        "Disponibilité": '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M7 3v4m10-4v4M3 10h18"/>',
    }

    def row(label: str, value: object) -> str:
        if isinstance(value, list):
            value = ", ".join(str(item) for item in value)
        value = str(value or "").strip()
        icon = f'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" aria-hidden="true">{icons[label]}</svg>'
        return (f'<div class="profile-summary-fact">{icon}<div class="profile-summary-fact-copy">'
                f'<span>{html.escape(label)}</span><span class="profile-summary-value">{html.escape(value or "À préciser")}</span>'
                '</div></div>')
    def availability() -> str:
        first, last = str(record.get("start_month") or ""), str(record.get("end_month") or "")
        months = ("janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août",
                  "septembre", "octobre", "novembre", "décembre")
        try:
            start = datetime.strptime(first, "%Y-%m") if first else None
            end = datetime.strptime(last, "%Y-%m") if last else None
        except ValueError:
            start = end = None
        if start and end:
            left = months[start.month - 1].capitalize()
            right = months[end.month - 1]
            return f"{left} à {right} {end.year}" if start.year == end.year else f"{left} {start.year} à {right} {end.year}"
        if start or end:
            value = start or end
            return f"{months[value.month - 1].capitalize()} {value.year}"
        return str(record.get("start_window") or "")
    roles = record.get("target_roles")
    if isinstance(roles, str):
        roles = [part.strip() for part in roles.split(",")]
    roles = [str(role).strip() for role in (roles or []) if str(role).strip()]
    chips = "".join(f'<span class="profile-role-chip">{html.escape(role)}</span>' for role in roles)
    if not chips:
        chips = '<span class="profile-role-empty">À préciser</span>'
    return (
        '<section class="profile-summary-card">'
        f'<div class="profile-summary-head"><span class="profile-avatar">{html.escape("".join(part[0] for part in record["name"].split()[:2]).upper())}</span>'
        f'<div><h3>{html.escape(record["name"])}</h3></div></div>'
        '<div class="profile-summary-roles"><span class="profile-summary-label">Métiers</span>'
        f'<div class="profile-role-list">{chips}</div></div>'
        '<div class="profile-summary-grid">'
        + row("Lieux", record.get("locations"))
        + row("Contrat", record.get("contracts"))
        + row("Disponibilité", availability())
        + '</div></section>'
    )
