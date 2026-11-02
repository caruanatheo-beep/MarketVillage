import {build} from 'esbuild-wasm';
import {readFile,writeFile} from 'node:fs/promises';
import {resolve} from 'node:path';
import {fileURLToPath} from 'node:url';
const bundle=await build({entryPoints:[fileURLToPath(new URL('./src/nightLighting.ts',import.meta.url))],bundle:true,write:false,format:'iife',globalName:'NightLighting'});
const sprites=await build({entryPoints:[fileURLToPath(new URL('./vendor/pixel-agents/webview-ui/src/office/sprites/spriteCache.ts',import.meta.url))],bundle:true,write:false,format:'iife',globalName:'SpriteCache'});
const original=await readFile(new URL('./check-command-browser.mjs',import.meta.url),'utf8');
const check=`(()=>{
const canvas=document.createElement('canvas');canvas.width=768;canvas.height=512;
const ctx=canvas.getContext('2d');ctx.fillStyle='#303848';ctx.fillRect(0,0,768,512);
NightLighting.renderNightLight(ctx,0,0,1);
const pixel=(x,y)=>Array.from(ctx.getImageData(x,y,1,1).data);
const lamp=pixel(Math.round(16.9*16),Math.round(2.65*16));
const voidPixel=pixel(0,0),unlit=pixel(24*16,20*16);
const bytes=ctx.getImageData(0,0,768,512).data;
let darker=0;for(let i=0;i<bytes.length;i+=4)if(bytes[i]<48||bytes[i+1]<56||bytes[i+2]<72)darker++;
return {lamp,voidPixel,unlit,darker,composite:ctx.globalCompositeOperation};
})()`;
const checks=`
await evaljs(${JSON.stringify(sprites.outputFiles[0].text)});
const raster=await evaljs(${JSON.stringify(`(()=>{
 const sprite=Array.from({length:16},()=>Array(32).fill('#a06030'));
 return [1,1.37,1.61,2.25].map(zoom=>{
  const c=SpriteCache.getCachedSprite(sprite,zoom),d=c.getContext('2d').getImageData(0,0,c.width,c.height).data;
  let damaged=0;for(let i=0;i<d.length;i+=4)if(d[i]!==160||d[i+1]!==96||d[i+2]!==48||d[i+3]!==255)damaged++;
  return {zoom,damaged};
 });
})()`)});
console.log('Sprite raster checks',raster);
assert.ok(raster.every(r=>r.damaged===0),'Fractional fit preserves opaque sprite colors without checker seams');
await evaljs(${JSON.stringify(bundle.outputFiles[0].text)});
const lighting=await evaljs(${JSON.stringify(check)});
assert.ok(lighting.lamp[0]>160 && lighting.lamp[0]>lighting.lamp[2],'Strong amber pool');
assert.deepEqual(lighting.voidPixel,[48,56,72,255],'No light outside architecture');
assert.deepEqual(lighting.unlit,[48,56,72,255],'Unlit corridor preserved');
assert.equal(lighting.darker,0,'Lightmap never globally darkens the scene');
assert.equal(lighting.composite,'source-over','Canvas blending restored');
console.log('Lightmap pixel checks passed',lighting);
`;
const source=original.replace("console.log('Browser checks passed');ws.close();chrome.kill();",checks+"console.log('Browser checks passed');ws.close();chrome.kill();");
const temp=resolve('artifacts/command-center/check-night-session.mjs');
await writeFile(temp,source);await import('file:///'+temp.replaceAll('\\','/'));
