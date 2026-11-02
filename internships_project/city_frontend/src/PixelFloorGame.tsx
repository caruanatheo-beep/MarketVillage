import React, { useEffect, useRef, useState } from "react";
import { buildDynamicCatalog, getCatalogEntry, type LoadedAssetData } from "../vendor/pixel-agents/webview-ui/src/office/layout/furnitureCatalog";
import { flattenManifest, type FurnitureManifest, type InheritedProps, type ManifestNode } from "../vendor/pixel-agents/core/src/manifestUtils";
import { setFloorSprites } from "../vendor/pixel-agents/webview-ui/src/office/floorTiles";
import { setWallSprites } from "../vendor/pixel-agents/webview-ui/src/office/wallTiles";
import { setCharacterTemplates } from "../vendor/pixel-agents/webview-ui/src/office/sprites/spriteData";
import { OfficeState } from "../vendor/pixel-agents/webview-ui/src/office/engine/officeState";
import { startGameLoop } from "../vendor/pixel-agents/webview-ui/src/office/engine/gameLoop";
import { renderFrame, renderTileGrid, type SelectionRenderState } from "../vendor/pixel-agents/webview-ui/src/office/engine/renderer";
import { Direction, TILE_SIZE, TileType, type OfficeLayout, type SpriteData } from "../vendor/pixel-agents/webview-ui/src/office/types";
import { type AgentStatus } from "./types";
import { AMBIENT_LAMPS, renderNightLight } from "./nightLighting";
import { GolfPractice, GOLF_BAYS, GOLF_ROWS } from "./GolfPractice";
import { worldY, wingPosition } from "./worldGeometry";
import { loadTowerArchitecture, renderTowerArchitecture, renderTowerBackdrop, renderTowerRelief, renderTowerSign } from "./TowerArchitecture";
import { renderTowerPerspective, projectTowerX, unprojectTowerX, unprojectTowerY, towerDisplayRows } from "./TowerPerspective";

type Agent = { id: string; name: string; status: AgentStatus };
type Task = { id: string; agent_id: string; description?: string; status?: string; depends_on?: string[]; delegated_by?: string; workflow_id?: string; result?: { approval_required?: boolean; role_version?: number; review_decision?: string; branch?: string } };
type Event = { id: number; task_id: string; agent_id: string; status: string };
type MarketReading = { series_id: string; label: string; value: number; previous?: number | null;
  change?: number | null; unit: string; observed_at: string; source?: string; source_url?: string };
type FeaturedOffer = { title: string; company: string; location: string; url: string; kind?: string; start_period?: string;
  published?: string; published_inferred?: boolean; source?: string; detected_at?: string; selection_reason?: string;
  selection_source?: "job_hunter"|"internships_cache"; total_offers?: number; tracker_updated_at?: string };
type Props = { agents: Agent[]; tasks: Task[]; events: Event[]; selectedId: string; onPick: (id: string) => void;
  marketPoints: MarketReading[]; marketRetrievedAt: string; marketError?: string; internshipError?: string;
  featuredOffers: FeaturedOffer[] };
type AssetLeaf = { id: string; file: string; width: number; height: number; footprintW: number; footprintH: number; orientation?: string; state?: string; frame?: number; mirrorSide?: boolean };
type MarketDeskPackAsset = AssetLeaf & { name: string; category: string; isDesk: boolean; canPlaceOnWalls?: boolean;
  canPlaceOnSurfaces?: boolean; backgroundTiles?: number; isWallTile?: boolean };
type LoadedCharacter = { down: SpriteData[]; up: SpriteData[]; right: SpriteData[] };
type Runtime = { office: OfficeState; golf: GolfPractice; zoom: number; zoomTarget: number; scale: number; offsetX: number; offsetY: number };

const ROOT = "/city/pixel-assets";
const ROSTER = ["market_analyst", "finance_tutor", "job_hunter", "networker", "outreach_agent", "developer", "innovation_lab", "internship_scout"];
const MANAGER_ID = "desk_manager";
const WORLD_ROSTER = [...ROSTER, MANAGER_ID];
const MARKET_PANEL = { col: 0, width: 14.5, top: 0.3, height: 5.3 };
const OFFERS_PANEL = { col: 34.5, width: 14.5, top: 0.3, height: 5.3 };
const agentIndex = (id: string) => id === MANAGER_ID ? ROSTER.length : ROSTER.indexOf(id);
const agentSeatId = (id: string) => uid(id === MANAGER_ID ? "manager-chair" : `chair-${id}`);
const FURNITURE_DIRS = ["BIN", "BOOKSHELF", "CACTUS", "CLOCK", "COFFEE", "COFFEE_TABLE", "CUSHIONED_BENCH", "CUSHIONED_CHAIR", "DESK", "DOUBLE_BOOKSHELF", "HANGING_PLANT", "LARGE_PAINTING", "LARGE_PLANT", "PC", "PLANT", "PLANT_2", "POT", "SMALL_PAINTING", "SMALL_PAINTING_2", "SMALL_TABLE", "SOFA", "TABLE_FRONT", "WHITEBOARD", "WOODEN_BENCH", "WOODEN_CHAIR"];
const uid = (id: string) => `marketdesk-${id}`;
const textiles: Record<string, HTMLImageElement> = {};
async function loadTextiles() {
  for (const name of ['ivory', 'slate']) textiles[name] = await loadImage(`${ROOT}/furniture/MARKETDESK_PACK/premium/rug-${name}.png`);
  for (const name of ['oak-night', 'lamp-amber']) textiles[name] = await loadImage(`${ROOT}/furniture/MARKETDESK_PACK/premium/${name}.png`);
}

function colorizePixels(image: HTMLImageElement | HTMLCanvasElement, sx = 0, sy = 0,
  sw = image instanceof HTMLImageElement ? image.naturalWidth : image.width,
  sh = image instanceof HTMLImageElement ? image.naturalHeight : image.height): SpriteData {
  const source = document.createElement("canvas");
  source.width = sw; source.height = sh;
  const context = source.getContext("2d", { willReadFrequently: true });
  if (!context) throw new Error("Le navigateur ne peut pas lire les sprites Pixel Agents.");
  context.imageSmoothingEnabled = false;
  context.drawImage(image, sx, sy, sw, sh, 0, 0, sw, sh);
  const pixels = context.getImageData(0, 0, sw, sh).data;
  return Array.from({ length: sh }, (_, y) => Array.from({ length: sw }, (_, x) => {
    const i = (y * sw + x) * 4;
    if (pixels[i + 3] < 16) return "";
    const hex = [pixels[i], pixels[i + 1], pixels[i + 2]].map(value => value.toString(16).padStart(2, "0")).join("");
    return pixels[i + 3] === 255 ? `#${hex}` : `#${hex}${pixels[i + 3].toString(16).padStart(2, "0")}`;
  }));
}

function harmonizeLoungeSofa(sprite: SpriteData): SpriteData {
  return sprite.map(row => row.map(pixel => {
    if (!pixel.startsWith("#") || pixel.length < 7) return pixel;
    const red = Number.parseInt(pixel.slice(1, 3), 16);
    const green = Number.parseInt(pixel.slice(3, 5), 16);
    const blue = Number.parseInt(pixel.slice(5, 7), 16);
    const max = Math.max(red, green, blue), min = Math.min(red, green, blue);
    const delta = max - min;
    if (delta === 0 || max < 40 || delta / max < 0.18) return pixel;
    let hue = red === max ? 60 * ((green - blue) / delta)
      : green === max ? 60 * ((blue - red) / delta + 2)
      : 60 * ((red - green) / delta + 4);
    if (hue < 0) hue += 360;
    if (hue < 330 && hue > 14) return pixel;
    const lightness = (max + min) / 2;
    const leather = lightness > 0.68 ? "#8494a1" : lightness > 0.42 ? "#5e7180" : "#3c4d5c";
    return leather + pixel.slice(7);
  }));
}

function loadImage(url: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const image = new Image();
    image.onload = () => resolve(image);
    image.onerror = () => reject(new Error(`Sprite introuvable : ${url}`));
    // A rebuilt bundle must not reuse an older palette from browser PNG cache.
    image.src = url.includes('/MARKETDESK_PACK/') ? `${url}?v=tower-objects-20261101-5` : url;
  });
}

async function loadSprite(url: string, width: number, height: number): Promise<SpriteData> {
  const image = await loadImage(url);
  if (image.naturalWidth !== width || image.naturalHeight !== height) {
    // Generated source art is reduced once to its native Pixel Agents sprite grid.
    // Nearest-neighbour sampling preserves hard pixel edges and alpha.
    const pixelCanvas = document.createElement("canvas");
    pixelCanvas.width = width; pixelCanvas.height = height;
    const context = pixelCanvas.getContext("2d", { willReadFrequently: true });
    if (!context) throw new Error(`Impossible de convertir le sprite : ${url}`);
    context.imageSmoothingEnabled = false;
    context.drawImage(image, 0, 0, image.naturalWidth, image.naturalHeight, 0, 0, width, height);
    return colorizePixels(pixelCanvas);
  }
  return colorizePixels(image, 0, 0, width, height);
}

async function loadCharacterSheets(): Promise<LoadedCharacter[]> {
  const characters: LoadedCharacter[] = [];
  for (let index = 0; index < 6; index++) {
    const image = await loadImage(`${ROOT}/characters/char_${index}.png`);
    const direction = (row: number) => Array.from({ length: 7 }, (_, frame) => colorizePixels(image, frame * 16, row * 32, 16, 32));
    characters.push({ down: direction(0), up: direction(1), right: direction(2) });
  }
  return characters;
}

