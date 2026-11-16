const ORIGIN = 'https://caruanatheo-beep.github.io';
const encoder = new TextEncoder();
const json = (data,status=200,cors=false) => Response.json(data,{status,headers:{
  'Cache-Control':'no-store','X-Content-Type-Options':'nosniff',
  ...(cors ? {'Access-Control-Allow-Origin':ORIGIN,'Vary':'Origin'} : {})}});
async function digest(value) {
  return [...new Uint8Array(await crypto.subtle.digest('SHA-256',encoder.encode(value)))].map(x=>x.toString(16).padStart(2,'0')).join('');
}
async function authorized(request,secret) {
  if (!secret || secret.length < 32) return false;
  const supplied=request.headers.get('Authorization') || '';
  return (await digest(supplied)) === (await digest('Bearer '+secret));
}
export function validateSuggestion(data) {
  if (!data || Array.isArray(data) || Object.keys(data).sort().join(',') !== 'company,honey,reason,url') throw Error('fields');
  if (Object.values(data).some(x=>typeof x!=='string') || data.honey) throw Error('fields');
  const company=data.company.trim(), reason=data.reason.trim();
  if(/[^\s@]+@[^\s@]+\.[^\s@]+/.test(company+' '+reason))throw Error('private');
  if (company.length<2 || company.length>80 || reason.length>600 || /[\x00-\x1f\x7f]/.test(company) || /[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]/.test(reason)) throw Error('text');
  const url=new URL(data.url.trim()), host=url.hostname;
  if (data.url.length>1000 || url.protocol!=='https:' || url.username || url.password || url.port
      || !host.includes('.') || /^(?:[\d.]+|\[.*\])$/.test(host) || /\.(?:local|internal)$/.test(host)
      || [...url.searchParams.keys()].some(key=>/^(?:key|api_?key|access_token|token|password|secret|authorization|signature)$/i.test(key))) throw Error('url');
  url.hash='';
  return {company,url:url.href,reason};
}
async function body(request) {
  if (!request.headers.get('Content-Type')?.toLowerCase().startsWith('application/json')) throw Error('type');
  // Read with a hard cap, including chunked requests without Content-Length.
  const reader=request.body?.getReader();
  if (!reader) throw Error('body');
  let size=0, chunks=[];
  for (;;) {
    const {done,value}=await reader.read(); if(done)break;
    size+=value.length; if(size>5000){await reader.cancel();throw Error('size');}
    chunks.push(value);
  }
  const joined=new Uint8Array(size); let offset=0;
  for(const chunk of chunks){joined.set(chunk,offset);offset+=chunk.length;}
  return JSON.parse(new TextDecoder('utf-8',{fatal:true}).decode(joined));
}
export default {
  async fetch(request,env) {
    const path=new URL(request.url).pathname;
    if(path==='/health' && request.method==='GET') return json({ok:true});
    const publicRoute=path==='/suggestions';
    const cors=publicRoute && request.headers.get('Origin')===ORIGIN;
    if(publicRoute && !cors)return json({success:false},403);
    if(publicRoute && request.method==='OPTIONS')return new Response(null,{status:204,headers:{
      'Access-Control-Allow-Origin':ORIGIN,'Vary':'Origin','Access-Control-Allow-Methods':'GET, POST',
      'Access-Control-Allow-Headers':'Content-Type','Access-Control-Max-Age':'600'}});
    if(!env.DB || !env.COLLECTOR_TOKEN || env.COLLECTOR_TOKEN.length<32)return json({success:false},503,cors);
    if(publicRoute && request.method==='GET') {
      try {
        const result=await env.DB.prepare('SELECT id,company,url,reason,created_at FROM suggestions WHERE archived_at IS NULL ORDER BY created_at DESC LIMIT 100').bind().all();
        return json({suggestions:result.results},200,true);
      }catch{return json({success:false},503,true);}
    }
    if(request.method!=='POST')return json({success:false},405,cors);
    if(!publicRoute && path!=='/archive')return json({success:false},404);
    if(!publicRoute && !await authorized(request,env.COLLECTOR_TOKEN))return json({success:false},401);
    try {
      const now=Math.floor(Date.now()/1000), day=now-now%86400;
      if(publicRoute) {
        let data;try{data=validateSuggestion(await body(request));}catch{return json({success:false},400,true);}
        const ip=request.headers.get('CF-Connecting-IP');
        if(!ip)return json({success:false},503,true);
        const key=await crypto.subtle.importKey('raw',encoder.encode(env.COLLECTOR_TOKEN),{name:'HMAC',hash:'SHA-256'},false,['sign']);
        const ipHash=[...new Uint8Array(await crypto.subtle.sign('HMAC',key,encoder.encode(day+':'+ip)))].map(x=>x.toString(16).padStart(2,'0')).join('');
        const id=await digest(JSON.stringify(data));
        if(await env.DB.prepare('SELECT id FROM suggestions WHERE id=?').bind(id).first())return json({success:true},200,true);
        // Single atomic insert enforces both limits across Worker instances.
        const result=await env.DB.prepare(`INSERT OR IGNORE INTO suggestions(id,company,url,reason,ip_hash,created_at)
          SELECT ?,?,?,?,?,? WHERE (SELECT count(*) FROM suggestions WHERE created_at>=?)<50
          AND (SELECT count(*) FROM suggestions WHERE created_at>=? AND ip_hash=?)<3`)
          .bind(id,data.company,data.url,data.reason,ipHash,now,day,day,ipHash).run();
        return json({success:result.meta.changes===1},result.meta.changes===1?201:429,true);
      }
      let data;try{data=await body(request);}catch{return json({success:false},400);}
      if(!data || !Array.isArray(data.ids) || data.ids.length>20
          || data.ids.some(id=>typeof id!=='string' || !/^[a-f0-9]{64}$/.test(id)))return json({success:false},400);
      await env.DB.batch(data.ids.map(id=>env.DB.prepare('UPDATE suggestions SET archived_at=? WHERE id=?').bind(now,id)));
      await env.DB.prepare('DELETE FROM suggestions WHERE archived_at IS NOT NULL AND archived_at<?').bind(now-30*86400).run();
      return json({success:true});
    } catch {return json({success:false},503,cors);}
  }
};
