import { CharacterState, Direction, TILE_SIZE } from '../vendor/pixel-agents/webview-ui/src/office/types';
import type { OfficeState } from '../vendor/pixel-agents/webview-ui/src/office/engine/officeState';
import type { AgentStatus } from './types';
import { worldY } from './worldGeometry';

// The six stance areas all strike east. Reservations are local
// ambient animation only: never create tasks, tool events or backend statuses.
export const OFFICE_PORTAL = {col:47,row:worldY(28)};
export const GOLF_PORTAL = {col:64,row:worldY(28)};
export const GOLF_BOUNDS = {left:50,right:66,top:worldY(8),bottom:worldY(31)};
export const GOLF_BAYS = [12,20,25].flatMap((matRow)=>[51,59].map(matCol=>({
  index:0,col:matCol+1,row:worldY(matRow)+1,matCol,matRow,
}))).map((bay,index)=>({...bay,index}));
export const GOLF_ROWS = worldY(33);
type Visit = { bay:number; stage:'to_portal'|'walking'|'playing'|'to_exit'|'returning'; elapsed:number; swing:number };
type Agent = {id:string;status:AgentStatus};
type Task = {agent_id:string;status?:string};
const BLOCKING = new Set(['queued','running','waiting_approval']);
const IDLE = new Set(['idle','completed','cancelled']);

export class GolfPractice {
  readonly visits = new Map<number,Visit>();
  private statuses = new Map<string,AgentStatus>();
  private tasked = new Set<string>();
  private age=Infinity;
  private cooldown = new Map<number,number>();
  private time=0;
  private assets:Record<string,HTMLImageElement>={};
  constructor(private office:OfficeState,private roster:string[]){}

  async load():Promise<void>{
    await Promise.all(['practice-net','md_golf_deck','md_golf_skyline'].map(name=>new Promise<void>((resolve,reject)=>{
      const image=new Image();image.onload=()=>{this.assets[name]=image;resolve();};
      image.onerror=()=>reject(new Error(`Impossible de charger le décor du practice : ${name}`));
      image.src=name==='practice-net'?'/city/pixel-assets/tower/practice-net.png':name==='md_golf_deck'?'/city/pixel-assets/tower/turf.png':`/city/pixel-assets/furniture/MARKETDESK_GOLF/${name}.png`;
    })));
  }
  sync(agents:Agent[],tasks:Task[]):void{
    this.statuses=new Map(agents.map(agent=>[agent.id,agent.status]));
    this.tasked=new Set(tasks.filter(task=>BLOCKING.has(task.status||'')).map(task=>task.agent_id));
    this.age=0;
    for(const [index] of this.visits)if(!this.eligible(index))this.interrupt(index);
  }
  private eligible(index:number):boolean{
    return this.age<35 && IDLE.has(this.statuses.get(this.roster[index])||'unknown') && !this.tasked.has(this.roster[index]);
  }
  private teleport(index:number, col:number, row:number):void{
    const ch=this.office.characters.get(index);
    if(!ch)return;
    ch.tileCol=col;ch.tileRow=row;
    ch.x=col*TILE_SIZE+TILE_SIZE/2;ch.y=row*TILE_SIZE+TILE_SIZE/2;
    ch.path=[];ch.moveProgress=0;ch.state=CharacterState.IDLE;
  }
  interrupt(index:number):void{
    if(!this.visits.has(index))return;
    const ch=this.office.characters.get(index);
    if(ch&&ch.tileCol>=GOLF_BOUNDS.left)this.teleport(index,OFFICE_PORTAL.col,OFFICE_PORTAL.row);
    this.visits.delete(index);this.office.setAgentPinned(index,true);
    this.office.sendToSeat(index);this.cooldown.set(index,this.time+100+index*7);
  }
  update(dt:number,collaborators:Set<number>=new Set()):void{
    this.time+=dt;this.age+=dt;
    for(const [index,visit] of this.visits){
      const ch=this.office.characters.get(index);
      if(!ch){this.visits.delete(index);continue;}
      if(!this.eligible(index)||collaborators.has(index)){this.interrupt(index);continue;}
      const bay=GOLF_BAYS[visit.bay];
      visit.elapsed+=dt;
      if(visit.stage==='to_portal' && ch.path.length===0 && ch.tileCol===OFFICE_PORTAL.col && ch.tileRow===OFFICE_PORTAL.row){
        this.teleport(index,GOLF_PORTAL.col,GOLF_PORTAL.row);
        visit.stage='walking';visit.elapsed=0;
        if(!this.office.walkToTile(index,bay.col,bay.row))this.interrupt(index);
      }
      if(visit.stage==='walking' && ch.path.length===0 && ch.tileCol===bay.col && ch.tileRow===bay.row){
        visit.stage='playing';visit.elapsed=0;
      }
      if(visit.stage==='playing'){
        // Freeze the idle wander FSM while the original character faces the tee.
        ch.state=CharacterState.IDLE;ch.dir=Direction.RIGHT;ch.wanderTimer=Infinity;ch.frame=0;
        visit.swing+=dt;
        if(visit.elapsed>32){
          visit.stage='to_exit';visit.elapsed=0;
          if(!this.office.walkToTile(index,GOLF_PORTAL.col,GOLF_PORTAL.row))this.interrupt(index);
        }
      }
      if(visit.stage==='to_exit' && ch.path.length===0 && ch.tileCol===GOLF_PORTAL.col && ch.tileRow===GOLF_PORTAL.row){
        this.teleport(index,OFFICE_PORTAL.col,OFFICE_PORTAL.row);
        visit.stage='returning';visit.elapsed=0;
        this.office.setAgentPinned(index,true);this.office.sendToSeat(index);
      }
      if(visit.stage==='returning' && ch.path.length===0){
        this.visits.delete(index);this.cooldown.set(index,this.time+110+index*7);
      }else if(['to_portal','walking','to_exit'].includes(visit.stage) && visit.elapsed>55)this.interrupt(index);
    }
    for(let index=0;index<this.roster.length;index++){
      if(this.visits.has(index)||collaborators.has(index)||!this.eligible(index)||this.time<(this.cooldown.get(index)??(18+index*9)))continue;
      const ch=this.office.characters.get(index);
      if(!ch||ch.path.length||ch.matrixEffect)continue;
      const bay=GOLF_BAYS.find(item=>![...this.visits.values()].some(v=>v.bay===item.index)&&
        ![...this.office.characters.values()].some(other=>other.id!==index&&other.tileCol===item.col&&other.tileRow===item.row));
      if(!bay)break;
      this.office.setAgentPinned(index,false);
      if(this.office.walkToTile(index,OFFICE_PORTAL.col,OFFICE_PORTAL.row))this.visits.set(index,{bay:bay.index,stage:'to_portal',elapsed:0,swing:0});
      else{this.office.setAgentPinned(index,true);this.cooldown.set(index,this.time+30);}
    }
  }

