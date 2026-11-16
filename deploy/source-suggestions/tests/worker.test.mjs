import {test} from 'node:test';
import assert from 'node:assert/strict';
import {DatabaseSync} from 'node:sqlite';
import {readFileSync} from 'node:fs';
import worker from '../worker/index.js';
const origin='https://caruanatheo-beep.github.io';
const token='test-collector-credential-for-unit-tests-only';
function fixture(){
 const db=new DatabaseSync(':memory:');
 db.exec(readFileSync(new URL('../drizzle/0000_suggestions.sql',import.meta.url),'utf8'));
 const env={COLLECTOR_TOKEN:token,DB:{
  prepare(sql){return {bind(...values){const stmt=db.prepare(sql);return {
   async first(){return stmt.get(...values);},
   async run(){return {meta:stmt.run(...values)};},
   async all(){return {results:stmt.all(...values)};}
  };}};},async batch(statements){return Promise.all(statements.map(stmt=>stmt.run()));}
 }};
 const call=(path,data,headers={})=>worker.fetch(new Request('https://receiver.test'+path,{
  method:'POST',headers:{'Content-Type':'application/json',...headers},body:JSON.stringify(data)}),env);
 const send=(company='Banque Test',extra={})=>call('/suggestions',{company,url:'https://careers.example.com/',reason:'Sales',honey:'',...extra},{Origin:origin,'CF-Connecting-IP':'192.0.2.1'});
 return {db,call,send,env};
}
test('public proposals persist, omit private data and can only be archived by owner',async()=>{
 const f=fixture(); assert.equal((await f.send()).status,201);
 assert.equal((await f.send()).status,200); // idempotent
 assert.equal((await f.call('/claim',{})).status,404);
 assert.equal((await f.call('/ack',{})).status,404);
 const publicList=await (await worker.fetch(new Request('https://receiver.test/suggestions',{headers:{Origin:origin}}),f.env)).json();
 assert.equal(publicList.suggestions.length,1);
 assert.deepEqual(Object.keys(publicList.suggestions[0]).sort(),['company','created_at','id','reason','url']);
 const id=publicList.suggestions[0].id;
 const auth={Authorization:'Bearer '+token};
 assert.equal((await f.call('/archive',{ids:[id]})).status,401);
 assert.equal((await f.call('/archive',{ids:[id]},auth)).status,200);
 const archived=await (await worker.fetch(new Request('https://receiver.test/suggestions',{headers:{Origin:origin}}),f.env)).json();
 assert.equal(archived.suggestions.length,0);
 f.db.exec('UPDATE suggestions SET archived_at=1');
 await f.call('/archive',{ids:[]},auth);
 assert.equal(f.db.prepare('SELECT count(*) AS n FROM suggestions').get().n,0);
});
test('persistent per-IP limits',async()=>{
 const f=fixture();
 for(let n=0;n<3;n++)assert.equal((await f.send('Banque '+n)).status,201);
 assert.equal((await f.send('Banque 4')).status,429);
 assert.equal(f.db.prepare('SELECT count(*) AS n FROM suggestions').get().n,3);
});
test('origin, schema, credentials in links and body size are rejected',async()=>{
 const f=fixture();
 assert.equal((await f.call('/suggestions',{}, {Origin:'https://evil.test'})).status,403);
 for(const extra of [{url:'https://user:password@example.com/'},{url:'https://127.0.0.1/'},
  {url:'https://example.com/?token=private'},{honey:'spam'},{company:'xx\r\nBcc: victim@example.com'},
  {reason:'x'.repeat(6000)},{email:'victim@example.com'}])assert.equal((await f.send('Test',extra)).status,400);
 assert.equal(f.db.prepare('SELECT count(*) AS n FROM suggestions').get().n,0);
});
test('daily global cap applies across IP addresses',async()=>{
 const f=fixture();
 for(let n=0;n<50;n++){
  const r=await f.call('/suggestions',{company:'Bank '+n,url:'https://example.com/',reason:'',honey:''},
   {Origin:origin,'CF-Connecting-IP':'192.0.2.'+n});
  assert.equal(r.status,201);
 }
 assert.equal((await f.send('One more')).status,429);
});
