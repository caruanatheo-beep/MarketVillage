---
title: AI Sales Desk Assistant
colorFrom: gray
colorTo: yellow
sdk: gradio
sdk_version: 6.28.0
python_version: 3.12
app_file: app.py
pinned: false
license: mit
short_description: AI market intelligence for Sales professionals
tags:
  - finance
  - macroeconomics
  - fixed-income
  - agentic-ai
  - gradio
---

# AI Sales Desk Assistant

## MarketVillage / MarketDesk City

This repository also contains **MarketDesk City**, the standalone pixel-art agent
workspace. Start it with `python -m internships_project.city_app` after installing
`requirements.txt`. See [City setup](MARKETDESK_CITY.md) and
[current agent roles and schedules](internships_project/CITY_AGENT_ROLES.md).
Markets (`app.py`), Internships (`app_internships.py`) and City keep separate
interfaces while sharing selected server-side services. Secrets, personal data,
SQLite databases and local exports are excluded from this repository.

AI Sales Desk Assistant is an agent-first Python and Gradio application designed for financial-markets Sales professionals. Its main product is an AI Sales Copilot that turns live public-market data, official economic releases, macro events and approved research into usable desk intelligence and client-conversation preparation.

The application is built to produce concise and auditable market intelligence. It separates observed data from interpretation, attaches sources to research outputs and preserves a deterministic fallback when model inference is unavailable.

Developed by **Théo Caruana**, MSc Financial Markets & Investments candidate at SKEMA Business School, with previous experience in Fixed Income and Derivatives Brokerage, Liquidity Sales and Global Markets Risk.

> This project uses public information only. It does not contain confidential employer data or proprietary research. It is intended for decision support and educational demonstration, not investment advice. Client-facing content requires human review.

## Main features

- Live cross-asset dashboard covering rates, FX, equities, volatility, commodities, credit and macro indicators.
- Official U.S. Treasury curve with previous-session comparisons.
- FRED integration with bounded fallbacks and historical charts.
- Recent official news from major central banks and economic institutions.
- Official macro and central-bank calendar with upcoming-event links.
- AI Sales Copilot as the default workspace, with workflows for morning preparation, change detection, move explanation, event scenarios and client-call preparation.
- Sales-ready answers structured around the bottom line, observed moves, driver confidence, client angle, next catalysts and open risks.
- Controlled tool selection, evidence registration, source auditing and session-level budgets.
- Local RAG over approved Federal Reserve, ECB, IMF and BIS publications.
- Dynamic official RAG with concurrent feed synchronization, persistent cache and automatic recovery through the live official-news pipeline.
- Desk-aware Sales workflow tool for client segmentation, discovery questions, scenario discipline and prioritization of commercially relevant moves.
- Deterministic evidence coverage score with no additional model call.
- Session-only conversational memory with a visible reset control.
- Professional PDF reports and email-ready drafts.
- Safe fallback research when the model or an external data provider is unavailable.

## Application sections

| Section | Purpose |
| --- | --- |
| Research Agent | Primary workspace for source-backed analysis, scenario mapping and client-call preparation |
| Overview | Supporting market observations, yield curve, cross-asset chart and morning brief |
| Markets | Market monitor with levels, daily changes, freshness and sources |
| News | Recent official macro and central-bank publications |
| Calendar | Upcoming official economic and policy events |
| Historical Charts | Up to six selected series over configurable lookback periods |
| Reports | PDF market reports with charts, catalysts, sources and email drafts |

## Three separate applications

| Project | Entry point | Default local address |
| --- | --- | --- |
| **Markets — AI Sales Desk** | `python app.py` | `http://127.0.0.1:7860` |
| **Internships** | `python app_internships.py` | `http://127.0.0.1:7861` |
| **MarketDesk City** | `python -m internships_project.city_app` | `http://127.0.0.1:7862` |

Each entry point serves its own interface. MarketDesk City is no longer embedded in, mounted by, or displayed as a tab in Internships. The apps remain in one repository and reuse selected server-side data services; their interfaces and launch processes are separate.

### MarketDesk City

