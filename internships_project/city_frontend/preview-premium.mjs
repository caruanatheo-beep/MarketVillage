// Isolated visual fixture: real renderer, no account data or paid backend calls.
import {build} from 'esbuild-wasm';
import {createServer} from 'node:http';
import {readFile} from 'node:fs/promises';
import {resolve} from 'node:path';
const base=import.meta.dirname;
const bundle=await build({absWorkingDir:base,stdin:{contents:`import React from 'react';import{createRoot}from'react-dom/client';import {PixelFloorGame} from './src/PixelFloorGame';const agents=['market_analyst','finance_tutor','job_hunter','networker','outreach_agent','developer','desk_manager'].map(id=>({id,name:id,status:'idle'}));createRoot(document.getElementById('root')).render(<PixelFloorGame agents={agents} tasks={[]} events={[]} selectedId="desk_manager" onPick={()=>{}} marketPoints={[]} marketRetrievedAt="" featuredOffers={[]}/>);`,resolveDir:base,loader:'tsx'},bundle:true,write:false,format:'iife'});
createServer(async(req,res)=>{try{const path=new URL(req.url,'http://localhost').pathname;
if(path==='/preview.js'){res.setHeader('Content-Type','text/javascript');res.end(bundle.outputFiles[0].contents);return;}
if(path.startsWith('/city/pixel-assets/')){const root=resolve(base,'../city_assets/pixel-agents/assets');const file=resolve(root,path.slice('/city/pixel-assets/'.length));if(!file.startsWith(root+'/')&&!file.startsWith(root+'\\'))throw Error('path');res.setHeader('Content-Type',file.endsWith('.png')?'image/png':'application/json');res.end(await readFile(file));return;}
res.setHeader('Content-Type','text/html');res.end(`<html><style>html,body,#root{margin:0;width:100%;height:100%;background:#0c131b;color:white}#root>div{width:100%;height:100%;position:relative}canvas{display:block;width:100%;height:100%}button{position:relative}</style><div id="root"></div><script src="/preview.js"></script></html>`);
}catch(e){res.statusCode=404;res.end(String(e));}}).listen(7877,'127.0.0.1',()=>console.log('Visual fixture http://127.0.0.1:7877'));


