import { mkdir, writeFile } from 'node:fs/promises';
import { dirname, resolve } from 'node:path';
import { deflateSync } from 'node:zlib';
import { readFile } from 'node:fs/promises';
import assert from 'node:assert/strict';

const out = resolve('internships_project/city_assets/pixel-agents/assets/furniture/MARKETDESK_PACK');
const C = {
  ink: '#111a25', outline: '#263544', edge: '#415365', metal: '#526779', metalHi: '#8498a7',
  desk: '#514333', wood: '#8b6d4d', woodHi: '#c3a27a', woodLit: '#dfc49b',
  screen: '#030c17', screenHi: '#102334', cyan: '#22dcec', blue: '#419fff', green: '#39e699',
  red: '#f26365', gold: '#ffba50', violet: '#b594ed', paper: '#dfd8c9', muted: '#8fa4b2',
};

function canvas(w, h) {
  const data = Buffer.alloc(w * h * 4);
  const rgba = hex => {
    const s = hex.replace('#', '');
    return [parseInt(s.slice(0, 2), 16), parseInt(s.slice(2, 4), 16), parseInt(s.slice(4, 6), 16), s.length > 6 ? parseInt(s.slice(6, 8), 16) : 255];
  };
  const put = (x, y, color) => {
    x = Math.round(x); y = Math.round(y);
    if (x < 0 || y < 0 || x >= w || y >= h || !color) return;
    const i = (y * w + x) * 4, p = rgba(color);
    // Source-over: textile/grain highlights must not punch transparent holes
    // through the already painted material and reveal the floor underneath.
    const sa=p[3]/255, da=data[i+3]/255, a=sa+da*(1-sa);
    for(let channel=0;channel<3;channel++)data[i+channel]=a?Math.round((p[channel]*sa+data[i+channel]*da*(1-sa))/a):0;
    data[i+3]=Math.round(a*255);
  };
  const rect = (x, y, rw, rh, color) => {
    for (let py = Math.floor(y); py < Math.ceil(y + rh); py++) for (let px = Math.floor(x); px < Math.ceil(x + rw); px++) put(px, py, color);
  };
  const frame = (x, y, rw, rh, border, fill) => { rect(x, y, rw, rh, border); rect(x + 1, y + 1, rw - 2, rh - 2, fill); };
  const line = (x0, y0, x1, y1, color, width = 1) => {
    let dx = Math.abs(x1 - x0), sx = x0 < x1 ? 1 : -1, dy = -Math.abs(y1 - y0), sy = y0 < y1 ? 1 : -1, err = dx + dy;
    for (;;) {
      rect(x0 - Math.floor(width / 2), y0 - Math.floor(width / 2), width, width, color);
      if (x0 === x1 && y0 === y1) break;
      const e2 = 2 * err;
      if (e2 >= dy) { err += dy; x0 += sx; }
      if (e2 <= dx) { err += dx; y0 += sy; }
    }
  };
  const poly = (points, color) => {
    const minY = Math.min(...points.map(p => p[1])), maxY = Math.max(...points.map(p => p[1]));
    for (let y = minY; y <= maxY; y++) {
      const xs = [];
      for (let i = 0; i < points.length; i++) {
        const [x1, y1] = points[i], [x2, y2] = points[(i + 1) % points.length];
        if (y1 === y2 || y < Math.min(y1, y2) || y >= Math.max(y1, y2)) continue;
        xs.push(Math.round(x1 + ((y - y1) * (x2 - x1)) / (y2 - y1)));
      }
      xs.sort((a, b) => a - b);
      for (let i = 0; i + 1 < xs.length; i += 2) rect(xs[i], y, xs[i + 1] - xs[i] + 1, 1, color);
    }
  };
  const box = (x, y, rw, rh, fill, border = C.outline) => {
    rect(x, y, rw, rh, border); rect(x + 1, y + 1, rw - 2, rh - 2, fill);
    rect(x + 1, y + 1, rw - 2, 1, '#ffffff24');
  };
  return { w, h, data, put, rect, frame, line, poly, box };
}

// Regression: translucent highlights preserve an opaque surface underneath.
{
  const sample = canvas(2, 1);
  sample.put(0, 0, '#000000'); sample.put(0, 0, '#ffffff80');
  sample.put(1, 0, '#ffffff80');
  assert.deepEqual([...sample.data], [128,128,128,255,255,255,255,128]);
}