MarketDesk City has its own FastAPI server. The tower presents seven interactive agent workstations, and the Desk Manager coordinates persistent workflows among the six specialists. The seven chats use Pydantic AI and specialized tools. Install the root `requirements.txt` and configure `OPENAI_API_KEY` server-side. Sensitive actions remain behind their existing approval flows. See [MARKETDESK_CITY.md](MARKETDESK_CITY.md) for startup instructions, integrations and limitations.


The audited employer-source inventory, connector status and access limits are documented in [internships_project/SOURCES.md](internships_project/SOURCES.md).

### Local Codex tools

Codex discovers the project skills in `.agents/skills/` and the short workflow rules in `AGENTS.md`. Graphify runs locally without a model call; its index excludes secrets and user data and is ignored by Git. From the project root:

```powershell
.\.codex-tools\python312\python.exe scripts\graphify.py query "Where is City chat routed?" --budget 700
.\.codex-tools\python312\python.exe scripts\graphify.py update .
```

Ponytail is installed as a project skill without lifecycle hooks. OmniRoute 3.8.52 is installed under `.codex-tools/omniroute`, with an isolated Node 24 runtime. An opt-in Codex profile lives at `~/.codex/omniroute-local.config.toml`; the usual `~/.codex/config.toml` and its authentication are unchanged. The profile targets a local gateway and uses `auto/subscription`, which fails closed when no eligible subscription provider is connected. No provider account, paid API, or gateway is enabled by this setup. To use it later, configure the gateway and its `OMNIROUTE_API_KEY` environment variable, then launch Codex explicitly with `codex --profile omniroute-local`. The isolated `.codex-tools/` directory is local and is not required to run MarketDesk.

Markets and Internships are independent Gradio applications in this repository. Their source code and caches are separate; neither embeds the other's interface. All three applications can run at the same time:

```powershell
.\.venv\Scripts\python.exe app.py
.\.venv\Scripts\python.exe app_internships.py
\.venv\Scripts\python.exe -m internships_project.city_app
```

Markets uses port 7860, Internships 7861, and MarketDesk City 7862 by default. `run_internships.ps1` starts only the internships application. For a separate environment, install `internships_project/requirements.txt` for Internships; deploy each service with its entry point above. The apps read the root `.env` for their own server-side settings. Browser-local tracking does not transfer between different ports or domains because browser storage is tied to the site address.

Internships covers public SmartRecruiters, Greenhouse, Workday and Société Générale career postings, plus VIE and graduate opportunities. Advertised April–September 2027 starts appear first, followed by the Paris-first ranking. Filters and browser-local application tracking remain available.

The Internships interface has three top-level tabs: **Jobs**, **AI Assistant**, and **My Profile**. Jobs contains **Offres**, **Nouvelles pour moi**, and **Mes candidatures**. Its wide keyword search covers job title, company or city, with a contract dropdown to the right; submit with Enter or use **Actualiser** to refresh the feeds. The single-column offers view has all, today, and last-seven-days publication filters; undated offers are excluded from the dated filters. **Mes candidatures** shows a four-column pipeline (preparation, in progress, interviews, decisions), actions due in the next seven days, and applications missing a next action. Select an offer and its current stage in the same row, then click **Enregistrer**. Notes and dates are optional in the collapsed details panel. The same form updates an existing application, including one that disappears from the live feeds. Use **Sauvegarder ou restaurer mon suivi** to copy a JSON backup or transfer it to another browser.

The default interface uses a light theme with a dark search panel and single-column results. Application stages are **À examiner**, **À candidater**, **Postulé**, **OA**, **HV**, **Interview**, **Offer**, **Rejected** and **Écartée**. Existing browser records using the previous French stages are mapped to the new stages when loaded.

In **My Profile**, enter a name and import a PDF, DOCX, TXT or MD CV, or write a summary. **Analyser et enregistrer ce profil** uses the existing `OPENAI_API_KEY` to extract verifiable experience, skills, target roles, locations, contracts, desired start dates and points to confirm. Review and edit these fields, then save. Named profiles are stored in this browser, separately from application tracking; the original uploaded file is not saved in the profile record. The AI request uses `store: false`. On a local installation, the prior `internships_project/data/candidate_profile.txt` appears as a legacy profile until edited; a shared deployment never reads that local file. PDF import requires `pypdf` from `internships_project/requirements.txt`.