function tradingDeskSprite(screenCount = 4, manager = false): SpriteData {
  const pixels: SpriteData = Array.from({ length: 32 }, () => Array(64).fill(""));
  const rect = (x: number, y: number, w: number, h: number, color: string) => {
    for (let row = y; row < y + h; row++) for (let col = x; col < x + w; col++)
      if (row >= 0 && row < 32 && col >= 0 && col < 64) pixels[row][col] = color;
  };
  // A shared 64×32 workstation, with a wider five-screen bank for the manager.
  rect(1, 18, 62, 3, "#252f3e"); rect(0, 21, 64, 6, "#9a7958");
  rect(1, 22, 62, 2, "#c4a17a"); rect(0, 27, 64, 4, "#343947");
  rect(2, 31, 7, 1, "#1e2531"); rect(55, 31, 7, 1, "#1e2531");
  const screenStep = Math.floor(64 / screenCount), screenWidth = screenStep - 1;
  const screenStart = screenCount === 4 ? 1 : Math.floor((64 - screenCount * screenWidth - (screenCount - 1)) / 2);
  for (let index = 0; index < screenCount; index++) {
    const x = screenStart + index * (screenWidth + 1), innerWidth = screenWidth - 4;
    rect(x, 1, screenWidth, 15, "#151b29"); rect(x + 1, 2, screenWidth - 2, 12, "#536274");
    rect(x + 2, 3, innerWidth, 10, "#091521"); rect(x + Math.floor(screenWidth / 2) - 1, 16, 3, 3, "#798a99");
    rect(x + 2, 4, innerWidth, 1, manager ? "#80e8ed" : index % 2 ? "#7ec9f4" : "#f0bb78");
    for (let row = 6; row < 12; row += 2) {
      rect(x + 2, row, Math.max(2, Math.floor(innerWidth * 0.36)), 1, row === 8 ? "#d87a75" : "#68c69c");
      rect(x + Math.max(5, Math.floor(screenWidth * 0.58)), row, Math.max(2, Math.floor(innerWidth * 0.34)), 1,
        row === 10 ? "#8bb6eb" : "#a89c69");
    }
    rect(x + 2, 14, screenWidth - 4, 1, "#8d9eaa");
  }
  rect(19, 23, 27, 4, "#1b2531"); rect(20, 24, 25, 1, "#9eabb8");
  for (let x = 21; x < 44; x += 3) rect(x, 25, 2, 1, "#617789");
  rect(51, 23, 9, 3, "#233344"); rect(52, 22, 7, 2, "#687b8c");
  rect(5, 22, 4, 3, "#e4e0d4"); rect(6, 21, 2, 1, "#e4e0d4");
  rect(18, 29, 25, 1, "#637084");
  rect(3, 17, 57, 1, "#465464"); rect(12, 16, 1, 2, "#465464"); rect(47, 16, 1, 2, "#465464");
  rect(47, 20, 1, 2, "#d2aa69"); rect(45, 19, 5, 1, "#e0bc79"); rect(44, 18, 7, 1, "#9d825b");
  rect(4, 28, 18, 2, "#4b5966"); rect(42, 28, 17, 2, "#4b5966");
  rect(6, 28, 14, 1, "#79828a"); rect(44, 28, 13, 1, "#79828a");
  return pixels;
}

function tradingChairSprite(): SpriteData {
  const pixels: SpriteData = Array.from({ length: 24 }, () => Array(32).fill(""));
  const rect = (x: number, y: number, w: number, h: number, color: string) => {
    for (let row = y; row < y + h; row++) for (let col = x; col < x + w; col++)
      if (row >= 0 && row < 24 && col >= 0 && col < 32) pixels[row][col] = color;
  };
  // Broad padded back, armrests, seat cushion, pedestal and five-point base; one tile remains walkable.
  rect(7, 1, 18, 2, "#202a37"); rect(5, 3, 22, 6, "#3e5064"); rect(7, 4, 18, 4, "#697d91");
  rect(3, 7, 3, 5, "#283443"); rect(26, 7, 3, 5, "#283443");
  rect(5, 9, 22, 4, "#273342"); rect(7, 10, 18, 2, "#71859a");
  rect(14, 13, 4, 5, "#929eaa"); rect(8, 17, 16, 1, "#697987");
  rect(14, 18, 4, 2, "#667686"); rect(5, 20, 8, 1, "#798796");
  rect(19, 20, 8, 1, "#798796"); rect(3, 21, 8, 1, "#3d4a58");
  rect(21, 21, 8, 1, "#3d4a58"); rect(10, 22, 12, 1, "#3d4a58");
  rect(5, 8, 1, 4, "#b5c5d2"); rect(26, 8, 1, 4, "#b5c5d2");
  return pixels;
}

async function readFurnitureManifest(url: string): Promise<unknown> {
  const response = await fetch(url, { cache: "no-store" });
  if (!response.ok) throw new Error(`Impossible de charger le manifeste ${url}.`);
  return response.json();
}

export async function loadFurniture(
  readManifest = readFurnitureManifest,
  readSprite = loadSprite,
): Promise<LoadedAssetData> {
  const catalog: LoadedAssetData["catalog"] = [];
  const sprites: Record<string, SpriteData> = {};
  await Promise.all(FURNITURE_DIRS.map(async dir => {
    const base = `${ROOT}/furniture/${dir}`;
    const manifest = await readManifest(`${base}/manifest.json`) as FurnitureManifest;
    const inherited: InheritedProps = { groupId: manifest.id, name: manifest.name, category: manifest.category,
      canPlaceOnWalls: manifest.canPlaceOnWalls, canPlaceOnSurfaces: manifest.canPlaceOnSurfaces,
      backgroundTiles: manifest.backgroundTiles };
    const nodes: ManifestNode[] = manifest.type === "asset"
      ? [{ type: "asset", id: manifest.id, file: manifest.file ?? `${manifest.id}.png`, width: manifest.width ?? 16,
        height: manifest.height ?? 16, footprintW: manifest.footprintW ?? 1, footprintH: manifest.footprintH ?? 1 }]
      : (manifest.members ?? []);
    await Promise.all(nodes.flatMap(node => flattenManifest(node, inherited)).map(async asset => {
      const leaf = asset as AssetLeaf;
      try {
        const sprite = await readSprite(`${base}/${leaf.file}`, leaf.width, leaf.height);
        sprites[asset.id] = asset.groupId === "SOFA" ? harmonizeLoungeSofa(sprite) : sprite;
        catalog.push({ id: asset.id, label: asset.label, category: asset.category, width: leaf.width, height: leaf.height,
          footprintW: leaf.footprintW, footprintH: leaf.footprintH, isDesk: asset.category === "desks",
          groupId: asset.groupId, orientation: asset.orientation, state: asset.state, frame: asset.frame,
          mirrorSide: asset.mirrorSide, rotationScheme: asset.rotationScheme, animationGroup: asset.animationGroup,
          canPlaceOnSurfaces: asset.canPlaceOnSurfaces, canPlaceOnWalls: asset.canPlaceOnWalls,
          backgroundTiles: asset.backgroundTiles });
      } catch (error) {
        console.warn("Pixel Agents furniture asset skipped", asset.id, error);
      }
    }));
  }));
  const packBase = `${ROOT}/furniture/MARKETDESK_PACK`;
  // The pack manifest changes as assets are added; never reuse a stale browser copy.
  const pack = await readManifest(`${packBase}/manifest.json`) as { assets: MarketDeskPackAsset[] };
  const golfPack = await readManifest(`${ROOT}/furniture/MARKETDESK_GOLF/manifest.json`) as { assets: MarketDeskPackAsset[] };
  const packAssets = [...pack.assets, ...golfPack.assets.map(asset => ({...asset, file:`../MARKETDESK_GOLF/${asset.file}`}))];
  await Promise.all(packAssets.filter(asset => !asset.isWallTile).map(async asset => {
    const sprite = await readSprite(`${packBase}/${asset.file}`, asset.width, asset.height);
    sprites[asset.id] = sprite;
    catalog.push({ id: asset.id, label: asset.name, category: asset.category, width: asset.width, height: asset.height,
      footprintW: asset.footprintW, footprintH: asset.footprintH, isDesk: asset.isDesk,
      groupId: asset.id, orientation: asset.orientation, canPlaceOnSurfaces: asset.canPlaceOnSurfaces,
      canPlaceOnWalls: asset.canPlaceOnWalls, backgroundTiles: asset.backgroundTiles });
  }));
  // Keep the existing door catalogue/footprints and replace only their artwork.
  sprites.MD_DOUBLE_GLASS_DOOR = await readSprite(`${ROOT}/tower/md_entry_glass.png?v=partitions-6`,64,32);
  sprites.MD_GLASS_DOOR = await readSprite(`${ROOT}/tower/md_entry_jamb.png?v=partitions-6`,16,32);
  for(const [id,file,width,height,footprintW,footprintH,backgroundTiles]of [
    ['MD_SIDE_GLASS_DOOR','md_side_entry',16,32,1,2,2],
    ['MD_INTERNAL_DOUBLE_DOOR','md_entry_pair',32,32,2,1,1],
  ] as const){
    sprites[id]=await readSprite(`${ROOT}/tower/${file}.png?v=partitions-6`,width,height);
    catalog.push({id,label:'Open glass doorway',category:'walls',width,height,footprintW,footprintH,
      isDesk:false,groupId:id,canPlaceOnWalls:true,backgroundTiles});
  }
  sprites.MARKET_TRADING_DESK = tradingDeskSprite();
  catalog.push({ id: "MARKET_TRADING_DESK", label: "Trading workstation", category: "desks",
    width: 64, height: 32, footprintW: 4, footprintH: 2, isDesk: true,
    groupId: "MARKET_TRADING_DESK", orientation: "front", canPlaceOnSurfaces: false,
    canPlaceOnWalls: false, backgroundTiles: 1 });
  sprites.MARKET_MANAGER_DESK = tradingDeskSprite(5, true);
  catalog.push({ id: "MARKET_MANAGER_DESK", label: "Head of Desk workstation", category: "desks",
    width: 64, height: 32, footprintW: 4, footprintH: 2, isDesk: true,
    groupId: "MARKET_MANAGER_DESK", orientation: "front", canPlaceOnSurfaces: false,
    canPlaceOnWalls: false, backgroundTiles: 1 });
  sprites.MARKET_ERGO_CHAIR = tradingChairSprite();
  catalog.push({ id: "MARKET_ERGO_CHAIR", label: "Ergonomic trading chair", category: "chairs",
    width: 32, height: 24, footprintW: 1, footprintH: 1, isDesk: false,
    groupId: "MARKET_ERGO_CHAIR", orientation: "back", canPlaceOnSurfaces: false,
    canPlaceOnWalls: false, backgroundTiles: 0 });
  if (!catalog.length || !buildDynamicCatalog({ catalog, sprites })) throw new Error("Le catalogue de mobilier Pixel Agents est vide.");
  for (const required of ["SOFA_FRONT", "BOOKSHELF", "DOUBLE_BOOKSHELF", "POT", "WOODEN_BENCH", "MD_PANORAMA_WINDOW",
    "MD_GLASS_DOOR", "MD_DOUBLE_GLASS_DOOR",
    "MD_GLOBAL_MARKETS_DESK", "MD_RESEARCH_DESK", "MD_TECH_DESK", "MD_CAREER_DESK", "MD_NETWORK_DESK",
    "MD_OUTREACH_DESK", "MD_EXECUTIVE_DESK", "MD_MARKET_TICKER", "MD_RESEARCH_BOARD", "MD_SERVER_RACK",
    "MD_CAREER_BOARD", "MD_NETWORK_TABLE", "MD_OUTREACH_DISPLAY", "MD_EXECUTIVE_WALL", "MD_EXECUTIVE_LIBRARY",
    "MD_EXECUTIVE_CHAIR", "MD_CONTACT_PHONE", "MD_CENTRAL_LOUNGE_SOFA", "MD_EXECUTIVE_MEETING_TABLE",
    "MD_EXECUTIVE_GLASS_PARTITION", "MD_LOUNGE_SOFA_L", "MD_LOUNGE_ARMCHAIR", "MD_LOUNGE_COFFEE_TABLE",
    "MD_MEETING_ROUND_TABLE", "MD_MEETING_CHAIR", "MD_LOUNGE_PLANTER", "MD_SERVER_RACK_CLUSTER", "MD_CAREER_CABINET",
    "MD_NETWORK_WORLD_MAP", "MD_TERRACE_TOPIARY"]) {
    if (!sprites[required]) throw new Error(`Sprite requis absent du manifeste : ${required}.`);
    if (!getCatalogEntry(required)) throw new Error(`Sprite chargé mais absent du catalogue : ${required}.`);
  }
  return { catalog, sprites };
}

