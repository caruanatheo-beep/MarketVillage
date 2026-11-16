"""Readable development results from saved evidence, without model inference."""
from __future__ import annotations


def format_coding_report(report: dict, *, max_chars: int = 9000, task_links: bool = False) -> str:
    def short(value, limit):
        text = ' '.join(str(value or '').split())
        return text if len(text) <= limit else text[:limit - 1].rstrip() + '…'

    lines = [f"Bilan du développement — {report['date']} (Paris)", report['overview']]
    sections = [('changes', 'Changements intégrés', .60),
                ('not_integrated', 'Terminés sans intégration', .12),
                ('blocked', 'Échecs et annulations', .14),
                ('active', 'En cours et en attente', .14)]
    for key, title, fraction in sections:
        items = report[key]
        lines.append(f'\n{title} ({len(items)})')
        if not items:
            lines.append('Aucun.')
            continue
        remaining, shown = int((max_chars - 650) * fraction), 0
        for item in items:
            agent = short(item['agent'], 40)
            if key == 'changes':
                row = f"- {agent} : {short(item.get('summary') or 'Résumé non renseigné.', 260)}"
                checks = item.get('server_checks') or []
                row += '\n  Vérifications serveur : ' + (short('; '.join(map(str, checks)), 180)
                         if checks else 'non renseignées.')
                row += '\n  ' + ('Activation City confirmée.' if item.get('live') is True else
                    'Activation non confirmée.' if item.get('live') is False else 'Activation inconnue.')
                if item.get('limitations'):
                    row += '\n  Limites : ' + short(item['limitations'], 100)
            elif key == 'not_integrated':
                row = f"- {agent} : {short(item.get('summary') or item['description'], 220)} Aucun changement intégré."
            elif key == 'blocked':
                state = 'Annulée' if item['status'] == 'cancelled' else 'Échec'
                row = f"- {agent} — {state} : {short(item.get('error') or item['description'], 220)}"
            else:
                state = {'running': 'En cours', 'queued': 'En attente',
                         'waiting_approval': 'En attente de validation'}.get(item['status'], item['status'])
                row = f"- {agent} — {state} : {short(item['description'], 140)}"
                if item.get('scheduled_at'):
                    from datetime import datetime
                    from zoneinfo import ZoneInfo
                    try:
                        when = datetime.fromisoformat(item['scheduled_at'].replace('Z', '+00:00'))
                        row += ' Reprise prévue le ' + when.astimezone(ZoneInfo('Europe/Paris')).strftime('%d/%m à %H:%M') + '.'
                    except (ValueError, TypeError):
                        pass
            task_id = str(item.get('id') or '')
            if task_links and len(task_id) == 32 and all(c in '0123456789abcdef' for c in task_id):
                row += f' [[mission:{task_id}]]'
            if len(row) > remaining:
                break
            lines.append(row)
            remaining -= len(row) + 1
            shown += 1
        if shown < len(items):
            lines.append(f'{len(items) - shown} autre(s) résultat(s) dans l’onglet Développement.')
    lines.append('\nUne intégration au code ne prouve pas son activation dans les autres applications.')
    return '\n'.join(lines)
