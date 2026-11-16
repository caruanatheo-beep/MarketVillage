// Keep the existing Windows archive credential inside this process.
const fs = require('node:fs');
const path = require('node:path');
async function main() {
  const ids = JSON.parse(fs.readFileSync(0, 'utf8'));
  if (!Array.isArray(ids) || ids.length < 1 || ids.length > 20 ||
      ids.some(id => typeof id !== 'string' || !/^[a-f0-9]{64}$/.test(id))) throw new Error('Invalid archive identifiers');
  const {Entry} = require(path.join(__dirname, '../.codex-tools/cloudflare-cli/node_modules/@napi-rs/keyring'));
  const secret = new Entry('MarketDesk-source-suggestions', 'archive-admin').getPassword();
  if (!secret || secret.length < 32) throw new Error('Archive credential unavailable');
  const response = await fetch('https://marketdesk-source-suggestions.source-suggestions.workers.dev/archive', {
    method: 'POST', redirect: 'error', signal: AbortSignal.timeout(12000),
    headers: {'Authorization': 'Bearer '+secret, 'Content-Type': 'application/json'},
    body: JSON.stringify({ids}),
  });
  if (!response.ok || (await response.json()).success !== true) throw new Error('Archive request failed');
  process.stdout.write(JSON.stringify({success:true,count:ids.length}));
}
main().catch(() => { process.stderr.write('Suggestion archive unavailable'); process.exitCode=1; });
