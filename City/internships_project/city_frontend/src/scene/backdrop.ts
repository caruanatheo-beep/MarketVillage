// Paris at night behind the building: sky, stars, three parallax layers and the Eiffel Tower.
import { P, mix, px, makeCanvas, seeded, halo, type Ctx } from "./pixels";

const TILE = 480, LAYER_H = 760;
const SKY_BANDS = [mix(P.ink, P.night, 0.55), mix(P.ink, P.night, 0.8), P.night, mix(P.night, P.indigo, 0.5),
  P.indigo, mix(P.indigo, P.plum, 0.3), mix(P.indigo, P.rust, 0.28), mix(P.indigo, P.rust, 0.45)];

type Layer = { canvas: HTMLCanvasElement; base: number; factor: number };

function farLayer(): HTMLCanvasElement {
  const [canvas, c] = makeCanvas(TILE, LAYER_H), random = seeded(11);
  const body = mix(P.night, P.ink, 0.35), light = mix(P.amber, P.rust, 0.35);
  for (let x = 0; x < TILE;) {
    const w = 12 + Math.floor(random() * 26), top = 14 + Math.floor(random() * 60);
    px(c, x, top, w, LAYER_H - top, body);
    if (random() < 0.3) px(c, x + (w >> 1), top - 6, 1, 6, body);
    for (let wy = top + 3; wy < LAYER_H - 4; wy += 4) for (let wx = x + 2; wx < x + w - 1; wx += 3)
      if (random() < (wy - top < 90 ? 0.22 : 0.07)) px(c, wx, wy, 1, 2, random() < 0.8 ? light : P.glow);
    x += w + (random() < 0.25 ? 3 : 0);
  }
  return canvas;
}

function roofLayer(seed: number, body: string, zinc: string, lit: number): HTMLCanvasElement {
  const [canvas, c] = makeCanvas(TILE, LAYER_H), random = seeded(seed);
  for (let x = 0; x < TILE;) {
    const w = Math.min(TILE - x, 54 + Math.floor(random() * 44)), top = 26 + Math.floor(random() * 22);
    // Zinc mansard roof, then the stone body with tall Haussmann windows.
    px(c, x + 2, top, w - 4, 3, zinc); px(c, x + 1, top + 3, w - 2, 7, zinc); px(c, x, top + 10, w, 1, mix(zinc, P.glow, 0.2));
    px(c, x, top + 11, w, LAYER_H - top, body);
    for (let chimney = x + 6; chimney < x + w - 8; chimney += 18 + Math.floor(random() * 14)) {
      px(c, chimney, top - 7, 5, 8, body);
      px(c, chimney, top - 9, 1, 2, mix(P.rust, P.ink, 0.4)); px(c, chimney + 2, top - 10, 1, 3, mix(P.rust, P.ink, 0.4)); px(c, chimney + 4, top - 9, 1, 2, mix(P.rust, P.ink, 0.4));
    }
    for (let dormer = x + 5; dormer < x + w - 6; dormer += 10)
      px(c, dormer, top + 4, 3, 4, random() < lit ? P.amber : mix(body, P.ink, 0.4));
    for (let wy = top + 16; wy < LAYER_H - 8; wy += 13) {
      px(c, x, wy + 8, w, 1, mix(body, P.ink, 0.35));
      for (let wx = x + 4; wx < x + w - 5; wx += 9) {
        const on = random() < (wy - top < 110 ? lit : lit * 0.3);
        px(c, wx, wy, 4, 7, on ? (random() < 0.7 ? P.amber : P.glow) : mix(body, P.ink, 0.45));
        if (on) px(c, wx, wy + 3, 4, 1, mix(P.amber, P.rust, 0.5));
      }
    }
    x += w;
  }
  return canvas;
}

function eiffelSprite(): HTMLCanvasElement {
  const W = 66, H = 134, [canvas, c] = makeCanvas(W, H), cx = W >> 1;
  const gold = P.amber, deep = mix(P.amber, P.rust, 0.55), bright = P.glow;
  for (let y = 0; y < H; y++) {
    const t = y / H;
    // Half-width profile: spire, upper shaft, two platforms and the spreading legs.
    let half = t < 0.1 ? 0.5 : t < 0.42 ? 1 + (t - 0.1) * 9 : t < 0.7 ? 4 + (t - 0.42) * 26 : 11.5 + ((t - 0.7) / 0.3) ** 1.6 * 20;
    if (Math.abs(t - 0.42) < 0.012) half += 2;
    if (Math.abs(t - 0.7) < 0.014) half += 3;
    half = Math.round(half);
    for (let dx = -half; dx <= half; dx++) {
      const edge = half - Math.abs(dx);
      // The arch between the legs and the open lattice in the middle.
      if (t > 0.74) { const arch = (half - 5) * Math.sqrt(Math.max(0, 1 - ((t - 0.74) / 0.26) ** 2 * 0.2)) - (1 - t) * 14; if (Math.abs(dx) < arch) continue; }
      const platform = Math.abs(t - 0.42) < 0.012 || Math.abs(t - 0.7) < 0.014;
      if (!platform && edge > 1 && half > 3 && (dx + y) % 2 === 0) continue;
      px(c, cx + dx, y, 1, 1, platform ? bright : edge === 0 ? (dx < 0 ? bright : gold) : (y % 3 === 0 ? gold : deep));
    }
  }
  px(c, cx, 0, 1, 2, bright);
  return canvas;
}

