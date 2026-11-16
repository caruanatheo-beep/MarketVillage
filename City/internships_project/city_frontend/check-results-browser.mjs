// Extend the existing browser checks with results and real popup navigation.
import {readFile,writeFile} from 'node:fs/promises';
import {resolve} from 'node:path';
const original=await readFile(new URL('./check-command-browser.mjs',import.meta.url),'utf8');
const checks=`
await evaljs("document.querySelector('.panel-tabs button').click()");await sleep(250);
await evaljs("document.querySelector('.ready-results summary').click()");await sleep(100);
await evaljs("document.querySelector('.ready-results button').click()");await sleep(250);
assert.equal(await evaljs("document.querySelector('.mission-results-body').textContent.includes('Résultat de validation locale uniquement.')"),true,'Readable result one click from chat');
await shot('mission-result');
await evaljs("document.querySelector('.mission-results-window .game-popup-heading button').click()");
await evaljs("document.querySelector('.dashboard-shortcuts button').click()");await sleep(600);
const targets=(await call('Target.getTargets')).result.targetInfos;
assert.ok(targets.some(t=>t.url==='http://127.0.0.1:7878/dashboard-preview/markets'),'Markets opens local dashboard tab');
await evaljs("document.querySelectorAll('.dashboard-shortcuts button')[1].click()");await sleep(600);
const next=(await call('Target.getTargets')).result.targetInfos;
assert.ok(next.some(t=>t.url==='http://127.0.0.1:7878/dashboard-preview/internships'),'Internships opens local dashboard tab');
console.log('Result access and dashboard popup checks passed');
`;
// Evaluated in the same CDP test session; never added to the shipped frontend.
const source=original.replace("console.log('Browser checks passed');ws.close();chrome.kill();",checks+"console.log('Browser checks passed');ws.close();chrome.kill();");
const temp=resolve('artifacts/command-center/check-results-session.mjs');
await writeFile(temp,source);await import('file:///'+temp.replaceAll('\\','/'));
