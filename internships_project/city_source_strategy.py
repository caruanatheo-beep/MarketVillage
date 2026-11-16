"""Bounded source research and resumable per-source pauses for Sacha."""
from datetime import datetime,timedelta,timezone
import json
import os
from pathlib import Path
import re

CHECKPOINT='.sacha-source-attempts.json'
RULES=(
    "Stratégie de secours obligatoire : commence par inventorier les connecteurs existants et leurs tests "
    "(Greenhouse, Lever, Ashby, Workday, SmartRecruiters, Oracle, CAREER_LISTINGS). Parmi les recommandations "
    "pertinentes, privilégie une extension de connecteur déjà disponible avant un nouveau collecteur. "
    "Une source déjà publiée et fonctionnelle est couverte : passe à une lacune plutôt que de la réauditer longuement. "
    "Pour chaque candidat, essaie au maximum trois méthodes distinctes : API/flux public documenté, "
    "HTML/JSON-LD public, puis le navigateur public déjà disponible si nécessaire. Pas de contournement "
    "d'authentification, CAPTCHA, 403 ou 429 ; respecte Retry-After et ne répète pas une méthode identique en boucle. "
    "Budget de recherche : 6 minutes maximum par source, vérifie l'heure avant chaque méthode. "
    "Sans progrès après ces essais, marque la source blocked, explique les preuves et passe à la suivante ; "
    "ne conclus pas qu'aucune offre n'existe. Réserve les dernières minutes aux tests et au rapport. "
    "Tiens à jour dès le premier essai le fichier local .sacha-source-attempts.json : une liste de "
    "{source, status, methods, reason, started_at}, started_at en ISO UTC au premier essai, "
    "status parmi exploring, selected, blocked, integrated ; méthodes distinctes "
    "et raison factuelle, sans donnée privée. Mets-le à jour à chaque changement de méthode et de source. "
    "Ce fichier est un journal de reprise, jamais un fichier à intégrer ; ne modifie pas .gitignore pour lui. Avant chaque nouvel essai, relis "
    ".sacha-source-controls.json si présent : une pause signifie passer à une autre source, en conservant le code. "
    "Respecte aussi les pauses serveur ci-dessous ; "
    "Pour chaque connecteur, teste la réponse nominale, l'échec API et son éventuel repli HTML, les 403/429, "
    "les réponses vides/incomplètes, la pagination et les doublons. Ne présente pas un repli non testé comme opérationnel. "
    "elles évitent de recommencer une source abandonnée. Si toutes les pistes pertinentes sont bloquées, "
    "termine honnêtement sans ajout forcé."
)


def source_key(name):
    return re.sub(r'\W+','',re.sub(r'\s*\([A-Z][A-Z0-9.& -]{1,15}\)\s*$','',name).casefold())


def _read(path):
    try:
        if path.stat().st_size>64_000:return {}
        return json.loads(path.read_text(encoding='utf-8-sig'))
    except (OSError,ValueError):return {}


def attempts_for(root: Path, task_id: str) -> list[dict]:
    if not re.fullmatch('[a-f0-9]{32}',task_id):return []
    path=root/'.city-worktrees'/task_id/CHECKPOINT
    if path.is_symlink():return []
    data=_read(path)
    if not isinstance(data,list):return []
    attempts=[]
    for row in data[:12]:
        if (not isinstance(row,dict) or not isinstance(row.get('source'),str)
                or not 2<=len(row['source'])<=100
                or row.get('status') not in {'exploring','selected','blocked','integrated'}):continue
        methods=row.get('methods')
        if not isinstance(methods,list):continue
        methods=[value.get('method','') if isinstance(value,dict) else value for value in methods]
        if any(not isinstance(value,str) for value in methods):continue
        status=row['status'];reason=str(row.get('reason') or '')[:300]
        try:
            elapsed=(datetime.now(timezone.utc)-datetime.fromisoformat(row['started_at'])).total_seconds()
            if status=='exploring' and elapsed>=360:
                status='blocked';reason=reason or 'Budget de recherche de six minutes atteint.'
        except (KeyError,TypeError,ValueError):pass
        attempts.append({'source':row['source'],'status':status,
            'methods':list(dict.fromkeys(value[:120] for value in methods))[:3],
            'reason':reason})
    return attempts