export class Backdrop {
  private layers: Layer[];
  private eiffel = eiffelSprite();
  private stars: { x: number; y: number; phase: number; bright: boolean }[] = [];
  private rainUntil = 0; private nextRain = 40;

  constructor() {
    const soften = (source: HTMLCanvasElement, blur: number): HTMLCanvasElement => {
      const [canvas, c] = makeCanvas(source.width, source.height);
      c.filter = `blur(${blur}px)`; c.drawImage(source, 0, 0); c.filter = "none";
      c.globalAlpha = 0.55; c.drawImage(source, 0, 0); c.globalAlpha = 1;
      return canvas;
    };
    this.layers = [
      { canvas: soften(farLayer(), 0.7), base: 96, factor: 0.07 },
      { canvas: soften(roofLayer(23, mix(P.night, P.ink, 0.55), mix(P.night, P.indigo, 0.4), 0.3), 0.5), base: 118, factor: 0.14 },
      { canvas: roofLayer(41, mix(P.ink, P.night, 0.3), mix(P.night, P.plum, 0.5), 0.2), base: 150, factor: 0.26 },
    ];
    const random = seeded(5);
    for (let i = 0; i < 150; i++) this.stars.push({ x: random(), y: random() * 0.62, phase: random() * 6.3, bright: random() < 0.16 });
  }

  // `scroll` is how far the camera sits below its highest position, in native pixels.
  draw(c: Ctx, viewW: number, viewH: number, originX: number, scroll: number, time: number): void {
    const bandH = Math.ceil(viewH * 0.78 / SKY_BANDS.length), skyShift = Math.round(scroll * 0.03);
    px(c, 0, 0, viewW, viewH, SKY_BANDS[SKY_BANDS.length - 1]);
    SKY_BANDS.forEach((color, i) => {
      const y = i * bandH - skyShift;
      px(c, 0, i === 0 ? 0 : y, viewW, bandH + (i === 0 ? y : 0), color);
      // One dithered row softens each band edge without leaving the pixel grid.
      if (i > 0) { c.fillStyle = SKY_BANDS[i - 1]; for (let x = (i % 2); x < viewW; x += 2) c.fillRect(x, y, 1, 1); }
    });
    for (const star of this.stars) {
      const twinkle = Math.sin(time * 1.3 + star.phase);
      if (twinkle < -0.55) continue;
      px(c, Math.floor(star.x * viewW), Math.floor(star.y * viewH) - skyShift, 1, 1, star.bright && twinkle > 0.3 ? P.glow : mix(P.indigo, P.glow, 0.55));
    }
    // Moon, top right, away from the tower.
    const moonX = originX + 150, moonY = 22 - skyShift;
    c.globalCompositeOperation = "lighter"; c.globalAlpha = 0.35; c.drawImage(halo(26, P.glow), moonX - 21, moonY - 21); c.globalAlpha = 1; c.globalCompositeOperation = "source-over";
    px(c, moonX + 1, moonY, 8, 10, P.glow); px(c, moonX, moonY + 2, 10, 6, P.glow); px(c, moonX + 2, moonY - 1, 6, 12, P.glow);
    px(c, moonX + 6, moonY + 2, 2, 2, mix(P.glow, P.indigo, 0.25)); px(c, moonX + 3, moonY + 6, 1, 2, mix(P.glow, P.indigo, 0.25));

    this.layers.forEach((layer, index) => {
      const y = Math.round(layer.base - scroll * layer.factor);
      const start = ((originX % TILE) + TILE) % TILE - TILE;
      for (let x = start; x < viewW; x += TILE) c.drawImage(layer.canvas, x, y);
      if (index === 0) {
        // The tower stands once, right of centre, between the far and middle layers.
        const ex = originX + 438, ey = Math.round(34 - scroll * 0.1);
        c.globalCompositeOperation = "lighter";
        c.globalAlpha = 0.5; c.drawImage(halo(70, mix(P.amber, P.rust, 0.4)), ex + 33 - 70, ey + 60 - 70);
        c.globalAlpha = 0.5 + 0.3 * Math.sin(time * 2.2); c.drawImage(halo(12, P.glow), ex + 33 - 12, ey - 11);
        c.globalAlpha = 1; c.globalCompositeOperation = "source-over";
        c.drawImage(this.eiffel, ex, ey);
        // Sparkle: a few random bright pixels on the lattice, like the hourly glitter.
        const sparkle = seeded(Math.floor(time * 6));
        for (let i = 0; i < 5; i++) { const sy = Math.floor(sparkle() * 120), half = 1 + sy * 0.09; px(c, ex + 33 + Math.round((sparkle() - 0.5) * 2 * half), ey + sy, 1, 1, P.glow); }
      }
    });

    if (time > this.nextRain) { this.rainUntil = time + 35; this.nextRain = time + 110 + Math.random() * 90; }
    if (time < this.rainUntil) {
      const fade = Math.min(1, (this.rainUntil - time) / 4, (time - (this.rainUntil - 35)) / 4);
      c.fillStyle = mix(P.indigo, P.glow, 0.5); c.globalAlpha = 0.3 * fade;
      const drop = seeded(Math.floor(time * 20));
      for (let i = 0; i < viewW / 5; i++) { const x = Math.floor(drop() * viewW), y = Math.floor(drop() * viewH); c.fillRect(x, y, 1, 3); c.fillRect(x - 1, y + 3, 1, 2); }
      c.globalAlpha = 1;
    }
  }
}
