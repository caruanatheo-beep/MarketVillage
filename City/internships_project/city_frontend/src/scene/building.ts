// The office building in cross-section. Static parts are baked once into a single
// native-resolution canvas whose windows stay transparent so Paris shows through.
import { P, mix, px, text, textWidth, makeCanvas, seeded, type Ctx } from "./pixels";

export const BW = 640, FLOOR_H = 96, SLAB = 12, FACADE = 24;
export const SHAFT_X = 24, ROOM_X = 68, ROOM_R = 572, STAIR_X = 576, CAR_X = 44;
export const SKY = 70, GROUND = 28;

export type Level = { id: string; name: string; sign: string; agents: string[]; built: boolean; accent: string };
// Top to bottom. Seven trade teams are merged into five floors so every room stays lively.
export const LEVELS: Level[] = [
  { id: "roof", name: "Toit-terrasse", sign: "", agents: [], built: true, accent: P.sage },
  { id: "head", name: "Head of Desk", sign: "HEAD OF DESK", agents: ["desk_manager"], built: true, accent: P.amber },
  { id: "markets", name: "Global Markets", sign: "GLOBAL MARKETS", agents: ["market_analyst"], built: true, accent: P.indigo },
  { id: "research", name: "Quant & Innovation", sign: "QUANT & INNOVATION", agents: ["finance_tutor", "innovation_lab"], built: false, accent: P.sage },
  { id: "code", name: "Atelier Code", sign: "ATELIER CODE", agents: ["job_hunter", "city_ui_engineer", "internships_engineer", "quality_engineer"], built: false, accent: P.indigo },
  { id: "careers", name: "Interviews & Stages", sign: "INTERVIEWS & STAGES", agents: ["developer", "internship_scout"], built: false, accent: P.rust },
  { id: "network", name: "Réseau & Outreach", sign: "RÉSEAU & OUTREACH", agents: ["networker", "securities_scout", "prime_services_scout", "outreach_agent"], built: false, accent: P.plum },
  { id: "lobby", name: "Hall & Café", sign: "HALL & CAFÉ", agents: [], built: false, accent: P.amber },
];
export const WORLD_H = LEVELS.length * FLOOR_H;
export const HEAD_LEVEL = 1;
export const footY = (level: number): number => level * FLOOR_H + FLOOR_H - 3;
export const floorLabel = (level: number): string => level === 0 ? "T" : level === LEVELS.length - 1 ? "RDC" : String(LEVELS.length - 1 - level);

// Where each agent sits (chair centre). Agents face right, towards their desk.
export const SEATS: Record<string, { level: number; x: number }> = { desk_manager: { level: 1, x: 372 }, market_analyst: { level: 2, x: 210 } };
LEVELS.forEach((level, index) => { if (!level.built) level.agents.forEach((id, i) => { SEATS[id] = { level: index, x: 130 + i * 110 }; }); });
export const ANTEROOM = (slot: number): number => 84 + (slot % 8) * 11;
export const ROOF_SPOTS: { x: number; pose: "sit" | "putt" | "stand" }[] = [
  { x: 118, pose: "sit" }, { x: 222, pose: "sit" }, { x: 284, pose: "sit" }, { x: 392, pose: "putt" }, { x: 528, pose: "stand" }];

export type Light = { x: number; y: number; r: number; color: string; base: number; level: number; flicker?: boolean };
const WARM = P.amber, SOFT = P.glow, COOL = mix(P.indigo, P.glow, 0.55);

const stone = mix(P.glow, P.plum, 0.28), stoneD = mix(P.glow, P.plum, 0.55), stoneL = mix(P.glow, P.plum, 0.1);
const slab = mix(P.plum, P.glow, 0.32), slabD = mix(P.plum, P.ink, 0.35);
const zinc = mix(P.indigo, P.glow, 0.42), zincD = mix(P.indigo, P.glow, 0.22);
const shaftC = mix(P.ink, P.night, 0.6), stairC = mix(P.plum, P.glow, 0.26);
const wood = mix(P.rust, P.amber, 0.25), woodD = mix(P.rust, P.ink, 0.35), walnut = mix(P.rust, P.plum, 0.5);
const leather = mix(P.rust, P.plum, 0.25), metal = mix(P.indigo, P.glow, 0.32);
const leaf = mix(P.sage, P.glow, 0.18), leafD = mix(P.sage, P.ink, 0.3);
const screenC = mix(P.night, P.indigo, 0.5);

