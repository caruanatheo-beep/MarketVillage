import { build } from "esbuild-wasm";
import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";
import assert from "node:assert/strict";

export async function checkLayout() {
  const base = dirname(fileURLToPath(import.meta.url));
  const compiled = await build({
    absWorkingDir: base,
    stdin: {
      contents: `export { loadFurniture, buildOfficeLayout, validateAgentRoutes } from './src/PixelFloorGame';
        export { worldY } from './src/worldGeometry';
        export { cockpitData, resultSummary } from './src/cockpitData';
        export { notificationRows, isPendingProposal, needsDecision, parisDay } from './src/notifications';
        export { buildTowerStructure } from './src/TowerArchitecture';
        export { TileType } from './vendor/pixel-agents/webview-ui/src/office/types';
        export { projectTowerX, unprojectTowerX, towerDepthFactor, projectTowerY, unprojectTowerY, towerDisplayRows } from './src/TowerPerspective';
        export { GolfPractice, GOLF_BAYS } from './src/GolfPractice';
        export { OfficeState } from './vendor/pixel-agents/webview-ui/src/office/engine/officeState';
        export { findPath } from './vendor/pixel-agents/webview-ui/src/office/layout/tileMap';`,
      resolveDir: base,
      loader: "ts",
    },
    bundle: true, write: false, platform: "node", format: "esm", logLevel: "silent",
  });
  const { loadFurniture, buildOfficeLayout, validateAgentRoutes, OfficeState, findPath, GolfPractice, GOLF_BAYS, worldY,
    projectTowerX, unprojectTowerX, towerDepthFactor, projectTowerY, unprojectTowerY, towerDisplayRows, buildTowerStructure, TileType,
    notificationRows, isPendingProposal, needsDecision, parisDay, cockpitData, resultSummary } =
    await import(`data:text/javascript;base64,${Buffer.from(compiled.outputFiles[0].text).toString("base64")}`);
  const proposal={id:'proposal',agent_id:'job_hunter',status:'completed',description:'Audit',created_at:'2026-01-01',result:{approval_required:true,role_version:2}};
  const done={id:'done',agent_id:'networker',status:'completed',description:'Contacts',created_at:'2026-01-02',result:{}};
  const rows=notificationRows([done,proposal],[{id:5,task_id:'done',created_at:'2026-01-02'}],4);
  assert.equal(rows[0].task.id,'proposal','Decisions stay ahead of newer completed missions');
  assert.equal(rows[1].unread,true,'Unread depends on the latest event per task');
  assert.equal(notificationRows([done],[{id:5,task_id:'done'}],5)[0].unread,false);
  assert.equal(needsDecision(proposal),true);
  assert.equal(isPendingProposal({...proposal,result:{...proposal.result,review_decision:'approved'}}),false);
  assert.equal(isPendingProposal({...proposal,result:{...proposal.result,branch:'isolated'}}),false);
  console.log('Notifications OK: decision priority, read markers and reviewed/branched proposals.');
  const finished={...done,agent_id:'internship_scout',description:'Stages',finished_at:'2026-11-02T23:10:00Z',result:{new_count:4}};
  const queued={...done,id:'queued',agent_id:'job_hunter',status:'queued'};
  const running={...queued,id:'running',status:'running'};
  const decision={...proposal,agent_id:'job_hunter',description:'Review'};
  const cockpit=cockpitData([finished,queued,running,decision],[{id:1,task_id:'running',message:'Sources analysées'},{id:2,task_id:'running',message:'Vérification en cours'}],new Date('2026-11-03T00:20:00Z'));
  assert.equal(cockpit.today,1,'Paris day crosses UTC midnight correctly');
  assert.equal(parisDay('2026-11-02T23:10:00Z'),'2026-11-03');
  assert.equal(cockpit.active[0].id,'running','Running tasks precede queued tasks');
  assert.equal(cockpit.decisions[0].id,decision.id);
  assert.equal(cockpit.latest.get('running').message,'Vérification en cours','Use latest real event');
  assert.equal(cockpit.finished.length,1,'Unresolved proposals are decisions, not finished results');
  assert.equal(resultSummary(finished),'4 nouveaux stages d\u00e9tect\u00e9s');
  assert.equal(cockpitData([],[]).today,0);
  console.log('Cockpit OK: real phases, decisions, results and Paris daily counts.');

  for(const zoom of [.5,1,2])for(const row of [-2,0,9,worldY(21),worldY(40),worldY(40)+2])for(const col of [-4,0,24,48,52]){
    const x=17+col*16*zoom,y=23+row*16*zoom;
    const projected=projectTowerX(x,y,17,23,zoom);
    assert.ok(Math.abs(unprojectTowerX(projected,y,17,23,zoom)-x)<1e-8,'Perspective hit-test round trip');
    assert.ok(Math.abs(unprojectTowerY(projectTowerY(y,23,zoom),23,zoom)-y)<1e-8,'Compact golf hit-test round trip');
    assert.ok(towerDepthFactor(y,23,zoom)>=.72&&towerDepthFactor(y,23,zoom)<=1,'Monotonic bounded perspective');
  }
  // Regression: crossing a former facade band, the doorway and the practice
  // cannot change a character's height or squash the golf equipment.
  for(const row of [8,9,worldY(21),worldY(31),worldY(33),worldY(36),worldY(39)]){
    const y=row*16;
    assert.equal(projectTowerY(y+24,0,1)-projectTowerY(y,0,1),24,'Sprite height remains native');
  }
  assert.equal(worldY(40),38,'Five redundant facade rows removed');
  assert.ok(towerDepthFactor(23,23,1)<towerDepthFactor(23+worldY(40)*16,23,1),'Base is larger than penthouse');
  const assetPath = url => resolve(base, "../city_assets/pixel-agents/assets", url.split('?')[0].replace("/city/pixel-assets/", ""));
  const assets = await loadFurniture(
    async url => JSON.parse(await readFile(assetPath(url), "utf8")),
    async (url, width, height) => {
      const png = await readFile(assetPath(url));
      assert.equal(png.subarray(1, 4).toString(), "PNG", `Invalid PNG: ${url}`);
      assert.equal(png.readUInt32BE(16), width, `PNG width differs from manifest: ${url}`);
      assert.equal(png.readUInt32BE(20), height, `PNG height differs from manifest: ${url}`);
      // Collision validation needs the real dimensions and footprints, not pixel colours.
      return Array.from({ length: height }, () => Array(width).fill(""));
    },
  );
  const office = new OfficeState(buildOfficeLayout());
  validateAgentRoutes(office);
  for (const [from, to] of [
    [[23, worldY(10)], [23, worldY(19)]],
    [[15, worldY(14)], [32, worldY(14)]],
  ]) {
    assert.ok(findPath(...from, ...to, office.tileMap, office.blockedTiles).length,
      `Lounge passage blocked from ${from} to ${to}`);
    assert.ok(findPath(...to, ...from, office.tileMap, office.blockedTiles).length,
      `Lounge return passage blocked from ${to} to ${from}`);
  }
  const floorCells=office.tileMap.flatMap((row,y)=>row.flatMap((tile,x)=>
    tile!==TileType.VOID&&tile!==TileType.WALL?[{x,y}]:[]));
  const connected=new Set(),pending=[floorCells[0]];
  for(let i=0;i<pending.length;i++){
    const {x,y}=pending[i],key=`${x},${y}`;
    if(connected.has(key))continue;
    connected.add(key);
    for(const [dx,dy]of [[1,0],[-1,0],[0,1],[0,-1]]){
      const tile=office.tileMap[y+dy]?.[x+dx];
      if(tile!==undefined&&tile!==TileType.VOID&&tile!==TileType.WALL&&!connected.has(`${x+dx},${y+dy}`))
        pending.push({x:x+dx,y:y+dy});
    }
  }
  assert.equal(connected.size,floorCells.length,'No disconnected floor fragment anywhere in the building');
  // Regression: visible corridors and plate interiors cannot contain sky holes.
  for(const [x0,x1,y0,y1]of [[1,12,11,17],[16,31,11,17],[0,13,20,28],[16,31,20,28],[33,46,20,28],
    [14,14,11,28],[0,46,18,19]])
    for(let y=y0;y<=y1;y++)for(let x=x0;x<=x1;x++)
      assert.notEqual(office.tileMap[y][x],TileType.VOID,`Sky hole inside a floor plate (${x},${y})`);
  const {edges,piers,lintels}=buildTowerStructure(office.tileMap);
  const solid=(x,y)=>office.tileMap[y]?.[x]!==undefined&&office.tileMap[y][x]!==TileType.VOID;
  for(const edge of edges)for(let offset=0;offset<edge.length;offset++){
    const x=edge.x+(edge.side==='north'||edge.side==='south'?offset:0),
      y=edge.y+(edge.side==='west'||edge.side==='east'?offset:0);
    const inside=edge.side==='south'?[x,y-1]:edge.side==='east'?[x-1,y]:[x,y];
    const outside=edge.side==='north'?[x,y-1]:edge.side==='west'?[x-1,y]:[x,y];
    assert.ok(solid(...inside)&&!solid(...outside),'Every facade is attached to a real building edge');
  }
  for(const run of piers)for(let y=run.y;y<run.y+run.length;y++)
    assert.equal(office.tileMap[y][run.x],TileType.WALL,'Glass pier must not cover a door or floor');
  for(const run of lintels)for(let x=run.x;x<run.x+run.length;x++)
    assert.equal(office.tileMap[run.y][x],TileType.WALL,'Glazing must stop before a doorway');
  for(const item of office.layout.furniture.filter(f=>f.type==='MD_PANORAMA_WINDOW'))
    for(let x=item.col;x<item.col+6;x++)
      assert.equal(office.tileMap[item.row][x],TileType.WALL,`Floating window ${item.uid} at ${x},${item.row}`);
  for(const [name,w,h]of [['md_corridor_pier',16,48],['md_glass_transom',64,16],['md_slab_edge',64,9]]){
    const png=await readFile(assetPath(`/city/pixel-assets/tower/${name}.png`));
    assert.equal(png.readUInt32BE(16),w);assert.equal(png.readUInt32BE(20),h);
  }
  for(let mask=0;mask<16;mask++){
    const png=await readFile(assetPath(`/city/pixel-assets/tower/md_partition_${mask.toString(16).padStart(2,'0')}.png`));
    assert.equal(png.readUInt32BE(16),16);assert.equal(png.readUInt32BE(20),24,'Raised wall height');
  }
  for(const [col,rows,doors]of [[13,[11,12,13,14,15,16,17],[14,15]],
    [32,[10,11,12,13,14,15,16],[14,15]]])for(const row of rows)
      assert.equal(office.tileMap[row][col]===TileType.WALL,!doors.includes(row),`Physical room wall/door (${col},${row})`);
  for(const col of [1,2,3,4,5,8,9,10,11,12])assert.equal(office.tileMap[18][col],TileType.WALL,'Global Markets south partition');
  for(const col of [33,34,35,36,37,38,41,42,43,44,45,46])assert.equal(office.tileMap[17][col],TileType.WALL,'Research south partition');
  for(const [col,row]of [[6,18],[7,18],[39,17],[40,17],[39,24],[40,24]])
    assert.notEqual(office.tileMap[row][col],TileType.WALL,'Double doorway stays open');
  // Every portal occupies a real opening, bounded by joined partition ends.
  const doors=office.layout.furniture.filter(item=>['MD_DOUBLE_GLASS_DOOR','MD_INTERNAL_DOUBLE_DOOR','MD_SIDE_GLASS_DOOR'].includes(item.type));
  for(const door of doors){
    const side=door.type==='MD_SIDE_GLASS_DOOR',width=side?1:door.type==='MD_DOUBLE_GLASS_DOOR'?4:2,height=side?2:1;
    for(let dy=0;dy<height;dy++)for(let dx=0;dx<width;dx++)
      assert.notEqual(office.tileMap[door.row+dy][door.col+dx],TileType.WALL,`Open portal ${door.uid}`);
    const ends=side?[[door.col,door.row-1],[door.col,door.row+height]]:[[door.col-1,door.row],[door.col+width,door.row]];
    for(const [x,y]of ends)assert.equal(office.tileMap[y][x],TileType.WALL,`Attached jamb ${door.uid} (${x},${y})`);
    const drawing=office.furniture[office.layout.furniture.indexOf(door)];
    assert.equal(drawing.y+drawing.sprite.length,(door.row+height)*16,`Bottom-anchored portal ${door.uid}`);
  }
  for(const [x,y]of [[13,10],[13,18],[32,9],[32,17],[32,19],[15,19],[15,29],[32,29]])
    assert.equal(office.tileMap[y][x],TileType.WALL,`Closed partition corner (${x},${y})`);
  console.log(`Structure OK: connected plate interiors, ${edges.length} attached edges, ${piers.length} native glass piers, ${lintels.length} door-safe glazing runs.`);
  for (const [x,y] of [[5,7],[42,7]]) {
    assert.ok(findPath(23,worldY(19),x,y,office.tileMap,office.blockedTiles).length,'Penthouse terrace must be accessible');
    assert.ok(findPath(x,y,23,worldY(19),office.tileMap,office.blockedTiles).length,'Penthouse terrace must have a return path');
  }
  // The actual seats move with their departments, not only the painted shell.
  for(const [id,col,row] of [
    ['marketdesk-chair-market_analyst',3,15], ['marketdesk-chair-finance_tutor',36,14],
    ['marketdesk-chair-job_hunter',3,24],
  ]){
    const seat=office.seats.get(id);
    assert.deepEqual([seat?.seatCol,seat?.seatRow],[col,row],`Shifted workstation ${id}`);
  }
  const workstations = [...office.seats].filter(([id]) => /^marketdesk-(chair-|manager-chair$)/.test(id));
  assert.equal(workstations.length, 9, "Expected nine assigned workstations");
  for (const [id, seat] of workstations) {
    const blocked = new Set(office.blockedTiles);
    // The engine unblocks an agent's own chair when leaving or returning to it.
    blocked.delete(`${seat.seatCol},${seat.seatRow}`);
    assert.ok(findPath(23, worldY(19), seat.seatCol, seat.seatRow, office.tileMap, blocked).length, `Cannot reach ${id}`);
    assert.ok(findPath(seat.seatCol, seat.seatRow, 23, worldY(19), office.tileMap, blocked).length, `Cannot leave ${id}`);
    for (const bay of GOLF_BAYS) {
      assert.ok(findPath(seat.seatCol,seat.seatRow,bay.col,bay.row,office.tileMap,blocked).length,`Cannot reach golf bay ${bay.index} from ${id}`);
      assert.ok(findPath(bay.col,bay.row,seat.seatCol,seat.seatRow,office.tileMap,blocked).length,`Cannot return from golf bay ${bay.index} to ${id}`);
    }
  }
  const roster=['market_analyst','finance_tutor','job_hunter','networker','outreach_agent','developer','innovation_lab','internship_scout','desk_manager'];
  roster.forEach((id,index)=>{office.addAgent(index,index%6,0,id==='desk_manager'?'marketdesk-manager-chair':`marketdesk-chair-${id}`,true);office.setAgentPinned(index,true);office.setAgentActive(index,false);});
  const golf=new GolfPractice(office,roster);
  const idle=roster.map(id=>({id,status:'idle'}));
  const played=new Set();
  let maxVisitors=0;
  for(let step=0;step<1800;step++) {
    if(step%100===0)golf.sync(idle,[]);
    golf.update(.05);office.update(.05);
    assert.ok(golf.visits.size<=5,'At most five reserved mats');
    assert.equal(new Set([...golf.visits.values()].map(v=>v.bay)).size,golf.visits.size,'No shared mat');
    maxVisitors=Math.max(maxVisitors,golf.visits.size);
    for(const [index,visit]of golf.visits)if(visit.stage==='playing')played.add(index);
    for(const ch of office.characters.values())assert.ok(!office.blockedTiles.has(`${ch.tileCol},${ch.tileRow}`)||office.seats.get(ch.seatId)?.seatCol===ch.tileCol,'Characters stay on navigable floor or own seat');
  }
  assert.ok(played.size>=5,'Original characters actually walk to mats and enter swing state');
  const visitor=[...golf.visits.keys()][0];assert.notEqual(visitor,undefined);
  const ch=office.characters.get(visitor),before=[ch.x,ch.y];
  golf.sync(idle,[{agent_id:roster[visitor],status:'queued'}]);
  assert.ok(!golf.visits.has(visitor),'A queued mission interrupts the ambient pause immediately');
  assert.deepEqual([ch.x,ch.y],before,'Mission return never teleports an agent');
  const seat=office.seats.get(ch.seatId);
  assert.deepEqual(ch.path.at(-1),{col:seat.seatCol,row:seat.seatRow},'Mission sends the agent to the real workstation');
  for(let step=0;step<800;step++){golf.update(.05);office.update(.05);}
  assert.equal(golf.visits.size,0,'Stale backend state stops ambient activity');
  console.log(`Golf OK: 90 round-trip paths, ${played.size} animated visitors, max ${maxVisitors} mats, mission interruption and stale-state protection.`);
  console.log(`Layout OK: ${assets.catalog.length} assets, ${office.layout.furniture.length} objects, all 9 workstations reachable (18 engine routes); perspective and inverse hit tests validated.`);
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  try { await checkLayout(); }
  catch (error) { console.error(error.message); process.exitCode = 1; }
}