async function loadEnvironmentSprites(): Promise<void> {
  const carpet = (seed: number): SpriteData => Array.from({ length: 16 }, (_, y) =>
    Array.from({ length: 16 }, (_, x) => {
      if (x === 0 && y === 0) return "#b6b6b6";
      const grain = (x * 17 + y * 29 + seed * 13) % 47;
      return grain === 0 ? "#a9a9a9" : grain < 4 ? "#b0b0b0" : "#b6b6b6";
    }));
  const wood: SpriteData = Array.from({ length: 16 }, (_, y) => Array.from({ length: 16 }, (_, x) => {
    if (x === 0 && y === 0) return "#b6b6b6";
    if (y === 7 || y === 15) return "#a9a9a9";
    return (x * 3 + y * 5) % 31 === 0 ? "#b0b0b0" : "#b9b9b9";
  }));
  const corridor = (): SpriteData => Array.from({ length: 16 }, () => Array(16).fill("#b0b0b0"));
  const threshold: SpriteData = Array.from({ length: 16 }, (_, y) => Array.from({ length: 16 }, () =>
    y === 7 || y === 8 ? "#c0c0c0" : y === 6 || y === 9 ? "#a6a6a6" : "#b4b4b4"));
  const floors = [wood, carpet(1), carpet(4), carpet(7), carpet(10), carpet(13), carpet(16), corridor(), corridor(), threshold];
  setFloorSprites(floors);
  const packBase = `${ROOT}/furniture/MARKETDESK_PACK`;
  const response = await fetch(`${packBase}/manifest.json`, { cache: "no-store" });
  if (!response.ok) throw new Error("Impossible de charger les modules de cloisons vitrées.");
  const pack = await response.json() as { assets: MarketDeskPackAsset[] };
  const wallModules = pack.assets.filter(asset => asset.isWallTile)
    .sort((a, b) => Number.parseInt(a.id.slice(-2), 16) - Number.parseInt(b.id.slice(-2), 16));
  if (wallModules.length !== 16) throw new Error("Le pack de cloisons doit contenir ses 16 jonctions auto-raccordables.");
  const wallSprites = await Promise.all(wallModules.map((_,mask) =>
    loadSprite(`${ROOT}/tower/md_partition_${mask.toString(16).padStart(2,'0')}.png?v=partitions-6`, 16, 24)));
  // Authored module colors are preserved; wall cells remain collision tiles in the layout.
  setWallSprites([wallSprites]);
}