// ── Reusable props ───────────────────────────────────────────────────────────
function plant(c: Ctx, x: number, f: number, tall = false): void {
  px(c, x - 3, f - 5, 7, 5, P.rust); px(c, x - 4, f - 6, 9, 1, mix(P.rust, P.glow, 0.3));
  const h = tall ? 22 : 11;
  px(c, x, f - 6 - h, 1, h, leafD);
  for (let i = 0; i < (tall ? 6 : 3); i++) {
    const y = f - 9 - i * 4, w = (tall ? 5 : 4) - (i >> 1);
    px(c, x - w, y, w, 2, i % 2 ? leaf : P.sage); px(c, x + 1, y - 2, w, 2, i % 2 ? P.sage : leaf);
    px(c, x - w - 1, y + 1, 1, 1, leafD); px(c, x + w + 1, y - 1, 1, 1, leafD);
  }
}
function floorLamp(c: Ctx, x: number, f: number, lights: Light[], level: number): void {
  px(c, x, f - 27, 1, 27, P.ink); px(c, x - 2, f - 1, 5, 1, P.ink);
  px(c, x - 3, f - 32, 7, 5, P.glow); px(c, x - 4, f - 28, 9, 1, P.amber); px(c, x - 2, f - 33, 5, 1, P.amber);
  lights.push({ x, y: f - 27, r: 40, color: WARM, base: 0.8, level });
}
function pendant(c: Ctx, x: number, top: number, drop: number, lights: Light[], level: number, base = 0.35): void {
  px(c, x, top, 1, drop, P.ink); px(c, x - 3, top + drop, 7, 2, mix(P.amber, P.rust, 0.4)); px(c, x - 2, top + drop + 2, 5, 1, P.glow);
  lights.push({ x, y: top + drop + 4, r: 46, color: WARM, base, level });
}
function picture(c: Ctx, x: number, y: number, w: number, h: number, a: string, b: string): void {
  px(c, x, y, w, h, woodD); px(c, x + 1, y + 1, w - 2, h - 2, a);
  px(c, x + 1, y + h - 4, w - 2, 3, b); px(c, x + w - 5, y + 2, 2, 2, P.glow);
}
function bookshelf(c: Ctx, x: number, f: number, w: number, h: number, seed: number): void {
  const random = seeded(seed), tones = [P.rust, P.sage, P.indigo, P.amber, P.plum, mix(P.glow, P.plum, 0.3), mix(P.indigo, P.glow, 0.4)];
  px(c, x, f - h, w, h, woodD); px(c, x + 1, f - h + 1, w - 2, h - 1, mix(P.plum, P.ink, 0.3));
  for (let y = f - h + 2; y < f - 6; y += 10) {
    for (let bx = x + 2; bx < x + w - 3;) {
      const bw = 1 + Math.floor(random() * 2), bh = 5 + Math.floor(random() * 3);
      if (random() < 0.86) px(c, bx, y + 8 - bh, bw, bh, tones[Math.floor(random() * tones.length)]);
      bx += bw + (random() < 0.2 ? 2 : 0);
    }
    px(c, x + 1, y + 8, w - 2, 1, wood);
  }
}
function officeChair(c: Ctx, x: number, f: number, color: string): void {
  px(c, x - 6, f - 18, 2, 12, color); px(c, x - 5, f - 19, 2, 1, color); px(c, x - 5, f - 7, 9, 2, color);
  px(c, x, f - 5, 1, 4, P.ink); px(c, x - 3, f - 1, 7, 1, P.ink);
}
function monitor(c: Ctx, x: number, y: number, w: number, h: number, seed: number, tint: string = P.amber): void {
  px(c, x, y, w, h, P.ink); px(c, x + 1, y + 1, w - 2, h - 2, screenC);
  const random = seeded(seed); let v = h / 2;
  for (let i = 2; i < w - 2; i++) { v = Math.max(2, Math.min(h - 3, v + (random() - 0.5) * 3)); px(c, x + i, y + Math.round(v), 1, 1, tint); }
  px(c, x + 2, y + 2, 4, 1, mix(P.indigo, P.glow, 0.5));
  px(c, x + (w >> 1) - 1, y + h, 2, 2, P.ink); px(c, x + (w >> 1) - 3, y + h + 2, 6, 1, P.ink);
}
function sign(c: Ctx, level: number): void {
  const label = `${floorLabel(level)} ${LEVELS[level].sign}`, y = level * FLOOR_H + SLAB + 5, w = textWidth(label) + 8;
  px(c, 73, y, w, 11, P.ink); px(c, 74, y + 1, w - 2, 9, mix(P.plum, P.ink, 0.4)); px(c, 74, y + 9, w - 2, 1, P.amber);
  text(c, label, 77, y + 3, P.glow);
}
function roomShell(c: Ctx, level: number, wall: string, floorA: string, floorB: string, pattern: number): void {
  const top = level * FLOOR_H, f = footY(level);
  px(c, 64, top + SLAB, 512, FLOOR_H - SLAB, wall);
  px(c, 64, top + SLAB, 512, 2, mix(wall, P.glow, 0.35)); px(c, 64, top + SLAB + 2, 512, 1, mix(wall, P.ink, 0.3));
  px(c, 64, f - 3, 512, 3, mix(wall, P.ink, 0.35));
  px(c, 64, f, 524, 3, floorA);
  for (let x = 64; x < 588; x += pattern) px(c, x, f + ((x / pattern) & 1), Math.max(1, pattern >> 1), 1, floorB);
  px(c, 64, f, 524, 1, mix(floorA, P.glow, 0.25));
}

