"""Account-scoped manager summaries based on recorded City missions."""
from __future__ import annotations

import json
import unicodedata
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from .city_development_report import format_coding_report

PARIS = ZoneInfo('Europe/Paris')
CONTACT_AGENTS = (('networker', 'Lina'), ('securities_scout', 'Clara'), ('prime_services_scout', 'Élodie'))


def _plain(value: str) -> str:
    return ''.join(c for c in unicodedata.normalize('NFKD', str(value or '').casefold()) if not unicodedata.combining(c))


def retry_advice(task: dict) -> dict:
    """Conservative advice for bulk retries; an explicit individual retry remains available."""
    status = task.get('status')
    text = _plain((task.get('error') or '') + ' ' + (task.get('last_event') or {}).get('message', ''))
    if task.get('blocked_dependencies'):
        return {'eligible': False, 'category': 'dépendance', 'reason': 'Une dépendance a échoué, est annulée ou introuvable ; examine le projet.'}
    if status == 'running':
        return {'eligible': False, 'category': 'en cours', 'reason': 'La mission est déjà en cours.'}
    if status == 'waiting_approval' and task.get('operation') in {'code_change', 'prepare_branch'}:
        return {'eligible': False, 'category': 'validation', 'reason': 'La proposition nécessite sa validation spécifique.'}
    if 'budget codex quotidien atteint' in text:
        return {'eligible': True, 'category': 'ancienne limite City supprimée', 'reason': 'Le budget quotidien propre à City ne bloque plus cette mission.'}
    if any(term in text for term in ('quota', 'rate limit', 'limite codex', 'limite de requetes')):
        return {'eligible': False, 'category': 'limite Codex', 'reason': 'Une limite est signalée ; attends son renouvellement avant une nouvelle tentative.'}
    if status == 'failed':
        if any(term in text for term in ('authentification', 'connexion chatgpt', 'codex login', 'autorisation', 'acces refuse', 'permission denied', 'os error 5')):
            return {'eligible': False, 'category': 'accès', 'reason': 'Un problème d’accès ou de connexion est signalé ; vérifie-le avant de relancer.'}
        if any(term in text for term in ('tests serveur en echec', 'build frontend en echec', 'conflit', 'validation', 'proposition')):
            return {'eligible': False, 'category': 'correction nécessaire', 'reason': 'Le résultat indique un problème à examiner avant une nouvelle tentative.'}
        if any(term in text for term in ('source', 'recherche publique')) and any(term in text for term in ('indisponible', 'inaccessible', 'echec')):
            return {'eligible': False, 'category': 'source', 'reason': 'Une source est signalée indisponible ; vérifie son accès avant de relancer.'}
        if not any(term in text for term in ('timeout', 'timed out', 'temporaire', 'temporary', 'delai', 'interromp', 'connection reset', 'connexion interrompue')):
            return {'eligible': False, 'category': 'à examiner', 'reason': 'La cause enregistrée ne permet pas de confirmer qu’une relance sera utile.'}
        return {'eligible': True, 'category': 'incident potentiellement temporaire', 'reason': 'Le message évoque une interruption ou un délai ; une nouvelle tentative peut être utile.'}
    return {'eligible': True, 'category': 'en attente', 'reason': 'La reprise conserve les dépendances et les limites de concurrence.'}


def _task_link(task_id: str) -> str:
    return f' [[mission:{task_id}]]' if len(task_id) == 32 and all(c in '0123456789abcdef' for c in task_id) else ''


def contacts_report(store, username: str, now: datetime | None = None) -> dict:
    moment = (now or datetime.now(timezone.utc)).astimezone(PARIS)
    start = moment.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc).isoformat()
    agents = []
    with store.db() as db:
        for agent_id, name in CONTACT_AGENTS:
            rows = db.execute("SELECT id,status,finished_at,result_json,error,parameters_json FROM city_tasks WHERE username=? AND agent_id=? "
                              "AND status IN ('completed','failed') AND finished_at IS NOT NULL "
                              "ORDER BY finished_at DESC,rowid DESC", (username, agent_id)).fetchall()
            entries = []
            for row in rows:
                try:
                    result = json.loads(row['result_json'] or '{}')
                    params = json.loads(row['parameters_json'] or '{}')
                except (ValueError, TypeError):
                    continue
                expected = {'securities_scout': 'discover_service_contacts', 'prime_services_scout': 'discover_prime_services_contacts'}
                if agent_id == 'networker' and not params.get('discover_public'):
                    continue
                if agent_id in expected and params.get('operation') != expected[agent_id]:
                    continue
                # Exclude unrelated school enrichment and other non-discovery missions.
                if row['status'] == 'completed' and not isinstance(result.get('contacts'), list):
                    continue
                entries.append({'id': row['id'], 'status': row['status'], 'finished_at': row['finished_at'],
                                'error': row['error'] or '', 'result': result})
            truncated = len(entries) > 50
            entries = entries[:50]
            today = [entry for entry in entries if entry['finished_at'] >= start]
            agents.append({'name': name, 'latest': entries[0] if entries else None,
                           'today': today, 'today_truncated': truncated})
    return {'date': moment.strftime('%d/%m/%Y'), 'agents': agents}