In **AI Assistant**, select a named profile and click **Analyser les meilleures offres récentes**. The selected profile automatically supplies the candidate name, evidence and search preferences. The assistant selects up to three offers published in the last 21 days, excluding offers marked **Hors cible** or already applied to, and produces a brief for each. Select one offer to generate an editable French or English cover letter, review it, save a draft for that profile and offer in this browser, and export the edited text as an A4 PDF. `INTERNSHIPS_AI_MODEL` optionally overrides the default `gpt-4o` model.

The ranking uses the selected profile's roles, locations, contract types and start months. For an explicit Sales or Trader target, matching job titles rank first and opposite-role titles are excluded; past CV roles do not override the desired role. A profile without target roles must be completed in **My Profile** before the assistant recommends offers. The AI-generated summary does not replace the latest CV for exact experience dates or degree status.

The agent examines the leading six results to find up to three accessible offers, preferring different employers when relevance is close. Choosing a profile in **AI Assistant** launches this analysis automatically; the analysis button remains available to refresh it. Each brief shows why an offer was selected and whether the full posting could be read. A missing or explicitly closed posting is replaced before the AI call. Before sending a letter, review the CV, start date, internship agreement and international work authorisation checks shown next to it. Letters can be drafted in French or English. **Sauvegarder ce brouillon** stores the edited text per profile and offer in the current browser; it is restored when that same profile and offer are selected again.

## Research workflow

The Research Agent follows a bounded workflow:

1. Classify the request.
2. Select only the relevant research tools.
3. Collect current market data, official news, events and approved RAG passages.
4. Validate and deduplicate the evidence.
5. Calculate a transparent evidence coverage score.
6. Use a maximum of one model call to synthesize the answer.
7. Append the audited source list and retain a deterministic fallback.

The model does not calculate values already available to Python. Market changes, curve spreads, timestamps, source admission, evidence scores, charts and usage limits remain deterministic and testable.

## Data sources

- U.S. Treasury for official daily par yields.
- FRED for public macroeconomic, rates, policy, FX and credit series.
- Public market quotes for intraday cross-asset observations.
- Federal Reserve, European Central Bank, Bank of England and Bank of Japan official feeds.
- Official economic and central-bank schedules.
- Approved public research documents from the Federal Reserve, ECB, IMF and BIS.

Availability and publication frequency vary by provider. Missing observations remain explicitly unavailable and are never replaced with demonstration data.

## Repository structure

```text
.
├── app.py
├── requirements.txt
├── run_local.ps1
├── diagnose_fred.py
├── rag_documents/
│   ├── *.pdf
│   └── rag_index.json
├── src/
│   ├── agent.py
│   ├── analytics.py
│   ├── calendar.py
│   ├── config.py
│   ├── data.py
│   ├── evidence.py
│   ├── llm.py
│   ├── memory.py
│   ├── models.py
│   ├── news.py
│   ├── reports.py
│   ├── security.py
│   ├── tools.py
│   ├── ui.py
│   └── web_search.py
└── tests/
```

## Local installation