export function buildOfficeLayout(): OfficeLayout {
  const cols = 48, rows = 40;
  const tiles: OfficeLayout["tiles"] = [];
  const tileColors: Array<{ h: number; s: number; b: number; c: number } | null> = [];
  // A single pale-oak finish keeps the floor visually continuous across rooms.
  const oak = { h: 34, s: 31, b: 24, c: -1 };
  const zones = [
    // Departments are deliberately unequal: Markets and Research flank the
    // shared lounge, while the three support teams form a compact lower wing.
    { label: "GLOBAL MARKETS", color: "#77d8e7", agent: ROSTER[0], desk: "MD_GLOBAL_MARKETS_DESK", x0: 3, x1: 14, y0: 10, y1: 18, col: 3, row: 12 },
    { label: "QUANT RESEARCH", color: "#9b8bea", agent: ROSTER[1], desk: "MD_RESEARCH_DESK", x0: 32, x1: 46, y0: 10, y1: 18, col: 34, row: 12 },
    { label: "TECH LAB", color: "#70cbb7", agent: ROSTER[2], desk: "MD_TECH_DESK", x0: 1, x1: 14, y0: 22, y1: 30, col: 2, row: 24 },
    { label: "INTERVIEW STUDIO", color: "#a995e5", agent: ROSTER[5], desk: "MD_CAREER_DESK", x0: 16, x1: 23, y0: 22, y1: 30, col: 17, row: 23 },
    { label: "INNOVATION LAB", color: "#70cbb7", agent: ROSTER[6], desk: "MD_RESEARCH_DESK", x0: 24, x1: 31, y0: 22, y1: 30, col: 25, row: 23 },
    { label: "NETWORK", color: "#70cbb7", agent: ROSTER[3], desk: "MD_NETWORK_DESK", x0: 33, x1: 46, y0: 22, y1: 26, col: 34, row: 22 },
    { label: "OUTREACH", color: "#77d8e7", agent: ROSTER[4], desk: "MD_OUTREACH_DESK", x0: 33, x1: 46, y0: 27, y1: 30, col: 34, row: 27 },
  ];
  // A furnished shared atrium replaces the long corridors and connects every wing.
  const lounge = { x0: 16, x1: 31, y0: 10, y1: 18 };
  // The executive suite occupies the upper centre, between the two live-data panels.
  const manager = { x0: 15, x1: 32, y0: 1, y1: 8, col: 21, row: 3 };
  const inZone = (zone: typeof zones[number], col: number, row: number) => {
    if (col < zone.x0 || col > zone.x1 || row < zone.y0 || row > zone.y1) return false;
    // Only the upper outside corner is recessed. Notches in south floors left
    // isolated holes above the continuous facade and entrance terrace.
    if (zone.agent === ROSTER[1] && row === 10 && col === 46) return false;
    return true;
  };
  const zoneAt = (col: number, row: number) => zones.find(zone => inZone(zone, col, row));
  const managerAt = (col: number, row: number) => col >= manager.x0 && col <= manager.x1 && row >= manager.y0 && row <= manager.y1;
  const loungeAt = (col: number, row: number) =>
    (col >= lounge.x0 && col <= lounge.x1 && row >= lounge.y0 && row <= lounge.y1) ||
    // The atrium opens into a short central foyer. Side departments keep their
    // own doorways, so this adds a common destination without a long corridor.
    (col >= 22 && col <= 25 && row >= 19 && row <= 20);
  const shortLink = (col: number, row: number) =>
    // Setback terraces join the executive floor at its west/east thresholds.
    (((col >= 4 && col <= 14) || (col >= 33 && col <= 43)) && row >= 7 && row <= 8) ||
    // The central Career doorway continues outdoors; no teleport or fake room.
    (col >= 22 && col <= 25 && row >= 30 && row <= 34) ||
    (col >= 1 && col <= 46 && row >= 33 && row <= 39) ||
    // Shared access gallery: required by the Tech Lab's alternate approach.
    (((col >= 6 && col <= 8) || col === 39 || (col >= 22 && col <= 25)) && row >= 19 && row <= 20) ||
    // Manager suite to lounge, and a compact three-prong route to the lower wing.
    (col >= 22 && col <= 25 && row >= 9 && row <= 10) ||
    (col >= 22 && col <= 25 && row >= 19 && row <= 21) ||
    // Direct, short connections let agents move between aligned departments.
    (col === 7 && row >= 19 && row <= 21) ||
    (col === 39 && row >= 19 && row <= 21) ||
    // Career connects to Network and Outreach through two doorway-sized links.
    (col >= 31 && col <= 33 && [24, 28].includes(row)) ||
    // Outreach and Network share a single internal doorway.
    (col === 39 && row === 26);
  const doorway = (col: number, row: number) =>
    shortLink(col, row) ||
    (row === 14 && [15, 32].includes(col)) ||
    // Secondary south-east opening keeps the Markets seat reachable around
    // the lounge furniture, even if the north doorway approach is obstructed.
    (col === 15 && [16, 17, 18].includes(row)) ||
    (row === 21 && [7, 39].includes(col));
  const partition = (col: number, row: number) =>
    // Glass dividers distinguish rooms without enclosing the open central lounge.
    (col === 15 && row >= 10 && row <= 18 && row !== 14 && row !== 16 && row !== 17 && row !== 18) ||
    (col === 32 && row >= 10 && row <= 18 && row !== 14) ||
    (col === 15 && row >= 22 && row <= 30) ||
    (col === 32 && row >= 22 && row <= 26 && row !== 24) ||
    (col === 32 && row >= 27 && row <= 30 && row !== 28) ||
    // A single glazed divider separates the compact Network and Outreach rooms.
    (row === 26 && col >= 33 && col <= 46 && col !== 39) ||
    // Window-backed edges; short links open directly to the atrium or departments.
    (row === 9 && ((col >= 3 && col <= 14) || (col >= 32 && col <= 46) ||
      (col >= 15 && col <= 32 && !(col >= 22 && col <= 25)))) ||
    (row === 21 && ((col >= 1 && col <= 14 && col !== 7) ||
      (col >= 16 && col <= 31 && !(col >= 22 && col <= 25)) ||
      (col >= 33 && col <= 46 && col !== 39))) ||
    (row === 0 && col >= manager.x0 && col <= manager.x1);
  for (let row = 0; row < rows; row++) for (let col = 0; col < cols; col++) {
    const zone = zoneAt(col, row);
    if (partition(col, row)) {
      tiles.push(TileType.WALL); tileColors.push(null);
      continue;
    }
    if (zone || managerAt(col, row) || loungeAt(col, row) || doorway(col, row)) {
      tiles.push(TileType.FLOOR_1);
      tileColors.push(oak);
      continue;
    }
    // Leave the building perimeter open; only explicit internal partitions become walls.
    tiles.push(TileType.VOID); tileColors.push(null);
  }
  const furniture: OfficeLayout["furniture"] = [];
  const put = (id: string, type: string, col: number, row: number) => {
    // Move south-edge decorations up before removing the unused room rows.
    if(row===16)row=15;
    const pos=wingPosition(col,row);
    furniture.push({ uid: uid(id), type, col:pos.col, row:pos.row });
  };
  for (const station of zones) {
    put(`desk-${station.agent}`, station.desk, station.col, station.row);
    put(`chair-${station.agent}`, "MARKET_ERGO_CHAIR", station.col + 2, station.row + 2);
  }
  put("chair-internship_scout", "MARKET_ERGO_CHAIR", 10, 26);
  // Panoramic windows form aligned glazed bands only on the north-facing facades.
  // The central manager screen wall stays clear, and career/network doors remain open.
  for (const [id, col, row] of [
    ["manager-window-west", 15, 0], ["manager-window-east", 27, 0],
    ["markets-window-west", 3, 9], ["markets-window-east", 9, 9],
    ["research-window-west", 33, 9], ["research-window-east", 39, 9],
  ] as Array<[string, number, number]>) put(id, "MD_PANORAMA_WINDOW", col, row);
  // Open sliding-door overlays make existing passable openings read as intentional architecture.
  // Their background rows are non-blocking, so routes and collisions remain unchanged.
  furniture.push({uid:uid("manager-glass-entry"),type:"MD_DOUBLE_GLASS_DOOR",col:22,row:10});
  furniture.push({uid:uid("tech-glass-entry"),type:"MD_INTERNAL_DOUBLE_DOOR",col:6,row:18});
  furniture.push({uid:uid("career-glass-entry"),type:"MD_DOUBLE_GLASS_DOOR",col:22,row:19});
  furniture.push({uid:uid("research-gallery-entry"),type:"MD_INTERNAL_DOUBLE_DOOR",col:39,row:17});
  furniture.push({uid:uid("network-glass-entry"),type:"MD_INTERNAL_DOUBLE_DOOR",col:39,row:19});
  // Door drawings use their resolved collision coordinates, never a second
  // room offset. Side doors cover two rows; front doors cover two columns.
  for(const [id,col,row]of [['markets',13,14],['research',32,14],['network',32,22],['outreach',32,26],['innovation',24,25]] as const)
    furniture.push({uid:uid(`${id}-side-entry`),type:'MD_SIDE_GLASS_DOOR',col,row});
  furniture.push({uid:uid('network-outreach-entry'),type:'MD_INTERNAL_DOUBLE_DOOR',col:39,row:24});
  put("manager-chair", "MD_EXECUTIVE_CHAIR", manager.col + 2, manager.row + 2);
  put("manager-desk", "MD_EXECUTIVE_DESK", manager.col, manager.row);
  put("manager-supervision-wall", "MD_EXECUTIVE_WALL", 21, 1);
  put("manager-library-left", "MD_EXECUTIVE_LIBRARY", 15, 2);
  put("manager-library-right", "MD_EXECUTIVE_LIBRARY", 29, 2);
  put("manager-glass-left", "MD_EXECUTIVE_GLASS_PARTITION", 15, 8);
  put("manager-glass-right", "MD_EXECUTIVE_GLASS_PARTITION", 27, 8);
  put("manager-meeting-table", "MD_EXECUTIVE_MEETING_TABLE", 16, 5);
  put("manager-lounge-seat-left", "MD_LOUNGE_ARMCHAIR", 17, 7);
  put("manager-lounge-seat-right", "MD_LOUNGE_ARMCHAIR", 19, 7);
  put("manager-lounge-seat", "MD_LOUNGE_ARMCHAIR", 25, 6);
  put("manager-sofa", "MD_CENTRAL_LOUNGE_SOFA", 29, 6); put("manager-hanging-plant", "HANGING_PLANT", 30, 1);
  for(const col of [5,13,33,41])put(`terrace-topiary-${col}`,"MD_TERRACE_TOPIARY",col,5);

  // One shared lounge; circulation runs around the furniture, not through it.
  put("lounge-sofa-west", "MD_LOUNGE_SOFA_L", 20, 11);
  put("lounge-chair-west", "MD_LOUNGE_ARMCHAIR", 25, 12);
  put("lounge-chair-east", "MD_LOUNGE_ARMCHAIR", 25, 15);
  put("lounge-coffee-table-west", "MD_LOUNGE_COFFEE_TABLE", 21, 15);
  // Keep the central north-south route clear between the atrium and executive suite.
  put("lounge-planter", "MD_LOUNGE_PLANTER", 16, 16);
  put("lounge-plant-east", "PLANT_2", 30, 16);

  // Department-specific details are tucked against the room edges, away from seats and doors.
  put("markets-library", "BOOKSHELF", 3, 10); put("markets-ticker", "MD_MARKET_TICKER", 8, 10);
  put("markets-clock", "CLOCK", 12, 10); put("markets-plant", "PLANT", 3, 16); put("markets-cactus", "CACTUS", 13, 16);
  put("markets-second-desk", "MD_GLOBAL_MARKETS_DESK", 8, 12);
  put("markets-lounge-sofa", "MD_CENTRAL_LOUNGE_SOFA", 10, 15);
  put("markets-lounge-table", "MD_LOUNGE_COFFEE_TABLE", 7, 16);
  put("research-library", "DOUBLE_BOOKSHELF", 33, 10); put("research-board", "MD_RESEARCH_BOARD", 41, 10);
  put("research-second-desk", "MD_RESEARCH_MEETING", 40, 12); put("research-plant", "PLANT_2", 33, 16);
  put("research-lounge-sofa", "MD_CENTRAL_LOUNGE_SOFA", 43, 15);
  put("research-lounge-table", "MD_LOUNGE_COFFEE_TABLE", 40, 16);
  put("technology-server-rack", "MD_SERVER_RACK", 1, 23); put("technology-server-rack-east", "MD_SERVER_RACK", 13, 23);
  put("technology-server-cluster", "MD_SERVER_RACK_CLUSTER", 1, 27);
  put("technology-board", "MD_RESEARCH_BOARD", 9, 22);
  put("desk-internship_scout", "MD_CAREER_DESK", 8, 24);
  put("technology-books", "BOOKSHELF", 11, 28);
  put("career-board", "MD_CAREER_BOARD", 16, 22); 
  put("career-cabinet", "MD_CAREER_CABINET", 16, 28);
  put("career-books", "BOOKSHELF", 29, 28);
  put("network-table", "MD_NETWORK_CONFERENCE", 40, 23);
  put("network-world-map", "MD_NETWORK_WORLD_MAP", 40, 21);
  
  
  put("network-library", "BOOKSHELF", 44, 22); put("network-plant", "PLANT_2", 45, 24);
  put("outreach-board", "MD_OUTREACH_DISPLAY", 40, 27); put("outreach-phone", "MD_CONTACT_PHONE", 38, 29);
  put("outreach-books", "BOOKSHELF", 33, 29); put("outreach-table", "SMALL_TABLE_FRONT", 41, 29);
  put("outreach-plant", "PLANT", 45, 29);

  put("golf-central-entry", "MD_DOUBLE_GLASS_DOOR", 22, 31);
  for (const bay of GOLF_BAYS) {
    put(`golf-mat-${bay.index}`, "MD_GOLF_MAT", bay.matCol, 35);
    put(`golf-bag-${bay.index}`, "MD_GOLF_BAG", bay.matCol+5, 36);
    put(`golf-basket-${bay.index}`, "MD_GOLF_BASKET", bay.matCol+4, 38);
  }
  put("golf-putting-green", "MD_GOLF_GREEN", 42, 35);
  for(const col of [1,8,15,26,33,40,46])put(`golf-lantern-${col}`,"MD_GOLF_LANTERN",col,33);
  for(const col of [2,12,28,37])put(`golf-bench-${col}`,"MD_GOLF_BENCH",col,39);
  for(const col of [7,17,32,43])put(`golf-planter-${col}`,"MD_GOLF_PLANTER",col,39);

  // Facade bands are real non-walkable gaps, crossed only by the stairs.
  const projectedTiles = Array(GOLF_ROWS*cols).fill(TileType.VOID);
  const projectedColors: typeof tileColors = Array(GOLF_ROWS*cols).fill(null);
  for(let row=0;row<40;row++) {
    if(row===17||row===18)continue;
    for(let col=0;col<cols;col++) {
      if(tiles[row*cols+col]===TileType.VOID)continue;
      const pos=wingPosition(col,row), index=pos.row*cols+pos.col;
      projectedTiles[index]=tiles[row*cols+col];
      projectedColors[index]=tileColors[row*cols+col];
    }
  }
  for(const [before,count,starts] of [[9,1,[22]],[21,1,[7,22,39]],[33,1,[22]]] as Array<[number,number,number[]]>) {
    for(let row=worldY(before)-count;row<worldY(before);row++)for(const start of starts)
      for(let col=start;col<start+(start===22?4:1);col++) {
        projectedTiles[row*cols+col]=TileType.FLOOR_1;
        projectedColors[row*cols+col]=tileColors[19*cols+23];
      }
  }
  // The short passage behind the shifted wing keeps the lower stair connected.
  for(let col=8;col<=22;col++){
    const index=worldY(19)*cols+col;projectedTiles[index]=TileType.FLOOR_1;projectedColors[index]=oak;
  }
  // Real walkable bridges connect the shifted wings to the unchanged atrium.
  for(const rawRow of [14,16])for(const col of [14,15]){
    const index=worldY(rawRow)*cols+col;projectedTiles[index]=TileType.FLOOR_1;projectedColors[index]=oak;
  }
  for(const row of [worldY(14)-1,worldY(14)]){
    projectedTiles[row*cols+32]=TileType.FLOOR_1;projectedColors[row*cols+32]=oak;
  }
  // The shifted walls used to leave open sky inside the building. These are
  // real circulation tiles, shared by rendering, collisions and pathfinding.
  const floorAt=(col:number,row:number)=>{
    const index=row*cols+col;projectedTiles[index]=TileType.FLOOR_1;projectedColors[index]=oak;
  };
  for(let row=worldY(10);row<=worldY(30);row++) floorAt(14,row);
  for(let row=worldY(10);row<=worldY(16);row++) floorAt(15,row);
  // A two-tile gallery joins all three landings, without isolated skyline holes.
  for(let row=worldY(19);row<=worldY(21);row++)
    for(let col=0;col<=46;col++) if(projectedTiles[row*cols+col]===TileType.VOID) floorAt(col,row);
  // Physical room dividers: raised sprites and navigation use these SAME cells.
  // Keep the two generous atrium doors and the established south approaches.
  const wallAt=(col:number,row:number)=>{
    projectedTiles[row*cols+col]=TileType.WALL;projectedColors[row*cols+col]=null;
  };
  for(let row=10;row<=18;row++) if(![14,15].includes(row)) wallAt(13,row);
  floorAt(13,14);floorAt(13,15);
  for(let row=9;row<=19;row++) if(![14,15].includes(row)) wallAt(32,row);
  floorAt(32,14);floorAt(32,15);
  // A real glazed boundary separates both upper departments from the gallery.
  for(let col=1;col<=12;col++) if(![6,7].includes(col)) wallAt(col,18);
  // One shared wall, not two touching rows of glass tiles above Tech Lab.
  for(let col=0;col<=13;col++) floorAt(col,19);
  for(let col=33;col<=46;col++) if(![39,40].includes(col)) wallAt(col,17);
  floorAt(39,17);floorAt(40,17);
  // The shared partition between Network and Outreach has one two-tile door.
  floorAt(39,24);floorAt(40,24);
  floorAt(32,23);floorAt(32,27);
  // Close corners on the final grid, after all wing setbacks. Door sprites
  // sit in these openings, never on the adjacent circulation gallery.
  wallAt(15,19);
  floorAt(39,19);floorAt(40,19);
  for(let col=0;col<=46;col++) if(col<22||col>25) wallAt(col,29);

  for(let row=worldY(22);row<=worldY(30);row++) if(![worldY(27),worldY(28)].includes(row)) wallAt(24,row);
  return { version: 1, cols, rows:GOLF_ROWS, tiles:projectedTiles, tileColors:projectedColors, furniture, carpetTiles: [], areas: [], areaTiles: [] };
}

function renderCorridorFloor(ctx: CanvasRenderingContext2D, offsetX: number, offsetY: number, zoom: number): void {
  // The caller clips once to the actual floor map. No duplicate room rectangles
  // or stale corner cuts may expose sky inside a navigable floor tile.
  const width = 48 * TILE_SIZE * zoom, height = GOLF_ROWS * TILE_SIZE * zoom;
  ctx.save();
  ctx.fillStyle = '#9d6532'; ctx.fillRect(offsetX, offsetY, width, height);
  const wood = textiles['oak-night'];
  if (wood) for (let y = 0; y < height; y += 96 * zoom)
    for (let x = 0; x < width; x += 192 * zoom)
      ctx.drawImage(wood, offsetX + x, offsetY + y, 192 * zoom, 96 * zoom);
  ctx.restore();
}

