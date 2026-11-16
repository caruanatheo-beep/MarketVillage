import {createServer} from 'node:http';
import {readFile} from 'node:fs/promises';
import {resolve} from 'node:path';
const root=resolve(import.meta.dirname,'../city_assets');
const ids=['desk_manager','market_analyst','finance_tutor','job_hunter','networker','outreach_agent','developer','innovation_lab'];
const names=['Desk Manager','Mira','Noé','Jules','Lina','Iris','Axel','Nova'];
const roles=['Coordination','Market Analyst','Quant Research','Software Engineer','Networker','Outreach','Interview Coach','Innovation Lab'];
const tasks=[['market_analyst','completed','Brief de marché — fixture de test'],['job_hunter','waiting_approval','Audit du code — fixture de test'],['networker','failed','Diagnostic contacts — fixture de test']].map(([agent_id,status,description],i)=>({id:`test-${i}`,agent_id,status,description,task_type:'test',created_at:'2026-10-31T12:00:00Z',started_at:'2026-10-31T12:01:00Z',finished_at:status==='completed'?'2026-10-31T12:02:00Z':undefined,result:status==='completed'?{text:'Résultat de validation locale uniquement.'}:{},error:status==='failed'?'Erreur de test contrôlée':undefined,depends_on:[],xp_awarded:0,input_tokens:0,output_tokens:0,api_cost_usd:0}));
const state={agents:ids.map((id,i)=>({id,name:names[i],role:roles[i],area:'MarketDesk',description:'Agent de validation locale — aucune exécution réelle.',available:true,xp:0,level:1,level_progress:0,achievements:[],status:tasks.find(t=>t.agent_id===id)?.status||'idle',latest:tasks.find(t=>t.agent_id===id)||null})),tasks,events:tasks.map((t,i)=>({id:i+1,agent_id:t.agent_id,task_id:t.id,status:t.status,message:t.description,created_at:t.created_at})),workflows:[],today_completed:1,week_completed:1,api_usage:{calls:0,estimated_usd:0,input_tokens:0,output_tokens:0,by_agent:{}},workspace:{profiles:[],contacts:[]}};
let filled=false;let launches=0;
const messages=[{id:'fixture-user',role:'user',content:'Prépare un brief et identifie des stages.',created_at:'2026-10-31T12:00:00Z'},{id:'fixture-assistant',role:'assistant',content:'**Validation locale**\n\nLe brief est disponible. La recherche de stages attend une validation. Aucun appel externe effectué.',created_at:'2026-10-31T12:02:00Z',tool_calls:[{name:'Mira — brief',status:'completed',text:'Résultat de test isolé.'}]}];
createServer(async(req,res)=>{try{let p=new URL(req.url,'http://localhost').pathname;
if(p==='/__fixture/filled'){filled=true;res.end('ok');return;}
if(p==='/__fixture/empty'){filled=false;res.end('ok');return;}
if(p==='/__fixture/launch-count'){res.setHeader('Content-Type','application/json');res.end(JSON.stringify({launches}));return;}
if(p.startsWith('/city/api/local-apps/')){launches++;res.setHeader('Content-Type','application/json');res.end(JSON.stringify({url:`http://127.0.0.1:7878/dashboard-preview/${p.split('/').pop()}`,reused:false}));return;}
if(p.startsWith('/dashboard-preview/')){res.end('Isolated dashboard launch fixture. No process started.');return;}
if(p.startsWith('/city/api/')){res.setHeader('Content-Type','application/json; charset=utf-8');res.end(JSON.stringify(p.endsWith('/state')?state:p.includes('/chat/')?{messages:filled?messages:[]}:p.includes('market-snapshot')?{points:[]}:p.includes('internship-highlight')?{featured_offer:null}:{}));return;}
if(p==='/'||p==='/city/')p='/city/city.html';
const file=p.startsWith('/city/pixel-assets/')?resolve(root,'pixel-agents/assets',p.slice(19)):resolve(root,p.replace(/^\/city\//,''));
if(!file.startsWith(root))throw Error('path');res.setHeader('Content-Type',file.endsWith('.css')?'text/css':file.endsWith('.js')?'text/javascript':file.endsWith('.png')?'image/png':file.endsWith('.json')?'application/json':'text/html; charset=utf-8');res.end(await readFile(file));
}catch(e){res.statusCode=404;res.end(String(e));}}).listen(Number(process.env.CITY_PREVIEW_PORT||7878),'127.0.0.1',()=>console.log('Isolated Command Center fixture'));