// ── Roof terrace ─────────────────────────────────────────────────────────────
function deckchair(c: Ctx, x: number, f: number): void {
  const cloth = P.glow, stripe = mix(P.rust, P.amber, 0.35);
  for (let i = 0; i < 3; i++) { px(c, x - 13 + i, f - 23 + i * 5, 4, 5, cloth); px(c, x - 13 + i, f - 21 + i * 5, 4, 1, stripe); px(c, x - 14 + i, f - 23 + i * 5, 1, 5, woodD); }
  px(c, x - 9, f - 8, 22, 3, cloth); for (let i = 0; i < 5; i++) px(c, x - 7 + i * 4, f - 8, 2, 3, stripe);
  px(c, x - 10, f - 13, 11, 1, wood); px(c, x - 1, f - 13, 1, 5, wood);
  px(c, x - 8, f - 5, 1, 5, woodD); px(c, x + 10, f - 5, 1, 5, woodD); px(c, x - 9, f - 5, 21, 1, woodD);
}
function shrubBox(c: Ctx, x: number, f: number, w: number): void {
  px(c, x, f - 9, w, 9, woodD); px(c, x, f - 9, w, 1, wood); px(c, x, f - 5, w, 1, mix(woodD, P.ink, 0.3));
  for (let i = 0; i * 4 < w - 2; i++) {
    const h = 6 + (i * 7) % 5;
    px(c, x + 1 + i * 4, f - 9 - h, 3, h, i % 2 ? leaf : P.sage); px(c, x + 2 + i * 4, f - 10 - h, 1, 1, leaf);
    if (i % 3 === 1) px(c, x + 2 + i * 4, f - 11 - h, 1, 2, mix(P.plum, P.glow, 0.55));
  }
}
function roof(c: Ctx, lights: Light[]): void {
  const f = footY(0), warmStone = mix(stone, P.amber, 0.12);
  // Low stone parapet with a zinc cap at the back, deck boards in front.
  px(c, 68, f - 11, 504, 11, warmStone); px(c, 68, f - 13, 504, 2, zinc); px(c, 68, f - 11, 504, 1, zincD);
  for (let x = 82; x < 572; x += 36) px(c, x, f - 10, 2, 10, stoneD);
  px(c, 64, f, 512, 3, wood); for (let x = 64; x < 576; x += 9) px(c, x, f, 1, 3, woodD); px(c, 64, f, 512, 1, mix(wood, P.glow, 0.35));
  // Bistro table with two chairs by the lift door.
  px(c, 125, f - 12, 14, 2, zinc); px(c, 131, f - 10, 2, 9, P.ink); px(c, 127, f - 1, 10, 1, P.ink);
  px(c, 128, f - 16, 3, 4, P.glow); px(c, 129, f - 17, 1, 1, P.amber); px(c, 134, f - 14, 3, 2, P.rust);
  lights.push({ x: 129, y: f - 15, r: 20, color: WARM, base: 1, level: 0, flicker: true });
  for (const [x, d] of [[118, -1], [146, 1]] as const) { px(c, x - 4, f - 8, 9, 2, mix(P.sage, P.glow, 0.2)); px(c, x + d * 4, f - 19, 1, 12, P.ink); px(c, x + d * 4 - (d > 0 ? 2 : 0), f - 19, 3, 1, P.ink); px(c, x - 4, f - 6, 1, 6, P.ink); px(c, x + 4, f - 6, 1, 6, P.ink); }
  // Olive tree in a terracotta pot.
  px(c, 162, f - 11, 13, 11, P.rust); px(c, 161, f - 12, 15, 2, mix(P.rust, P.glow, 0.35)); px(c, 163, f - 4, 11, 1, mix(P.rust, P.ink, 0.3)); px(c, 168, f - 30, 2, 18, woodD); px(c, 166, f - 24, 2, 1, woodD);
  for (const [dx, dy, w, h] of [[-10, -47, 22, 9], [-14, -41, 30, 9], [-10, -34, 21, 6], [-5, -51, 13, 5]]) px(c, 169 + dx, f + dy, w, h, P.sage);
  for (const [dx, dy] of [[-7, -45], [3, -48], [9, -39], [-12, -37], [0, -35], [6, -44], [-3, -40], [11, -33]]) px(c, 169 + dx, f + dy, 3, 2, leaf);
  for (const [dx, dy] of [[-9, -40], [4, -42], [-1, -47], [8, -36]]) px(c, 169 + dx, f + dy, 2, 1, leafD);
  // Pergola lounge: timber frame, hanging lanterns, striped deckchairs, rug.
  px(c, 196, f, 114, 1, P.amber); for (let x = 198; x < 308; x += 6) px(c, x, f + 1, 3, 1, P.rust);
  px(c, 192, 38, 2, f - 38, woodD); px(c, 314, 24, 2, f - 24, woodD); px(c, 188, 38, 130, 3, wood); px(c, 188, 41, 130, 1, woodD);
  for (let x = 196; x < 314; x += 12) px(c, x, 36, 2, 2, woodD);
  for (const x of [222, 254, 286]) { px(c, x, 42, 1, 7, P.ink); px(c, x - 2, 49, 5, 6, P.ink); px(c, x - 1, 50, 3, 4, P.glow); px(c, x, 51, 1, 2, P.amber); lights.push({ x, y: 52, r: 34, color: WARM, base: 1, level: 0, flicker: true }); }
  for (let i = 0; i < 9; i++) { px(c, 194 + i * 3, 42 + (i % 3), 2, 3 + (i * 5) % 4, i % 2 ? leaf : P.sage); px(c, 300 + i * 2, 42, 1, 2 + (i * 3) % 5, leaf); }
  deckchair(c, 222, f); deckchair(c, 284, f);
  px(c, 249, f - 9, 10, 1, wood); px(c, 253, f - 8, 2, 8, woodD); px(c, 251, f - 13, 2, 4, P.glow); px(c, 255, f - 12, 3, 3, P.sage);
  // Planters, putting green with flag and ball, spare putter, telescope aimed at the tower.
  shrubBox(c, 328, f, 32); shrubBox(c, 548, f, 22);
  px(c, 368, f - 2, 124, 2, mix(P.sage, P.glow, 0.3)); px(c, 368, f - 2, 124, 1, mix(P.sage, P.glow, 0.5)); for (let x = 372; x < 490; x += 7) px(c, x, f - 1, 3, 1, P.sage);
  px(c, 366, f - 3, 2, 3, woodD); px(c, 492, f - 3, 2, 3, woodD);
  px(c, 470, f - 2, 4, 1, P.ink); px(c, 472, f - 20, 1, 18, P.glow); px(c, 473, f - 20, 7, 5, P.amber); px(c, 473, f - 18, 5, 1, P.rust);
  px(c, 420, f - 4, 2, 2, P.glow);
  px(c, 498, f - 17, 1, 17, zinc); px(c, 497, f - 1, 4, 1, zinc); px(c, 496, f - 18, 3, 1, P.rust);
  px(c, 512, f - 14, 1, 14, P.ink); px(c, 508, f - 7, 1, 7, P.ink); px(c, 516, f - 7, 1, 7, P.ink);
  px(c, 505, f - 19, 14, 4, mix(P.rust, P.amber, 0.45)); px(c, 518, f - 20, 4, 6, P.amber); px(c, 503, f - 18, 2, 2, P.ink); px(c, 505, f - 19, 14, 1, P.glow);
  // String lights from the lift house to the pergola mast and on to the stair house.
  const run = (x0: number, y0: number, x1: number, y1: number, sag: number) => {
    for (let x = x0; x <= x1; x++) {
      const t = (x - x0) / (x1 - x0), y = Math.round(y0 + (y1 - y0) * t + Math.sin(t * Math.PI) * sag);
      px(c, x, y, 1, 1, P.ink);
      if ((x - x0) % 13 === 6) { px(c, x - 1, y + 1, 3, 3, P.glow); px(c, x, y + 1, 1, 1, P.amber); lights.push({ x, y: y + 2, r: 13, color: WARM, base: 1, level: 0, flicker: true }); }
    }
  };
  run(68, 36, 314, 24, 10); run(316, 24, 572, 36, 16);
}
const top0 = (level: number): number => level * FLOOR_H;