function renderWindowLight(ctx: CanvasRenderingContext2D, offsetX: number, offsetY: number, zoom: number): void {
  const cell = TILE_SIZE * zoom;
  const rooms = [
    { x0: 15, x1: 32, y0: 1, y1: 8 },
    { x0: 1, x1: 12, y0: 10, y1: 18 }, { x0: 16, x1: 31, y0: 10, y1: 18 }, { x0: 32, x1: 46, y0: 9, y1: 17 },
    { x0: 22, x1: 25, y0: 19, y1: 20 },
    { x0: 0, x1: 13, y0: 22, y1: 30 }, { x0: 16, x1: 31, y0: 22, y1: 30 },
    { x0: 33, x1: 46, y0: 22, y1: 26 }, { x0: 33, x1: 46, y0: 27, y1: 30 },
  ];
  ctx.save();
  ctx.globalCompositeOperation = "screen";
  for (const room of rooms) {
    const top = offsetY + worldY(room.y0) * cell, bottom = offsetY + (worldY(room.y1)+1) * cell;
    ctx.save();
    ctx.beginPath();
    ctx.rect(offsetX + room.x0 * cell, top, (room.x1 - room.x0 + 1) * cell, bottom - top);
    ctx.clip();
    for (const side of [0, 1]) {
      const start = room.x0 + (side === 0 ? 2 : room.x1 - room.x0 - 2);
      const end = start + (side === 0 ? 2.6 : -2.6);
      const gradient = ctx.createLinearGradient(0, top, 0, bottom);
      gradient.addColorStop(0, "rgba(101, 155, 231, 0.07)");
      gradient.addColorStop(0.55, "rgba(101, 155, 231, 0.02)");
      gradient.addColorStop(1, "rgba(101, 155, 231, 0)");
      ctx.fillStyle = gradient;
      ctx.beginPath();
      ctx.moveTo(offsetX + (start - 0.65) * cell, top);
      ctx.lineTo(offsetX + (start + 0.65) * cell, top);
      ctx.lineTo(offsetX + (end + 2.2) * cell, bottom);
      ctx.lineTo(offsetX + (end - 2.2) * cell, bottom);
      ctx.closePath(); ctx.fill();
    }
    ctx.restore();
  }
  ctx.restore();
}

function renderFloorFinishes(ctx: CanvasRenderingContext2D, offsetX: number, offsetY: number, zoom: number): void {
  renderCorridorFloor(ctx, offsetX, offsetY, zoom);
  const cell = TILE_SIZE * zoom;
  for (const [name, x, y, w, h] of [
    ['slate',20,2,8,6], ['ivory',19,10,9,8],
    ['slate',1,23,11,6], ['ivory',19,23,10,6], ['slate',39,22,6,4],
  ] as const) {
    if (textiles[name]) ctx.drawImage(textiles[name],offsetX+x*cell,offsetY+worldY(y)*cell,w*cell,(worldY(y+h)-worldY(y))*cell);
  }
  renderWindowLight(ctx, offsetX, offsetY, zoom);
}

// Light is decorative, independent of agent activity. No fabricated mission signals.
function renderContactShadows(ctx: CanvasRenderingContext2D, ox:number, oy:number, zoom:number, office:OfficeState) {
  ctx.save();
  ctx.beginPath();
  office.tileMap.forEach((row,y)=>row.forEach((tile,x)=>{
    if(tile!==TileType.VOID&&tile!==TileType.WALL)ctx.rect(ox+x*16*zoom,oy+y*16*zoom,16*zoom,16*zoom);
  }));ctx.clip();
  for(const f of office.furniture){
    const w=f.sprite[0]?.length??0, h=f.sprite.length;
    if(w<12||h<10)continue;
    const x=ox+(f.x+3)*zoom,y=oy+(f.y+h-5)*zoom;
    const centre=f.x+w/2,foot=f.y+h-3;
    const lamp=AMBIENT_LAMPS.reduce((near,item)=>Math.hypot(item[0]*16-centre,item[1]*16-foot)<Math.hypot(near[0]*16-centre,near[1]*16-foot)?item:near);
    const vx=centre-lamp[0]*16,vy=foot-lamp[1]*16,length=Math.hypot(vx,vy)||1;
    const dx=vx/length*7*zoom,dy=vy/length*5*zoom;
    ctx.fillStyle='#07101e27';ctx.beginPath();ctx.moveTo(x,y);
    ctx.lineTo(x+(w-4)*zoom,y);ctx.lineTo(x+(w-4)*zoom+dx,y+dy+5*zoom);ctx.lineTo(x+dx,y+dy+5*zoom);ctx.closePath();ctx.fill();
    ctx.fillStyle='#10182328';ctx.fillRect(x-2*zoom,y-2*zoom,(w+1)*zoom,8*zoom);
    ctx.fillStyle='#111b2959';ctx.fillRect(x,y,(w-3)*zoom,4*zoom);
    ctx.fillStyle='#10192324';ctx.fillRect(x+2*zoom,y-zoom,(w-6)*zoom,2*zoom);
  }
  renderNightLight(ctx,ox,oy,zoom,true);
  ctx.restore();
}
function renderLuminaires(ctx:CanvasRenderingContext2D,ox:number,oy:number,zoom:number){
  if(!textiles['lamp-amber'])return;
  ctx.save();
  for(const [x,y] of AMBIENT_LAMPS){
    const px=ox+x*16*zoom,py=oy+y*16*zoom;
    ctx.drawImage(textiles['lamp-amber'],px,py,16*zoom,24*zoom);
    const halo=ctx.createRadialGradient(px+8*zoom,py+8*zoom,0,px+8*zoom,py+8*zoom,9*zoom);
    halo.addColorStop(0,'#fff0bdac');halo.addColorStop(.25,'#ffd07060');halo.addColorStop(.55,'#ffb52e28');halo.addColorStop(1,'#ff982000');
    ctx.fillStyle=halo;ctx.fillRect(px-zoom,py-zoom,18*zoom,18*zoom);
  }
  ctx.restore();
}

function renderEveningLight(ctx:CanvasRenderingContext2D,ox:number,oy:number,zoom:number,office:OfficeState){
  const cell=16*zoom;
  ctx.save();ctx.beginPath();
  // Clip the light pass to real occupied architecture, never the surrounding void/widgets.
  office.tileMap.forEach((row,y)=>row.forEach((tile,x)=>{
    if(tile!==TileType.VOID)ctx.rect(ox+x*cell,oy+y*cell,cell,cell);
  }));
  ctx.clip();
  renderNightLight(ctx,ox,oy,zoom);
  ctx.restore();
}

function renderZoneLabels(ctx: CanvasRenderingContext2D, zoom: number, offsetX: number, offsetY: number): void {
  const labels = [
    { text: "HEAD OF DESK", color: "#b89bff", col: 24, row: 7.35 },
    { text: "GLOBAL MARKETS", color: "#77d8e7", col: 5.5, row: 16.45 },
    { text: "QUANT RESEARCH", color: "#9b8bea", col: 39.5, row: 15.45 },
    { text: "ENGINEERING", color: "#70cbb7", col: 6.5, row: 29.1 },
    { text: "INTERVIEWS", color: "#a995e5", col: 20, row: 29.1 },
    { text: "INNOVATION", color: "#70cbb7", col: 28, row: 29.1 },
    { text: "NETWORK", color: "#70cbb7", col: 40, row: 25.45 },
    { text: "OUTREACH", color: "#77d8e7", col: 40, row: 29.1 },
  ];
  ctx.save();
  const fontSize = Math.max(10, Math.min(13, 8.8 * zoom));
  ctx.font = `600 ${fontSize}px Inter, "Segoe UI", Arial, sans-serif`;
  ctx.textAlign = "center"; ctx.textBaseline = "middle";
  for (const item of labels) {
    const y = offsetY + worldY(item.row) * TILE_SIZE * zoom;
    const x = projectTowerX(offsetX + item.col * TILE_SIZE * zoom, y, offsetX, offsetY, zoom);
    const textWidth = ctx.measureText(item.text).width;
    const mark = Math.max(2, zoom * 1.05), gap = Math.max(3, zoom * 1.5);
    const padX = Math.max(4, zoom * 2.2), padY = Math.max(3, zoom * 1.35);
    const width = textWidth + mark + gap + padX * 2, height = fontSize + padY * 2;
    const left = x - width / 2, top = y - height / 2;
    // Compact wayfinding plaques echo the dark interface without obscuring the floor.
    ctx.fillStyle = "rgba(9, 19, 31, 0.96)";
    ctx.fillRect(left, top, width, height);
    ctx.lineWidth = Math.max(0.8, zoom * 0.35);
    ctx.strokeStyle = item.color + "b8";
    ctx.strokeRect(left, top, width, height);
    ctx.fillStyle = item.color;
    ctx.fillRect(left + padX, y - mark / 2, mark, mark);
    ctx.fillStyle = "#edf4fa";
    ctx.fillText(item.text, x + (mark + gap) / 2, y);
  }
  ctx.restore();
}