  renderFloor(ctx:CanvasRenderingContext2D,ox:number,oy:number,zoom:number):void{
    ctx.save();ctx.imageSmoothingEnabled=false;
    const cell=16*zoom,x=ox+GOLF_BOUNDS.left*cell,y=oy+GOLF_BOUNDS.top*cell;
    const w=(GOLF_BOUNDS.right-GOLF_BOUNDS.left+1)*cell,h=(GOLF_BOUNDS.bottom-GOLF_BOUNDS.top+1)*cell;
    ctx.beginPath();ctx.rect(x,y,w,h);ctx.clip();
    ctx.fillStyle='#34454a';ctx.fillRect(x,y,w,h);
    const deck=this.assets.md_golf_deck;
    if(deck)for(let row=GOLF_BOUNDS.top;row<=GOLF_BOUNDS.bottom;row+=4)for(let col=GOLF_BOUNDS.left;col<=GOLF_BOUNDS.right;col+=8)
      ctx.drawImage(deck,ox+col*cell,oy+row*cell,128*zoom,64*zoom);
    ctx.fillStyle='#0c1d2970';ctx.fillRect(x,y,w,cell*.7);
    ctx.restore();
    // A netted skyline gives the separate practice terrace its own boundary.
    const skyline=this.assets.md_golf_skyline;
    if(skyline){ctx.save();ctx.imageSmoothingEnabled=false;
      ctx.beginPath();ctx.rect(x,y,w,cell*1.2);ctx.clip();
      for(let col=50;col<67;col+=6)ctx.drawImage(skyline,ox+col*cell,oy+(GOLF_BOUNDS.top-.7)*cell,96*zoom,32*zoom);
      ctx.restore();
    }
  }

