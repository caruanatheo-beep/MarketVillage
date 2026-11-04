"""Bounded specialist services. Legacy agent IDs remain stable for SQLite history.

Jules coding is delegated to the local sandboxed Codex runner after human approval.
Other specialist operations expose bounded services, not arbitrary shell commands.
"""
from __future__ import annotations

import ast
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
from datetime import datetime, timezone

from .marketdesk_city import CityError

VERSION = 2
CODING_AGENTS = ("job_hunter", "city_ui_engineer", "internships_engineer", "quality_engineer")
SPECIALISTS = {"job_hunter", "finance_tutor", "developer", "innovation_lab", "securities_scout", *CODING_AGENTS}
DEFAULT_OPERATIONS = {'job_hunter':'repository_audit','finance_tutor':'quant_report',
                      'developer':'daily_questions','innovation_lab':'innovation_review',
                      'city_ui_engineer':'develop','internships_engineer':'develop','quality_engineer':'develop',
                      'securities_scout':'discover_service_contacts'}
OPERATIONS = {
    "job_hunter": {"repository_audit", "codex_review", "code_change", "prepare_branch", "develop"},
    "city_ui_engineer": {"develop"},
    "internships_engineer": {"develop"},
    "quality_engineer": {"develop"},
    "finance_tutor": {"quant_report"},
    "developer": {"daily_questions", "mock_interview", "evaluate_answer"},
    "innovation_lab": {"innovation_review"},
    "securities_scout": {"discover_service_contacts"},
}
ROLE_NAMES = {"job_hunter": "Software Engineer", "finance_tutor": "Quant Research",
              "developer": "Interview Coach", "innovation_lab": "Innovation Lab",
              "city_ui_engineer": "UI Engineer", "internships_engineer": "Sources Engineer",
              "quality_engineer": "Quality Engineer", "securities_scout": "Securities Services Scout"}