function chart(c, x, y, w, h, color, seed = 1) {
  c.rect(x, y + h - 1, w, 1, '#223449');
  c.rect(x, y + Math.floor(h / 2), w, 1, '#132638');
  const pts = [];
  // Small desktop screens have only 6px of plot height. The former 2px/4px
  // margins collapsed their entire chart to a horizontal line.
  for (let i = 0; i < w; i++) {
    const wave = Math.sin((i + seed * 3) * 0.62)*.28 + Math.sin((i + seed) * 0.23)*.2;
    pts.push([x+i,y+Math.max(0,Math.min(h-2,Math.round((h-2)*(.5-wave))))]);
  }
  for (let i = 1; i < pts.length; i++) c.line(pts[i - 1][0], pts[i - 1][1], pts[i][0], pts[i][1], color);
  for (let i = 3; h > 10 && i < w - 1; i += 5) {
    const hh = 2 + ((i * 7 + seed * 3) % 5);
    c.rect(x + i, y + h - 3 - hh, 1, hh, i % 2 ? C.green : C.red);
  }
}

function monitor(c, x, y, w, h, mode, accent, seed = 0) {
  c.frame(x, y, w, h, '#070d15', '#243345');
  c.rect(x+1,y+1,w-2,1,'#52677a');
  c.rect(x + 2, y + 2, w - 4, h - 5, C.screen);
  c.rect(x + 2, y + 2, w - 4, 1, accent);
  c.put(x+w-3,y+h-2,C.cyan);
  const ix = x + 3, iy = y + 5, iw = w - 6;
  if (mode === 'chart' || mode === 'markets') {
    chart(c, ix, iy, iw, h - 9, seed % 2 ? C.cyan : C.green, seed + 4);
    for (let i = 0; i < Math.max(2, Math.floor(iw / 5)); i++) c.rect(ix + i * 4, iy, 2, 1, [C.cyan, C.gold, C.green][i % 3]);
  } else if (mode === 'code') {
    const rows = Math.max(3, Math.floor((h - 8) / 3));
    for (let r = 0; r < rows; r++) {
      const start = ix + (r % 3) * 2, len = Math.max(2, iw - (r * 3 + seed) % Math.max(3, iw - 2));
      c.rect(start, iy + r * 3, len, 1, [C.cyan, C.green, C.violet, C.muted][(r + seed) % 4]);
      if (len > 6) c.rect(start + 2, iy + r * 3 + 1, len - 4, 1, '#d3b46b');
    }
  } else if (mode === 'jobs') {
    for (let r = 0; r < Math.floor((h - 8) / 3); r++) {
      c.rect(ix, iy + r * 3, 2, 2, r === 0 ? C.violet : C.blue);
      c.rect(ix + 4, iy + r * 3, Math.max(3, iw - 7 - r * 2), 1, '#dae5ea');
      c.rect(ix + 4, iy + r * 3 + 1, Math.max(2, iw - 12), 1, C.muted);
    }
  } else if (mode === 'mail') {
    c.rect(ix, iy, iw, 2, '#223549');
    for (let r = 0; r < Math.floor((h - 8) / 3); r++) {
      c.rect(ix, iy + 3 + r * 3, 2, 2, [C.cyan, C.violet, C.gold][r % 3]);
      c.rect(ix + 4, iy + 3 + r * 3, iw - 6 - r % 2 * 3, 1, '#dae5ea');
      c.rect(ix + 4, iy + 4 + r * 3, iw - 11, 1, C.muted);
    }
  }
  const stemX = x + Math.floor(w / 2);
  c.rect(stemX - 1, y + h, 3, 2, C.metal);
  c.rect(stemX - 4, y + h + 2, 9, 1, C.metalHi);
}

function crc32(buf) {
  let crc = 0xffffffff;
  for (const b of buf) {
    crc ^= b;
    for (let k = 0; k < 8; k++) crc = (crc >>> 1) ^ (crc & 1 ? 0xedb88320 : 0);
  }
  return (crc ^ 0xffffffff) >>> 0;
}
function pngChunk(type, body) {
  const name = Buffer.from(type), len = Buffer.alloc(4), checksum = Buffer.alloc(4);
  len.writeUInt32BE(body.length); checksum.writeUInt32BE(crc32(Buffer.concat([name, body])));
  return Buffer.concat([len, name, body, checksum]);
}
function encodePng(c) {
  const ihdr = Buffer.alloc(13);
  ihdr.writeUInt32BE(c.w, 0); ihdr.writeUInt32BE(c.h, 4); ihdr[8] = 8; ihdr[9] = 6;
  const rows = [];
  for (let y = 0; y < c.h; y++) rows.push(Buffer.concat([Buffer.from([0]), c.data.subarray(y * c.w * 4, (y + 1) * c.w * 4)]));
  return Buffer.concat([Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]), pngChunk('IHDR', ihdr), pngChunk('IDAT', deflateSync(Buffer.concat(rows))), pngChunk('IEND', Buffer.alloc(0))]);
}

