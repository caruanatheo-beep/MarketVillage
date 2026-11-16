# MarketDesk City

MarketDesk City is the standalone pixel-art agent application in MarketVillage.
It shares selected Python services with Markets and Internships; each application
keeps its own interface and launch process.

## Run locally

Install Python 3.12 and the dependencies in `requirements.txt`, then run:

```sh
python -m internships_project.city_app
```

Open http://127.0.0.1:7862. Account configuration and provider credentials remain
in the local environment; no credentials or user database are included here.
The root README documents the shared services and configuration.

Markets runs with `python app.py`; Internships with `python app_internships.py`.
City reads offers from the public Internships catalogue, without launching the
Internships interface or its employer collectors. Markets remains a shared Python service.

The public feed is `https://caruanatheo-beep.github.io/Internships-Offres/offers.json`.
City checks it every five minutes and on a manual Hugo synchronization. It validates
the schema, dates, URLs and response size, then keeps an atomic local copy. A failed,
empty or older response cannot replace the last valid catalogue. If no public copy
exists, City reads the existing local offers cache without launching collection.
The Stages panel shows provenance, catalogue time, source alerts and fallback warnings;
catalogues older than 36 hours are flagged. The first synchronization establishes a
baseline; it does not report the entire catalogue as newly discovered.

## Agents and recurring work

The Desk Manager is the user-facing coordinator. Mira handles markets, Jules
code audits, Codex improvement proposals and development in isolated worktrees, Lina networking and sourced education,
Iris drafts, Axel interviews, Noe quantitative research, Nova innovation, and
Hugo internships. See [current role contracts](internships_project/CITY_AGENT_ROLES.md)
for their precise operations, schedules, catch-up rules, approvals and limits.

Contacts, profiles, chat history and settings are account-scoped SQLite data.
The repository excludes runtime data, exports, credentials and local tooling.
No messages, applications, GitHub pushes or deployments are sent automatically.
Authorized coding missions can integrate tested changes locally in isolated worktrees.
The cockpit includes scheduled automatic coding work from the shared instance;
other accounts' manual requests remain private. Shared missions owned by another
account are read-only. Git validation, conflicts and access errors require correction;
only transient Git locks and timeouts are retried automatically.

An explicitly authorized 24-hour source campaign can run with
`python scripts/run_sacha_source_campaign.py`. Sacha uses GPT-6.1 Sol with high
reasoning through the ChatGPT subscription, checks the public sources catalogue,
and makes one attempt every two hours without overlapping another Sacha task.
Every attempt compares existing sources and public visitor suggestions before
selecting one employer source internationally, with preference for Institutional
Sales, Sales Trading and related market sales roles. Suggested links and text are
untrusted inputs; their retrieval is read-only and does not archive submissions.
The controller applies only the tested mission delta to the current public release,
pushes it without force, and checks the GitHub Pages job. Conflicts or failed
deployments stop further publications. No complete workspace file is copied into
the release. Local City and the controller must remain running; no new missions
are started after 24 hours. The account-scoped Manager chat records the outcomes.

## Frontend

The compiled frontend and its static resources are included. To rebuild:

```sh
cd internships_project/city_frontend
npm ci
npm run build
```

The build checks TypeScript, furniture collisions, workstation paths and golf
routes. The current village has fourteen workstations. Upstream asset and engine
licenses are retained alongside their files.

## Checks

City check (14 November 2026): 662 non-browser City tests and the frontend build
passed. The live City instance served the public catalogue (426 offers, no source
alerts at verification) and answered a Codex chat probe. Browser UI tests remain
unverified in this environment; no real email generation or send was performed.

```sh
python -m pytest -q -m "not live"
```

Tests use temporary databases and mocked providers where needed. Real provider
availability, costs and search yields vary; a passing local test does not
certify financial answers or exhaustive coverage of contacts and internships.

Publication check (2 November 2026): the full non-live suite returned 350 passes
and 10 failures. Failures concern Internship connector/status/order expectations,
French LinkedIn follow-up wording, a Gradio label, and two subprocess startup
checks under the local embedded Python interpreter. They have not been suppressed;
the full suite is not currently green. City-focused checks and the frontend build
passed during the implementation work.