def validate_mission(agent_id: str, parameters: dict, description: str = "") -> dict:
    """Reject legacy payloads and shell commands; development prose goes to Codex only."""
    if agent_id == "internship_scout":
        if parameters.get("operation", "refresh_internships") != "refresh_internships" or set(parameters).intersection(
                {"command", "shell", "code", "script", "discover_public"}):
            raise CityError("Hugo peut uniquement actualiser les stages via Internships.")
        return {**parameters, "operation":"refresh_internships"}
    if agent_id not in SPECIALISTS:
        return parameters
    payload = dict(parameters)
    operation = payload.get("operation", "")
    if operation not in OPERATIONS[agent_id]:
        raise CityError(f"Mission incompatible avec {ROLE_NAMES[agent_id]}. Choisis une opération spécialisée.")
    forbidden = {"cached_only", "discover_public", "contact_id", "profile_id", "command", "shell", "code", "script"}
    if forbidden.intersection(payload):
        raise CityError("Cet outil ne fait plus partie des responsabilités de cet agent.")
    contradictions = {
        'job_hunter': r'\b(stage|internship|offres?|candidatures?|contacts?)\b',
        'finance_tutor': r'\b(quiz|entretien|interview|tutorat|hirevue)\b',
        'developer': r'\b(debug|deploy|déploiement|diagnostic|logs?|dépôt|repository)\b',
        'innovation_lab': r'\b(postuler|candidatures?|envoyer|déployer|merge)\b',
        'city_ui_engineer': r'\b(postuler|candidatures?|envoyer|déployer|merge)\b',
        'internships_engineer': r'\b(postuler|candidatures?|envoyer|déployer|merge)\b',
        'quality_engineer': r'\b(postuler|candidatures?|envoyer|déployer|merge)\b',
        'securities_scout': r'\b(postuler|candidatures?|envoyer|déployer|merge)\b',
    }
    if operation == 'develop':
        request = str(payload.get('request') or '').strip()
        if agent_id not in CODING_AGENTS or len(request) > 3000 or (request and len(request) < 10):
            raise CityError('Décris le développement souhaité en 10 à 3 000 caractères, ou laisse vide pour une analyse autonome.')
        payload['request'] = request
    if operation == 'code_change':
        request = str(payload.get('request') or '').strip()
        if agent_id != 'job_hunter' or not 10 <= len(request) <= 3000:
            raise CityError('Décris la correction ou fonctionnalité souhaitée (10 à 3 000 caractères).')
        payload['request'] = request
    if operation not in {'code_change', 'develop'} and re.search(contradictions[agent_id], description, re.IGNORECASE):
        raise CityError(f"Cette consigne contredit la mission exclusive {ROLE_NAMES[agent_id]}.")
    payload["role_version"] = VERSION
    return payload


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def git(root: Path, *args: str) -> str:
    try:
        completed = subprocess.run(["git", "-c", "core.longpaths=true", "-c", "core.hooksPath=NUL" if os.name == "nt" else "core.hooksPath=/dev/null",
                                    *args], cwd=root, capture_output=True, text=True, encoding="utf-8",
                                   errors="replace", timeout=25, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise CityError("Dépôt Git inaccessible ou délai dépassé.") from exc
    if completed.returncode:
        # Never return raw stderr (remote credentials and filesystem paths).
        raise CityError("Git indisponible pour cette opération. Vérifie le clone local du dépôt.")
    return completed.stdout.strip()


def repository_audit() -> dict:
    root = repo_root()
    findings, checked = [], 0
    # No .env, private data, caches, vendor files, or imported documents.
    for path in sorted([*(root / "internships_project").glob("city_*.py"), root / 'internships_project/marketdesk_city.py']):
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8-sig")
        checked += 1
        try:
            ast.parse(text)
        except SyntaxError as exc:
            findings.append({"file": path.name, "line": exc.lineno, "issue": "Erreur de syntaxe", "severity": "error"})
        for index, line in enumerate(text.splitlines(), 1):
            if re.search(r"requests\.(get|post)\(", line) and "timeout" not in line:
                findings.append({"file": path.name, "line": index, "issue": "Vérifier le délai HTTP (appel potentiellement multiligne)", "severity": "review"})
    revision, blocked, dirty = "", "", False
    try:
        revision = git(root, "rev-parse", "HEAD")
        # Read local tracking state; do not silently fetch/push to an unknown remote.
        dirty = bool(git(root, "status", "--porcelain", "--untracked-files=no"))
    except CityError as exc:
        blocked = str(exc)
    proposal = {"issue": "Ajouter un test AST de non-régression des modules City", "file": "tests/test_city_syntax_audit.py", "severity": "proposal"}
    remote = {}
    repository = os.getenv('MARKETDESK_GITHUB_REPO', '').strip()
    if not repository:
        try:
            origin = git(root,'remote','get-url','origin')
            match = re.fullmatch(r'(?:https://github\.com/|git@github\.com:|ssh://git@github\.com/)([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)/?',origin)
            if match:
                repository = match[1].removesuffix('.git')
        except CityError:
            pass
    remote_note = "Aucun dépôt GitHub reconnu : configure MARKETDESK_GITHUB_REPO=owner/repo ou un remote origin GitHub."
    if re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repository):
        import requests
        try:
            response = requests.get(f'https://api.github.com/repos/{repository}/commits', params={'per_page': 5}, timeout=(5, 10))
            response.raise_for_status()
            remote = {'source': f'https://github.com/{repository}', 'commits': [
                {'sha': item['sha'], 'url': item['html_url'], 'date': item['commit']['committer']['date']}
                for item in response.json()[:5]], 'checked_at': datetime.now(timezone.utc).isoformat()}
            latest = remote['commits'][0]['sha'] if remote['commits'] else ''
            remote['sync_status'] = 'unknown' if not revision or not latest else 'same_head' if revision == latest else 'different_head'
            remote_note = (f"GitHub : {repository}. Révision locale identique au dernier commit distant consulté. "
                           if remote['sync_status']=='same_head' else
                           f"GitHub : {repository}. La révision locale diffère du dernier commit distant consulté. "
                           if remote['sync_status']=='different_head' else
                           f"GitHub : {repository}. Comparaison des révisions indisponible. ")
            remote_note += "Consultation en lecture seule ; aucun fetch, pull ou changement de fichiers."
        except (requests.RequestException, ValueError, KeyError, TypeError):
            remote = {'blockage': 'API GitHub publique inaccessible ; aucune authentification supplémentaire activée.'}
            remote_note = f"Dépôt GitHub reconnu : {repository}, mais son API publique est inaccessible. L’audit porte sur les fichiers locaux."
    next_step = ("Audit terminé, aucun fichier généré à cette étape. Clique sur « Valider la proposition » pour préparer "
                 "le test AST dans une branche locale isolée, puis consulter son résultat. Aucun commit, push ou merge automatique."
                 if revision else "Préparation de branche bloquée : crée un dépôt Git local avec une première révision, puis relance l’audit.")
    if dirty:
        remote_note += " Des fichiers suivis ont des modifications locales non commitées ; l’audit lit leur contenu actuel."
    return {"title": "Jules · revue du code MarketDesk City", "revision": revision, "working_tree_dirty":dirty, "checked_files": checked,
            "findings": findings[:15], "proposal": proposal, "blockage": blocked, "github": remote,
            "source": "Analyse AST du clone local, référence Git" if revision else "Analyse AST locale · Git non disponible",
            "approval_required": True, "text": f"{checked} modules City analysés. Proposition : {proposal['issue']}.\n\n"
            + remote_note + "\n\n" + next_step,
            "as_of": datetime.now(timezone.utc).isoformat(), "role_version": VERSION}


