import { mkdir, writeFile } from 'node:fs/promises';
import { dirname, resolve } from 'node:path';
import { deflateSync } from 'node:zlib';

const out = resolve('internships_project/city_assets/pixel-agents/assets/furniture/MARKETDESK_PACK');
const C = {
  ink: '#111a25', outline: '#263544', edge: '#415365', metal: '#526779', metalHi: '#8498a7',
  desk: '#514333', wood: '#8b6d4d', woodHi: '#c3a27a', woodLit: '#dfc49b',
  screen: '#08131f', screenHi: '#142434', cyan: '#55d3e0', blue: '#62aee8', green: '#70d695',
  red: '#df7180', gold: '#e0b766', violet: '#b594ed', paper: '#dfd8c9', muted: '#8fa4b2',
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
    data[i] = p[0]; data[i + 1] = p[1]; data[i + 2] = p[2]; data[i + 3] = p[3];
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

function chart(c, x, y, w, h, color, seed = 1) {
  c.rect(x, y + h - 2, w, 1, '#70818f66');
  c.rect(x, y + Math.floor(h / 2), w, 1, '#70818f33');
  const pts = [];
  for (let i = 0; i < w; i += 2) {
    const wave = Math.sin((i + seed * 3) * 0.38) * 2 + Math.sin((i + seed) * 0.13) * 2;
    pts.push([x + i, Math.max(y + 2, Math.min(y + h - 4, Math.floor(y + h * 0.52 - wave)))]);
  }
  for (let i = 1; i < pts.length; i++) c.line(pts[i - 1][0], pts[i - 1][1], pts[i][0], pts[i][1], color);
  for (let i = 3; i < w - 1; i += 5) {
    const hh = 2 + ((i * 7 + seed * 3) % 5);
    c.rect(x + i, y + h - 3 - hh, 1, hh, i % 2 ? C.green : C.red);
  }
}

function monitor(c, x, y, w, h, mode, accent, seed = 0) {
  c.box(x, y, w, h, '#202c39', C.ink);
  c.rect(x + 2, y + 2, w - 4, h - 5, C.screen);
  c.rect(x + 2, y + 2, w - 4, 1, accent);
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

function workstation(id, mode, accent, screens = 4, width = 80) {
  const c = canvas(width, 32);
  c.rect(3, 29, width - 6, 2, '#0b101680');
  const gap = 2, mw = Math.floor((width - 8 - (screens - 1) * gap) / screens), start = Math.floor((width - screens * mw - (screens - 1) * gap) / 2);
  for (let i = 0; i < screens; i++) monitor(c, start + i * (mw + gap), 0, mw, 14, mode, accent, i + id.length);
  c.rect(start + 2, 16, width - 2 * start - 4, 2, C.metal);
  c.rect(2, 18, width - 4, 2, C.woodLit); c.rect(1, 20, width - 2, 5, C.wood);
  c.rect(2, 19, width - 4, 1, accent); c.rect(3, 25, width - 6, 2, '#332a24');
  c.rect(5, 27, 4, 3, C.metal); c.rect(width - 9, 27, 4, 3, C.metal);
  c.rect(13, 20, width - 26, 1, '#ead3a7');
  const keyW = Math.min(24, width - 45);
  c.box(Math.floor(width / 2 - keyW / 2), 22, keyW, 3, '#303d4b', C.ink);
  for (let i = 0; i < keyW - 4; i += 3) c.rect(Math.floor(width / 2 - keyW / 2) + 2 + i, 23, 2, 1, '#8495a2');
  c.box(width - 18, 21, 8, 4, '#303d4b', C.ink);
  c.rect(width - 16, 22, 4, 1, C.gold); c.rect(width - 16, 23, 4, 1, C.cyan);
  // Under-desk cable loom and brushed-metal edge make each console read as a workstation.
  c.rect(10, 26, width - 20, 1, C.metalHi); c.rect(Math.floor(width / 2), 27, 1, 2, C.ink);
  return { id, c };
}

function marketTicker() {
  const c = canvas(96, 32);
  c.box(0, 1, 96, 29, '#182635', C.ink);
  c.rect(3, 4, 90, 2, C.metal);
  for (let k = 0; k < 4; k++) {
    const x = 4 + k * 22;
    if (k) c.rect(x - 2, 7, 1, 19, '#5e738455');
    c.rect(x, 7, 8, 1, C.muted); c.rect(x, 10, 15, 1, '#e4ecf2');
    c.rect(x, 12, 7, 1, k % 2 ? C.red : C.green);
    chart(c, x, 15, 16, 10, k % 2 ? C.red : C.green, k + 4);
  }
  c.rect(4, 27, 88, 1, C.cyan);
  return c;
}

function researchBoard() {
  const c = canvas(64, 32);
  c.box(0, 1, 64, 29, '#344250', C.ink);
  c.rect(3, 4, 58, 2, C.metalHi);
  chart(c, 4, 8, 25, 14, C.cyan, 7);
  c.rect(33, 8, 25, 1, C.gold);
  for (let i = 0; i < 4; i++) { c.rect(33, 11 + i * 3, 3, 2, i % 2 ? C.violet : C.cyan); c.rect(38, 11 + i * 3, 19 - (i % 3) * 3, 1, '#d8e0e6'); }
  c.rect(4, 25, 54, 1, '#bf9e6f');
  for (let i = 0; i < 7; i++) c.rect(5 + i * 7, 26, 4, 2, [C.gold, C.cyan, C.green][i % 3]);
  return c;
}

function serverRack() {
  const c = canvas(32, 48);
  c.rect(5, 44, 23, 3, '#0c121b80');
  c.box(4, 0, 24, 45, '#253344', C.ink);
  c.rect(6, 2, 20, 2, C.metalHi); c.rect(6, 4, 20, 1, C.cyan);
  for (let r = 0; r < 4; r++) {
    const y = 7 + r * 9;
    c.box(6, y, 20, 7, '#111b27', '#607487');
    c.rect(8, y + 2, 10, 1, '#758897'); c.rect(8, y + 4, 7, 1, '#526b7a');
    for (let i = 0; i < 3; i++) c.rect(20 + i * 2, y + 2, 1, 2, [C.cyan, C.green, C.gold][(i + r) % 3]);
    c.rect(8, y + 6, 15, 1, '#334659');
  }
  c.rect(2, 9, 2, 24, C.metal); c.rect(28, 9, 2, 24, C.metal);
  c.rect(8, 45, 4, 2, C.ink); c.rect(20, 45, 4, 2, C.ink);
  return c;
}

function careerBoard() {
  const c = canvas(64, 32);
  c.box(0, 1, 64, 29, '#29394a', C.ink);
  c.rect(3, 4, 58, 2, C.violet);
  c.rect(4, 8, 21, 18, '#162333'); c.rect(6, 10, 17, 3, '#d8e0e8');
  for (let r = 0; r < 3; r++) { c.rect(6, 15 + r * 3, 3, 2, [C.cyan, C.green, C.gold][r]); c.rect(11, 15 + r * 3, 10, 1, '#ced8df'); c.rect(11, 16 + r * 3, 7, 1, C.muted); }
  c.rect(29, 8, 29, 18, '#172435');
  c.rect(31, 10, 25, 3, '#4b6474');
  for (let i = 0; i < 4; i++) { c.rect(32 + i * 6, 15, 4, 8, i === 1 ? C.violet : '#d9e1e5'); c.rect(32 + i * 6, 15, 4, 2, i % 2 ? C.cyan : C.gold); }
  c.rect(4, 27, 56, 1, C.metalHi);
  return c;
}

function meetingTable() {
  const c = canvas(64, 24);
  c.rect(5, 20, 54, 3, '#10172170');
  c.rect(7, 16, 4, 6, C.metal); c.rect(53, 16, 4, 6, C.metal);
  c.box(2, 5, 60, 12, C.wood, C.outline);
  c.rect(4, 6, 56, 2, C.woodLit); c.rect(4, 15, 56, 1, '#4b3b2d');
  c.box(17, 8, 26, 6, '#d4c6a9', '#8a795e');
  c.rect(20, 10, 18, 1, '#7c8c91'); c.rect(21, 11, 16, 1, '#a9b7b6');
  c.rect(7, 9, 4, 3, C.paper); c.rect(51, 9, 4, 3, C.paper);
  c.rect(12, 9, 2, 2, C.gold); c.rect(47, 10, 2, 2, C.cyan);
  return c;
}

function executiveMeetingTable() {
  const c = canvas(80, 32);
  c.rect(8, 27, 64, 3, '#10172170');
  c.rect(13, 21, 5, 8, C.metal); c.rect(62, 21, 5, 8, C.metal);
  c.box(3, 7, 74, 17, '#574637', C.ink);
  c.rect(5, 8, 70, 2, '#c4a67a'); c.rect(6, 10, 68, 11, '#a17e54');
  c.rect(6, 21, 68, 2, '#594431'); c.rect(7, 11, 66, 1, '#ddc49a');
  c.box(25, 12, 30, 7, '#304550', '#26353e'); c.rect(28, 14, 24, 1, C.cyan);
  c.rect(13, 13, 6, 4, C.paper); c.rect(14, 14, 4, 1, '#87969b');
  c.rect(59, 12, 7, 1, C.paper); c.rect(58, 14, 8, 1, '#c8bda8');
  c.box(68, 12, 5, 5, '#394d54', C.ink); c.rect(69, 13, 3, 1, C.gold);
  return c;
}

function outreachDisplay() {
  const c = canvas(64, 32);
  c.box(0, 1, 64, 29, '#1d2c3c', C.ink);
  c.rect(3, 4, 58, 2, C.cyan);
  c.box(4, 8, 24, 16, '#0d1926', '#617587');
  for (let r = 0; r < 3; r++) { c.rect(6, 10 + r * 4, 4, 3, [C.cyan, C.violet, C.gold][r]); c.rect(12, 10 + r * 4, 12, 1, '#dce5ea'); c.rect(12, 12 + r * 4, 9, 1, C.muted); }
  c.box(33, 8, 26, 16, '#0d1926', '#617587');
  c.rect(35, 10, 22, 2, '#3d5968');
  for (let r = 0; r < 3; r++) { c.rect(36, 14 + r * 3, 3, 2, r === 0 ? C.green : C.cyan); c.rect(41, 14 + r * 3, 15 - r, 1, '#dce5ea'); }
  c.rect(4, 27, 56, 1, C.metalHi);
  return c;
}

function executiveShelf() {
  const c = canvas(48, 48);
  c.rect(3, 45, 42, 2, '#11192270');
  c.box(3, 0, 42, 45, '#34404b', C.ink);
  for (const y of [3, 15, 27, 39]) { c.rect(5, y, 38, 2, C.woodHi); c.rect(5, y + 2, 38, 1, '#44372b'); }
  const colors = [C.cyan, C.paper, C.gold, C.violet, C.red, C.green, '#b7a17e'];
  for (let row = 0; row < 3; row++) {
    let x = 7;
    while (x < 40) {
      const bw = 2 + ((x * 3 + row * 5) % 4);
      const h = 6 + ((x + row * 7) % 4);
      c.rect(x, 14 - h + row * 12, bw, h, colors[(x + row) % colors.length]);
      c.rect(x, 14 - h + row * 12, bw, 1, '#ffffff55');
      x += bw + 1;
    }
  }
  c.rect(5, 1, 38, 1, '#d8c398');
  return c;
}

function managerWall() {
  const c = canvas(96, 32);
  c.box(0, 1, 96, 29, '#152131', C.ink);
  c.rect(3, 4, 90, 2, C.violet);
  const accents = [C.cyan, C.green, C.gold, C.violet, C.cyan];
  for (let i = 0; i < 5; i++) {
    const x = 4 + i * 18;
    c.box(x, 8, 16, 16, '#0b1420', '#627587');
    if (i === 2) chart(c, x + 2, 12, 12, 9, C.cyan, 9);
    else {
      c.rect(x + 2, 11, 9, 1, accents[i]);
      for (let r = 0; r < 4; r++) { c.rect(x + 2, 14 + r * 2, 4 + (r % 2) * 2, 1, '#dce5ea'); c.rect(x + 10, 14 + r * 2, 3, 1, [C.green, C.red, C.gold, C.cyan][r]); }
    }
  }
  c.rect(4, 27, 88, 1, '#8d9eac');
  return c;
}

function executiveChair() {
  const c = canvas(32, 32);
  c.rect(8, 28, 16, 2, '#11192270');
  c.box(8, 0, 16, 15, '#263747', C.ink);
  c.rect(10, 2, 12, 2, C.violet); c.rect(10, 5, 12, 7, '#536a7b'); c.rect(11, 6, 10, 5, '#7b8d9a');
  c.rect(5, 13, 3, 7, C.metal); c.rect(24, 13, 3, 7, C.metal);
  c.box(6, 15, 20, 7, '#394c5c', C.ink); c.rect(8, 16, 16, 4, '#8999a4');
  c.rect(14, 22, 4, 5, C.metalHi); c.rect(7, 27, 18, 2, C.metal);
  c.rect(5, 29, 7, 1, C.metal); c.rect(20, 29, 7, 1, C.metal);
  return c;
}

function contactPhone() {
  const c = canvas(16, 16);
  c.rect(3, 14, 11, 1, '#11192270');
  c.box(4, 0, 9, 15, '#344758', C.ink);
  c.rect(6, 2, 5, 1, C.metalHi); c.rect(6, 4, 5, 4, '#091725');
  c.rect(7, 5, 3, 1, C.cyan); c.rect(7, 7, 2, 1, C.green);
  for (let row = 0; row < 2; row++) for (let col = 0; col < 3; col++) c.rect(6 + col * 2, 10 + row * 2, 1, 1, '#c6d2d9');
  c.rect(7, 13, 3, 1, C.violet); c.rect(12, 3, 1, 2, C.cyan);
  return c;
}

function makeManagerDesk() {
  const result = workstation('manager', 'markets', C.violet, 5, 96).c;
  result.rect(2, 18, 92, 1, C.gold);
  result.rect(2, 20, 92, 5, '#715a41'); result.rect(3, 21, 90, 1, '#d2b48c');
  result.rect(17, 22, 35, 2, '#243342'); result.rect(19, 22, 31, 1, C.metalHi);
  result.rect(63, 21, 12, 3, '#243342'); result.rect(66, 22, 6, 1, C.cyan);
  return result;
}

function loungeSofa() {
  const c = canvas(48, 32);
  c.rect(4, 28, 40, 2, '#10172180');
  c.box(2, 3, 44, 23, '#263345', C.ink);
  c.rect(4, 5, 40, 8, '#586a79'); c.rect(5, 6, 38, 5, '#738391');
  c.rect(4, 14, 40, 9, '#435665'); c.rect(5, 15, 38, 6, '#607584');
  c.rect(5, 22, 38, 3, '#344756'); c.rect(7, 26, 3, 2, C.wood); c.rect(38, 26, 3, 2, C.wood);
  for (const x of [7, 19, 31]) { c.rect(x, 15, 1, 6, '#415562'); c.rect(x + 1, 15, 9, 1, '#8b9aa3'); }
  c.box(6, 7, 7, 5, '#93b6bd', '#314451'); c.rect(7, 8, 5, 1, '#c2dbd9');
  c.box(35, 7, 7, 5, '#b9a0cf', '#314451'); c.rect(36, 8, 5, 1, '#d7c7e4');
  c.rect(4, 4, 40, 1, '#a9bbc1');
  return c;
}

function sofaSection(c, x, y, w, h, horizontal = true) {
  c.rect(x + 2, y + h - 3, w - 4, 2, '#10172180');
  c.box(x, y, w, h - 2, '#293648', C.ink);
  if (horizontal) {
    c.rect(x + 2, y + 2, w - 4, 5, '#667985');
    c.rect(x + 2, y + 8, w - 4, h - 14, '#4b606e');
    c.rect(x + 3, y + 9, w - 6, 1, '#91a3a8');
    for (let sx = x + 3; sx < x + w - 3; sx += 14) c.rect(sx, y + 9, 1, h - 14, '#344956');
  } else {
    c.rect(x + 2, y + 2, 5, h - 6, '#667985');
    c.rect(x + 8, y + 2, w - 14, h - 6, '#4b606e');
    c.rect(x + 9, y + 3, w - 16, 1, '#91a3a8');
    for (let sy = y + 4; sy < y + h - 4; sy += 14) c.rect(x + 9, sy, w - 16, 1, '#344956');
  }
  c.rect(x + 2, y + h - 5, w - 4, 2, '#354956');
}

function loungeSofaL() {
  const c = canvas(64, 48);
  // Two joined seat runs make a single readable corner sofa and collision footprint.
  sofaSection(c, 2, 2, 60, 25, true);
  sofaSection(c, 2, 20, 28, 26, false);
  c.box(11, 6, 8, 6, '#9ec3c6', '#344856'); c.rect(13, 7, 4, 1, '#d7e6df');
  c.box(43, 6, 8, 6, '#bba9d2', '#344856'); c.rect(45, 7, 4, 1, '#e0d7ec');
  c.box(11, 31, 8, 7, '#d8b876', '#574839'); c.rect(13, 32, 4, 1, '#f0d79c');
  return c;
}

function loungeArmchair() {
  const c = canvas(32, 32);
  c.rect(5, 29, 22, 2, '#10172180');
  c.box(4, 3, 24, 25, '#293648', C.ink);
  c.rect(7, 5, 18, 7, '#6d808b'); c.rect(8, 6, 16, 4, '#88999f');
  c.rect(7, 13, 18, 10, '#536a77'); c.rect(8, 14, 16, 7, '#728893');
  c.rect(5, 13, 3, 11, '#a58056'); c.rect(24, 13, 3, 11, '#a58056');
  c.rect(8, 26, 3, 2, C.wood); c.rect(21, 26, 3, 2, C.wood);
  c.rect(8, 4, 16, 1, '#c1d0cb');
  return c;
}

function loungeCoffeeTable() {
  const c = canvas(48, 32);
  c.rect(6, 27, 36, 3, '#10172170');
  c.rect(8, 22, 4, 7, C.metal); c.rect(36, 22, 4, 7, C.metal);
  c.box(3, 7, 42, 17, '#604a39', C.ink);
  c.rect(5, 8, 38, 2, '#c7a97a'); c.rect(6, 10, 36, 11, '#a88760');
  c.rect(6, 21, 36, 2, '#6f523a'); c.rect(7, 11, 34, 1, '#dfc596');
  c.box(13, 13, 8, 5, '#314a55', '#202d36'); c.rect(15, 14, 4, 1, C.cyan);
  c.rect(30, 12, 5, 1, C.paper); c.rect(29, 14, 7, 1, '#c8bda8');
  c.box(36, 12, 4, 4, '#394d54', C.ink); c.rect(37, 13, 2, 1, C.gold);
  return c;
}

function meetingRoundTable() {
  const c = canvas(48, 32);
  c.rect(7, 27, 34, 3, '#10172170');
  c.rect(17, 20, 14, 8, C.metal); c.rect(19, 21, 10, 5, C.metalHi);
  for (let y = 6; y < 24; y++) {
    const inset = Math.abs(15 - y) < 4 ? 5 : 2;
    c.rect(inset, y, 48 - inset * 2, 1, y < 9 ? '#c4aa7f' : y > 20 ? '#624d39' : '#94754f');
  }
  c.rect(6, 10, 36, 1, '#dbc59d'); c.rect(5, 14, 38, 1, '#c0a77d');
  c.box(20, 11, 8, 6, '#304650', '#273640'); c.rect(22, 12, 4, 1, C.cyan);
  c.rect(12, 11, 4, 3, C.paper); c.rect(33, 17, 4, 2, C.gold);
  c.rect(7, 23, 3, 3, '#5b4634'); c.rect(38, 23, 3, 3, '#5b4634');
  return c;
}

function meetingChair() {
  const c = canvas(16, 16);
  c.rect(3, 14, 10, 1, '#10172180');
  c.box(3, 1, 10, 8, '#344656', C.ink); c.rect(5, 3, 6, 4, '#647986');
  c.rect(4, 9, 8, 3, '#536b78'); c.rect(5, 12, 2, 2, C.metal); c.rect(9, 12, 2, 2, C.metal);
  c.rect(5, 2, 6, 1, '#b4c3c4');
  return c;
}

function planterBox() {
  const c = canvas(48, 16);
  c.rect(4, 14, 40, 2, '#10172180');
  c.box(2, 8, 44, 6, '#624a37', C.ink); c.rect(4, 9, 40, 1, '#c5a476');
  c.rect(5, 11, 38, 1, '#332a22');
  for (const [x, y, color] of [[10, 4, '#78a76d'], [17, 2, '#88b879'], [24, 4, '#6f9f62'], [31, 2, '#91b87b'], [38, 4, '#76a16a']]) {
    c.rect(x - 2, y + 1, 5, 3, color); c.rect(x - 1, y, 3, 4, '#b1cb88'); c.rect(x, y + 4, 1, 5, '#5c7c50');
  }
  return c;
}

function serverRackCluster() {
  const c = canvas(48, 48);
  c.rect(4, 44, 40, 3, '#10172180');
  for (let i = 0; i < 3; i++) {
    const x = 2 + i * 15;
    c.box(x, 1, 14, 43, '#263646', C.ink);
    c.rect(x + 2, 3, 10, 2, C.metalHi); c.rect(x + 2, 5, 10, 1, C.cyan);
    for (let r = 0; r < 4; r++) {
      const y = 8 + r * 8;
      c.box(x + 2, y, 10, 6, '#101a26', '#647a88');
      c.rect(x + 4, y + 2, 5, 1, '#637786'); c.rect(x + 4, y + 4, 4, 1, '#354957');
      c.rect(x + 9, y + 2, 1, 2, [C.cyan, C.green, C.gold, C.violet][(i + r) % 4]);
    }
    c.rect(x + 2, 42, 10, 1, C.metalHi);
  }
  c.rect(15, 4, 2, 37, '#8295a0'); c.rect(30, 4, 2, 37, '#8295a0');
  return c;
}

function careerCabinet() {
  const c = canvas(32, 32);
  c.rect(4, 29, 24, 2, '#10172180'); c.box(4, 2, 24, 26, '#3b4b59', C.ink);
  for (let r = 0; r < 3; r++) {
    const y = 5 + r * 7;
    c.rect(6, y, 20, 1, '#8899a2'); c.rect(7, y + 1, 18, 4, '#536675');
    c.rect(9, y + 2, 9, 1, '#8799a1'); c.rect(21, y + 2, 2, 2, C.gold);
  }
  c.rect(6, 26, 20, 1, '#c3a67a');
  return c;
}

function executiveGlassPartition() {
  const c = canvas(48, 16);
  c.rect(1, 12, 46, 3, '#10172180');
  c.rect(0, 1, 48, 3, '#263848'); c.rect(2, 2, 44, 1, '#b6c6cb');
  c.rect(0, 4, 2, 8, '#2a3c4c'); c.rect(46, 4, 2, 8, '#2a3c4c');
  c.rect(3, 4, 42, 7, '#6ba8b322'); c.rect(4, 5, 40, 1, '#d6eff044');
  c.rect(15, 4, 2, 8, '#708998'); c.rect(31, 4, 2, 8, '#708998');
  c.rect(1, 11, 46, 1, C.metalHi); c.rect(0, 14, 4, 1, C.metal);
  c.rect(44, 14, 4, 1, C.metal);
  return c;
}

// Reusable one-tile partition pieces. Cardinal mask bits match Pixel Agents:
// N=1, E=2, S=4, W=8. Keeping each module on the native 16px grid lets the
// renderer join straight runs, corners, ends and T/cross intersections cleanly.
function glassWallTile(mask) {
  const c = canvas(16, 16);
  const horizontal = (mask & 10) !== 0;
  const vertical = (mask & 5) !== 0;
  if (horizontal) {
    c.rect(0, 0, 16, 1, '#17232e');
    c.rect(0, 1, 16, 1, '#627985');
    c.rect(0, 2, 16, 8, '#8fb9c63a');
    c.rect(0, 4, 16, 1, '#d8edf04c');
    c.rect(1, 8, 14, 1, '#a8d1d345');
    c.rect(0, 10, 16, 1, '#405461');
    c.rect(0, 11, 16, 1, '#eee1c6');
    c.rect(0, 12, 16, 3, '#c5b493');
    c.rect(0, 15, 16, 1, '#8d806d');
    if (!(mask & 8)) { c.rect(0, 1, 2, 11, '#34434d'); c.rect(1, 2, 1, 8, '#b6c8c4'); }
    if (!(mask & 2)) { c.rect(14, 1, 2, 11, '#34434d'); c.rect(14, 2, 1, 8, '#b6c8c4'); }
  }
  if (vertical) {
    c.rect(0, 0, 16, 16, '#14202a48');
    c.rect(1, 0, 2, 16, '#263640');
    c.rect(3, 0, 1, 16, '#81969d');
    c.rect(4, 0, 8, 16, '#8fb9c636');
    c.rect(5, 0, 1, 16, '#d8edf04a');
    c.rect(12, 0, 1, 16, '#455965');
    c.rect(13, 0, 2, 16, '#263640');
    if (!(mask & 1)) { c.rect(2, 0, 12, 2, '#34434d'); c.rect(4, 1, 8, 1, '#b6c8c4'); }
    if (!(mask & 4)) { c.rect(2, 14, 12, 2, '#34434d'); c.rect(4, 14, 8, 1, '#b6c8c4'); }
  }
  if (horizontal && vertical) {
    c.rect(1, 1, 14, 14, '#8fb9c622');
    c.rect(1, 1, 14, 2, '#263640'); c.rect(1, 12, 14, 2, '#c5b493');
    c.rect(2, 2, 12, 1, '#b6c8c4'); c.rect(3, 7, 10, 2, '#657985');
    c.rect(6, 3, 4, 9, '#8fb9c632'); c.rect(7, 3, 1, 9, '#d8edf04a');
  } else if (!horizontal && !vertical) {
    // A compact glass-and-metal post closes isolated wall cells gracefully.
    c.rect(2, 1, 12, 14, '#34434d'); c.rect(3, 2, 10, 10, '#8fb9c640');
    c.rect(4, 3, 1, 8, '#d8edf04c'); c.rect(3, 12, 10, 2, '#c5b493');
  }
  return c;
}

function panoramicWindow() {
  const c = canvas(96, 32);
  c.rect(0, 29, 96, 3, '#1019228a');
  c.rect(0, 0, 96, 4, '#263541'); c.rect(2, 1, 92, 1, '#71848c');
  c.rect(3, 4, 90, 20, '#91b8c5');
  c.rect(3, 4, 90, 7, '#bdd4cf'); c.rect(3, 11, 90, 7, '#a7c4c1');
  c.rect(3, 18, 90, 6, '#8ea9a8');
  // Low skyline and treeline keep the view calm and consistent across modules.
  c.rect(4, 17, 88, 2, '#829c98');
  for (const [x, y, w, h, color] of [
    [7, 14, 8, 4, '#809995'], [18, 12, 7, 6, '#879f99'], [27, 15, 5, 3, '#718d88'],
    [37, 13, 9, 5, '#78938e'], [49, 15, 7, 3, '#6f8985'], [59, 12, 8, 6, '#839b95'],
    [71, 14, 7, 4, '#718d88'], [81, 12, 8, 6, '#829b96'],
  ]) c.rect(x, y, w, h, color);
  c.rect(5, 6, 1, 16, '#e9f3e84d'); c.rect(8, 5, 20, 1, '#edf5ef52');
  c.rect(35, 5, 1, 17, '#dff0ef35'); c.rect(68, 6, 1, 15, '#e7f3f041');
  for (const x of [0, 31, 63, 94]) { c.rect(x, 1, 2, 25, '#263541'); c.rect(x + 1, 4, 1, 19, '#71848c'); }
  c.rect(0, 24, 96, 2, '#445763'); c.rect(0, 26, 96, 3, '#e1d0ad');
  c.rect(0, 29, 96, 1, '#9a896e'); c.rect(2, 27, 92, 1, '#f2e4c9');
  return c;
}

function glassDoor(width = 16) {
  const c = canvas(width, 32);
  c.rect(0, 27, width, 4, '#10192276');
  c.rect(1, 1, width - 2, 3, '#263541'); c.rect(2, 2, width - 4, 1, '#91a4aa');
  c.rect(1, 4, 2, 23, '#34434d'); c.rect(width - 3, 4, 2, 23, '#34434d');
  c.rect(3, 5, width - 6, 20, '#91bdcc38');
  c.rect(4, 6, Math.max(2, Math.floor(width / 3)), 18, '#d9eef044');
  c.rect(3, 25, width - 6, 1, '#71838b');
  if (width <= 16) {
    // Sliding panel parked to one side leaves a visible walk-through opening.
    c.rect(8, 5, 5, 20, '#293943'); c.rect(9, 6, 3, 18, '#87b9c64a');
    c.rect(9, 7, 1, 15, '#e0f1f04f'); c.rect(8, 25, 5, 1, '#a4b6b8');
    c.rect(7, 14, 1, 3, '#d5c69f');
  } else {
    // Four-cell opening with two glazed leaves parked at the jambs.
    c.rect(4, 5, 17, 20, '#2c3d49'); c.rect(5, 6, 15, 18, '#8bbbc943');
    c.rect(6, 7, 1, 15, '#e4f2f04d'); c.rect(43, 5, 17, 20, '#2c3d49');
    c.rect(44, 6, 15, 18, '#8bbbc943'); c.rect(45, 7, 1, 15, '#e4f2f04d');
    c.rect(19, 13, 1, 4, '#d5c69f'); c.rect(44, 13, 1, 4, '#d5c69f');
    c.rect(21, 5, 22, 20, '#14212a16');
  }
  c.rect(0, 30, width, 1, '#d4c4a3'); c.rect(0, 31, width, 1, '#4a5860');
  return c;
}

const glassWallSpecs = Array.from({ length: 16 }, (_, mask) => [
  `MD_GLASS_WALL_MASK_${mask.toString(16).toUpperCase().padStart(2, '0')}`,
  `Glass partition junction ${mask.toString(16).toUpperCase().padStart(2, '0')}`,
  'walls', 16, 16, 1, 1, false, `glass_wall_${mask.toString(16).padStart(2, '0')}.png`, { isWallTile: true },
]);

const specs = [
  ...glassWallSpecs,
  ['MD_PANORAMA_WINDOW', 'Panoramic glazed window module', 'windows', 96, 32, 6, 1, false, 'panoramic_window.png', { canPlaceOnWalls: true, backgroundTiles: 1 }],
  ['MD_GLASS_DOOR', 'Open sliding glass door', 'doors', 16, 32, 1, 1, false, 'glass_door.png', { backgroundTiles: 1 }],
  ['MD_DOUBLE_GLASS_DOOR', 'Open double glass door', 'doors', 64, 32, 4, 1, false, 'double_glass_door.png', { backgroundTiles: 1 }],
  ['MD_GLOBAL_MARKETS_DESK', 'Global Markets trading station', 'desks', 80, 32, 5, 2, true, 'global_markets_desk.png'],
  ['MD_RESEARCH_DESK', 'Research analytics station', 'desks', 80, 32, 5, 2, true, 'research_desk.png'],
  ['MD_TECH_DESK', 'Technology engineering station', 'desks', 80, 32, 5, 2, true, 'tech_desk.png'],
  ['MD_CAREER_DESK', 'Career offer review station', 'desks', 80, 32, 5, 2, true, 'career_desk.png'],
  ['MD_NETWORK_DESK', 'Network collaboration station', 'desks', 80, 32, 5, 2, true, 'network_desk.png'],
  ['MD_OUTREACH_DESK', 'Outreach communications station', 'desks', 80, 32, 5, 2, true, 'outreach_desk.png'],
  ['MD_EXECUTIVE_DESK', 'Head of Desk executive console', 'desks', 96, 32, 6, 2, true, 'executive_desk.png'],
  ['MD_MARKET_TICKER', 'Global Markets wall ticker', 'wall', 96, 32, 6, 1, false, 'market_ticker.png', { canPlaceOnWalls: true, backgroundTiles: 1 }],
  ['MD_RESEARCH_BOARD', 'Research economics board', 'wall', 64, 32, 4, 1, false, 'research_board.png', { canPlaceOnWalls: true, backgroundTiles: 1 }],
  ['MD_SERVER_RACK', 'Technology server rack', 'electronics', 32, 48, 1, 2, false, 'server_rack.png'],
  ['MD_CAREER_BOARD', 'Career opportunities board', 'wall', 64, 32, 4, 1, false, 'career_board.png', { canPlaceOnWalls: true, backgroundTiles: 1 }],
  ['MD_NETWORK_TABLE', 'Network meeting table', 'misc', 64, 24, 4, 1, false, 'network_table.png'],
  ['MD_OUTREACH_DISPLAY', 'Outreach contact dashboard', 'wall', 64, 32, 4, 1, false, 'outreach_display.png', { canPlaceOnWalls: true, backgroundTiles: 1 }],
  ['MD_EXECUTIVE_WALL', 'Head of Desk supervision wall', 'wall', 96, 32, 6, 1, false, 'executive_wall.png', { canPlaceOnWalls: true, backgroundTiles: 1 }],
  ['MD_EXECUTIVE_LIBRARY', 'Executive reference library', 'storage', 48, 48, 3, 2, false, 'executive_library.png'],
  ['MD_EXECUTIVE_CHAIR', 'Executive chair', 'chairs', 32, 32, 1, 1, false, 'executive_chair.png', { orientation: 'back' }],
  ['MD_CONTACT_PHONE', 'Outreach desk phone', 'electronics', 16, 16, 1, 1, false, 'contact_phone.png', { canPlaceOnSurfaces: true }],
  ['MD_LOUNGE_SOFA_L', 'L-shaped central lounge sofa', 'seating', 64, 48, 4, 3, false, 'lounge_sofa_l.png'],
  ['MD_LOUNGE_ARMCHAIR', 'Lounge armchair', 'seating', 32, 32, 2, 2, false, 'lounge_armchair.png'],
  ['MD_LOUNGE_COFFEE_TABLE', 'Lounge coffee table', 'tables', 48, 32, 3, 2, false, 'lounge_coffee_table.png'],
  ['MD_MEETING_ROUND_TABLE', 'Network meeting table', 'tables', 48, 32, 3, 2, false, 'meeting_round_table.png'],
  ['MD_MEETING_CHAIR', 'Meeting chair', 'chairs', 16, 16, 1, 1, false, 'meeting_chair.png'],
  ['MD_LOUNGE_PLANTER', 'Central lounge planter', 'plants', 48, 16, 3, 1, false, 'lounge_planter.png'],
  ['MD_SERVER_RACK_CLUSTER', 'Three-rack server cabinet', 'electronics', 48, 48, 3, 3, false, 'server_rack_cluster.png'],
  ['MD_CAREER_CABINET', 'Career application archive cabinet', 'storage', 32, 32, 2, 2, false, 'career_cabinet.png'],
  ['MD_EXECUTIVE_GLASS_PARTITION', 'Executive glass partition', 'walls', 48, 16, 3, 1, false, 'executive_glass_partition.png', { canPlaceOnWalls: true, backgroundTiles: 1 }],
  ['MD_CENTRAL_LOUNGE_SOFA', 'Central lounge sofa', 'seating', 48, 32, 3, 2, false, 'central_lounge_sofa.png'],
  ['MD_EXECUTIVE_MEETING_TABLE', 'Executive meeting table', 'tables', 80, 32, 5, 2, false, 'executive_meeting_table.png'],
];

const images = new Map([
  ...Array.from({ length: 16 }, (_, mask) => [
    `MD_GLASS_WALL_MASK_${mask.toString(16).toUpperCase().padStart(2, '0')}`, glassWallTile(mask),
  ]),
  ['MD_PANORAMA_WINDOW', panoramicWindow()],
  ['MD_GLASS_DOOR', glassDoor()],
  ['MD_DOUBLE_GLASS_DOOR', glassDoor(64)],
  ['MD_GLOBAL_MARKETS_DESK', workstation('markets', 'markets', C.gold, 4).c],
  ['MD_RESEARCH_DESK', workstation('research', 'chart', C.cyan, 3).c],
  ['MD_TECH_DESK', workstation('technology', 'code', C.green, 3).c],
  ['MD_CAREER_DESK', workstation('career', 'jobs', C.violet, 3).c],
  ['MD_NETWORK_DESK', workstation('network', 'chart', C.cyan, 2).c],
  ['MD_OUTREACH_DESK', workstation('outreach', 'mail', C.violet, 3).c],
  ['MD_EXECUTIVE_DESK', makeManagerDesk()],
  ['MD_MARKET_TICKER', marketTicker()],
  ['MD_RESEARCH_BOARD', researchBoard()],
  ['MD_SERVER_RACK', serverRack()],
  ['MD_CAREER_BOARD', careerBoard()],
  ['MD_NETWORK_TABLE', meetingTable()],
  ['MD_OUTREACH_DISPLAY', outreachDisplay()],
  ['MD_EXECUTIVE_WALL', managerWall()],
  ['MD_EXECUTIVE_LIBRARY', executiveShelf()],
  ['MD_EXECUTIVE_CHAIR', executiveChair()],
  ['MD_CONTACT_PHONE', contactPhone()],
  ['MD_LOUNGE_SOFA_L', loungeSofaL()],
  ['MD_LOUNGE_ARMCHAIR', loungeArmchair()],
  ['MD_LOUNGE_COFFEE_TABLE', loungeCoffeeTable()],
  ['MD_MEETING_ROUND_TABLE', meetingRoundTable()],
  ['MD_MEETING_CHAIR', meetingChair()],
  ['MD_LOUNGE_PLANTER', planterBox()],
  ['MD_SERVER_RACK_CLUSTER', serverRackCluster()],
  ['MD_CAREER_CABINET', careerCabinet()],
  ['MD_EXECUTIVE_GLASS_PARTITION', executiveGlassPartition()],
  ['MD_CENTRAL_LOUNGE_SOFA', loungeSofa()],
  ['MD_EXECUTIVE_MEETING_TABLE', executiveMeetingTable()],
]);

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

await mkdir(out, { recursive: true });
const assets = [];
for (const item of specs) {
  const [id, name, category, width, height, footprintW, footprintH, isDesk, file, options = {}] = item;
  const image = images.get(id);
  if (!image || image.w !== width || image.h !== height) throw new Error('Asset dimensions do not match manifest: ' + id);
  await writeFile(resolve(out, file), encodePng(image));
  assets.push({ id, name, category, file, width, height, footprintW, footprintH, isDesk,
    canPlaceOnWalls: false, canPlaceOnSurfaces: false, backgroundTiles: 0, ...options });
}
await writeFile(resolve(out, 'manifest.json'), JSON.stringify({ pack: 'MarketDesk Pixel Floor', tileSize: 16, assets }, null, 2) + '\n');
console.log('Generated ' + assets.length + ' original pixel sprites in ' + out);