function renderMarketDecor(ctx: CanvasRenderingContext2D, zoom: number, offsetX: number, offsetY: number,
  marketPoints: MarketReading[], _marketRetrievedAt: string, _marketError: string | undefined,
  featured: FeaturedOffer | null, offerIndex: number, offerCount: number, internshipError?: string): void {
  const cell = TILE_SIZE * zoom;
  const panel = (geometry: typeof MARKET_PANEL, accent: string) => {
    const x = offsetX + geometry.col * cell, y = offsetY + geometry.top * cell;
    const w = geometry.width * cell, h = geometry.height * cell;
    ctx.save();
    // A metal chassis, sill and short mounts physically anchor the LED panel.
    ctx.fillStyle='#020916b8';ctx.fillRect(x+cell*.18,y+cell*.2,w,h);
    ctx.fillStyle='#28545a';ctx.fillRect(x-cell*.14,y-cell*.14,w+cell*.28,h+cell*.28);
    const glass=ctx.createLinearGradient(x,y,x+w,y+h);
    glass.addColorStop(0,'#102e32f5');glass.addColorStop(1,'#091b24f5');
    ctx.fillStyle=glass;ctx.fillRect(x,y,w,h);
    ctx.strokeStyle='#5d8985';ctx.lineWidth=Math.max(1,zoom*.55);ctx.strokeRect(x,y,w,h);
    ctx.fillStyle='#35656a';ctx.fillRect(x-cell*.14,y+h+cell*.09,w+cell*.28,cell*.1);
    for(const bx of [x+cell*.8,x+w-cell*1.1]){
      ctx.fillStyle='#17363a';ctx.fillRect(bx,y+h+cell*.19,cell*.3,cell*.7);
      ctx.fillStyle='#608d87';ctx.fillRect(bx,y+h+cell*.19,cell*.07,cell*.7);
    }
    ctx.shadowColor=accent;ctx.shadowBlur=cell*.17;
    ctx.fillStyle=accent;ctx.fillRect(x,y+cell*.28,Math.max(1.5,cell*.065),h-cell*.56);
    ctx.restore();return {x,y,w,h};
  };
  const write = (value: string, x: number, y: number, color: string, size: number, weight = "normal", maxWidth?: number) => {
    ctx.textAlign = "left";
    ctx.textBaseline = "middle";
    ctx.fillStyle = color;
    ctx.font = `${weight} ${Math.max(zoom < .7 ? 5.5 : 9.5, size * zoom)}px Inter, Arial, sans-serif`;
    // Truncate rather than horizontally distorting the type.
    let text = value;
    if (maxWidth && ctx.measureText(text).width > maxWidth) {
      while (text.length && ctx.measureText(text + "…").width > maxWidth) text = text.slice(0, -1);
      text += "…";
    }
    ctx.fillText(text, x, y);
  };
  const market = panel(MARKET_PANEL, "#75f0df");
  const jobs = panel(OFFERS_PANEL, "#27d9b3");
  const items = [
    {id:"SP500", label:"S&P 500", decimals:1},
    {id:"DGS10", label:"10Y UST", decimals:2},
    {id:"DEXUSEU", label:"EUR/USD", decimals:4},
    {id:"DCOILWTICO", label:"WTI", decimals:1},
  ];
  const gap = cell * 0.34;
  const slot = (market.w - gap * 2) / items.length;
  write("MARKET BRIEF", market.x + cell * .52, market.y + cell * .55, "#75f0df", 8.3, "700");
  const centered = (text: string, x: number, y: number, color: string, size: number, weight: string) => {
    ctx.font = `${weight} ${Math.max(zoom < .7 ? 5.5 : 9.5, size * zoom)}px Inter, Arial, sans-serif`;
    write(text, x - ctx.measureText(text).width / 2, y, color, size, weight);
  };
  items.forEach((item, index) => {
    const x = market.x + gap + (index + .5) * slot;
    const point = marketPoints.find(reading => reading.series_id === item.id);
    if (index) {
      ctx.fillStyle = "#b4c5d31f";
      ctx.fillRect(x - slot * .5, market.y + cell * 1.15, Math.max(1, zoom * 0.4), cell * 2.25);
    }
    centered(item.label, x, market.y + cell * 1.4, "#bdcbe0", 7.3, "600");
    if (!point || !Number.isFinite(point.value)) {
      centered("—", x, market.y + cell * 2.2, "#e5edf4", 8, "700");
      centered("N/D", x, market.y + cell * 3.05, "#94a7b8", 5, "500");
      return;
    }
    const value = point.value.toLocaleString("en-GB", {minimumFractionDigits:item.decimals, maximumFractionDigits:item.decimals});
    const delta = point.change != null && point.previous != null && point.previous !== 0
      ? item.id === "DGS10"
        ? `${point.change >= 0 ? "+" : ""}${(point.change * 100).toFixed(0)} bp`
        : `${point.change >= 0 ? "+" : ""}${(point.change / point.previous * 100).toFixed(1)}%`
      : "—";
    centered(value + (item.id === "DGS10" ? "%" : ""), x, market.y + cell * 2.2, "#f4f7fb", 12.6, "700");
    centered(delta, x, market.y + cell * 3.05,
      point.change == null ? "#a8b6c3" : point.change >= 0 ? "#41ecc4" : "#ff665e",
      8, "700");
    if(point.previous != null && Number.isFinite(point.previous)) {
      const rising=point.value>=point.previous;
      const left=x-slot*.31,right=x+slot*.31,base=market.y+cell*4.35;
      ctx.strokeStyle='#94b4c72e';ctx.lineWidth=Math.max(1,zoom*.4);
      ctx.beginPath();ctx.moveTo(left,base);ctx.lineTo(right,base);ctx.stroke();
      ctx.strokeStyle=rising?'#41ecc4':'#ff665e';ctx.lineWidth=Math.max(1,zoom*.7);
      ctx.beginPath();ctx.moveTo(left,base-(rising?.08:.38)*cell);ctx.lineTo(right,base-(rising?.38:.08)*cell);ctx.stroke();
      ctx.fillStyle=ctx.strokeStyle;ctx.fillRect(right-zoom,base-(rising?.38:.08)*cell-zoom,2*zoom,2*zoom);
    }
  });

  const x = jobs.x + cell * 0.62;
  const max = jobs.w - cell * 1.25;
  write("OPPORTUNITÉ DU JOUR", x, jobs.y + cell * 0.55, "#75f0df", 7.8, "700", max);
  if (!featured) {
    write(internshipError ? "Offres temporairement indisponibles" : "Aucune offre à afficher",
      x, jobs.y + cell * 2.0, "#c1ccd7", 5, "500", max);
    return;
  }
  write(featured.company || "Entreprise non indiquée", x, jobs.y + cell * 1.3, "#f2f5fa", 12, "700", max);
  ctx.font = `500 ${Math.max(zoom < .7 ? 5.5 : 9.5, 8.7 * zoom)}px Inter, Arial, sans-serif`;
  const words = featured.title.split(/\s+/);
  let line = "";
  while (words.length && ctx.measureText([line, words[0]].filter(Boolean).join(" ")).width <= max) line += (line ? " " : "") + words.shift();
  if (!line) line = words.shift() || "";
  write(line, x, jobs.y + cell * 2.05, "#e5eaf2", 8.7, "500", max);
  write(words.join(" "), x, jobs.y + cell * 2.78, "#e5eaf2", 8.7, "500", max);
  write(featured.location || "Lieu non indiqué", x, jobs.y + cell * 3.55, "#c5d1e4", 7.5, "500", max);
  write("Voir l’offre ↗", x, jobs.y + cell * 4.35, "#75f0df", 7.5, "600", max * .5);
  if (offerCount > 1) {
    const navY = jobs.y + cell * 4.35;
    const buttonW = cell * 0.88, buttonH = cell * 0.58;
    const prevX = jobs.x + jobs.w - cell * 2.62;
    const nextX = jobs.x + jobs.w - cell * 1.48;
    ctx.save();
    ctx.textBaseline = "middle";
    ctx.textAlign = "center";
    ctx.font = `700 ${Math.max(6, 5 * zoom)}px Inter, Arial, sans-serif`;
    for (const [label, bx] of [["‹", prevX], ["›", nextX]] as const) {
      ctx.fillStyle = "#19494f";
      ctx.fillRect(bx, navY - buttonH / 2, buttonW, buttonH);
      ctx.strokeStyle = "#83cbd9a0";
      ctx.lineWidth = Math.max(1, zoom * 0.35);
      ctx.strokeRect(bx, navY - buttonH / 2, buttonW, buttonH);
      ctx.fillStyle = "#edf5fa";
      ctx.fillText(label, bx + buttonW / 2, navY);
    }
    ctx.textAlign = "right";
    ctx.fillStyle = "#a6b5c4";
    ctx.fillText(`${offerIndex + 1} / ${offerCount}`, prevX - cell * 0.2, navY);
    ctx.restore();
  }
}

function renderTaskLabels(ctx: CanvasRenderingContext2D, zoom: number, offsetX: number, offsetY: number,
  office: OfficeState, agents: Agent[], tasks: Task[]): void {
  ctx.save();
  ctx.font = `bold ${Math.max(7, 6 * zoom)}px ui-monospace, monospace`;
  ctx.textAlign = "center"; ctx.textBaseline = "middle";
  for (const agent of agents) {
    if (agent.status !== "running" && agent.status !== "waiting_approval") continue;
    const character = office.characters.get(agentIndex(agent.id));
    const task = tasks.find(item => item.agent_id === agent.id && item.status === agent.status);
    const description = task?.description?.trim();
    if (!character || !description) continue;
    const label = description.length > 30 ? `${description.slice(0, 29).trimEnd()}…` : description;
    const x = offsetX + character.x * zoom, y = offsetY + (character.y - 25) * zoom;
    const width = ctx.measureText(label).width + 10 * zoom, height = 12 * zoom;
    ctx.fillStyle = "#07101def"; ctx.fillRect(x - width / 2, y - height / 2, width, height);
    ctx.strokeStyle = agent.status === "waiting_approval" ? "#ffd173" : "#65eaff";
    ctx.shadowColor = ctx.strokeStyle; ctx.shadowBlur = zoom * 5;
    ctx.lineWidth = Math.max(1.5, zoom * 0.55); ctx.strokeRect(x - width / 2, y - height / 2, width, height);
    ctx.fillStyle = agent.status === "waiting_approval" ? "#f3cc82" : "#b9f4ff"; ctx.fillText(label, x, y);
  }
  ctx.restore();
}

function adjacentWalkable(office: OfficeState, targetId: number, fromId: number): { col: number; row: number } | null {
  const target = office.characters.get(targetId), source = office.characters.get(fromId);
  if (!target || !source) return null;
  return office.walkableTiles.filter(tile => Math.abs(tile.col - target.tileCol) + Math.abs(tile.row - target.tileRow) === 1)
    .sort((a, b) => (Math.abs(a.col - source.tileCol) + Math.abs(a.row - source.tileRow)) - (Math.abs(b.col - source.tileCol) + Math.abs(b.row - source.tileRow)))[0] ?? null;
}

function workstationAgentAt(office: OfficeState, x: number, y: number): number | null {
  const col = Math.floor(x / TILE_SIZE), row = Math.floor(y / TILE_SIZE);
  for (const [seatId, seat] of office.seats) {
    const owner = [...office.characters.values()].find(character => character.seatId === seatId);
    const fromSeatCol = col - seat.seatCol, fromSeatRow = row - seat.seatRow;
    if (owner && ((Math.abs(fromSeatCol) <= 2 && fromSeatRow >= -2 && fromSeatRow <= 1) ||
      (fromSeatCol >= 4 && fromSeatCol <= 6 && fromSeatRow >= -1 && fromSeatRow <= 2))) return owner.id;
  }
  return null;
}