def approved_base(root: Path, audit: dict) -> str:
    """Keep the approved snapshot stable even when the working application advances."""
    revision = str(audit.get('revision') or '')
    if not re.fullmatch(r'(?:[a-f0-9]{40}|[a-f0-9]{64})',revision):
        raise CityError('Révision de proposition invalide. Demande une nouvelle revue à Jules.')
    try:
        git(root,'cat-file','-e',revision+'^{commit}')
    except CityError as exc:
        raise CityError('La révision validée n’est plus disponible dans ce clone. Demande une nouvelle revue à Jules.') from exc
    return revision


def branch_context(root: Path, revision: str) -> dict:
    current = git(root,'rev-parse','HEAD')
    dirty = bool(git(root,'status','--porcelain','--untracked-files=no'))
    note = f'Branche fondée sur la version validée {revision[:12]}.'
    if current != revision:
        note += ' Le dépôt courant a évolué depuis la proposition : revoir le diff et relancer les tests sur la version courante avant intégration.'
    if dirty:
        note += ' Les modifications locales non commitées du dépôt principal ne sont pas copiées dans cette branche.'
    return {'base_revision':revision,'current_revision':current,'base_is_current':current==revision,
            'working_tree_dirty':dirty,'base_note':note}


def prepare_branch(task_id: str, audit: dict, approval: bool) -> dict:
    """Prepare a reviewable, isolated branch. Never checkout or edit the working app.

    This safe concrete improvement adds a compile-only regression test; execution
    uses Python's AST parser in-process and does not execute repository code/hooks.
    """
    if not approval or not audit.get("revision") or not re.fullmatch(r"[a-f0-9]{32}", task_id):
        raise CityError("Une revue Git datée et ta validation explicite sont requises.")
    if audit.get('coding_request'):
        from .city_coding import implement_change
        return implement_change(task_id, audit)
    root = repo_root()
    revision = approved_base(root,audit)
    branch = "marketdesk/jules-" + task_id[:12]
    directory = root / ".city-worktrees" / task_id
    if directory.exists():
        raise CityError("Cette branche a déjà été préparée. Consulte son résultat existant.")
    directory.parent.mkdir(exist_ok=True)
    git(root, "worktree", "add", "-b", branch, directory.relative_to(root).as_posix(), revision)
    target = directory / "tests" / "test_city_syntax_audit.py"
    target.parent.mkdir(exist_ok=True)
    if target.exists():
        raise CityError("Ce test existe déjà : aucun fichier existant ne sera écrasé.")
    target.write_text('"""Compile-only regression coverage; no application import or external API."""\n'
                      'import ast\nfrom pathlib import Path\n\ndef test_city_modules_compile():\n'
                      '    root = Path(__file__).resolve().parents[1] / "internships_project"\n'
                      '    for path in sorted(root.glob("city_*.py")):\n'
                      '        ast.parse(path.read_text(encoding="utf-8-sig"), filename=path.name)\n', encoding="utf-8")
    tested = list((directory / "internships_project").glob("city_*.py"))
    for source in [target, *tested]:
        ast.parse(source.read_text(encoding="utf-8-sig"), filename=source.name)
    context = branch_context(root,revision)
    return {"title": "Jules · branche prête à examiner", "branch": branch, "file": str(target.relative_to(root)),**context,
            "tests": {"method": "AST syntax regression", "passed": len(tested) + 1}, "approval_required": True,
            "text": f"Branche locale {branch} : test de compilation ajouté, {len(tested)+1} fichiers validés. Aucun commit, push ou merge automatique.\n\n"+context['base_note'],
            "role_version": VERSION}


