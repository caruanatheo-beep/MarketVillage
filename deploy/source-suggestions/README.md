# Private source suggestion inbox

Cloudflare Worker with D1 storage and schema migrations.
`POST /suggestions` accepts anonymous, bounded public source metadata from
the GitHub Pages origin. Public proposals expose only company, career URL,
comment, timestamp and identifier. IP hashes stay private.
Suggestions never trigger emails. No SMTP, AI key or GitHub write token is
needed by this service. The existing offer email alerts are independent.
`COLLECTOR_TOKEN` is retained as the private archive credential and HMAC key
for compatibility with the prepared hosting configuration. Legacy delivery
columns in the database remain unused; `/claim` and `/ack` no longer exist.

`POST /archive` (collector authentication required) removes proposals from the
public list after implementation. Records archived more than 30 days ago are
purged on the next authenticated archive request.

Build: `node scripts/build.mjs`. Tests: `node --test tests/worker.test.mjs`
(Node 22.13+; built-in SQLite is used only by tests).

Deploy directly to Cloudflare with `wrangler.jsonc`: run `wrangler d1 migrations
apply marketdesk-source-suggestions --remote`, set `COLLECTOR_TOKEN` using
`wrangler secret put COLLECTOR_TOKEN`, then `wrangler deploy`. Use the Free plan.
Migrations live in `drizzle/`. The receiver is public for anonymous submission;
the archive route still enforces its secret. No domain purchase is required.
Never store secrets, runtime data, addresses or SMTP configuration in source.

Application logs contain no submitted text or credentials. Hosting providers
can still retain infrastructure request logs. Origin checks are not identity
checks; atomic per-IP and global daily submission limits bound anonymous abuse.

The production receiver is
`https://marketdesk-source-suggestions.source-suggestions.workers.dev`.
The Pages form must remain disabled until a real write is verified; then set
the public repository variable `SOURCE_REQUEST_ENDPOINT` to that URL followed
by `/suggestions`. This variable is an address, not a credential.
A JSON file in GitHub could also hold public suggestions, but writing it needs
an authenticated server-side call: a repository token must never enter the
public website. That alternative would still require hosting a receiver.
