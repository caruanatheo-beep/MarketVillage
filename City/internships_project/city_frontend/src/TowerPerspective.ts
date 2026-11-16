import { worldY } from './worldGeometry';

// One projection for floors, objects, robots, labels and pointer hit tests.
// Navigation remains on the original orthogonal grid.
export function towerDepthFactor(screenY:number, offsetY:number, zoom:number):number {
  const depth=Math.max(0,Math.min(1,(screenY-offsetY)/(worldY(40)*16*zoom)));
  return .72+.28*depth;
}

export function projectTowerX(x:number,y:number,offsetX:number,offsetY:number,zoom:number):number {
  if(x>=offsetX+50*16*zoom){
    const centre=offsetX+58.5*16*zoom;
    return centre+(x-centre)*.94;
  }
  const centre=offsetX+24*16*zoom;
  return centre+(x-centre)*towerDepthFactor(y,offsetY,zoom);
}

export function unprojectTowerX(x:number,y:number,offsetX:number,offsetY:number,zoom:number):number {
  const officeCentre=offsetX+24*16*zoom,golfCentre=offsetX+58.5*16*zoom;
  const officeEdge=officeCentre+(offsetX+48*16*zoom-officeCentre)*towerDepthFactor(y,offsetY,zoom);
  const golfEdge=golfCentre+(offsetX+50*16*zoom-golfCentre)*.94;
  if(x>=(officeEdge+golfEdge)/2)return golfCentre+(x-golfCentre)/.94;
  const centre=offsetX+24*16*zoom;
  return centre+(x-centre)/towerDepthFactor(y,offsetY,zoom);
}

// Never scale vertical bands: characters, mats and doors keep the same
// pixel height everywhere. Space is saved in the physical layout instead.
export function projectTowerY(y:number,_offsetY:number,_zoom:number):number {return y;}
export function unprojectTowerY(y:number,_offsetY:number,_zoom:number):number {return y;}
export function towerDisplayRows(rows:number):number {return rows;}

export function renderTowerPerspective(ctx:CanvasRenderingContext2D,source:HTMLCanvasElement,
  offsetX:number,offsetY:number,zoom:number):void {
  ctx.save();ctx.imageSmoothingEnabled=false;
  // Fine native-pixel scanlines avoid diagonal mesh seams in translucent
  // glass and tiny character sprites. Static architecture is cached upstream.
  const band=Math.max(1,Math.round(zoom*1.5));
  for(let y=0;y<source.height;y+=band){
    const height=Math.min(band,source.height-y),middle=y+height/2;
    const factor=towerDepthFactor(middle,offsetY,zoom);
    const top=projectTowerY(y,offsetY,zoom);
    const bottom=projectTowerY(y+height,offsetY,zoom);
    const split=Math.min(source.width,Math.max(0,offsetX+50*16*zoom));
    const officeLeft=projectTowerX(0,middle,offsetX,offsetY,zoom);
    ctx.drawImage(source,0,y,split,height,officeLeft,top,split*factor,bottom-top);
    if(split<source.width){
      const golfLeft=projectTowerX(split,middle,offsetX,offsetY,zoom);
      ctx.drawImage(source,split,y,source.width-split,height,golfLeft,top,(source.width-split)*.94,bottom-top);
    }
  }
  ctx.restore();
}