def backtest(prices, *, lookback: int = 60, cost_bps: float = 10, strategy: str = "momentum") -> dict:
    """Long/cash, lagged close signal, next-close returns; no forward filling."""
    import pandas as pd
    values = pd.to_numeric(prices, errors="coerce").dropna().sort_index()
    values = values[~values.index.duplicated(keep="last")]
    if not 5 <= lookback <= 252 or not 0 <= cost_bps <= 100 or len(values) < lookback + 60 or (values <= 0).any():
        raise CityError("Historique insuffisant/invalide : au moins lookback + 60 clôtures positives, coûts 0–100 pb.")
    if strategy not in {"momentum", "mean_reversion"}:
        raise CityError("Stratégie non disponible. Momentum ou retour à la moyenne uniquement ; aucun faux carry sans taux de financement.")
    signal = values.pct_change(lookback, fill_method=None)
    position = ((signal > 0) if strategy == "momentum" else (signal < 0)).astype(float).shift(1).fillna(0)
    gross = position * values.pct_change(fill_method=None).fillna(0)
    turnover = position.diff().abs().fillna(position.abs())
    net = (gross - turnover * cost_bps / 10000).iloc[lookback + 1:]
    # Liquidate at the final close and charge the final one-way cost.
    net.iloc[-1] -= float(position.iloc[-1]) * cost_bps / 10000
    equity = (1 + net).cumprod()
    volatility = float(net.std(ddof=1) * math.sqrt(252))
    peak = equity.cummax().clip(lower=1)
    metrics = {"total_return": float(equity.iloc[-1] - 1), "annualized_volatility": volatility,
               "sharpe_rf_zero": float(net.mean() / net.std(ddof=1) * math.sqrt(252)) if volatility > 0 else None,
               "max_drawdown": float((equity / peak - 1).min()), "transaction_cost_bps": cost_bps,
               "observations": len(net), "turnover": float(turnover.iloc[lookback+1:].sum() + position.iloc[-1])}
    # Inline SVG from numeric values only; survives the existing Markdown result viewer.
    points = " ".join(f"{i*480/max(1,len(equity)-1):.1f},{100-(v-float(equity.min()))/max(.001,float(equity.max()-equity.min()))*90:.1f}" for i, v in enumerate(equity))
    return {"metrics": metrics, "equity": [{"date": str(d)[:10], "value": round(float(v), 6)} for d,v in equity.items()],
            "chart_svg": f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 480 110"><polyline fill="none" stroke="#8b9cfa" stroke-width="2" points="{points}"/></svg>'}


def quant_report(parameters: dict) -> dict:
    from src.data import FredCollector
    from src.data import SERIES
    series_id = str(parameters.get("series_id") or "SP500")
    # Price indices only: yields are NOT asset prices, FX carry requires funding data.
    if series_id not in {"SP500", "NASDAQCOM"}:
        raise CityError("Choisis SP500 ou NASDAQCOM pour ce backtest sur indice prix. FX carry, ETF total return et obligations nécessitent d'autres historiques validés.")
    spec = next((s for s in SERIES if s.series_id == series_id), None)
    if spec is None:
        raise CityError("Cet indice n'est pas disponible dans le fournisseur Markets configuré.")
    frame, errors = FredCollector(timeout=15).fetch_history([series_id], days=1825)
    if frame.empty or spec.label not in frame:
        raise CityError("Historique FRED indisponible. Aucun résultat de backtest ne sera inventé.")
    prices = frame.set_index("Date")[spec.label]
    result = backtest(prices, lookback=int(parameters.get("lookback", 60)), cost_bps=float(parameters.get("cost_bps", 10)), strategy=str(parameters.get("strategy") or "momentum"))
    metrics = result["metrics"]
    return {**result, "title": "Noé · recherche quantitative", "source": f"https://fred.stlouisfed.org/series/{series_id}",
            "as_of": str(frame.Date.max())[:10], "strategy": parameters.get("strategy", "momentum"), "role_version": VERSION,
            "text": f"Indice prix {series_id}, {result['equity'][0]['date']} à {result['equity'][-1]['date']}. "
            f"Rendement net {metrics['total_return']:.2%} ; volatilité annualisée {metrics['annualized_volatility']:.2%} ; "
            f"Sharpe (taux sans risque=0) {metrics['sharpe_rf_zero']} ; max drawdown {metrics['max_drawdown']:.2%}. "
            "Signal clôture décalé d'une séance, coûts par changement de position et liquidation finale. "
            "Limites : indice non directement négociable, dividendes exclus, hypothèse 252 séances, coûts fixes sans impact/slippage variable, "
            "biais de sélection, paramètres non optimisés et aucun test hors échantillon indépendant. Ce n'est pas une recommandation. " + "; ".join(errors)}


QUESTIONS = (
    ("rates", "Un client détient une obligation à taux fixe. Que devient son prix si les taux montent ? Explique duration et convexité.", ["prix", "baisse", "duration", "convexité"]),
    ("fx", "Comment expliquerais-tu un forward FX à un trésorier, et quels risques restent après la couverture ?", ["taux", "change", "contrepartie", "liquidité"]),
    ("credit", "Compare spread de crédit, risque de défaut et liquidité pour une obligation corporate.", ["défaut", "spread", "liquidité", "recouvrement"]),
    ("sales", "Un client refuse ton prix. Comment identifies-tu son besoin et défends-tu ta proposition sans promettre de rendement ?", ["besoin", "risque", "prix", "alternative"]),
    ("behavior", "Décris un désaccord avec un collègue : contexte, action personnelle et résultat vérifiable.", ["contexte", "action", "résultat", "appris"]),
    ("options", "Explique delta, gamma et vega à un client et comment ils évoluent dans un marché volatil.", ["delta", "gamma", "vega", "volatilité"]),
    ("repo", "À quoi sert un repo et quels risques distingues-tu entre collatéral et contrepartie ?", ["collatéral", "contrepartie", "financement", "haircut"]),
    ("curve", "Une courbe s'inverse : donne deux explications possibles sans en faire une prévision certaine.", ["taux", "inflation", "anticipations", "prime"]),
    ("case", "Cas Sales : un client exportateur veut protéger sa marge tout en gardant un potentiel favorable. Compare forward et option.", ["forward", "option", "prime", "risque"]),
    ("ethics", "Un client demande un rendement garanti sur un produit risqué : comment réponds-tu ?", ["risque", "garanti", "transparence", "conformité"]),
)


def interview(parameters: dict) -> dict:
    day = str(parameters.get("period") or datetime.now(timezone.utc).date().isoformat())
    offset = int(hashlib.sha256(day.encode()).hexdigest()[:4], 16) % len(QUESTIONS)
    selected = [QUESTIONS[(offset+i) % len(QUESTIONS)] for i in range(5)]
    if parameters["operation"] == "evaluate_answer":
        question_id = str(parameters.get("question_id") or "")
        question = next((q for q in QUESTIONS if q[0] == question_id), None)
        answer = str(parameters.get("answer") or "").strip()
        if not question or not 20 <= len(answer) <= 5000:
            raise CityError("Choisis une question d'Axel et fournis une réponse de 20 à 5 000 caractères.")
        normalized = answer.casefold()
        covered = [k for k in question[2] if k in normalized]
        missing = [k for k in question[2] if k not in normalized]
        return {"title": "Axel · retour sur ta réponse", "question_id": question_id, "answer": answer,
                "covered": covered, "to_review": missing, "rubric_coverage": len(covered), "role_version": VERSION,
                "text": "Pré-évaluation indicative par grille, pas une validation de l'exactitude. "
                + "Notions repérées : " + ", ".join(covered) + ". À développer : " + ", ".join(missing), "source": "Grille technique locale"}
    mock = parameters["operation"] == "mock_interview"
    return {"title": "Axel · entretien blanc hebdomadaire" if mock else "Axel · 5 questions du jour",
            "questions": [{"id": q[0], "question": q[1], "seconds": 120 if mock else 90} for q in selected],
            "text": ("Simulation HireVue : 30 secondes de préparation, 120 secondes par réponse. " if mock else "Sales · Sales & Trading · Global Markets. ")
                    + "\n\n" + "\n\n".join(f"{i+1}. [{q[0]}] {q[1]}" for i,q in enumerate(selected)),
            "source": "Banque de questions et mini-cas MarketDesk", "role_version": VERSION}


def innovation_review(excluded: set[str] | None = None) -> dict:
    import requests
    # Public repository search, no install/code execution and no invented cost claims.
    excluded = excluded or set()
    since = datetime.now(timezone.utc).strftime('%Y-%m-01')
    try:
        search = requests.get("https://api.github.com/search/repositories", params={
            "q": f"topic:ai-agents archived:false pushed:>={since} stars:>100", "sort": "updated", "per_page": 10}, timeout=(5, 10))
        search.raise_for_status()
        repositories = [item['full_name'] for item in search.json().get('items', []) if item.get('license') and item.get('html_url') not in excluded][:3]
    except (requests.RequestException, ValueError, KeyError):
        repositories = []
    if len(repositories) < 2:
        raise CityError("Veille GitHub indisponible ou aucun nouveau projet documenté. Aucune proposition recyclée comme nouveauté.")
    ideas = []
    for repository in repositories:
        try:
            response = requests.get(f"https://api.github.com/repos/{repository}", timeout=(5, 10), headers={"Accept": "application/vnd.github+json"})
            response.raise_for_status()
            item = response.json()
            if not item.get("html_url") or not item.get("license"):
                raise ValueError("licence inconnue")
            tracing = any(word in (item.get('description') or '').casefold() for word in ('trace', 'observability', 'monitor'))
            ideas.append({"repository": item["html_url"], "license": item["license"].get("spdx_id"), "checked_at": datetime.now(timezone.utc).isoformat(),
                          "title": f"Évaluer {item.get('name', repository)} pour City",
                          "description": str(item.get('description') or '')[:400],
                          "specification": "Comparer dans un prototype isolé ce projet aux services City actuels. Mesurer latence, consommation de tokens et couverture des tests sur fixtures synthétiques, sans données personnelles. Vérifier la licence et les dépendances puis revue du Desk Manager avant toute intégration.",
                          "feasibility": "Revue de compatibilité nécessaire", "complexity": "Moyenne" if tracing else "Faible",
                          "api_cost": "Aucune API payante activée. Coût d'hébergement/LLM non estimé sans mesure.",
                          "approval_required": True})
        except (requests.RequestException, ValueError, KeyError):
            continue
    if len(ideas) < 2:
        raise CityError("Veille GitHub incomplète : deux dépôts avec licence doivent être accessibles. Réessaie plus tard ; aucun résultat n'est inventé.")
    ideas = ideas[:2]
    return {"title": "Nova · deux propositions d'innovation", "ideas": ideas, "approval_required": True,
            "source": "API publique GitHub · métadonnées et licences (code non exécuté)", "role_version": VERSION,
            "text": "\n\n".join(f"{i+1}. {idea['title']}\n{idea['repository']} · {idea['license']}\n{idea['specification']}\nComplexité : {idea['complexity']}. {idea['api_cost']}" for i,idea in enumerate(ideas))}


def run_specialist(agent_id: str, username: str, parameters: dict) -> dict:
    parameters = validate_mission(agent_id, parameters)
    operation = parameters["operation"]
    if operation == "repository_audit":
        return repository_audit()
    if operation == 'codex_review':
        from .city_coding import review_repository
        return review_repository()
    if operation == 'code_change':
        from .city_coding import change_proposal
        return change_proposal(parameters['request'])
    if operation == 'develop':
        raise CityError('Le développement Codex doit être lancé par le worker City dans un worktree isolé.')
    if operation == "prepare_branch":
        # Only the approval-specific store method may supply these server-owned values.
        raise CityError("Utilise la validation de proposition du Desk Manager pour préparer une branche.")
    if operation == "quant_report":
        return quant_report(parameters)
    if operation in {"daily_questions", "mock_interview", "evaluate_answer"}:
        return interview(parameters)
    if operation == "innovation_review":
        return innovation_review(set(parameters.get('excluded_repositories') or []))
    if operation == "discover_service_contacts":
        from .network_discovery import discover_service_contacts
        return discover_service_contacts(username)
    raise CityError("Opération spécialisée inconnue.")