def record_attempts(state: dict, task: dict, root: Path, now=None) -> list[dict]:
    now=now or datetime.now(timezone.utc)
    attempts=attempts_for(root,task['id'])
    backoffs=state.setdefault('source_backoffs',{})
    for attempt in attempts:
        key=source_key(attempt['source'])
        if task.get('result',{}).get('integrated') and attempt['status'] in {'selected','integrated'}:
            backoffs.pop(key,None)
            attempt['status']='integrated'
        elif attempt['status']=='integrated' and task['status'] in {'failed','cancelled'}:
            # A coding/integration failure is not evidence that the career source failed.
            backoffs.pop(key,None)
            attempt['status']='selected'
        elif attempt['status']=='blocked':
            backoffs[key]={**attempt,'until':(now+timedelta(hours=24)).isoformat(),
                'reason':attempt['reason'] or 'Mission interrompue ; conserver le travail et essayer un autre candidat.'}
    if attempts and task.get('result',{}).get('integrated'):
        path=root/'.city-worktrees'/task['id']/CHECKPOINT
        temp=path.with_suffix('.tmp');temp.write_text(json.dumps(attempts,ensure_ascii=False),encoding='utf-8')
        os.replace(temp,path)
    return attempts


def source_selection_context(root: Path, now=None, *, agent_id=None) -> str:
    now=now or datetime.now(timezone.utc)
    state=_read(root/'internships_project/data/sacha_source_campaign.json')
    automatic=state.get('source_backoffs',{}) if isinstance(state,dict) else {}
    automatic=dict(automatic) if isinstance(automatic,dict) else {}
    # A daily mission may run outside a campaign. Its explicit blocked checkpoint
    # still prevents tomorrow's mission from repeating the same unsuccessful research.
    latest={}
    for path in (root/'.city-worktrees').glob('*/'+CHECKPOINT):
        try:
            modified=datetime.fromtimestamp(path.stat().st_mtime,timezone.utc)
            if now-modified>=timedelta(hours=24):continue
            for attempt in attempts_for(root,path.parent.name):
                key=source_key(attempt['source'])
                if key not in latest or modified>latest[key][0]:latest[key]=(modified,attempt)
        except OSError:continue
    for key,(modified,attempt) in latest.items():
        if attempt['status']=='blocked':
            automatic[key]={**attempt,'until':(modified+timedelta(hours=24)).isoformat()}
        elif attempt['status']=='integrated':automatic.pop(key,None)
    manual=_read(root/'internships_project/data/sacha_source_pauses.json')
    blocked=[]
    for row in {**automatic,**(manual if isinstance(manual,dict) else {})}.values():
        try:
            if row.get('until') and datetime.fromisoformat(row['until'])<=now:continue
            blocked.append({'source':str(row['source'])[:100],'reason':str(row.get('reason',''))[:150],
                            'until':row.get('until') or 'reprise manuelle'})
        except (TypeError,ValueError,KeyError,AttributeError):continue
    return ('\nSources mises de côté par le serveur : '+json.dumps(blocked[:12],ensure_ascii=False)
            +'\n'+(source_priority_request(root,agent_id=agent_id) or ''))


