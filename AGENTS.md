# Project development

This repository contains three separate applications: Markets (`app.py`), Internships (`app_internships.py`), and MarketDesk City (`python -m internships_project.city_app`). Keep their interfaces and route registration separate; MarketDesk City must not be embedded in the Internships app. Shared server-side services may be reused where needed.

- Start with a narrow `rg --files` or `rg -n` search and read only the files needed for the task. Do not dump entire directories, generated assets, caches, or logs.
- For cross-file questions, query the local Graphify index first: `.codex-tools/python312/python.exe scripts/graphify.py query "<question>" --budget 1200`. Use source files to verify the answer. Run `update .` only after relevant code changes or when the index is stale.
- Reuse existing components, services, and tests. Make the smallest complete change, including necessary callers and validation; avoid duplicate implementations and speculative scaffolding.
- Keep `.env`, user data, CVs, exports, and authentication material out of search output, Graphify, and commits. Graphify exclusions live in `.graphifyignore`.
- Run the focused test or build for the touched area. Expand testing only to resolve a concrete risk.
- Preserve existing auth, APIs, and user data. Do not enable third-party hooks, model gateways, or new paid APIs without explicit approval.