// Original native-resolution furnishings. Footprints deliberately match the
// existing validated furniture; visual changes cannot silently close a route.
const manifest = JSON.parse(await readFile(resolve(out, 'manifest.json'), 'utf8'));
if (!manifest.assets.some(a => a.id === 'MD_INTERIOR_GLASS_BAND')) {
  manifest.assets.push({...manifest.assets.find(a => a.id === 'MD_PANORAMA_WINDOW'),
    id:'MD_INTERIOR_GLASS_BAND', name:'Interior glazed partition — no exterior view',
    file:'premium/interior_glass_band.png'});
}
const saved = [];
if(!manifest.assets.some(a=>a.id==='MD_NETWORK_WORLD_MAP')){
 manifest.assets.push({...manifest.assets.find(a=>a.id==='MD_RESEARCH_BOARD'),
   id:'MD_NETWORK_WORLD_MAP',name:'Framed world map',file:'premium/network_world_map.png',
   width:64,height:32,footprintW:4,footprintH:1,backgroundTiles:1,isDesk:false,canPlaceOnWalls:true});
}
if(!manifest.assets.some(a=>a.id==='MD_TERRACE_TOPIARY')){
 manifest.assets.push({id:'MD_TERRACE_TOPIARY',name:'Terrace topiary in stone planter',
   file:'premium/terrace_topiary.png',width:32,height:64,footprintW:2,footprintH:4,
   backgroundTiles:3,isDesk:false,category:'decor',canPlaceOnWalls:false,canPlaceOnSurfaces:false});
}
// New native sprites keep the same validated footprint as the furniture they replace.
for(const [id,base] of [['MD_RESEARCH_MEETING','MD_RESEARCH_DESK'],['MD_NETWORK_CONFERENCE','MD_MEETING_ROUND_TABLE']]) {
 if(!manifest.assets.some(a=>a.id===id)) manifest.assets.push({...manifest.assets.find(a=>a.id===base),id,name:id,file:`premium/${id.toLowerCase()}.png`,isDesk:false});
}
function lamp(c,x,y) {
 c.rect(x-5,y+1,13,13,'#f3cb7418');
 c.box(x,y+8,5,2,'#574b3d','#303a3e');c.rect(x+2,y+1,1,8,'#ad9471');
 c.poly([[x,y],[x+4,y],[x+6,y+5],[x-2,y+5]],'#f3d19a');c.rect(x-1,y+4,6,1,'#fff0ce');
}
function wood(c,x,y,w,h) {
  c.frame(x,y,w,h,'#40291e','#a76330');
  c.rect(x+2,y+1,w-4,2,'#d99a53');
  c.rect(x+1,y+h-3,w-2,2,'#704020');
  for(let r=4;r<h-3;r+=4) c.line(x+3,y+r,x+w-4,y+r,'#b8793c');
}
function paper(c,x,y) { c.box(x,y,7,5,'#ece8d9','#b8b4aa'); c.rect(x+2,y+2,4,1,'#8e9ca1'); }
function plant(c,x,y) {
  c.box(x+3,y+10,8,5,'#a77c53','#4a4636');
  for(const [dx,dy] of [[5,1],[1,4],[8,4],[3,7],[9,8]]) {
    c.poly([[x+dx,y+dy],[x+dx+4,y+dy-1],[x+dx+6,y+dy+3],[x+dx+2,y+dy+5]],'#486647');
    c.line(x+dx+1,y+dy+1,x+dx+3,y+dy+3,'#7b9957');
  }
}
function desk(w,h,kind) {
  const c=canvas(w,h);
  if(kind==='executive'||kind==='global'){
    // Authored crescent workstation: angled return wings, a leather inset,
    // independent screen arms and a recessed knee space rather than a bench.
    const executive=kind==='executive', mid=Math.floor(w/2);
    c.poly([[2,16],[9,13],[w-10,13],[w-3,16],[w-1,27],[w-9,31],[mid+15,31],[mid+10,28],[mid-11,28],[mid-16,31],[8,31],[1,27]],'#14202d70');
    c.poly([[2,15],[9,12],[w-10,12],[w-3,15],[w-2,25],[w-9,29],[mid+15,29],[mid+10,26],[mid-11,26],[mid-16,29],[8,29],[1,25]],executive?'#422b21':'#433328');
    c.poly([[3,15],[10,13],[w-11,13],[w-4,15],[w-4,23],[w-10,26],[mid+15,26],[mid+10,24],[mid-11,24],[mid-16,26],[9,26],[3,23]],executive?'#a66b36':'#bc874d');
    c.line(10,14,w-11,14,'#e8b878');c.line(4,24,9,27,'#6f482c');
    c.line(w-5,24,w-10,27,'#6f482c');
    c.poly([[mid-21,17],[mid+21,17],[mid+22,23],[mid+10,24],[mid-11,24],[mid-22,23]],'#233e3b');
    c.line(mid-20,17,mid+20,17,'#58746b');
    const mw=Math.floor((w-16)/4)-2;
    for(let i=0;i<4;i++){
      const x=6+i*(mw+2),y=i===0||i===3?2:0;
      monitor(c,x,y,mw,13,'chart',['#56e3d2','#67b9ff','#f4be62','#54d6d0'][i],i+11);
      if(i===0)c.line(x,3,x,13,'#9caaa9');
      if(i===3)c.line(x+mw-1,3,x+mw-1,13,'#9caaa9');
    }
    c.frame(mid-13,19,26,4,'#0b1721','#344451');
    for(let x=mid-11;x<mid+11;x+=3)c.rect(x,20,2,1,'#9eafb4');
    c.box(mid+17,19,6,4,'#25333a','#13212a');
    paper(c,7,19);c.box(w-13,18,7,5,'#1a2a33','#0a151f');c.rect(w-12,19,5,1,'#b4c8ca');
    for(const x of [7,w-18]){c.box(x,27,11,4,'#64432b','#302c26');c.rect(x+4,28,3,1,'#c2ab78');}
    c.rect(mid-9,27,18,2,'#0e1924');
    c.box(w-25,19,3,3,'#d9ba7c','#6f522b');c.put(w-24,19,'#fbe4af');
    return c;
  }
  c.rect(4,h-4,w-6,4,'#111a2544');
  wood(c,2,15,w-4,13);
  for(const x of [6,w-16]) {c.box(x,25,10,5,'#79583d','#403c37'); c.rect(x+3,27,4,1,'#cab07f');}
  if(kind==='executive'){
    c.rect(3,16,w-6,12,'#704022');c.rect(5,16,w-10,2,'#ce8c48');
    c.box(26,19,w-50,8,'#34483f','#273b35');
    for(const x of [5,w-18]){c.frame(x,23,12,6,'#483426','#805738');c.rect(x+4,25,4,1,'#c5a76f');}
  }
  const count=kind==='executive'||kind==='global'?4:3, mw=Math.floor((w-12)/count)-2;
  for(let n=0;n<count;n++) monitor(c,5+n*(mw+2),0,mw,15,kind==='tech'?'code':kind==='career'?'jobs':kind==='outreach'?'mail':'chart',n%2?'#26b6cc':'#dd9438',n+2);
  c.box(w/2-13,21,25,5,'#28333c','#18222a');
  for(let x=0;x<22;x+=3) for(let y=0;y<2;y++) c.rect(w/2-11+x,22+y*2,2,1,'#8e9ba1');
  paper(c,5,21); c.box(w-13,21,7,4,'#2b353e','#17212a');c.rect(w-11,22,3,1,'#9baeb6');
  // Screen spill onto the desk, stationery and a brass cup coaster.
  c.rect(20,18,w-40,1,'#38c5eb65');
  c.box(w-23,23,4,4,'#d4c5a0','#7a6245');c.rect(w-22,23,2,2,'#473d32');
  lamp(c,w-7,18);
  // Walnut apron, separate pedestals and a brass lip give the desk real volume.
  c.rect(3,28,w-6,2,'#3c2b22');c.rect(5,28,w-10,1,'#936743');
  for(const x of [6,w-16]){
    c.rect(x,26,10,4,'#523b2b');c.rect(x+1,26,8,1,'#b18b59');
    c.rect(x+4,28,3,1,'#d8ba80');
  }
  if(kind==='executive'){
    c.rect(4,17,w-8,2,'#9a5c2f');c.rect(4,19,w-8,1,'#603c28');
    c.box(w/2-13,21,25,5,'#233d35','#152921');
  }
  return c;
}
function sofa(w,h,corner=false) {
  const c=canvas(w,h), front=corner?29:h-4;
  const pad=(x,y,ww,hh,fill)=>{
    c.rect(x+1,y,ww-2,hh,'#504c45');c.rect(x,y+1,ww,hh-2,'#504c45');
    c.rect(x+1,y+1,ww-2,hh-3,fill);
    c.rect(x+2,y+1,ww-4,1,'#ecdfc7');
    c.rect(x+2,y+hh-3,ww-4,2,'#887d69');
  };
  // Distinct backrest, seat deck, upholstered apron, walnut feet and cast shadow.
  c.rect(4,front-1,w-6,4,'#101b244c');
  c.rect(5,front-6,w-10,5,'#574b3c');
  c.rect(6,front-1,3,2,'#302c28');c.rect(w-9,front-1,3,2,'#302c28');
  pad(3,3,w-6,12,'#b3a48a');
  pad(5,13,w-10,front-15,'#cfc2a7');
  const count=w<40?1:3, sw=Math.floor((w-18)/count);
  for(let i=0;i<count;i++){
    const x=9+i*sw;
    pad(x,4,sw-1,10,'#c3b59b');
    pad(x,15,sw-1,front-19,'#d9cdb4');
    c.rect(x+3,17,Math.max(1,sw-7),1,'#f1e4c71e');
  }
  // Rolled arms have a bright crown and a darker vertical face.
  pad(2,10,7,front-11,'#ac9c82');pad(w-9,10,7,front-11,'#ac9c82');
  c.rect(3,12,4,front-16,'#c7b89d');c.rect(w-8,12,4,front-16,'#c7b89d');
  if(corner){
    c.rect(4,front,22,h-front-1,'#101b244c');
    pad(3,front-6,23,h-front+3,'#af9e82');
    pad(9,front-9,16,h-front+5,'#d5c7aa');
    c.rect(10,front-7,14,3,'#d5c7aa');
    c.rect(5,h-4,3,2,'#302c28');c.rect(22,h-4,3,2,'#302c28');
  }
  // Two asymmetric loose cushions and seams: linen and muted sage.
  pad(10,10,7,7,'#8a9884');c.line(12,12,14,14,'#b6c0a8');
  if(w>=40){pad(w-19,11,8,7,'#a3947d');c.line(w-17,13,w-14,15,'#d7c6a6');}
  // Directional upholstery shading: rolled backs, deep seams and weighted feet.
  for(let x=10;x<w-10;x++){
    c.put(x,4,'#e1d4b7');c.put(x,12,'#81745e');
    c.put(x,front-5,'#8f8065');c.put(x,front-3,'#574d40');
  }
  for(let x=12;x<w-12;x+=13){c.line(x,5,x,11,'#8b7c63');c.put(x+2,7,'#eee0bf');}
  c.rect(3,front-2,w-6,2,'#17202b68');
  return c;
}
function table(w,h,meeting=false) {
  const c=canvas(w,h);c.rect(6,h-5,w-9,4,'#17212a44');
  c.poly([[8,4],[w-9,4],[w-3,10],[w-3,h-10],[w-10,h-5],[9,h-5],[3,h-11],[3,10]],'#674c36');
  c.poly([[9,3],[w-10,3],[w-4,9],[w-4,h-12],[w-10,h-8],[9,h-8],[4,h-12],[4,9]],'#bf9464');
  c.line(10,5,w-11,5,'#e3bd89');
  plant(c,Math.floor(w/2)-7,3);paper(c,w-15,h-16);
  if(meeting){paper(c,8,9);c.box(9,h-15,8,5,'#d0d4d0','#6b797d');}
  return c;
}
function library(w,h) {
  const c=canvas(w,h);wood(c,1,1,w-2,h-3);
  c.rect(1,1,w-2,h-3,'#503a2a');c.rect(2,2,w-4,2,'#a07643');
  for(let y=5;y<h-9;y+=13){c.rect(5,y,w-10,11,'#423f35');
    for(let x=6;x<w-8;x+=5){const colors=['#8a5551','#638585','#d0b67a','#b4b6a6','#526b7d'];const z=(Math.floor(x/5)+Math.floor(y/13)*3)%5;c.rect(x,y+2+z%3,3,8-z%3,colors[z]);c.rect(x,y+4,3,1,'#dfc79b');}
    c.rect(4,y+11,w-8,2,'#b28b53');c.rect(4,y+12,w-8,1,'#463321');}
  return c;
}
function board(w,h,kind) {
 const c=canvas(w,h);wood(c,0,1,w,h-2);c.rect(3,4,w-6,h-8,kind==='career'?'#b89a73':'#e2e0d2');
 if(kind==='career'){
   c.rect(3,4,w-6,h-8,'#243b48');
   const colors=['#77bac5','#bba1d5','#d4b56f','#88b997'];
   for(let col=0;col<4;col++){
     const x=5+col*14;c.rect(x,6,12,3,colors[col]);
     for(let row=0;row<2;row++){
       const y=12+row*7;c.box(x,y,11,6,'#e6ddc7','#78838a');
       c.rect(x+2,y+2,6,1,'#657481');c.rect(x+2,y+4,4,1,colors[col]);
     }
   }
   c.rect(4,h-5,w-8,1,'#b5d9d5');
 }
 else if(kind==='outreach') {for(let y=7;y<h-7;y+=10){c.frame(6,y,12,7,'#638393','#ede7d8');c.line(7,y+1,12,y+4,'#638393');c.line(12,y+4,16,y+1,'#638393');for(let x=23;x<w-7;x+=9)c.rect(x,y+2,6,2,'#8c9c9c');}}
 else {for(let x=8;x<w-8;x+=9)c.rect(x,h-11-(x%17),5,4+x%17,'#6e949a');c.line(7,h-9,w-7,h-9,'#839196');c.line(8,20,22,17,'#b57450');c.line(22,17,34,20,'#b57450');c.line(34,20,w-8,7,'#b57450');}
 return c;
}
for(const a of manifest.assets) {
 let c;const id=a.id;
 if(id==='MD_NETWORK_WORLD_MAP'){
 c=canvas(a.width,a.height);
 c.frame(0,0,64,31,'#312e27','#b28c57');c.frame(2,2,60,27,'#e3cc9d','#244555');
 for(let x=8;x<60;x+=10)c.rect(x,4,1,23,'#7c9b9f24');
 for(let y=9;y<27;y+=8)c.rect(4,y,56,1,'#7c9b9f24');
 const continents=[[[7,9],[15,5],[24,8],[20,13],[16,14],[14,19],[10,15]],[[20,18],[26,19],[28,24],[24,28],[21,23]],[[30,9],[37,6],[42,9],[54,7],[58,13],[52,17],[44,14],[40,18],[35,14]],[[32,15],[39,15],[42,21],[37,26],[33,21]],[[49,23],[55,22],[58,26],[52,27]]];
 for(const points of continents)c.poly(points,'#b0bea6');
 c.line(4,28,59,28,'#74664b');c.put(34,10,'#f0d49b');
 }else if(id==='MD_NETWORK_CONFERENCE'){
 c=canvas(a.width,a.height);const w=a.width,h=a.height;
 // A true round table with five seats, rolled padded backs and radial arms.
 const ellipse=(cx,cy,rx,ry,color)=>c.poly(Array.from({length:32},(_,i)=>[Math.round(cx+Math.cos(i*Math.PI/16)*rx),Math.round(cy+Math.sin(i*Math.PI/16)*ry)]),color);
 for(const [x,y]of [[8,1],[30,1],[1,13],[36,13],[19,23]]){
   c.box(x,y,11,8,'#284256','#101f2e');c.rect(x+2,y+1,7,2,'#637b89');
   c.rect(x+1,y+7,2,2,'#142636');c.rect(x+8,y+7,2,2,'#142636');
 }
 ellipse(24,18,18,11,'#101b2966');ellipse(24,16,17,10,'#523922');
 ellipse(24,14,17,9,'#b9874e');ellipse(24,13,14,7,'#c49960');
 c.line(14,10,29,9,'#e0b77c');paper(c,12,12);paper(c,29,13);
 c.box(22,11,4,4,'#496243','#253d30');c.put(24,10,'#91a261');
 }else if(id==='MD_RESEARCH_MEETING'){
 c=canvas(a.width,a.height);const w=a.width,h=a.height;
 const seats=[[12,0],[w-26,0],[12,h-9],[w-26,h-9]];
 for(const [x,y] of seats){c.box(x,y,13,9,'#3c4c4c','#1b2a30');c.rect(x+1,y+1,11,2,'#88948a');c.rect(x+2,y+8,2,2,'#223039');c.rect(x+9,y+8,2,2,'#223039');}
 c.poly([[9,8],[w-10,8],[w-5,12],[w-6,h-12],[w-11,h-7],[11,h-7],[5,h-12],[5,12]],'#563c27');
 c.poly([[10,7],[w-11,7],[w-6,11],[w-7,h-14],[w-12,h-10],[12,h-10],[6,h-14],[6,11]],'#b88245');
 c.line(11,8,w-12,8,'#e8bb7c');
 paper(c,13,11);paper(c,w-24,11);c.box(w/2-6,11,9,6,'#0f1f2d','#566a78');
 c.rect(w/2-5,12,7,2,'#406678');c.box(w/2+10,12,4,4,'#718c53','#354f35');
 }else if(id==='MD_EXECUTIVE_WALL'){
 c=canvas(a.width,a.height);c.box(0,2,a.width,27,'#263842','#17242e');
 c.rect(2,3,a.width-4,1,'#8b9c9c');
 for(let i=0;i<4;i++)monitor(c,3+i*23,5,21,20,'chart','#70888f',i+3);
 c.rect(2,28,a.width-4,2,'#a58860');
 }else if(a.isWallTile){
 c=canvas(16,16);const mask=parseInt(id.slice(-2),16);
 // Narrow continuous glass rails, no repeated handles or cabinet-like panels.
 if(mask&10){c.rect(0,5,16,7,'#8dabb34c');c.rect(0,3,16,2,'#33454c');c.rect(0,5,16,1,'#acbcb8');c.rect(0,12,16,2,'#38494f');c.rect(0,14,16,1,'#b8ad96');}
 if(mask&5){c.rect(5,0,7,16,'#8dabb34c');c.rect(3,0,2,16,'#33454c');c.rect(5,0,1,16,'#acbcb8');c.rect(12,0,2,16,'#38494f');}
 if(!mask)c.box(5,3,6,11,'#849899','#33454c');
 }else if(id==='MD_INTERIOR_GLASS_BAND'){
 c=canvas(a.width,a.height);
 // Transparent interior glazing: no skyline, blue sky or outdoor lighting.
 c.rect(0,5,a.width,24,'#95b8c126');
 c.rect(0,3,a.width,2,'#253742');c.rect(0,5,a.width,1,'#8a9a99');
 c.rect(0,27,a.width,3,'#293a44');c.rect(0,30,a.width,2,'#9a805b');
 for(let x=0;x<a.width;x+=32){
   c.rect(x,5,2,22,'#314550');c.rect(x+2,5,1,21,'#9db1b18c');
   c.poly([[x+6,8],[x+9,8],[x+22,24],[x+19,24]],'#d4e5d627');
   c.rect(x+3,17,28,2,'#d4e5dc60');
 }
 c.rect(a.width-2,5,2,22,'#314550');
 }else if(id==='MD_PANORAMA_WINDOW'){
 c=canvas(a.width,a.height);c.box(0,1,a.width,28,'#14213c','#25313a');
 // Dusk skyline, illuminated offices and quiet reflections behind real mullions.
 for(let x=3;x<a.width-4;x+=30){
 for(let y=4;y<24;y++)c.rect(x,y,27,1,y<12?'#182d50':'#294467');
 for(let n=0;n<4;n++){const bx=x+n*7,by=14-(n*3+x)%7;
 c.rect(bx,by,5,24-by,'#101c32');
 for(let yy=by+2;yy<23;yy+=4)for(let xx=bx+1;xx<bx+5;xx+=2)if((xx+yy)%3)c.rect(xx,yy,1,1,(xx+yy)%2?'#ffd78b':'#e8b361');}
 c.poly([[x+1,5],[x+7,5],[x+22,23],[x+17,23]],'#b8d7df21');
 c.rect(x+27,3,2,23,'#263742');c.rect(x+27,3,1,22,'#708187');}
 c.rect(1,26,a.width-2,2,'#e1cfac');c.rect(0,28,a.width,2,'#947956');c.rect(0,30,a.width,2,'#303a3d');
 }else if(id.includes('SERVER_RACK')){
 c=canvas(a.width,a.height);
 const count=id.endsWith('CLUSTER')?3:1, step=Math.floor(a.width/count);
 for(let n=0;n<count;n++){
 const x=n*step+1,w=step-3,h=a.height;
 c.rect(x+2,h-5,w,4,'#07111c65');
 c.poly([[x,5],[x+4,1],[x+w-2,1],[x+w,5]],'#65717b');
 c.rect(x,5,w,h-10,'#1a2736');c.rect(x+w-3,6,3,h-12,'#344653');
 c.rect(x+1,6,1,h-13,'#8c9597');c.rect(x+3,7,w-8,h-16,'#061421');
 c.rect(x+4,8,w-10,3,'#354a5b');c.rect(x+5,9,3,1,'#6be0ea');
 for(let y=14;y<h-13;y+=6){
   c.box(x+3,y,w-8,5,'#172b3d','#526775');
   c.rect(x+4,y+2,Math.max(2,w-14),1,'#08131b');
   c.put(x+w-7,y+2,n%2?'#edbd60':'#65e4d2');
   c.put(x+w-7,y+3,'#31a5cd');
 }
 c.rect(x+4,h-12,w-9,2,'#080f18');
 c.rect(x+2,h-6,3,2,'#0e1722');c.rect(x+w-5,h-6,3,2,'#0e1722');
 c.line(x+4,8,x+Math.min(w-5,9),h-14,'#aac6d414');
 }
 }else if(id==='MD_CAREER_CABINET'){
 c=canvas(a.width,a.height);wood(c,1,3,29,26);
 c.rect(3,5,25,10,'#463b35');
 for(let x=5;x<26;x+=4){c.rect(x,6,3,8,['#839cad','#c49d6e','#a2ac89'][x%3]);c.rect(x,8,3,1,'#eee1be');}
 for(let y=17;y<28;y+=6){c.box(3,y,25,5,'#a77d51','#674b35');c.rect(13,y+2,6,1,'#d1c5a2');}
 c.rect(3,29,3,2,'#2c3033');c.rect(25,29,3,2,'#2c3033');
 }else if(id==='MD_OUTREACH_DISPLAY')c=board(a.width,a.height,'outreach');
 else if(id.endsWith('_DESK')) c=desk(a.width,a.height,id.split('_')[1].toLowerCase());
 else if(id.includes('SOFA')) c=sofa(a.width,a.height,id.endsWith('_L'));
 else if(id==='MD_LOUNGE_ARMCHAIR') {c=sofa(a.width,a.height); /* deeper upholstered seat */}
 else if(id.includes('COFFEE_TABLE')||id.includes('MEETING_TABLE')||id==='MD_MEETING_ROUND_TABLE'||id==='MD_NETWORK_TABLE') c=table(a.width,a.height,id.includes('MEETING'));
 else if(id==='MD_EXECUTIVE_LIBRARY') c=library(a.width,a.height);
 else if(id==='MD_RESEARCH_BOARD'||id==='MD_CAREER_BOARD') c=board(a.width,a.height,id==='MD_CAREER_BOARD'?'career':'research');
 else if(id==='MD_LOUNGE_PLANTER'){c=canvas(a.width,a.height);wood(c,1,10,a.width-2,6);for(let x=0;x<a.width-10;x+=9)plant(c,x,-1);}
 if(!c)continue;
 const name=a.file.split('/').pop();
 a.file='premium/'+name.replace(/(?:_upholstery_v2|_warm_v3|_night_v4)?\.png$/,'_night_v4.png');
 await mkdir(resolve(out,'premium'),{recursive:true});await writeFile(resolve(out,a.file),encodePng(c));saved.push(id);
}
// Standalone textile PNG, used as a nonblocking floor finish.
for(const [name,base,edge] of [['rug-ivory','#c8baa1','#e5d9c2'],['rug-slate','#58636b','#9ca4a4']]){
 const c=canvas(96,64);c.rect(0,0,96,64,'#17202c35');c.rect(1,1,94,61,edge);c.rect(3,3,90,57,base);
 c.frame(5,5,86,52,edge,base);
 // Woven border, corner rosettes and tiny fringe, rather than a plain inset box.
 const motif=name==='rug-ivory'?'#a08b6e':'#74888f';
 for(let x=10;x<87;x+=6){c.put(x,7,motif);c.put(x,56,motif);}
 for(let y=12;y<54;y+=6){c.put(7,y,motif);c.put(88,y,motif);}
 for(const [x,y] of [[11,11],[84,11],[11,52],[84,52]]){
   c.poly([[x,y-3],[x+3,y],[x,y+3],[x-3,y]],motif);c.put(x,y,edge);
 }
 for(let x=3;x<93;x+=3){c.rect(x,0,1,2,edge);c.rect(x,62,1,2,edge);}
 for(let y=7;y<55;y++)for(let x=7;x<89;x++)if((x*17+y*13)%11<3)c.put(x,y,(x+y)%2?edge+'20':'#282b3009');
 await writeFile(resolve(out,'premium',name+'.png'),encodePng(c));
}
// Native seamless oak: staggered joints, individual grain and knots, no tile grid.
{
 // Copper/honey oak sampled from the user's Cozy Night Office reference.
 const c=canvas(192,96), hues=['#88562f','#9d6532','#80512c','#a8703b','#936035','#8c582f','#ab7542','#986738'];
 for(let row=0;row<12;row++){
 const y=row*8; c.rect(0,y,192,8,hues[(row*5)%8]);c.rect(0,y,192,1,'#633b2338');c.rect(0,y+1,192,1,'#ffd28b25');
 const joint=(row*53+31)%192;c.rect(joint,y,1,8,'#674b3438');
 for(let n=0;n<6;n++){const x=(n*37+row*19)%188,gy=y+3+n%4,len=Math.min(192-x,8+(row+n*7)%24);
 c.rect(x,gy,len,1,n%2?'#f3bb7228':'#693b1e1c');}
 if(row%4===1){const x=(row*41)%180;c.line(x,y+4,x+7,y+3,'#79533535');c.line(x+7,y+3,x+15,y+4,'#79533535');}
 }
 await writeFile(resolve(out,'premium/oak-night.png'),encodePng(c));
}
// Nonblocking luminaires sit on existing shelves; no hidden navigation obstacles.
{
 const c=canvas(16,24);c.rect(4,21,9,2,'#0c15294a');c.box(4,19,8,3,'#5b4635','#283039');
 c.rect(7,8,2,11,'#af8951');c.poly([[4,2],[11,2],[14,10],[1,10]],'#ddae6b');
 c.rect(4,3,6,6,'#ffe3a1');c.rect(2,9,11,2,'#fff1c3');c.rect(6,11,4,1,'#c8a46a');
 await writeFile(resolve(out,'premium/lamp-amber.png'),encodePng(c));
}
await writeFile(resolve(out,'manifest.json'),JSON.stringify(manifest,null,2)+'\n');
console.log('Premium original PNG sprites:',saved.length, '+ 2 textiles + oak + amber luminaire');


