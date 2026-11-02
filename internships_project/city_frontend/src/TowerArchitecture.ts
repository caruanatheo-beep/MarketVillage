import { TileType } from '../vendor/pixel-agents/webview-ui/src/office/types';
import { worldY } from './worldGeometry';

const images: Record<string, HTMLImageElement> = {};
export async function loadTowerArchitecture(): Promise<void> {
  await Promise.all(['penthouse-crown','md_atrium_canopy','md_vertical_sign','manhattan-canyon',
    'terrace','garden-parapet','md_slab_edge'].map(name =>
    new Promise<void>((resolve,reject) => {
      const image = new Image();
      image.onload = () => { images[name] = image; resolve(); };
      image.onerror = () => reject(new Error(`Architecture introuvable : ${name}`));
      image.src = `/city/pixel-assets/tower/${name}.png?v=partitions-2`;
    })));
}

export function renderTowerBackdrop(ctx: CanvasRenderingContext2D, ox:number, oy:number, zoom:number):void {
  const backdrop=images['manhattan-canyon'];if(!backdrop)return;
  const c=16*zoom,width=72*c,height=width*backdrop.height/backdrop.width;
  ctx.save();ctx.imageSmoothingEnabled=false;ctx.globalAlpha=.42;
  ctx.drawImage(backdrop,ox-12*c,oy-c,width,height);
  ctx.globalAlpha=1;ctx.globalCompositeOperation='destination-over';
  ctx.fillStyle='#061021';ctx.fillRect(0,0,ctx.canvas.width,ctx.canvas.height);ctx.restore();
}

type Edge = {x:number;y:number;length:number;side:'north'|'south'|'west'|'east'};
type Pier = {x:number;y:number;length:number};
// Derive every facade from the FINAL footprint, after the room setbacks.
export function buildTowerStructure(tiles:TileType[][]):{edges:Edge[];piers:Pier[];lintels:Pier[]} {
  const occupied=(x:number,y:number)=>tiles[y]?.[x]!==undefined&&tiles[y][x]!==TileType.VOID;
  const edges:Edge[]=[],piers:Pier[]=[],lintels:Pier[]=[];
  for(const side of ['north','south','west','east'] as const){
    const horizontal=side==='north'||side==='south';
    const lines=horizontal?tiles.length:tiles[0].length,cells=horizontal?tiles[0].length:tiles.length;
    const dx=side==='west'?-1:side==='east'?1:0,dy=side==='north'?-1:side==='south'?1:0;
    for(let line=0;line<lines;line++){
      let start=-1;
      for(let cell=0;cell<=cells;cell++){
        const x=horizontal?cell:line,y=horizontal?line:cell;
        const exposed=cell<cells&&occupied(x,y)&&!occupied(x+dx,y+dy);
        if(exposed&&start<0)start=cell;
        if(!exposed&&start>=0){
          edges.push({x:horizontal?start:line+(side==='east'?1:0),
            y:horizontal?line+(side==='south'?1:0):start,length:cell-start,side});start=-1;
        }
      }
    }
  }
  // Merge actual partition runs. Crop the final module instead of stretching
  // an entire storey image and then cutting it into disconnected tile fragments.
  for(let x=0;x<tiles[0].length;x++){
    let start=-1;
    for(let y=worldY(10);y<=worldY(31);y++){
      const wall=y<worldY(31)&&tiles[y]?.[x]===TileType.WALL;
      if(wall&&start<0)start=y;
      if(!wall&&start>=0){if(y-start>=2)piers.push({x,y:start,length:y-start});start=-1;}
    }
  }
  for(let y=worldY(21);y<worldY(31);y++){
    let start=-1;
    for(let x=0;x<=tiles[y].length;x++){
      const wall=x<tiles[y].length&&tiles[y][x]===TileType.WALL;
      if(wall&&start<0)start=x;
      if(!wall&&start>=0){if(x-start>=2)lintels.push({x:start,y,length:x-start});start=-1;}
    }
  }
  return {edges,piers,lintels};
}