def format_contacts_report(report: dict) -> str:
    lines = [f"### Recherche de contacts · {report['date']} (Paris)"]
    for agent in report['agents']:
        today, latest = agent['today'], agent['latest']
        completed = [item for item in today if item['status'] == 'completed']
        added = sum(len(item['result'].get('contacts') or []) for item in completed)
        duplicate_values = [item['result'].get('duplicates') for item in completed]
        duplicates = sum(value for value in duplicate_values if isinstance(value, int))
        duplicate_label = (f'{duplicates} doublon(s) écarté(s)' if all(isinstance(value, int) for value in duplicate_values)
                           else 'nombre de doublons incomplet')
        failures = sum(item['status'] == 'failed' for item in today)
        lines.append(f"\n**{agent['name']}** · aujourd’hui : {added} contact(s) ajouté(s), {duplicate_label}, {failures} recherche(s) en échec." + (' Historique partiel (50 résultats maximum).' if agent['today_truncated'] else ''))
        if not latest:
            lines.append('Aucun résultat de recherche enregistré.')
            continue
        try:
            date = datetime.fromisoformat(latest['finished_at'].replace('Z', '+00:00')).astimezone(PARIS).strftime('%d/%m à %H:%M')
        except (ValueError, TypeError):
            date = 'date inconnue'
        if latest['status'] == 'failed':
            lines.append(f"Dernière recherche ({date}) : échec — {latest['error'] or 'cause non enregistrée'}." + _task_link(latest['id']))
            previous = next((item for item in today if item['status'] == 'completed'), None)
            if not previous:
                continue
            latest = previous
            try:
                date = datetime.fromisoformat(latest['finished_at'].replace('Z', '+00:00')).astimezone(PARIS).strftime('%d/%m à %H:%M')
            except (ValueError, TypeError):
                date = 'date inconnue'
            lines.append('Résultat précédent enregistré aujourd’hui :')
        result = latest['result']
        contacts = result.get('contacts') or []
        lines.append(f"Dernière recherche ({date}) : {len(contacts)} ajouté(s), {result.get('duplicates', 'nombre inconnu')} doublon(s). Source : {result.get('source') or result.get('provider') or 'non renseignée'}." + _task_link(latest['id']))
        for contact in contacts[:5]:
            url = str(contact.get('source_url') or '')
            source = f' [Source]({url})' if url.startswith(('https://', 'http://')) and not any(c.isspace() or c == ')' for c in url) else ' Source individuelle non renseignée.'
            lines.append(f"- {contact.get('name') or 'Nom non renseigné'} · {contact.get('role') or 'Poste à confirmer'} · {contact.get('company') or 'Entreprise à confirmer'}.{source}")
        if len(contacts) > 5:
            lines.append(f"- {len(contacts)-5} autre(s) contact(s) dans le résultat de la mission.")
        for warning in (result.get('warnings') or [])[:3]:
            lines.append(f"- Limite : {str(warning)[:250]}")
        if not contacts:
            lines.append('Aucun nouveau contact enregistré lors de cette recherche.')
    lines.append('\nLes postes et localisations restent à confirmer dans les sources. Ce bilan ne lance aucune recherche.')
    return '\n'.join(lines)


def daily_report(store, username: str) -> str:
    report = store.daily_coding_changes(username)
    lines = [format_coding_report(report, task_links=True), '', format_contacts_report(contacts_report(store, username)), '', '### Stages · dernier résultat de Hugo']
    with store.db() as db:
        row = db.execute("SELECT id,status,finished_at,result_json,error FROM city_tasks WHERE username=? AND agent_id='internship_scout' "
                         "AND status IN ('completed','failed') ORDER BY finished_at DESC,rowid DESC LIMIT 1", (username,)).fetchone()
    if not row:
        lines.append('Aucune actualisation terminée enregistrée.')
    else:
        try:
            date = datetime.fromisoformat(row['finished_at'].replace('Z', '+00:00')).astimezone(PARIS).strftime('%d/%m/%Y à %H:%M (Paris)')
        except (ValueError, TypeError, AttributeError):
            date = 'date inconnue'
        if row['status'] == 'failed':
            lines.append(f"Dernière actualisation en échec ({date}) : {row['error'] or 'cause non enregistrée'}." + _task_link(row['id']))
        else:
            try:
                result = json.loads(row['result_json'] or '{}')
            except (ValueError, TypeError):
                result = {}
            lines.append(f"Dernier résultat enregistré ({date}) : {str(result.get('summary') or result.get('text') or 'Résumé non renseigné.')[:700]}" + _task_link(row['id']))
            for offer in (result.get('offers') or [])[:5]:
                url = str(offer.get('url') or '')
                link = f' [Offre]({url})' if url.startswith(('https://', 'http://')) and not any(c.isspace() or c == ')' for c in url) else ''
                lines.append(f"- {offer.get('title', 'Offre')} · {offer.get('company', 'Entreprise non renseignée')}.{link}")
    return '\n'.join(lines)