export function validateAgentRoutes(office: OfficeState): void {
  const hub = { col: 23, row: worldY(19) };
  if (!office.walkableTiles.some(tile => tile.col === hub.col && tile.row === hub.row)) {
    throw new Error("Le passage central du plan n'est pas praticable.");
  }
  const walkable = new Set(office.walkableTiles.map(tile => `${tile.col},${tile.row}`));
  const links = [
    [23,30],[23,31],[23,32],[23,33],[23,34],
    [23, 9], [23, 10], [15, 14], [32, 14],
    [23, 19], [23, 20], [23, 21],
    [7, 19], [7, 20], [7, 21], [39, 19], [39, 20], [39, 21],
    [31, 24], [32, 24], [33, 24], [31, 28], [32, 28], [33, 28], [39, 26],
  ];
  for (const [col, rawRow] of links) {
    const row=worldY(rawRow);
    if (!walkable.has(`${col},${row}`)) throw new Error(`Un passage du plan est bloqué (${col}, ${row}).`);
  }

  // Detect furniture that ended up outside the floor or overlaps another
  // blocking object. Surface items such as coffee cups may intentionally sit
  // on tables; wall-mounted display rows are deliberately non-blocking.
  const occupied = new Map<string, string>();
  const furnitureIssues: string[] = [];
  for (const item of office.layout.furniture) {
    const entry = getCatalogEntry(item.type);
    if (!entry) throw new Error(`Mobilier introuvable dans le plan : ${item.type}.`);
    const backgroundRows = entry.backgroundTiles ?? 0;
    if (entry.canPlaceOnSurfaces) continue;
    for (let dr = backgroundRows; dr < entry.footprintH; dr++) for (let dc = 0; dc < entry.footprintW; dc++) {
      const col = item.col + dc, row = item.row + dr;
      const tile = office.tileMap[row]?.[col];
      if (tile === undefined || tile === TileType.VOID || tile === TileType.WALL) {
        furnitureIssues.push(`Le mobilier ${item.uid} deborde d'une salle (${col}, ${row}).`);
        continue;
      }
      const key = `${col},${row}`;
      const previous = occupied.get(key);
      if (previous) furnitureIssues.push(`Mobilier superpose : ${previous} et ${item.uid} (${col}, ${row}).`);
      else occupied.set(key, item.uid);
    }
  }
  if (furnitureIssues.length) {
    throw new Error(`Le plan contient ${furnitureIssues.length} probleme(s) de mobilier :\n${furnitureIssues.join("\n")}`);
  }
  // Flood-fill once from the hub, then validate every workstation. This
  // reports all disconnected seats in one restart instead of failing on the
  // first one and revealing the next error only after another reload.
  const reachable = new Set<string>([`${hub.col},${hub.row}`]);
  const queue = [hub];
  for (let index = 0; index < queue.length; index++) {
    const current = queue[index];
    for (const [dc, dr] of [[0, -1], [0, 1], [-1, 0], [1, 0]]) {
      const col = current.col + dc, row = current.row + dr, key = `${col},${row}`;
      if (reachable.has(key) || !walkable.has(key)) continue;
      reachable.add(key);
      queue.push({ col, row });
    }
  }

  const routeIssues: string[] = [];
  for (const id of WORLD_ROSTER) {
    const seat = office.seats.get(agentSeatId(id));
    if (!seat) {
      routeIssues.push(`poste absent : ${id}`);
      continue;
    }
    const approaches = office.walkableTiles.filter(tile =>
      Math.abs(tile.col - seat.seatCol) + Math.abs(tile.row - seat.seatRow) === 1);
    if (!approaches.some(tile => reachable.has(`${tile.col},${tile.row}`))) {
      const nearby = approaches.length
        ? approaches.map(tile => `${tile.col},${tile.row}`).join(" / ")
        : "aucune case d'approche praticable";
      routeIssues.push(`${id} (${seat.seatCol}, ${seat.seatRow}; acces: ${nearby})`);
    }
  }
  if (routeIssues.length) {
    throw new Error(`Postes non accessibles depuis le passage central :\n${routeIssues.join("\n")}`);
  }
}