  render(ctx:CanvasRenderingContext2D,ox:number,oy:number,zoom:number):void{
    ctx.save();const cell=TILE_SIZE*zoom;
    // The portals are animated in-world; their walkable tiles stay on separate islands.
    for(const [portal,label] of [[OFFICE_PORTAL,'GOLF'],[GOLF_PORTAL,'DESKS']] as const){
      const px=ox+(portal.col+.5)*cell,py=oy+(portal.row+.5)*cell;
      const glow=ctx.createRadialGradient(px,py,0,px,py,cell*1.55);
      glow.addColorStop(0,'#94ffe4bb');glow.addColorStop(.55,'#48d6bd66');glow.addColorStop(1,'#48d6bd00');
      ctx.fillStyle=glow;ctx.fillRect(px-cell*1.55,py-cell*1.55,cell*3.1,cell*3.1);
      ctx.strokeStyle='#a8ffe9';ctx.lineWidth=Math.max(2,zoom*1.8);
      ctx.beginPath();ctx.ellipse(px,py-cell*.2,cell*.48,cell*.85,0,0,Math.PI*2);ctx.stroke();
      ctx.font=`700 ${Math.max(7,6*zoom)}px "Segoe UI",sans-serif`;
      ctx.textAlign='center';ctx.fillStyle='#e6fff5';ctx.fillText(label,px,py-cell*1.1);
    }
    // Fine mesh encloses the practice terrace without blocking its portal.
    const net=this.assets['practice-net'];
    if(net){
      ctx.save();ctx.beginPath();ctx.rect(ox+50*cell,oy+GOLF_BOUNDS.top*cell,17*cell,.9*cell);ctx.clip();
      for(let x=50;x<67;x+=4)ctx.drawImage(net,ox+x*cell,oy+GOLF_BOUNDS.top*cell,4*cell,.9*cell);
      ctx.restore();
    }
    // Local additive light pools brighten wood, characters and the green.
    ctx.beginPath();ctx.rect(ox+50*cell,oy+GOLF_BOUNDS.top*cell,17*cell,(GOLF_BOUNDS.bottom-GOLF_BOUNDS.top+1)*cell);ctx.clip();
    ctx.globalCompositeOperation='screen';
    for(const col of [50,58,66]){
      const x=ox+(col+.5)*cell,y=oy+(GOLF_BOUNDS.top+.35)*cell,r=cell*2.8;
      const glow=ctx.createRadialGradient(x,y,0,x,y,r);
      glow.addColorStop(0,'#ffd181b0');glow.addColorStop(.35,'#f69b3e50');glow.addColorStop(1,'#e8781200');
      ctx.fillStyle=glow;ctx.fillRect(x-r,y-r,r*2,r*2);
      ctx.save();ctx.translate(x,y+cell*.9);ctx.scale(1,.45);
      const reflection=ctx.createRadialGradient(0,0,0,0,0,r);
      reflection.addColorStop(0,'#efbd655c');reflection.addColorStop(1,'#efbd6500');
      ctx.fillStyle=reflection;ctx.fillRect(-r,-r,2*r,2*r);ctx.restore();
    }
    ctx.globalCompositeOperation='source-over';
    for(const [index,visit] of this.visits){
      if(visit.stage!=='playing')continue;
      const ch=this.office.characters.get(index);if(!ch)continue;
      const x=ox+ch.x*zoom,y=oy+(ch.y-10)*zoom,phase=(visit.swing%3.8)/3.8;
      const angle=phase<.35?-.3-phase*5:phase<.55?-2.05+(phase-.35)*17.5:1.45-(phase-.55)*3.88;
      const handX=x+4*zoom,handY=y+1*zoom;
      // Articulated sleeve/hand and club share the character's world transform.
      ctx.strokeStyle='#bac8d3';ctx.lineWidth=Math.max(1,zoom);
      ctx.beginPath();ctx.moveTo(x+1*zoom,y-2*zoom);ctx.lineTo(handX,handY);ctx.stroke();
      const endX=handX+Math.cos(angle)*13*zoom,endY=handY+Math.sin(angle)*13*zoom;
      ctx.beginPath();ctx.moveTo(handX,handY);ctx.lineTo(endX,endY);ctx.stroke();
      ctx.fillStyle='#6c8c99';ctx.fillRect(endX-2*zoom,endY,4*zoom,2*zoom);
      if(phase>.48&&phase<.85){
        const t=(phase-.48)/.37;
        ctx.fillStyle='#fff7d9';ctx.beginPath();ctx.arc(x+(25+t*31)*zoom,oy+ch.y*zoom-(4+Math.sin(t*Math.PI)*14)*zoom,Math.max(.7,zoom),0,Math.PI*2);ctx.fill();
      }
    }
    ctx.restore();
    ctx.save();ctx.font=`600 ${Math.max(7,7*zoom)}px "Segoe UI",sans-serif`;ctx.textAlign='center';
    ctx.fillStyle='#e8d3a6';ctx.fillText('GOLF PRACTICE',ox+58*cell,oy+worldY(10)*cell);
    ctx.font=`${Math.max(6,5*zoom)}px "Segoe UI",sans-serif`;ctx.fillStyle='#b3b9b2';
    ctx.fillText('Pause détente · aucune mission IA',ox+58*cell,oy+worldY(11)*cell);ctx.restore();
  }
}