def source_priority_request(root: Path, *, agent_id=None) -> str | None:
    data=_read(root/'internships_project/data/sacha_source_priorities.json')
    if not isinstance(data,dict) or not isinstance(data.get('groups'),list):return None
    assignments=data.get('assignments',{})
    assigned=None
    if agent_id and isinstance(assignments,dict) and agent_id in assignments:
        until=datetime.fromisoformat(data['assignment_ends_at'])
        if datetime.now(timezone.utc)<until:
            assigned=assignments[agent_id]
            if not isinstance(assigned,list) or not assigned or any(not isinstance(v,str) for v in assigned):
                raise ValueError('Invalid source lane assignment')
            keys=[source_key(v) for names in assignments.values() for v in names]
            if len(keys)!=len(set(keys)):raise ValueError('Overlapping source lane assignments')
    lines=['Priorités explicites utilisateur : ajouter UNE source encore absente ou réellement non couverte, '
           'avant toute découverte hors liste. Stages/VIE/graduate/junior, international ; pertinence des métiers ci-dessous. '
           'La catégorie quant/market making est expressément autorisée par cette nouvelle consigne.']
    for group in data['groups'][:5]:
        if not isinstance(group,dict):continue
        names=group.get('employers');roles=group.get('roles')
        if not isinstance(names,list) or not isinstance(roles,list):continue
        if any(not isinstance(item,str) or len(item)>100 for item in names+roles):continue
        if assigned is not None:
            names=[name for name in names if name in assigned]
            if not names:continue
        lines.append(str(group.get('category',''))[:100]+': '+', '.join(names[:12])+' ; postes : '+', '.join(roles[:8])+'.')
    if assigned is not None:
        lines.append('LOT EXCLUSIF : travaille uniquement les entreprises listées ci-dessus. Les autres appartiennent à un autre agent ; aucune découverte hors lot. Si le lot est couvert ou bloqué, termine sans ajouter une entreprise hors lot.')
    if assigned is None or 'TP ICAP' in assigned:
        lines.append('TP ICAP : une seule entrée groupe ; mots-clés/alias Tullett Prebon, ICAP, Liquidnet et Louis Capital Markets, sans fiches entreprises séparées.')
    if assigned is None or 'Ostrum AM' in assigned:
        lines.append('Ostrum AM : entrée dédiée taux/crédit, même si BPCE/Natixis sont suivis.')
    if assigned is None or 'LSEG' in assigned:lines.append('LSEG : mots-clés Workspace et LCH SA.')
    lines.append('Analyse catalogue public et connecteurs locaux ; recommandations publiques à lire et vérifier. Réutilise les collecteurs disponibles. '
        'Implémente collecteur, fiche Sources et logo officiel avec tests et collecte réelle. '
        'Renseigne SOURCE_ADDED_ON à la date réelle de publication pour « Ajoutées cette semaine ». '
        'Aucune offre ou implantation supposée ; respecte pauses et secours. Le contrôleur publie et archive après confirmation publique.')
    result='\n'.join(lines)
    if len(result)>2700:raise ValueError('Source priorities exceed mission budget')
    return result


def set_source_pause(root: Path, name: str, *, resume=False, hours=None, reason='Arrêt demandé') -> dict:
    if not isinstance(name,str) or not 2<=len(name.strip())<=100 or re.search(r'[\x00-\x1f]',name):
        raise ValueError('Nom de source invalide')
    if hours is not None and not 0<hours<=720:raise ValueError('Durée invalide')
    path=root/'internships_project/data/sacha_source_pauses.json'
    pauses=_read(path)
    if not isinstance(pauses,dict):pauses={}
    key=source_key(name)
    if resume:
        # An explicit manual resume also overrides a previously automatic cooldown.
        pauses[key]={'source':name,'until':datetime.now(timezone.utc).isoformat(),'reason':'Reprise demandée'}
    else:
        pauses[key]={'source':name,'reason':str(reason)[:300],
            'until':(datetime.now(timezone.utc)+timedelta(hours=hours)).isoformat() if hours else None}
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix('.tmp');temp.write_text(json.dumps(pauses,ensure_ascii=False),encoding='utf-8')
    os.replace(temp,path)
    return pauses[key]


def sync_source_controls(root: Path, task_id: str) -> None:
    if not re.fullmatch('[a-f0-9]{32}',task_id):return
    directory=root/'.city-worktrees'/task_id
    if not (directory/CHECKPOINT).is_file():return
    if directory.is_symlink():return
    state=_read(root/'internships_project/data/sacha_source_campaign.json')
    lanes=[state,state.get('second_lane',{})] if isinstance(state,dict) else []
    agent_id=next((lane.get('agent_id','internships_engineer') for lane in lanes if lane.get('task_id')==task_id),None)
    content=json.dumps({'selection':source_selection_context(root,agent_id=agent_id)},ensure_ascii=False)
    target=directory/'.sacha-source-controls.json'
    if target.exists() and target.read_text(encoding='utf-8')==content:return
    temp=target.with_suffix('.tmp');temp.write_text(content,encoding='utf-8');os.replace(temp,target)