// ── Head of Desk ─────────────────────────────────────────────────────────────
function headOfDesk(c: Ctx, lights: Light[]): void {
  const L = 1, top = top0(L), f = footY(L), wall = mix(mix(P.sage, P.plum, 0.34), P.glow, 0.14);
  roomShell(c, L, wall, wood, woodD, 6);
  // Walnut wainscot under a dark green wall.
  px(c, 64, f - 34, 512, 31, walnut); px(c, 64, f - 35, 512, 1, mix(walnut, P.glow, 0.3));
  for (let x = 70; x < 572; x += 14) px(c, x, f - 32, 1, 27, mix(walnut, P.ink, 0.3));
  // Panoramic window: transparent panes, slim dark frames.
  c.clearRect(250, top + 20, 312, 54);
  c.fillStyle = "rgba(32,47,100,.16)"; c.fillRect(250, top + 20, 312, 54);
  px(c, 248, top + 18, 316, 2, P.ink); px(c, 248, top + 74, 316, 3, woodD); px(c, 248, top + 77, 316, 1, mix(walnut, P.glow, 0.35));
  for (let x = 248; x <= 562; x += 63) px(c, x, top + 18, 2, 58, P.ink);
  c.fillStyle = "rgba(249,228,185,.10)"; for (let x = 262; x < 560; x += 63) { c.fillRect(x, top + 22, 3, 50); c.fillRect(x + 6, top + 22, 1, 50); }
  // Glass partition with an open doorway between the waiting area and the office.
  c.fillStyle = "rgba(249,228,185,.13)"; c.fillRect(170, top + SLAB + 3, 14, FLOOR_H - SLAB - 6);
  px(c, 169, top + SLAB + 3, 1, 78, metal); px(c, 184, top + SLAB + 3, 1, 78, metal); px(c, 169, top + SLAB + 3, 16, 1, metal); px(c, 170, f - 34, 14, 1, metal);
  c.fillStyle = "rgba(249,228,185,.22)"; for (let i = 0; i < 9; i++) c.fillRect(172 + i, top + 30 + i * 2, 1, 6);
  px(c, 181, f - 18, 1, 5, P.amber);
  // Waiting area: bench, sconce, picture, plant.
  px(c, 84, f - 8, 46, 4, leather); px(c, 84, f - 9, 46, 1, mix(leather, P.glow, 0.3)); px(c, 86, f - 4, 2, 4, P.ink); px(c, 126, f - 4, 2, 4, P.ink);
  picture(c, 92, top + 34, 26, 18, mix(P.indigo, P.glow, 0.3), P.sage);
  px(c, 140, top + 36, 4, 6, P.amber); px(c, 141, top + 42, 2, 2, P.ink); lights.push({ x: 142, y: top + 40, r: 34, color: WARM, base: 0.75, level: L });
  plant(c, 160, f, true);
  sign(c, L);
  // Office: bookshelf, monstera, executive desk, leather armchair.
  bookshelf(c, 186, f, 50, 62, 7);
  plant(c, 244, f, true);
  px(c, 352, f, 150, 2, mix(P.plum, P.amber, 0.3)); px(c, 356, f + 1, 142, 1, P.amber);
  px(c, 362, f - 22, 3, 16, leather); px(c, 361, f - 23, 5, 2, mix(leather, P.glow, 0.2)); px(c, 363, f - 8, 12, 3, leather); px(c, 368, f - 5, 1, 4, P.ink); px(c, 365, f - 1, 8, 1, P.ink);
  px(c, 380, f - 14, 92, 2, mix(walnut, P.amber, 0.35)); px(c, 382, f - 12, 88, 12, walnut);
  px(c, 384, f - 10, 26, 9, mix(walnut, P.ink, 0.25)); px(c, 442, f - 10, 26, 9, mix(walnut, P.ink, 0.25));
  px(c, 395, f - 6, 4, 1, P.amber); px(c, 453, f - 6, 4, 1, P.amber); px(c, 412, f - 12, 28, 12, mix(walnut, P.ink, 0.5));
  // Banker's lamp, twin monitors, papers and a mug.
  px(c, 388, f - 16, 5, 1, P.amber); px(c, 390, f - 20, 1, 4, P.amber); px(c, 386, f - 23, 9, 3, P.sage); px(c, 387, f - 20, 7, 1, P.glow);
  lights.push({ x: 390, y: f - 18, r: 38, color: WARM, base: 0.9, level: L });
  monitor(c, 402, f - 32, 22, 15, 3); monitor(c, 428, f - 32, 22, 15, 4, mix(P.sage, P.glow, 0.4));
  lights.push({ x: 424, y: f - 24, r: 30, color: COOL, base: 0.3, level: L });
  px(c, 454, f - 15, 9, 1, P.glow); px(c, 456, f - 16, 8, 1, mix(P.glow, P.plum, 0.2)); px(c, 466, f - 18, 3, 4, P.rust);
  // Lounge: sofa, low table, floor lamp.
  px(c, 498, f - 18, 52, 10, leather); px(c, 498, f - 19, 52, 1, mix(leather, P.glow, 0.25)); px(c, 496, f - 12, 4, 10, leather); px(c, 548, f - 12, 4, 10, leather);
  px(c, 500, f - 9, 48, 6, mix(leather, P.glow, 0.12)); px(c, 524, f - 9, 1, 6, mix(leather, P.ink, 0.3)); px(c, 498, f - 3, 2, 3, P.ink); px(c, 548, f - 3, 2, 3, P.ink);
  px(c, 506, f - 14, 8, 5, P.amber); px(c, 536, f - 13, 7, 4, P.sage);
  floorLamp(c, 562, f, lights, L);
  pendant(c, 300, top + SLAB, 8, lights, L, 0.3); pendant(c, 470, top + SLAB, 8, lights, L, 0.3);
}

