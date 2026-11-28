// Palette and low-level pixel helpers. Everything is drawn at native resolution and
// scaled by an integer factor afterwards; nothing here may use fractional coordinates.
export type Ctx = CanvasRenderingContext2D;

// The eight colours sampled from references/lofi-wallpaper.png. Every other colour
// in the scene and the interface is a mix of two of these.
export const P = {
  ink: "#100a0e", night: "#14224d", indigo: "#202f64", plum: "#3b2a2f",
  rust: "#824c2b", amber: "#e7a856", glow: "#f9e4b9", sage: "#4f6444",
} as const;

export function rgb(hex: string): [number, number, number] {
  const n = parseInt(hex.slice(1), 16);
  return [n >> 16, (n >> 8) & 255, n & 255];
}
export function mix(a: string, b: string, t: number): string {
  const x = rgb(a), y = rgb(b);
  return "#" + x.map((v, i) => Math.round(v + (y[i] - v) * t).toString(16).padStart(2, "0")).join("");
}

export function px(c: Ctx, x: number, y: number, w: number, h: number, color: string): void {
  c.fillStyle = color; c.fillRect(Math.round(x), Math.round(y), w, h);
}

export function makeCanvas(w: number, h: number): [HTMLCanvasElement, Ctx] {
  const canvas = document.createElement("canvas");
  canvas.width = w; canvas.height = h;
  const c = canvas.getContext("2d")!;
  c.imageSmoothingEnabled = false;
  return [canvas, c];
}

// Deterministic random numbers so the building looks the same on every load.
export function seeded(seed: number): () => number {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

// 3×5 pixel font for signs, tickers and clocks.
const GLYPHS: Record<string, string> = {
  A: "010101111101101", B: "110101110101110", C: "011100100100011", D: "110101101101110", E: "111100110100111",
  F: "111100110100100", G: "011100101101011", H: "101101111101101", I: "111010010010111", J: "001001001101010",
  K: "101101110101101", L: "100100100100111", M: "101111111101101", N: "110101101101101", O: "010101101101010",
  P: "110101110100100", Q: "010101101110011", R: "110101110101101", S: "011100010001110", T: "111010010010010",
  U: "101101101101111", V: "101101101101010", W: "101101111111101", X: "101101010101101", Y: "101101010010010",
  Z: "111001010100111", "0": "111101101101111", "1": "010110010010111", "2": "110001010100111",
  "3": "110001010001110", "4": "101101111001001", "5": "111100110001110", "6": "011100110101010",
  "7": "111001010010010", "8": "010101010101010", "9": "010101011001110", "&": "010101010101011",
  ".": "000000000000010", "-": "000000111000000", "!": "010010010000010", "+": "000010111010000",
  "%": "101001010100101", ":": "000010000010000", "/": "001001010100100",
};
export function text(c: Ctx, value: string, x: number, y: number, color: string): number {
  c.fillStyle = color;
  let cursor = x;
  for (const raw of value.toUpperCase()) {
    const accent = raw === "É";
    const glyph = GLYPHS[accent ? "E" : raw];
    if (glyph) for (let i = 0; i < 15; i++) if (glyph[i] === "1") c.fillRect(cursor + (i % 3), y + Math.floor(i / 3), 1, 1);
    if (accent) c.fillRect(cursor + 1, y - 2, 2, 1);
    cursor += 4;
  }
  return cursor - x - 1;
}
export const textWidth = (value: string): number => value.length * 4 - 1;

// Additive light sprite: quantised radial falloff with ordered dithering, so halos
// keep hard pixel edges instead of a smooth gradient.
const BAYER = [0, 8, 2, 10, 12, 4, 14, 6, 3, 11, 1, 9, 15, 7, 13, 5];
const halos = new Map<string, HTMLCanvasElement>();
export function halo(radius: number, color: string): HTMLCanvasElement {
  const key = `${radius}|${color}`;
  const cached = halos.get(key);
  if (cached) return cached;
  const size = radius * 2, [canvas, c] = makeCanvas(size, size);
  const image = c.createImageData(size, size), [r, g, b] = rgb(color);
  for (let y = 0; y < size; y++) for (let x = 0; x < size; x++) {
    const distance = Math.hypot(x - radius + 0.5, y - radius + 0.5) / radius;
    if (distance >= 1) continue;
    // Seven shallow steps; a light dither only on the outermost one keeps the rim soft.
    const falloff = (1 - distance) ** 1.6 * 7.6;
    const level = Math.min(7, Math.floor(falloff + (falloff < 1 ? (BAYER[(y & 3) * 4 + (x & 3)] + 0.5) / 16 : 0)));
    const i = (y * size + x) * 4;
    image.data[i] = r; image.data[i + 1] = g; image.data[i + 2] = b; image.data[i + 3] = level * 14;
  }
  c.putImageData(image, 0, 0);
  halos.set(key, canvas);
  return canvas;
}
