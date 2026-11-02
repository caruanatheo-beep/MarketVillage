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
City can call their collectors directly without launching either interface.

## Agents and recurring work

The Desk Manager is the user-facing coordinator. Mira handles markets, Jules
code audits and isolated proposals, Lina networking and sourced education,
Iris drafts, Axel interviews, Noe quantitative research, Nova innovation, and
Hugo internships. See [current role contracts](internships_project/CITY_AGENT_ROLES.md)
for their precise operations, schedules, catch-up rules, approvals and limits.

Contacts, profiles, chat history and settings are account-scoped SQLite data.
The repository excludes runtime data, exports, credentials and local tooling.
No messages, applications, merges or deployments are sent automatically.

## Frontend

The compiled frontend and its static resources are included. To rebuild:

```sh
cd internships_project/city_frontend
npm ci
npm run build
```

The build checks TypeScript, furniture collisions, workstation paths and golf
routes. The current village has nine workstations. Upstream asset and engine
licenses are retained alongside their files.

## Checks

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