export function PixelFloorGame(props: Props): React.ReactElement {
  const canvas = useRef<HTMLCanvasElement>(null);
  const runtime = useRef<Runtime | null>(null);
  const pick = useRef(props.onPick); pick.current = props.onPick;
  const selected = useRef(props.selectedId); selected.current = props.selectedId;
  const latest = useRef(props); latest.current = props;
  const lastStatuses = useRef(new Map<string, AgentStatus>());
  const lastEvent = useRef<number | null>(null);
  const visits = useRef(new Map<string, number>());
  const [ready, setReady] = useState(false);
  const [loadError, setLoadError] = useState("");
  const [offerIndex, setOfferIndex] = useState(0);
  const offerIndexRef = useRef(offerIndex);
  offerIndexRef.current = offerIndex;
  const offerKey = props.featuredOffers.map(offer => offer.url).join("|");
  useEffect(() => setOfferIndex(0), [offerKey]);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const characters = await loadCharacterSheets();
        setCharacterTemplates(characters);
        await Promise.all([loadFurniture(), loadEnvironmentSprites(), loadTextiles(), loadTowerArchitecture()]);
        const office = new OfficeState(buildOfficeLayout());
        validateAgentRoutes(office);
        WORLD_ROSTER.forEach((id, index) => {
          const seatId = agentSeatId(id);
          if (!office.seats.has(seatId)) throw new Error(`Le poste fixe de ${id} est absent du plan.`);
          office.addAgent(index, id === MANAGER_ID ? 5 : id === "innovation_lab" ? 4 : index % 6, id === MANAGER_ID ? 250 : id === "innovation_lab" ? 120 : id === "internship_scout" ? 200 : 0, seatId, true);
          office.setAgentPinned(index, true);
          office.setAgentActive(index, false);
          office.setAgentTool(index, null);
        });
        const golf = new GolfPractice(office, WORLD_ROSTER);
        await golf.load();
        if (cancelled) return;
        runtime.current = { office, golf, zoom: 1, zoomTarget: 1, scale: 1, offsetX: 0, offsetY: 0 };
        setReady(true);
      } catch (error) {
        if (!cancelled) setLoadError(error instanceof Error ? error.message : "Pixel Agents n’a pas pu charger ses sprites.");
      }
    })();
    return () => { cancelled = true; runtime.current = null; };
  }, []);

  useEffect(() => {
    if (!ready || !canvas.current) return;
    const node = canvas.current;
    const resize = () => {
      // Native pixel art gains little from unbounded Retina raster surfaces.
      const rect = node.getBoundingClientRect(), dpr = Math.min(window.devicePixelRatio || 1, 1.5);
      node.width = Math.max(1, Math.round(rect.width * dpr));
      node.height = Math.max(1, Math.round(rect.height * dpr));
    };
    resize();
    const observer = new ResizeObserver(resize); observer.observe(node);
    const floor = runtime.current?.office;
    if (!floor) return () => observer.disconnect();
    const worldCanvas=document.createElement('canvas');
    const worldContext=worldCanvas.getContext('2d')!;
    // The immutable floor/facade pass is cached at native resolution, with
    // margins for exterior fins and the crown. Moving sprites are never baked.
    const layout=floor.getLayout(), margin=64;
    const floorCanvas=document.createElement('canvas');
    floorCanvas.width=layout.cols*TILE_SIZE+2*margin;
    floorCanvas.height=layout.rows*TILE_SIZE+2*margin;
    const floorContext=floorCanvas.getContext('2d')!;
    renderTileGrid(floorContext,floor.tileMap,margin,margin,1,layout.tileColors,layout.cols);
    // Foundations continue beneath thin walls; their transparent glass must
    // reveal the indoor floor, never the skyline behind the building.
    floorContext.save();floorContext.beginPath();
    floor.tileMap.forEach((row,y)=>row.forEach((tile,x)=>{
      if(tile!==TileType.VOID)
        floorContext.rect(margin+x*TILE_SIZE,margin+y*TILE_SIZE,TILE_SIZE,TILE_SIZE);
    }));
    floorContext.clip();renderFloorFinishes(floorContext,margin,margin,1);floorContext.restore();
    renderTowerArchitecture(floorContext,margin,margin,1,floor.tileMap);
    renderTowerRelief(floorContext,margin,margin,1,floor.tileMap);
    renderContactShadows(floorContext,margin,margin,1,floor);
    runtime.current?.golf.renderFloor(floorContext,margin,margin,1);
    node.dataset.worldRows=String(floor.getLayout().rows);
    node.dataset.worldCols=String(floor.getLayout().cols);
    const stop = startGameLoop(node, {
      update: dt => {
        runtime.current?.golf.update(dt,new Set(visits.current.values()));
        floor.update(dt);
        const golfers=runtime.current?.golf.visits;
        const description=`Practice : ${golfers?.size??0} agent(s) en pause, dont ${[...(golfers?.values()??[])].filter(v=>v.stage==='playing').length} sur un tapis. Les pauses ne sont pas des missions IA.`;
        if(node.getAttribute('aria-description')!==description)node.setAttribute('aria-description',description);
      },
      render: output => {
        const ctx=worldContext;
        const layout = floor.getLayout();
        // Include the projecting roof crown in the fixed camera's visible bounds.
        const fitScale = Math.min(node.width / (layout.cols * TILE_SIZE), node.height / ((towerDisplayRows(layout.rows) + 1) * TILE_SIZE)) * 0.99;
        const live = runtime.current;
        if (live) {
          live.zoom += (live.zoomTarget - live.zoom) * 0.18;
          if (Math.abs(live.zoomTarget - live.zoom) < 0.002) live.zoom = live.zoomTarget;
        }
        const scale = fitScale * (live?.zoom ?? 1);
        const virtualHeight=Math.ceil(node.height+(layout.rows-towerDisplayRows(layout.rows))*TILE_SIZE*scale);
        if(worldCanvas.width!==node.width||worldCanvas.height!==virtualHeight){
          worldCanvas.width=node.width;worldCanvas.height=virtualHeight;
        }
        const index = agentIndex(selected.current);
        const selection: SelectionRenderState = { selectedAgentId: index < 0 ? null : index, hoveredAgentId: floor.hoveredAgentId,
          hoveredTile: null, seats: floor.seats, characters: floor.characters };
        const position = renderFrame(ctx, node.width, virtualHeight, floor.tileMap, floor.furniture, floor.getCharacters(), scale,
          0, 0, selection, undefined, layout.tileColors, layout.cols, layout.rows, layout.carpetTiles, layout.areas,
          layout.areaTiles, false, null, floor.pets, undefined, {image:floorCanvas,margin});
        renderEveningLight(ctx,position.offsetX,position.offsetY,scale,floor);
        renderLuminaires(ctx,position.offsetX,position.offsetY,scale);
        runtime.current?.golf.render(ctx,position.offsetX,position.offsetY,scale);
        const offers = latest.current.featuredOffers;
        const visibleOffer = offers.length ? offers[Math.min(offerIndexRef.current, offers.length - 1)] : null;

        if (live) {
          live.scale = scale; live.offsetX = position.offsetX; live.offsetY = position.offsetY;
          node.dataset.viewScale=String(scale);node.dataset.viewX=String(position.offsetX);node.dataset.viewY=String(position.offsetY);
          renderTaskLabels(ctx, scale, position.offsetX, position.offsetY, floor, latest.current.agents, latest.current.tasks);
        }
        output.clearRect(0,0,node.width,node.height);
        renderTowerBackdrop(output,position.offsetX,position.offsetY,scale);
        renderTowerPerspective(output,worldCanvas,position.offsetX,position.offsetY,scale);
        renderTowerSign(output,position.offsetX,position.offsetY,scale);
        renderZoneLabels(output,scale,position.offsetX,position.offsetY);
        const focus=floor.characters.get(index),agent=latest.current.agents.find(a=>a.id===selected.current);
        if(focus&&agent){
          const y=position.offsetY+focus.y*scale;
          const x=projectTowerX(position.offsetX+focus.x*scale,y,position.offsetX,position.offsetY,scale);
          output.save();output.strokeStyle='#8ee5ee';output.lineWidth=1.5;
          output.beginPath();output.ellipse(x,y+5*scale,10*scale,4*scale,0,0,Math.PI*2);output.stroke();
          output.font='600 12px Inter, "Segoe UI", sans-serif';
          const width=output.measureText(agent.name).width+18,top=y-32*scale-22;
          output.fillStyle='#0c2136f2';output.fillRect(x-width/2,top,width,22);
          output.strokeRect(x-width/2,top,width,22);
          output.textAlign='center';output.textBaseline='middle';output.fillStyle='#e5fbff';
          output.fillText(agent.name,x,top+11);output.restore();
        }
        // Billboards face the viewer: keep their type on a flat, legible plane.
        renderMarketDecor(output,scale,position.offsetX,position.offsetY,latest.current.marketPoints,
          latest.current.marketRetrievedAt,latest.current.marketError,visibleOffer,offerIndexRef.current,
          offers.length,latest.current.internshipError);
      },
    });
    return () => { stop(); observer.disconnect(); };
  }, [ready]);

  useEffect(() => {
    const floor = runtime.current?.office;
    if (!ready || !floor) return;
    runtime.current?.golf.sync(props.agents,props.tasks);
    const agentsById = new Map(props.agents.map(agent => [agent.id, agent]));
    for (const id of WORLD_ROSTER) {
      const index = agentIndex(id);
      const status = agentsById.get(id)?.status ?? "idle";
      if (lastStatuses.current.get(id) === status) continue;
      lastStatuses.current.set(id, status);
      floor.setAgentActive(index, status === "running");
      // Generic activity strings are not real tool events; live task labels
      // below are sourced only from the matching FastAPI task record.
      floor.setAgentTool(index, null);
      if (status === "waiting_approval") floor.showPermissionBubble(index);
      else floor.clearPermissionBubble(index);
    }
    if(props.tasks.some(task=>task.status === "waiting_approval" || (task.status === "completed" &&
      (task.result as {approval_required?:boolean;role_version?:number;review_decision?:string;branch?:string}|undefined)?.role_version === 2 &&
      (task.result as {approval_required?:boolean})?.approval_required && !(task.result as {review_decision?:string})?.review_decision && !(task.result as {branch?:string})?.branch))) floor.showPermissionBubble(agentIndex(MANAGER_ID));
    else floor.clearPermissionBubble(agentIndex(MANAGER_ID));
    const newest = Math.max(0, ...props.events.map(event => event.id));
    if (lastEvent.current === null) { lastEvent.current = newest; return; }
    for (const event of props.events.filter(item => item.id > lastEvent.current!)) {
      const task = props.tasks.find(item => item.id === event.task_id);
      if (!task) continue;
      const target = agentIndex(task.agent_id);
      const sourceIds = (task.depends_on ?? []).map(id => props.tasks.find(item => item.id === id)?.agent_id).filter((id): id is string => !!id);
      if (!sourceIds.length && task.delegated_by) sourceIds.push(task.delegated_by);
      const sources = sourceIds.map(agentIndex).filter(index => index >= 0 && index !== target);
      if (event.status === "running" && target >= 0) {
        for (const source of sources) {
          runtime.current?.golf.interrupt(source);
          const waypoint = adjacentWalkable(floor, target, source);
          if (waypoint && floor.walkToTile(source, waypoint.col, waypoint.row)) visits.current.set(task.id, source);
        }
      }
      if (["completed", "failed", "cancelled"].includes(event.status)) {
        const visitor = visits.current.get(task.id);
        if (visitor !== undefined) { floor.sendToSeat(visitor); visits.current.delete(task.id); }
      }
    }
    lastEvent.current = newest;
  }, [ready, props.agents, props.events, props.tasks]);

  const pickAt = (event: React.MouseEvent<HTMLCanvasElement>) => {
    const live = runtime.current, node = canvas.current;
    if (!live || !node) return;
    const rect = node.getBoundingClientRect(), dpr = node.width / rect.width;
    const screenY=unprojectTowerY((event.clientY-rect.top)*dpr,live.offsetY,live.scale);
    const x = (unprojectTowerX((event.clientX-rect.left)*dpr,screenY,live.offsetX,live.offsetY,live.scale)-live.offsetX)/live.scale;
    const y = (screenY - live.offsetY) / live.scale;
    const tileX = ((event.clientX-rect.left)*dpr-live.offsetX)/live.scale/TILE_SIZE, tileY = y / TILE_SIZE;
    if (tileX >= MARKET_PANEL.col && tileX <= MARKET_PANEL.col + MARKET_PANEL.width &&
      tileY >= MARKET_PANEL.top && tileY <= MARKET_PANEL.top + MARKET_PANEL.height) {
      pick.current("market_analyst");
      return;
    }
    const offers = latest.current.featuredOffers;
    if (tileX >= OFFERS_PANEL.col && tileX <= OFFERS_PANEL.col + OFFERS_PANEL.width &&
      tileY >= OFFERS_PANEL.top && tileY <= OFFERS_PANEL.top + OFFERS_PANEL.height) {
      const prevX = OFFERS_PANEL.col + OFFERS_PANEL.width - 2.62;
      const nextX = OFFERS_PANEL.col + OFFERS_PANEL.width - 1.48;
      if (offers.length > 1 && tileY >= OFFERS_PANEL.top + 4.06 && tileY <= OFFERS_PANEL.top + 4.65) {
        if (tileX >= prevX && tileX <= prevX + 0.88) {
          setOfferIndex((offerIndexRef.current - 1 + offers.length) % offers.length);
          return;
        }
        if (tileX >= nextX && tileX <= nextX + 0.88) {
          setOfferIndex((offerIndexRef.current + 1) % offers.length);
          return;
        }
      }
      const offer = offers[Math.min(offerIndexRef.current, offers.length - 1)];
      try {
        const url = new URL(offer?.url || "");
        if (url.protocol === "https:" || url.protocol === "http:") window.open(url.href, "_blank", "noopener,noreferrer");
      } catch { /* Ignore a malformed job link. */ }
      return;
    }
    const agents = live.office.getCharacters().filter(character => !character.isSubagent && character.id >= 0 && character.id < WORLD_ROSTER.length);
    const hit = agents.find(character => Math.abs(x - character.x) <= 11 && Math.abs(y - character.y) <= 18);
    if (hit) { pick.current(WORLD_ROSTER[hit.id]); return; }
    const owner = workstationAgentAt(live.office, x, y);
    if (owner !== null) pick.current(WORLD_ROSTER[owner]);
  };

  const hoverAt = (event: React.MouseEvent<HTMLCanvasElement>) => {
    const live = runtime.current, node = canvas.current;
    if (!live || !node) return;
    const rect = node.getBoundingClientRect(), dpr = node.width / rect.width;
    const screenY=unprojectTowerY((event.clientY-rect.top)*dpr,live.offsetY,live.scale);
    const x = (unprojectTowerX((event.clientX-rect.left)*dpr,screenY,live.offsetX,live.offsetY,live.scale)-live.offsetX)/live.scale;
    const y = (screenY - live.offsetY) / live.scale;
    const tileX = ((event.clientX-rect.left)*dpr-live.offsetX)/live.scale/TILE_SIZE, tileY = y / TILE_SIZE;
    if (tileX >= MARKET_PANEL.col && tileX <= MARKET_PANEL.col + MARKET_PANEL.width &&
      tileY >= MARKET_PANEL.top && tileY <= MARKET_PANEL.top + MARKET_PANEL.height) {
      node.style.cursor = "pointer";
      const labels = ["S&P 500", "10Y UST", "EUR/USD", "WTI"];
      const gap = 0.34;
      const slot = (MARKET_PANEL.width - gap * 2) / labels.length;
      const index = Math.max(0, Math.min(labels.length - 1, Math.floor((tileX - MARKET_PANEL.col - gap) / slot)));
      const ids = ["SP500", "DGS10", "DEXUSEU", "DCOILWTICO"];
      const point = latest.current.marketPoints.find(item => item.series_id === ids[index]);
      node.title = point
        ? `${labels[index]} · ${point.value} ${point.unit}\nVariation : ${point.change == null ? "non disponible" : point.change}\nObservation : ${point.observed_at || "date inconnue"}\nSource : ${point.source || "source non indiquée"}`
        : `${labels[index]} · donnée temporairement indisponible${latest.current.marketError ? `\n${latest.current.marketError}` : ""}`;
      return;
    }
    const offers = latest.current.featuredOffers;
    if (tileX >= OFFERS_PANEL.col && tileX <= OFFERS_PANEL.col + OFFERS_PANEL.width &&
      tileY >= OFFERS_PANEL.top && tileY <= OFFERS_PANEL.top + OFFERS_PANEL.height) {
      node.style.cursor = "pointer";
      const offer = offers[Math.min(offerIndexRef.current, offers.length - 1)];
      const prevX = OFFERS_PANEL.col + OFFERS_PANEL.width - 2.62;
      const nextX = OFFERS_PANEL.col + OFFERS_PANEL.width - 1.48;
      const isPager = offers.length > 1 && tileY >= OFFERS_PANEL.top + 4.06 && tileY <= OFFERS_PANEL.top + 4.65 &&
        (tileX >= prevX && tileX <= prevX + 0.88 || tileX >= nextX && tileX <= nextX + 0.88);
      node.title = isPager ? "Parcourir les offres" : offer
        ? `${offer.company} — ${offer.title}\n${offer.location || "Lieu non indiqué"}\nContrat : ${offer.kind || "non indiqué"}\nDébut : ${offer.start_period || "non indiqué"}\nPublication : ${offer.published ? offer.published_inferred ? `date estimée à la détection (${offer.published})` : offer.published : "non indiquée"}\nSource : ${offer.source || "non indiquée"}${offer.selection_reason ? `\n${offer.selection_reason}` : ""}`
        : latest.current.internshipError || "Aucune offre disponible";
      return;
    }
    node.title = "Clique sur un agent ou un poste de travail pour le sélectionner.";
    const hit = live.office.getCharacters().find(character => character.id >= 0 && character.id < WORLD_ROSTER.length && Math.abs(x - character.x) <= 11 && Math.abs(y - character.y) <= 18);
    live.office.hoveredAgentId = hit?.id ?? null;
    if (node) node.style.cursor = hit || workstationAgentAt(live.office, x, y) !== null ? "pointer" : "default";
  };

  return <div className="tower-game pixelagents-game" role="application" aria-label="MarketDesk City, bureau Pixel Agents animé">
    <canvas ref={canvas} tabIndex={0} onClick={pickAt} onMouseMove={hoverAt} onKeyDown={event => {
      if (event.key === "ArrowLeft" || event.key === "ArrowRight") {
        const count = latest.current.featuredOffers.length;
        if (count > 1) {
          event.preventDefault();
          setOfferIndex((offerIndexRef.current + (event.key === "ArrowRight" ? 1 : -1) + count) % count);
        }
      } else if (event.key === "Enter") {
        const offer = latest.current.featuredOffers[Math.min(offerIndexRef.current, latest.current.featuredOffers.length - 1)];
        if (offer?.url) window.open(offer.url, "_blank", "noopener,noreferrer");
      }
    }} onWheel={event => {
      event.preventDefault();
      if (runtime.current) runtime.current.zoomTarget = Math.min(1.8, Math.max(1, runtime.current.zoomTarget * Math.exp(-event.deltaY * 0.001)));
    }} onMouseLeave={() => { if (runtime.current) runtime.current.office.hoveredAgentId = null; }} />
    {loadError && <div className="pixelagents-error" role="alert">Chargement du bureau impossible : {loadError}</div>}
  </div>;
}