// ── Global Markets ───────────────────────────────────────────────────────────
export const WALL_SCREENS = [100, 186, 272, 358].map((x, i) => ({ x, y: top0(2) + 33, w: 78, h: 24, seed: i + 1 }));
export const TICKER = { x: 150, y: top0(2) + 20, w: 414 };
const DESKS = [98, 218, 338, 458];
function globalMarkets(c: Ctx, lights: Light[]): void {
  const L = 2, top = top0(L), f = footY(L), wall = mix(P.indigo, P.plum, 0.3);
  roomShell(c, L, wall, mix(P.night, P.indigo, 0.6), mix(P.indigo, P.glow, 0.18), 5);
  px(c, 64, f - 22, 512, 19, mix(wall, P.ink, 0.25));
  // LED ticker rail and the wall of market screens (their content is drawn live).
  px(c, TICKER.x - 2, TICKER.y - 2, TICKER.w + 4, 9, P.ink); px(c, TICKER.x - 2, TICKER.y + 7, TICKER.w + 4, 1, metal);
  for (const s of WALL_SCREENS) { px(c, s.x - 2, s.y - 2, s.w + 4, s.h + 4, P.ink); px(c, s.x, s.y, s.w, s.h, screenC); px(c, s.x + 34, s.y + s.h + 2, 10, 2, P.ink); lights.push({ x: s.x + 39, y: s.y + 12, r: 44, color: COOL, base: 0.3, level: L }); }
  // World clocks.
  ["PAR", "LDN", "NYC", "TKY"].forEach((city, i) => {
    const x = 452 + i * 29, y = top + 34;
    px(c, x + 2, y, 9, 13, P.glow); px(c, x, y + 2, 13, 9, P.glow); px(c, x + 1, y + 1, 11, 11, P.glow);
    px(c, x + 6, y + 3, 1, 4, P.ink); px(c, x + 6, y + 6, 3 - (i % 2) * 5 + (i % 2) * 2, 1, P.ink); px(c, x + 6, y + 6, 1, 1, P.rust);
    text(c, city, x + 1, y + 16, mix(P.glow, P.indigo, 0.3));
  });
  sign(c, L);
  // Trading desks: three screens in an arc, a fourth stacked, turret phone and keyboard.
  DESKS.forEach((x, i) => {
    officeChair(c, x - 8, f, i === 1 ? mix(P.indigo, P.glow, 0.3) : mix(P.plum, P.ink, 0.2));
    px(c, x, f - 14, 88, 2, metal); px(c, x + 2, f - 12, 84, 9, mix(P.plum, P.ink, 0.35)); px(c, x + 4, f - 3, 2, 3, P.ink); px(c, x + 82, f - 3, 2, 3, P.ink);
    px(c, x + 34, f - 9, 20, 4, mix(P.plum, P.ink, 0.6));
    monitor(c, x + 12, f - 32, 22, 15, 20 + i * 4); monitor(c, x + 36, f - 32, 22, 15, 21 + i * 4, mix(P.sage, P.glow, 0.45)); monitor(c, x + 60, f - 32, 22, 15, 22 + i * 4);
    px(c, x + 84, f - 16, 3, 2, P.ink); px(c, x + 85, f - 21, 1, 5, P.ink); px(c, x + 82, f - 24, 6, 3, P.amber); px(c, x + 83, f - 21, 4, 1, P.glow);
    lights.push({ x: x + 85, y: f - 20, r: 24, color: WARM, base: 0.85, level: L });
    px(c, x + 3, f - 15, 8, 1, mix(P.glow, P.indigo, 0.4)); px(c, x + 3, f - 16, 2, 1, P.ink);
    lights.push({ x: x + 46, y: f - 28, r: 40, color: COOL, base: i === 1 ? 0.5 : 0.25, level: L });
  });
  // Coffee corner by the stairs.
  px(c, 548, f - 20, 14, 20, mix(P.plum, P.ink, 0.3)); px(c, 550, f - 18, 10, 6, P.ink); px(c, 552, f - 16, 2, 2, P.amber); px(c, 553, f - 10, 4, 4, P.glow);
  plant(c, 80, f); px(c, 302, top + SLAB + 3, 0, 0, P.ink);
  for (const x of [150, 280, 410, 540]) { px(c, x - 14, top + SLAB + 3, 28, 2, P.glow); px(c, x - 15, top + SLAB + 2, 30, 1, metal); lights.push({ x, y: top + SLAB + 8, r: 50, color: SOFT, base: 0.12, level: L }); }
}