Python 3.12 is recommended for deployment. From PowerShell in the project directory:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py
```

If Python 3.12 is not installed:

```powershell
py install 3.12
```

The application normally opens at [http://127.0.0.1:7860](http://127.0.0.1:7860). When this port is occupied locally, the entry point selects the next available port and prints the address in the terminal.

In MarketDesk City, **Résultats disponibles → Voir** opens a readable mission result. Contributions from the same workflow appear together. **Résultats** lists all completed missions; technical data and event logs remain available in the result details.

When City runs on loopback, its launcher reserves a free port starting at `MARKETDESK_CITY_PORT` (default 7862) and prints the exact `/city/` URL. Occupied ports are skipped without stopping existing processes. Public/hosted deployments keep their configured port unchanged.

City's **Markets** and **Internships** shortcuts start the independent dashboards with City's Python interpreter, then open them in a new tab. Local instances started by City are reused during that City session, use free loopback ports 7870–7889 and retain their existing login mechanisms. Allow popups for the local City site. This launcher is authenticated, accepts only the two fixed application scripts and refuses remote/hosted requests. Both dashboards' dependencies must be installed in the same Python environment. Stopping City does not stop an opened dashboard; restarting City can start a new instance. The direct launch commands continue to work separately.

The included script can automate local setup and launch:

```powershell
.\run_local.ps1
```

## Environment variables

Create a local `.env` file in the repository root. Never commit this file.

Minimal Hugging Face configuration:

```dotenv
ENABLE_LLM=true
ALLOW_PUBLIC_LLM=false
LLM_PROVIDER=huggingface
LLM_MODEL=Qwen/Qwen2.5-7B-Instruct:featherless-ai
HF_TOKEN=your_hugging_face_token
```

Optional configuration:

```dotenv
FRED_API_KEY=
REQUEST_TIMEOUT_SECONDS=8
CACHE_TTL_SECONDS=900
LIVE_CACHE_TTL_SECONDS=60
MAX_LLM_CALLS_PER_SESSION=5
LLM_COOLDOWN_SECONDS=10
MAX_AGENT_STEPS=4
MAX_TOOL_CALLS_PER_SESSION=18
MAX_CALLS_PER_TOOL=4
MAX_MEMORY_TURNS=6
MAX_CONTEXT_CHARS=18000
MAX_NEWS_ITEMS=10
ENABLE_WEB_SEARCH=true
WEB_SEARCH_MAX_RESULTS=5
```

An OpenAI-compatible endpoint can be used instead:

```dotenv
ENABLE_LLM=true
LLM_PROVIDER=openai_compatible
LLM_MODEL=your_supported_model
OPENAI_API_KEY=your_api_key
OPENAI_BASE_URL=https://api.openai.com/v1
```

`FRED_API_KEY` is optional. The application can use public FRED routes and other public-source fallbacks when the key is absent.

## Tests

Run the deterministic test suite before each release:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

The suite covers market calculations, data fallbacks, calendar and news parsing, agent tool selection, evidence admission, security controls, reports, UI construction and application startup.

To diagnose FRED independently from the interface:

```powershell
.\.venv\Scripts\python.exe diagnose_fred.py
```

## Hugging Face deployment

1. Create a new Hugging Face Space.
2. Select **Gradio** as the SDK and **Python 3.12** as the runtime.
3. Upload or push the repository with `app.py` and this `README.md` at the root.
4. Open **Settings**, then add credentials under **Secrets**.
5. Add non-sensitive limits under **Variables** if the defaults need to change.
6. Wait for the build to complete and review the runtime logs.
7. Test the dashboard, Research Agent, calendar, historical charts and report export.

Recommended Space secrets:

```text
HF_TOKEN
FRED_API_KEY          # optional
OPENAI_API_KEY        # only for an OpenAI-compatible provider
```

Recommended Space variables:

```text
ENABLE_LLM=true
ALLOW_PUBLIC_LLM=true
LLM_PROVIDER=huggingface
LLM_MODEL=Qwen/Qwen2.5-7B-Instruct:featherless-ai
```

`ALLOW_PUBLIC_LLM=true` permits anonymous visitors to trigger model calls. Enable it only after setting provider budgets and session limits. When it is false, the dashboard and deterministic research fallback remain available.

## Security and cost controls

- Credentials are loaded from environment variables and redacted from errors.
- External URLs must use HTTPS and pass a domain allowlist.
- Private-network targets, unsupported ports and unsafe schemes are rejected.
- External content is treated as data, never as an instruction.
- Model calls, tool calls, context size, memory and search results are bounded.
- General questions use the existing dashboard snapshot; live web search is reserved for relevant causal or announcement requests.
- Client-ready conversion does not create a second model call.
- Conversation memory remains inside the active Gradio session and is not intentionally stored permanently.

## Known limitations

- Public quotes can be delayed and are not a substitute for a professional market-data terminal.
- Official macro observations may be published with a lag and may later be revised.
- Public-source connectivity can vary across local Windows, cloud and institutional networks.
- The calendar does not invent unavailable consensus or actual values.
- The local RAG corpus is intentionally limited to approved public documents.
- Model output may contain errors and must be reviewed before external distribution.
- The application does not provide investment advice, order execution or automatic client communication.
- Internship coverage is limited to selected employers with public job feeds. If no matching VIE is available in those feeds, the Internships tab links to Business France's official VIE search. Always check the original posting for eligibility and closing dates.
- On the local Internships app, application tracking is saved automatically to `internships_project/data/user_state.json` with a local backup. Existing browser tracking is imported on first launch. The file is ignored by Git. In shared mode, each authenticated account has separate profiles, applications, preferences and letter drafts in SQLite; public job offers remain shared.

## Share Internships with friends

Configure your own administrator account in the hosting service's secret environment variables (never commit passwords):

```text
INTERNSHIPS_USERS_JSON={"theo":"a-long-unique-password"}
INTERNSHIPS_ADMIN_USER=theo
INTERNSHIPS_USER_DB=/data/accounts.sqlite3
# Optional: share this code with friends to restrict registration.
INTERNSHIPS_SIGNUP_CODE=a-long-private-invitation-code
```

Use at least 12 characters per password. Start `python app_internships.py`. Friends can click **Créer un compte** on the login page and choose their own username and password. Usernames must be lowercase, 3–32 characters, with letters, digits, `.`, `-` or `_`. New passwords are stored as salted hashes in SQLite; the initial administrator password remains in `INTERNSHIPS_USERS_JSON`. `INTERNSHIPS_ADMIN_USER` must match one of those initial accounts; if omitted, the first account in the JSON is the administrator. Only that account sees the **Administration** tab, with usernames and registration dates but no passwords. Set `INTERNSHIPS_SIGNUP_CODE` if you want friends to enter a shared invitation code when registering; without it, registration is open to anyone who can reach the site.

The offer collectors continue refreshing the shared feed hourly. The administrator sees the latest snapshot; other accounts see the latest snapshot at least **3 hours old**, including in AI recommendations. The rolling history is stored in `internships_project/data/internships_history.json` beside the shared offer cache. On first startup after this change, an existing cache is used as the baseline; if no old cache exists, other accounts will see offers after the first collected snapshot has aged three hours. Keep the data directory on persistent storage when hosting.

Deleting a registered account permanently blocks reuse of that exact username and removes the account’s private records. Because accounts currently require only a username and password, this cannot identify the same person if they register under a different username. Preventing that would require a verified identity such as email verification or an administrator-controlled individual invitation.

The Administration tab also records each AI generation's account, action (profile analysis, offer recommendations or letter), model, timestamp, response ID, input tokens, cached input tokens and output tokens. It shows totals by account, action, month and model, plus the 50 most recent calls. The USD figure is an **estimate**, calculated when the response is received using public text-token rates for supported models. Missing usage or unknown pricing stays unknown instead of becoming $0. Calls made before this ledger was added cannot be reconstructed. The ledger stores neither prompts nor CV contents and is not an OpenAI invoice; compare it with your OpenAI Platform billing for final charges. Rates were checked on 26 October 2026 against the [GPT-4o](https://developers.openai.com/api/docs/models/gpt-4o), [GPT-4o mini](https://developers.openai.com/api/docs/models/gpt-4o-mini) and [GPT-4.1 mini](https://developers.openai.com/api/docs/models/gpt-4.1-mini) model pages.

The app keeps Gradio's authenticated login and associates private records with each username. On Railway or Hugging Face Spaces, startup refuses to expose the app without `INTERNSHIPS_USERS_JSON`. Set `INTERNSHIPS_USER_DB` to a **persistent volume** path: it now contains both login accounts and private profiles/candidatures. Without a persistent volume, registered accounts and personal data can disappear after a restart or redeployment. Back up the SQLite file on that volume. Keep the API key in the host's secrets too; AI generations use the same key and quota for all accounts. Serve the shared app over HTTPS.

Before public hosting, terminate TLS at the platform or reverse proxy. Railway and Hugging Face deployments are detected automatically; for another HTTPS host, set `INTERNSHIPS_PUBLIC_HTTPS=1` so signup cookies and session-cookie handling use the secure production mode. Do not set it for local HTTP development. Public hosting must set `INTERNSHIPS_USERS_JSON`, `INTERNSHIPS_ADMIN_USER`, `INTERNSHIPS_USER_DB`, `OPENAI_API_KEY`, and a persistent volume. The app disables Gradio analytics, uses no advertising tracker, rate-limits failed login attempts and paid AI generations, and serves shared-mode PDFs through an authenticated account-bound route. Each account is limited to 12 AI generations per hour and one in-flight generation; a generated PDF download is available to its owner for one hour. Generic Gradio file URLs are disabled in shared mode.

CV files are limited to 8 MB and PDF, DOCX, TXT or MD; the server extracts the text and deletes the temporary upload immediately. The extracted text and profile details remain in that user's profile until the profile/account is deleted. AI analysis and letter requests send the selected profile facts and offer details to OpenAI with `store:false`; the provider's own processing terms still apply. The private `/confidentialite` page summarizes this data flow. Deleting a profile removes its saved data, AI brief cache and pending PDF exports; deleting a registered account also blocks that username. This description is informational, not a legal-compliance guarantee.

Browser storage is tied to the exact origin (host and port). Before moving to a new host, start the authenticated app locally on the **same address and port** used previously, sign in to your account, open **Mon profil → Importer mes données de ce navigateur**, and click the import button. Existing account records take precedence if a field conflicts. If your former local tracker lives in `internships_project/data/user_state.json`, migrate it on that computer with `python -m internships_project.migrate_local_state theo` after setting `INTERNSHIPS_USER_DB` to the same database path. Use the exact username. The browser import transfers profiles and drafts; the command transfers the local tracker and preferences. Copy the resulting SQLite database to the host's persistent volume before inviting friends.

Gradio's built-in login is suitable for a small invited group. It does not provide multifactor authentication, automatic lockout or advanced account management. Anyone with an account can use the shared AI API quota. Do not use a temporary `share=True` URL as durable hosting: it depends on your computer remaining on. The app does not currently send invitation or password-reset emails.

The separate Internships process refreshes employer listings at startup and then every hour while it runs. Its cache is valid for one hour; **Actualiser** can trigger a manual refresh. BPCE/Natixis/BRED offers are read from the group's public Open Data JSON instead of its JavaScript-only career listing. CACEIS uses the direct French offer links. The sources detail shows direct-site counts, unavailable connectors and sites with no matching offers; a career portal link alone does not import jobs. Market-role filtering excludes private equity, back-office and unrelated corporate finance roles, including from an existing cache. Closed BNP Paribas listings are excluded. Set `VIE_API_KEY` in `.env` to enable the optional Business France search API; without it, the tab shows current verified VIE seed offers and links to the official portal. Never commit the key. Start dates are shown and filtered only when explicitly stated in a posting.

### E-mail alerts for newly detected offers

For an initial trial, alerts can go to **one address** using a standard SMTP account. The feature is disabled by default and uses no LLM or paid email API. Add the following to the server's environment or local `.env` (never commit the password):

```dotenv
INTERNSHIPS_ALERT_EMAIL_TO=you@example.com
INTERNSHIPS_ALERT_EMAIL_FROM=alerts@example.com
INTERNSHIPS_SMTP_HOST=smtp.example.com
INTERNSHIPS_SMTP_PORT=587
INTERNSHIPS_SMTP_USERNAME=your-smtp-login
INTERNSHIPS_SMTP_PASSWORD=your-smtp-password
INTERNSHIPS_SMTP_SECURITY=starttls
INTERNSHIPS_EMAIL_ALERTS_ENABLED=1
```

Use a sender address authorized by your SMTP provider. Set `INTERNSHIPS_SMTP_SECURITY=ssl` and port `465` if the provider requires implicit TLS. After configuring the address and SMTP credentials, run `python -m internships_project.email_alerts --test` to send one explicit SMTP test message, or `python -m internships_project.email_alerts --preview` to email a styled preview using up to three already cached offers. Preview does not collect sources or change the alert history. Restart the internships app after changing `.env`. The first completed collection after activation records the current offers as a baseline and sends **no bulk alert**. Each later completed collection sends one email containing only newly detected, deduplicated offers and their direct links. The digest includes styled HTML offer cards and a plain-text fallback. Unverified JobTeaser sitemap links are excluded. A failed SMTP delivery will be retried at the next refresh if the offers remain in the feed. The seen-offer ledger lives in the same persistent SQLite database as the accounts (`INTERNSHIPS_USER_DB`); keep that volume when hosting. Alerts run only while the app process is running and can also follow a manual refresh.

The AI Assistant's **Mail** subtab for reviewed speculative applications is documented in [internships_project/MAIL.md](internships_project/MAIL.md), including its source-backed address hypotheses, per-account data, SMTP/Resend configuration, limits, and response-tracking limitation.

The internship fetch runs independent Workday searches concurrently. SmartRecruiters keeps all matching cards while opening full descriptions for at most 50 high-priority offers per board, so start dates on other cards may remain unknown. Known employers display their own site's brand icon when the browser can load it; cards fall back to initials when no icon is configured or available.

Internship results are saved to `internships_project/data/internships_cache.json` (ignored by Git). The application opens from this snapshot immediately and refreshes in the background; the refresh button starts a new fetch. Legacy Adzuna offers are excluded when this cache is read. **All** shows every matching offer, while **Weekly** shows offers whose publication or first detection date is today or one of the preceding six days (UTC). Both views share the same filters. Use **New since my last visit** and **Mark offers as viewed** to review new postings, or mark a tracked offer **Écartée** to hide it. Viewed markers remain in the browser; tracked applications are also saved locally on the standalone app.

When a source supplies no publication date, the first day the app detects the offer is saved as its date. Cards and AI briefs label this date **Détectée**; later refreshes retain it, and an employer publication date replaces it if one becomes available. Older undated cached offers use the cache snapshot date as the earliest recoverable detection date. These offers can then appear in Today and Weekly based on detection date.

Use the JSON export in **Mes candidatures** to move application records to another computer.

Adzuna is no longer queried, even if `ADZUNA_APP_ID` and `ADZUNA_APP_KEY` remain in `.env`. Remove those secrets from your deployment when convenient. JobTeaser search and detail pages returned HTTP 403 to the app's unauthenticated HTTP client on 25 October 2026. An experimental connector instead reads [JobTeaser's public sitemap](https://assets-cf.jobteaser.com/sitemaps/sitemap.xml) once per day, selecting only URLs that explicitly identify a followed employer and relevant early-career role. The card opens that exact JobTeaser URL. Missing location and publication dates are not guessed; the app stores its first detection date. Sitemap links are not verified open offers and are excluded from AI briefs. Matching direct employer offers take precedence in deduplication. The daily sitemap result is cached separately in `internships_project/data/jobteaser_sitemap_cache.json`.

## Release workflow

Use `main` for the stable public version and a separate branch for each material update:

```powershell
git checkout -b feature/short-feature-name
git add .
git commit -m "Describe the feature"
git push -u origin feature/short-feature-name
```

After validation, merge into `main` and create a version tag:

```powershell
git checkout main
git pull
git tag v2.8.0
git push origin main --tags
```

## Intelligence refresh controls

- `INTRADAY_REFRESH_SECONDS` refreshes quote-capable instruments only (default: 120, accepted range: 60–300).
- `MACRO_REFRESH_SECONDS` refreshes FRED/Treasury and the market snapshot less frequently (default: 1800).
- `RAG_SYNC_SECONDS` controls the background refresh of the official Fed, ECB, BIS and IMF publication catalogue (default: 21600).
- `RAG_MAX_DOCUMENTS` bounds the persistent dynamic corpus (default: 120).
- `TRADING_ECONOMICS_API_KEY` activates the market-expectations calendar used for previous, consensus and actual values. `guest:guest` is the limited default; use your own key for production coverage.

The desk profile selector adapts the brief and agent synthesis to Rates Sales, FX Sales, Cross-Asset or Market Risk. Consensus data are merged from Trading Economics and can be overridden in `data/macro_expectations.csv` using the columns `date,title,previous,consensus,actual,unit,source_url`. Rows are matched to official events by date and title; surprise is calculated automatically. Market reactions are explicitly labelled as observed moves rather than proven event causality. The Research Agent tab also contains a document manager for adding, editing, removing and reindexing local PDF research while official-feed documents continue to synchronize automatically.

## License

Released under the [MIT License](LICENSE).

## Author

**Théo Caruana**  
MSc Financial Markets & Investments, SKEMA Business School
