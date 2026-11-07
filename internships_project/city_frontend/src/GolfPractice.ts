import { CharacterState, Direction, TILE_SIZE } from '../vendor/pixel-agents/webview-ui/src/office/types';
import type { OfficeState } from '../vendor/pixel-agents/webview-ui/src/office/engine/officeState';
import type { AgentStatus } from './types';
import { worldY } from './worldGeometry';

// The six stance areas face the backstop. Reservations are local
// ambient animation only: never create tasks, tool events or backend statuses.
// The office gate stands on the shared east gallery, outside every desk.
export const OFFICE_PORTAL = {col:48,row:worldY(19)};
export const GOLF_PORTAL = {col:65,row:worldY(28)};
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

const SWING_SECONDS = 4.4;
const ease = (value:number)=>value*value*(3-2*value);
export function golfBallPosition(bay:typeof GOLF_BAYS[number],flight:number){
  const teeY=worldY(bay.matRow)*TILE_SIZE+11;
  return {x:bay.matCol*TILE_SIZE+43+6*flight+3*Math.sin(Math.PI*flight),
    y:teeY-(teeY-GOLF_BOUNDS.top*TILE_SIZE-12)*flight-12*Math.sin(Math.PI*flight)};
}
export function golfSwingPose(seconds:number){
  const phase=(seconds%SWING_SECONDS)/SWING_SECONDS;
  if(phase<.18)return {phase,angle:.12,sway:0,bob:Math.sin(phase/.18*Math.PI)*.3,flight:0};
  // Keep feet below the mat's draw order: a negative bob hides the sprite behind its mat.
  if(phase<.43){const t=ease((phase-.18)/.25);return {phase,angle:.12-1.42*t,sway:-1.8*t,bob:0,flight:0};}
  if(phase<.55){const t=ease((phase-.43)/.12);return {phase,angle:-1.3+1.42*t,sway:-1.8+4*t,bob:.8*t,flight:0};}
  if(phase<.79){const t=ease((phase-.55)/.24);return {phase,angle:.12-1.35*t,sway:2-1.2*t,bob:.8-.8*t,flight:(phase-.55)/.24};}
  const t=ease((phase-.79)/.21);
  return {phase,angle:-1.23+1.35*t,sway:.8*(1-t),bob:0,flight:0};
}

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
    await Promise.all(['md_golf_backstop','md_golf_deck','md_golf_skyline','md_golf_portal'].map(name=>new Promise<void>((resolve,reject)=>{
      const image=new Image();image.onload=()=>{this.assets[name]=image;resolve();};
      image.onerror=()=>reject(new Error(`Impossible de charger le décor du practice : ${name}`));
      image.src=name==='md_golf_backstop'?'/city/pixel-assets/tower/md_golf_backstop.svg':
        name==='md_golf_portal'?'/city/pixel-assets/tower/md_golf_portal.svg':
        name==='md_golf_deck'?'/city/pixel-assets/tower/turf.png':`/city/pixel-assets/furniture/MARKETDESK_GOLF/${name}.png`;
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
        const pose=golfSwingPose(visit.swing);
        ch.x=ch.tileCol*TILE_SIZE+TILE_SIZE/2+pose.sway;
        ch.y=ch.tileRow*TILE_SIZE+TILE_SIZE/2+pose.bob;
        if(visit.elapsed>32){
          ch.x=ch.tileCol*TILE_SIZE+TILE_SIZE/2;
          ch.y=ch.tileRow*TILE_SIZE+TILE_SIZE/2;
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
    const backstop=this.assets.md_golf_backstop;
    if(backstop)ctx.drawImage(backstop,x,y,w,4*cell);
    const gate=this.assets.md_golf_portal;
    if(gate)for(const [portal,label] of [[OFFICE_PORTAL,'GOLF'],[GOLF_PORTAL,'DESKS']] as const){
      const px=ox+(portal.col+.5)*cell,foot=oy+(portal.row+1)*cell;
      ctx.drawImage(gate,px-32*zoom,foot-78*zoom,64*zoom,78*zoom);
      ctx.fillStyle='#dcfff7';ctx.font=`700 ${7*zoom}px "Segoe UI",sans-serif`;
      ctx.textAlign='center';ctx.fillText(label,px,foot-65*zoom);
    }
  }

  render(ctx:CanvasRenderingContext2D,ox:number,oy:number,zoom:number):void{
    ctx.save();const cell=TILE_SIZE*zoom;
    // A restrained edge pulse keeps the doorway alive without covering agents.
    for(const portal of [OFFICE_PORTAL,GOLF_PORTAL]){
      const px=ox+(portal.col+.5)*cell,foot=oy+(portal.row+1)*cell;
      ctx.strokeStyle=`rgba(115,255,223,${.22+.13*Math.sin(this.time*2.4)})`;
      ctx.lineWidth=Math.max(1,zoom);
      ctx.strokeRect(px-25*zoom,foot-68*zoom,50*zoom,59*zoom);
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
      const pose=golfSwingPose(visit.swing),x=ox+ch.x*zoom,y=oy+(ch.y-12)*zoom;
      const handX=x+7*zoom,handY=y+1*zoom,clubLength=12*zoom;
      const bay=GOLF_BAYS[visit.bay],tee=golfBallPosition(bay,0);
      const teeX=ox+tee.x*zoom,teeY=oy+tee.y*zoom;
      // The club stays outside the character silhouette; impact starts at the printed tee.
      ctx.lineCap='round';ctx.lineJoin='round';
      ctx.strokeStyle='#172a35';ctx.lineWidth=Math.max(2,2.6*zoom);
      ctx.beginPath();ctx.moveTo(x+3*zoom,y-5*zoom);ctx.lineTo(x+5*zoom,y-zoom);ctx.stroke();
      ctx.strokeStyle='#8aa9b5';ctx.lineWidth=Math.max(1,1.5*zoom);
      ctx.beginPath();ctx.moveTo(x+3*zoom,y-5*zoom);ctx.lineTo(x+5*zoom,y-zoom);ctx.stroke();
      ctx.strokeStyle='#d8aa83';ctx.lineWidth=Math.max(1,1.2*zoom);
      ctx.beginPath();ctx.moveTo(x+5*zoom,y-zoom);ctx.lineTo(handX,handY);ctx.stroke();
      if(pose.phase>=.43&&pose.phase<.58){
        ctx.globalAlpha=.22;ctx.strokeStyle='#d3e6e9';ctx.lineWidth=Math.max(1,zoom);
        for(const lag of [.32,.62]){
          ctx.beginPath();ctx.moveTo(handX,handY);
          const trailAngle=Math.max(-1.4,pose.angle+(pose.phase<.43?lag:-lag));
          ctx.lineTo(handX+Math.cos(trailAngle)*clubLength,handY+Math.sin(trailAngle)*clubLength);ctx.stroke();
        }
        ctx.globalAlpha=1;
      }
      const endX=handX+Math.cos(pose.angle)*clubLength,endY=handY+Math.sin(pose.angle)*clubLength;
      ctx.strokeStyle='#d7e7e9';ctx.lineWidth=Math.max(1,zoom);
      ctx.beginPath();ctx.moveTo(handX,handY);ctx.lineTo(endX,endY);ctx.stroke();
      ctx.strokeStyle='#536e7b';ctx.lineWidth=Math.max(2,2*zoom);
      ctx.beginPath();ctx.moveTo(endX-2*zoom,endY);ctx.lineTo(endX+2*zoom,endY+zoom);ctx.stroke();
      if(!pose.flight){
        ctx.fillStyle='#fff9df';ctx.beginPath();ctx.arc(teeX,teeY,Math.max(1,1.15*zoom),0,Math.PI*2);ctx.fill();
      }else{
        const t=pose.flight,ball=golfBallPosition(bay,t),ballX=ox+ball.x*zoom,ballY=oy+ball.y*zoom;
        for(const lag of [.08,.16,.24])if(t>lag){
          const previous=golfBallPosition(bay,t-lag);
          ctx.globalAlpha=Math.max(0,(.35-lag)*(.85-t));
          ctx.fillStyle='#bdf8e9';ctx.beginPath();ctx.arc(ox+previous.x*zoom,oy+previous.y*zoom,Math.max(.6,zoom*.7),0,Math.PI*2);ctx.fill();
        }
        ctx.globalAlpha=1;ctx.fillStyle='#fffdf0';ctx.beginPath();ctx.arc(ballX,ballY,Math.max(1,1.25*zoom),0,Math.PI*2);ctx.fill();
        if(t<.18){
          ctx.strokeStyle=`rgba(255,244,185,${1-t/.18})`;ctx.lineWidth=Math.max(1,zoom);
          ctx.beginPath();ctx.arc(teeX,teeY,Math.max(2,5*t*zoom),0,Math.PI*2);ctx.stroke();
        }
        if(t>.88){
          ctx.strokeStyle=`rgba(208,255,235,${(t-.88)/.12})`;ctx.lineWidth=Math.max(1,zoom);
          ctx.beginPath();ctx.arc(ballX,ballY,Math.max(2,(t-.88)*25*zoom),0,Math.PI*2);ctx.stroke();
        }
      }
    }
    ctx.restore();
  }
}