// ── Floors still to be fitted out ────────────────────────────────────────────
function shellFloor(c: Ctx, L: number, lights: Light[]): void {
  const level = LEVELS[L], top = top0(L), f = footY(L), wall = mix(mix(level.accent, P.plum, 0.5), P.glow, 0.22), random = seeded(L * 31);
  roomShell(c, L, wall, mix(slab, P.glow, 0.1), slabD, 8);
  sign(c, L);
  level.agents.forEach((id, i) => {
    const x = SEATS[id].x;
    px(c, x - 6, f - 7, 9, 2, woodD); px(c, x - 5, f - 5, 1, 5, woodD); px(c, x + 1, f - 5, 1, 5, woodD);
    px(c, x + 8, f - 13, 34, 2, wood); px(c, x + 10, f - 11, 2, 11, woodD); px(c, x + 38, f - 11, 2, 11, woodD);
    px(c, x + 12, f - 22, 14, 9, P.ink); px(c, x + 13, f - 21, 12, 7, screenC); px(c, x + 15, f - 19, 6, 1, P.amber); px(c, x + 12, f - 14, 16, 1, metal);
    lights.push({ x: x + 19, y: f - 18, r: 30, color: COOL, base: 0.2, level: L });
    if (i % 2 === 0) { px(c, x + 30, f - 18, 4, 5, P.rust); px(c, x + 31, f - 22, 2, 4, leaf); }
  });
  // Dust sheets, boxes and a ladder until the floor gets its own identity.
  for (let i = 0; i < 4; i++) {
    const x = 470 - i * 4 + Math.floor(random() * 60), w = 9 + Math.floor(random() * 6), h = 7 + Math.floor(random() * 5);
    px(c, x, f - h - (i > 1 ? 9 : 0), w, h, mix(P.rust, P.glow, 0.35)); px(c, x, f - h - (i > 1 ? 9 : 0) + 2, w, 1, mix(P.rust, P.ink, 0.2));
  }
  px(c, 552, f - 40, 1, 40, woodD); px(c, 560, f - 40, 1, 40, woodD); for (let y = f - 36; y < f; y += 6) px(c, 552, y, 9, 1, woodD);
  pendant(c, 320, top + SLAB, 14, lights, L, 0.3);
}

