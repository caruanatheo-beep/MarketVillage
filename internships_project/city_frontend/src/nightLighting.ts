// Static lightmaps are baked once at native pixel resolution, then applied to the
// live scene (including moving agents). They never encode task activity.
import { worldY, wingPosition } from './worldGeometry';
type Room = readonly [number, number, number, number];
const ROOMS: Room[] = [[15,1,18,8],[1,10,12,9],[16,10,16,9],[33,9,14,9],
  [0,22,14,9],[16,22,16,9],[33,22,14,5],[33,27,14,4]].map(([x,y,w,h])=>[x,worldY(y),w,worldY(y+h)-worldY(y)] as Room);
export const AMBIENT_LAMPS = [
  [16.4,2.1],[30.4,2.1],[18,6], [2,10.25],[12,15.3],
  [18,11],[27,11],[27.5,15], [33.3,10.25],[44,15],
  [3,22.2],[29.7,22.2],[44.6,22.1],[45,27.2],
].map(([x,y])=>{const p=wingPosition(x,y);return [p.col,p.row];});
const SCREENS = [[23.2,3.8],[4.6,13],[10.6,13],[36.6,13],
  [4.6,25],[10.6,25],[22.6,24],[27.6,24],[36.6,23],[36.6,28]].map(([x,y])=>{const p=wingPosition(x,y);return [p.col,p.row];});
const MAP_WIDTH = 48 * 16;
const MAP_HEIGHT = (worldY(40) + 1) * 16;
let lightmap: HTMLCanvasElement | undefined;
let reflectionMap: HTMLCanvasElement | undefined;

function bake(): void {
  lightmap=document.createElement('canvas');lightmap.width=MAP_WIDTH;lightmap.height=MAP_HEIGHT;
  reflectionMap=document.createElement('canvas');reflectionMap.width=MAP_WIDTH;reflectionMap.height=MAP_HEIGHT;
  const light=lightmap.getContext('2d')!, floor=reflectionMap.getContext('2d')!;
  function pool(ctx:CanvasRenderingContext2D,x:number,y:number,r:number,color:string,strength:number,flat=1){
    const room=ROOMS.find(([rx,ry,w,h])=>x>=rx&&x<rx+w&&y>=ry&&y<ry+h);
    if(!room)return;
    ctx.save();ctx.beginPath();ctx.rect(room[0]*16,room[1]*16,room[2]*16,room[3]*16);ctx.clip();
    ctx.translate(x*16,y*16);ctx.scale(1,flat);
    const g=ctx.createRadialGradient(0,0,1,0,0,r);
    g.addColorStop(0,`rgba(${color},${strength})`);
    g.addColorStop(.22,`rgba(${color},${strength*.8})`);
    g.addColorStop(.58,`rgba(${color},${strength*.28})`);
    g.addColorStop(1,`rgba(${color},0)`);
    ctx.fillStyle=g;ctx.fillRect(-r,-r,r*2,r*2);ctx.restore();
  }
  for(const [x,y] of AMBIENT_LAMPS){
    pool(light,x+.5,y+.55,48,'255,153,26',1);
    pool(light,x+.5,y+.55,12,'255,224,156',1);
    pool(floor,x+.55,y+1.65,43,'243,183,98',.9,.48);
  }
  for(const [x,y] of SCREENS){
    pool(light,x,y+.7,29,'17,90,237',.8);
    pool(floor,x,y+1.25,32,'55,178,255',.6,.35);
  }
  // Emission from real display/board positions, independent of mission status.
  for(const [x,y] of [[10.8,10.8],[23,2.4],[18,22.7],[42.8,27.8]]){
    pool(light,x,worldY(y),29,'74,190,231',.24);
    pool(floor,x,worldY(y+1.1),32,'72,168,221',.18,.5);
  }
  for(const [x,y] of [[43,10.8],[10.8,22.5]])
    pool(light,x,worldY(y),25,'255,197,121',.25);
  for(const [x,y] of [[1.7,24],[13.7,24],[2.5,28]]){
    pool(light,x,worldY(y),17,'39,139,241',.28);
    pool(floor,x+.5,worldY(y+1.1),22,'40,150,231',.22,.55);
  }
}

export function renderNightLight(ctx:CanvasRenderingContext2D,x:number,y:number,scale:number,floor=false){
  if(!lightmap)bake();
  ctx.save();
  // Soft light keeps the wood/chrome shadows saturated instead of bleaching
  // every material with a second full-strength screen pass.
  ctx.globalCompositeOperation=floor?'screen':'soft-light';
  ctx.globalAlpha=floor?.7:.9;
  ctx.drawImage((floor?reflectionMap:lightmap)!,x,y,MAP_WIDTH*scale,MAP_HEIGHT*scale);
  if(!floor){
    ctx.globalCompositeOperation='screen';ctx.globalAlpha=.72;
    ctx.drawImage(lightmap!,x,y,MAP_WIDTH*scale,MAP_HEIGHT*scale);
  }
  ctx.restore();
}