export function renderTowerArchitecture(ctx:CanvasRenderingContext2D,ox:number,oy:number,zoom:number,tiles:TileType[][]):void {
  const c=16*zoom,{edges}=buildTowerStructure(tiles);
  const image=(name:string,x:number,y:number,w:number,h:number)=>{
    if(images[name])ctx.drawImage(images[name],ox+x*c,oy+y*c,w*c,h*c);
  };
  ctx.save();ctx.imageSmoothingEnabled=false;
  ctx.save();ctx.beginPath();ctx.rect(0,0,ctx.canvas.width,ctx.canvas.height);
  // Extrusions may occupy sky, but cannot erase any floor, landing or doorway.
  tiles.forEach((row,y)=>row.forEach((tile,x)=>{
    if(tile!==TileType.VOID)ctx.rect(ox+x*c,oy+y*c,c,c);
  }));ctx.clip('evenodd');
  for(const edge of edges){
    const x=ox+edge.x*c,y=oy+edge.y*c;
    if(edge.side==='south'){
      const shade=ctx.createLinearGradient(0,y,0,y+.65*c);
      shade.addColorStop(0,'#365a78');shade.addColorStop(.35,'#1a3552');shade.addColorStop(1,'#071323');
      ctx.fillStyle=shade;ctx.fillRect(x,y,edge.length*c,.75*c);
      ctx.fillStyle='#e5b471';ctx.fillRect(x,y,edge.length*c,zoom);
      ctx.fillStyle='#02081385';ctx.fillRect(x+.18*c,y+.75*c,edge.length*c,.24*c);
      // One attached slab trim, repeated at its native size.
      const slab=images['md_slab_edge'];
      if(slab&&edge.y<worldY(33))for(let px=0;px<edge.length*16;px+=slab.width){
        const width=Math.min(slab.width,edge.length*16-px);
        ctx.drawImage(slab,0,0,width,9,x+px*zoom,y,width*zoom,9*zoom);
      }
    }else if(edge.side==='west'||edge.side==='east'){
      const direction=edge.side==='west'?-1:1;
      ctx.beginPath();ctx.moveTo(x,y);ctx.lineTo(x+direction*.45*c,y+.22*c);
      ctx.lineTo(x+direction*.45*c,y+(edge.length+.22)*c);ctx.lineTo(x,y+edge.length*c);ctx.closePath();
      ctx.fillStyle=edge.side==='west'?'#2c4e6b':'#18324f';ctx.fill();
      ctx.strokeStyle='#86a4b6';ctx.lineWidth=zoom;ctx.stroke();
      ctx.fillStyle='#040c1850';ctx.fillRect(x+(direction<0?-.6:.2)*c,y+.3*c,.2*c,edge.length*c);
    }else{
      ctx.fillStyle='#18314b';ctx.fillRect(x,y-.4*c,edge.length*c,.4*c);
      ctx.fillStyle='#506e86';ctx.fillRect(x,y-.4*c,edge.length*c,zoom*2);
      ctx.fillStyle='#b7afa0';ctx.fillRect(x,y-.05*c,edge.length*c,zoom);
    }
  }
  ctx.restore();
  // Interior partitions now use the engine's raised, auto-connected wall
  // sprites, depth-sorted with characters. Never paint a second flat wall here.
  image('penthouse-crown',15,-.7,18,1.2);
  for(const [x,w]of [[16,6],[26,6]])image('md_atrium_canopy',x,worldY(10)-.4,w,.65);
  // Parapets are attached to the actual roof terraces, without floating stairs.
  for(const [x,w]of [[4,11],[33,11]]){
    ctx.save();ctx.beginPath();ctx.rect(ox+x*c,oy+7*c,w*c,2*c);ctx.clip();
    for(let xx=x;xx<x+w;xx+=8)image('terrace',xx,7,8,4);
    ctx.restore();
    for(let xx=x;xx<x+w;xx+=4)image('garden-parapet',xx,7.1,Math.min(4,x+w-xx),.85);
  }
  ctx.restore();
}

export function renderTowerRelief(ctx:CanvasRenderingContext2D,ox:number,oy:number,zoom:number,tiles:TileType[][]):void {
  const c=16*zoom;
  const floor=(x:number,y:number)=>tiles[y]?.[x]!==undefined&&tiles[y][x]!==TileType.WALL&&tiles[y][x]!==TileType.VOID;
  ctx.save();ctx.beginPath();
  tiles.forEach((row,y)=>row.forEach((_,x)=>{if(floor(x,y))ctx.rect(ox+x*c,oy+y*c,c,c);}));ctx.clip();
  for(let y=0;y<tiles.length;y++)for(let x=0;x<tiles[y].length;x++){
    if(!floor(x,y))continue;
    const px=ox+x*c,py=oy+y*c;
    if(tiles[y-1]?.[x]===TileType.WALL){
      const g=ctx.createLinearGradient(0,py,0,py+c*1.5);
      g.addColorStop(0,'#07101f80');g.addColorStop(.3,'#10182930');g.addColorStop(1,'#10182900');
      ctx.fillStyle=g;ctx.fillRect(px,py,c,c*1.5);
    }
    if(tiles[y]?.[x-1]===TileType.WALL){
      const g=ctx.createLinearGradient(px,0,px+c*.5,0);
      g.addColorStop(0,'#07101f60');g.addColorStop(1,'#07101f00');
      ctx.fillStyle=g;ctx.fillRect(px,py,c*.5,c);
    }
  }ctx.restore();
}

export function renderTowerSign(ctx:CanvasRenderingContext2D,ox:number,oy:number,zoom:number):void {
  const sign=images['md_vertical_sign'];if(!sign)return;
  const c=16*zoom,x=Math.max(3*zoom,ox-1.55*c);
  ctx.save();ctx.imageSmoothingEnabled=false;ctx.drawImage(sign,x,oy+worldY(11)*c,1.3*c,6.8*c);ctx.restore();
}