// ── Structure: slabs, shaft, stairs, façade ──────────────────────────────────
function structure(c: Ctx, lights: Light[]): void {
  // Lift shaft, from the roof house down to the ground.
  px(c, SHAFT_X, 34, 40, WORLD_H - 34, shaftC);
  px(c, 27, 34, 1, WORLD_H - 34, mix(shaftC, P.glow, 0.2)); px(c, 60, 34, 1, WORLD_H - 34, mix(shaftC, P.glow, 0.2));
  for (let L = 1; L < LEVELS.length; L++) {
    const top = top0(L), f = footY(L);
    px(c, SHAFT_X, top, 40, SLAB, slabD); px(c, SHAFT_X, top + SLAB - 1, 40, 1, P.ink);
    const label = floorLabel(L); for (let y = top + 22; y < top + FLOOR_H; y += 22) px(c, 28, y, 32, 1, mix(shaftC, P.glow, 0.1));
    text(c, label, CAR_X - (textWidth(label) >> 1), top + 28, mix(shaftC, P.glow, 0.6));
    // Stairwell: back wall, two flights, half landing and the floor landing.
    px(c, STAIR_X, top - 3, 40, FLOOR_H, stairC); for (let y = top + 2; y < top + FLOOR_H - 6; y += 12) px(c, STAIR_X, y, 40, 1, mix(stairC, P.ink, 0.12));
    // Far flight first (darker), then the near flight with its handrail.
    for (let i = 0; i < 12; i++) { px(c, 606 - i * 2, f - 48 - (i + 1) * 4, 4, 9, mix(stairC, P.ink, 0.5)); px(c, 606 - i * 2, f - 48 - (i + 1) * 4, 4, 1, stoneD); }
    for (let i = 0; i < 12; i++) { px(c, 588 + i * 2, f - (i + 1) * 4, 4, 10, mix(stairC, P.ink, 0.3)); px(c, 588 + i * 2, f - (i + 1) * 4, 4, 1, stoneL); }
    px(c, 610, f - 48, 6, 4, mix(stairC, P.ink, 0.3)); px(c, 610, f - 48, 6, 1, stoneL);
    for (let i = 0; i < 24; i++) px(c, 589 + i, f - 10 - i * 2, 1, 2, P.ink);
    px(c, 588, f - 10, 1, 10, P.ink);
    px(c, 600, top + 26, 4, 5, P.glow); px(c, 600, top + 25, 4, 1, P.ink); lights.push({ x: 602, y: top + 29, r: 26, color: WARM, base: 0.6, level: L });
    // Slab in section, with hatching, stopping at the stair opening.
    px(c, 64, top, 524, SLAB, slab); px(c, 64, top, 524, 1, mix(slab, P.glow, 0.3)); px(c, 64, top + SLAB - 1, 524, 1, slabD);
    for (let x = 68; x < 586; x += 7) { px(c, x, top + 4, 2, 1, slabD); px(c, x + 2, top + 6, 2, 1, slabD); }
    // Party walls with a doorway on each side.
    px(c, 60, f, 8, 3, metal); px(c, 65, f - 38, 2, 3, P.amber); lights.push({ x: 66, y: f - 36, r: 12, color: WARM, base: 0.9, level: L });
    for (const x of [64, 572]) { px(c, x, top + SLAB, 4, FLOOR_H - SLAB - 3 - 30, stoneD); px(c, x + 1, top + SLAB, 2, FLOOR_H - SLAB - 3 - 30, stone); px(c, x - 1, f - 31, 6, 2, woodD); }
  }
  // Roof houses for the lift and the stairs.
  const f0 = footY(0);
  for (const [x, w] of [[SHAFT_X, 44], [572, 44]] as const) {
    px(c, x - 2, 30, w + 4, 2, zincD); px(c, x - 1, 32, w + 2, 4, zinc); px(c, x, 36, w, 8, stone); px(c, x, 43, w, 1, stoneD); px(c, x + (w >> 1) - 3, 37, 6, 5, P.ink); px(c, x + (w >> 1) - 2, 38, 4, 3, P.amber);
  }
  px(c, SHAFT_X, 44, 4, f0 - 44 + 3, stone); px(c, 60, 44, 4, f0 - 44 + 3, stone); px(c, 64, 44, 4, f0 - 44 - 30, stone); px(c, 63, f0 - 31, 6, 2, woodD);
  px(c, STAIR_X, 44, 40, f0 - 44 + 3, stairC); px(c, 612, 44, 4, f0 - 44 + 3, stone); px(c, 572, 44, 4, f0 - 44 - 30, stone); px(c, 571, f0 - 31, 6, 2, woodD);
  px(c, STAIR_X, f0, 12, 3, wood);
  for (const x of [72, 566]) { px(c, x, 54, 3, 5, P.amber); px(c, x, 53, 3, 1, P.ink); lights.push({ x: x + 1, y: 57, r: 30, color: WARM, base: 1, level: 0 }); }
  px(c, CAR_X, 34, 1, 10, P.ink);

  // Haussmann façade returns: dressed stone, cornices, tall windows with ironwork.
  for (const x0 of [0, BW - FACADE]) {
    const left = x0 === 0, random = seeded(left ? 3 : 9);
    for (let L = 1; L < LEVELS.length; L++) {
      const top = top0(L);
      px(c, x0, top, FACADE, FLOOR_H, stone);
      for (let k = 0; k < 11; k++) { px(c, x0, top + 14 + k * 8, FACADE, 1, stoneD); px(c, x0 + (k % 2 ? 7 : 16), top + 14 + k * 8, 1, 8, stoneD); }
      px(c, x0, top, FACADE, 3, stoneL); px(c, x0, top + 3, FACADE, 2, stoneD); px(c, x0, top + 5, FACADE, 2, stone); px(c, x0, top + 7, FACADE, 1, stoneD);
      const wx = left ? x0 + 4 : x0 + 9;
      px(c, wx - 1, top + 30, 13, 44, stoneL); px(c, wx, top + 32, 11, 42, mix(P.amber, P.plum, 0.45)); px(c, wx, top + 32, 11, 6, mix(P.amber, P.glow, 0.3));
      px(c, wx + 5, top + 32, 1, 42, P.ink); px(c, wx, top + 46, 11, 1, P.ink); px(c, wx - 2, top + 74, 15, 2, stoneL);
      px(c, wx - 1, top + 64, 13, 1, P.ink); for (let i = 0; i < 13; i += 2) px(c, wx - 1 + i, top + 65, 1, 9, P.ink);
      lights.push({ x: wx + 5, y: top + 50, r: 30, color: WARM, base: 0.7, level: L });
      // The cut edge of the removed front wall.
      for (let y = top + 9; y < top + FLOOR_H; y += 5) if (random() < 0.6) px(c, left ? x0 + FACADE - 2 : x0, y, 2, 3, left ? shaftC : stairC);
    }
    // Zinc mansard, dormer and chimney at roof level.
    for (let i = 0; i < 10; i++) px(c, left ? x0 + 10 - i : x0, 46 + i, 14 + i, 1, zinc);
    px(c, x0, 56, FACADE, 34, zinc); for (let x = x0 + 3; x < x0 + FACADE; x += 6) px(c, x, 56, 1, 34, zincD);
    px(c, x0, 90, FACADE, 3, stoneL); px(c, x0, 93, FACADE, 3, stoneD);
    const dx = left ? x0 + 5 : x0 + 9;
    px(c, dx - 1, 62, 11, 16, stone); px(c, dx, 60, 9, 2, zincD); px(c, dx + 1, 65, 7, 11, P.amber); px(c, dx + 4, 65, 1, 11, P.ink);
    lights.push({ x: dx + 4, y: 70, r: 24, color: WARM, base: 1, level: 0 });
    const chimneyX = left ? x0 + 13 : x0 + 2;
    px(c, chimneyX, 30, 9, 18, mix(P.rust, P.plum, 0.3)); px(c, chimneyX - 1, 29, 11, 2, stoneD);
    for (let i = 0; i < 3; i++) px(c, chimneyX + 1 + i * 3, 24, 2, 5, P.rust);
  }
  // Pavement and street.
  px(c, 0, WORLD_H, BW, 3, stoneL); px(c, 0, WORLD_H + 3, BW, GROUND - 3, mix(P.plum, P.ink, 0.45));
  for (let x = 6; x < BW; x += 22) px(c, x, WORLD_H + 1, 1, 2, stoneD);
}

export function bakeBuilding(): { canvas: HTMLCanvasElement; lights: Light[] } {
  const [canvas, c] = makeCanvas(BW, WORLD_H + GROUND), lights: Light[] = [];
  headOfDesk(c, lights); globalMarkets(c, lights);
  LEVELS.forEach((level, index) => { if (!level.built) shellFloor(c, index, lights); });
  structure(c, lights);
  roof(c, lights);
  return { canvas, lights };
}

// Moving content of the screens. `power` is the floor's activity between 0 and 1.
export function drawScreens(c: Ctx, time: number, power: number): void {
  // Ticker: pixel text scrolling to the left.
  const tape = "CAC 40 +0.4%   EUR/USD 1.12   OAT 10A 3.21%   BRENT 81.7   S&P 500 +0.2%   BUND 2.48%   DAX -0.1%   ";
  const offset = Math.floor(time * 14) % (tape.length * 4);
  c.save(); c.beginPath(); c.rect(TICKER.x, TICKER.y, TICKER.w, 5); c.clip();
  for (let x = -offset; x < TICKER.w; x += tape.length * 4) text(c, tape, TICKER.x + x, TICKER.y, power > 0.5 ? P.amber : mix(P.amber, P.ink, 0.45));
  c.restore();
  for (const s of WALL_SCREENS) {
    const speed = 2 + power * 7, up = mix(P.sage, P.glow, 0.5), tint = s.seed % 2 ? P.amber : up;
    c.fillStyle = mix(P.indigo, P.glow, 0.15); for (let gy = 7; gy < s.h; gy += 8) for (let gx = 2; gx < s.w; gx += 3) c.fillRect(s.x + gx, s.y + gy, 1, 1);
    let last = -1;
    for (let i = 0; i < s.w - 2; i++) {
      const u = i + time * speed, v = Math.sin(u * 0.19 + s.seed * 2) * 0.3 + Math.sin(u * 0.07 + s.seed) * 0.28 + Math.sin(u * 0.53) * 0.08;
      const y = Math.round(s.h / 2 + v * s.h * 0.62);
      c.fillStyle = tint; c.fillRect(s.x + 1 + i, s.y + Math.max(1, Math.min(s.h - 2, y)), 1, last < 0 ? 1 : Math.max(1, Math.abs(y - last)));
      last = y;
    }
    text(c, ["CAC", "FX", "TAUX", "VOL"][s.seed - 1], s.x + 3, s.y + 3, P.glow);
  }
}

// Lift car. `foot` is its floor line, `door` goes from 0 (closed) to 1 (open).
export function drawCar(c: Ctx, foot: number, door: number, passenger: (() => void) | null): void {
  const x = 28, top = foot - 42;
  px(c, CAR_X, 34, 1, Math.max(0, top - 34), mix(shaftC, P.glow, 0.35));
  px(c, x, top, 32, 42, mix(walnut, P.amber, 0.2)); px(c, x + 2, top + 12, 28, 1, mix(walnut, P.ink, 0.3)); px(c, x + 12, top + 6, 8, 20, mix(P.indigo, P.glow, 0.45));
  px(c, x, top, 32, 3, metal); px(c, x + 8, top + 3, 16, 1, P.glow); px(c, x, foot, 32, 3, metal);
  passenger?.();
  const leaf = Math.round(15 * (1 - door));
  c.fillStyle = "rgba(249,228,185,.2)"; c.fillRect(x + 1, top + 3, leaf, 39); c.fillRect(x + 31 - leaf, top + 3, leaf, 39);
  if (leaf > 0) { px(c, x + leaf, top + 3, 1, 39, metal); px(c, x + 31 - leaf, top + 3, 1, 39, metal); }
  px(c, x, top, 1, 45, metal); px(c, x + 31, top, 1, 45, metal);
}
