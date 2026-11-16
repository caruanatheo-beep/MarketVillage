import { readFile } from 'node:fs/promises';
import { inflateSync } from 'node:zlib';
import { resolve } from 'node:path';

const packDir = resolve('internships_project/city_assets/pixel-agents/assets/furniture/MARKETDESK_PACK');
const manifest = JSON.parse(await readFile(resolve(packDir, 'manifest.json'), 'utf8'));
let transparentSprites = 0;

for (const asset of manifest.assets) {
  const png = await readFile(resolve(packDir, asset.file));
  if (png.toString('hex', 0, 8) !== '89504e470d0a1a0a') throw new Error(`Invalid PNG signature: ${asset.file}`);
  const compressed = [];
  let offset = 8;
  let width = 0;
  let height = 0;
  let colorType = -1;
  while (offset < png.length) {
    const length = png.readUInt32BE(offset);
    const type = png.toString('ascii', offset + 4, offset + 8);
    const data = png.subarray(offset + 8, offset + 8 + length);
    if (type === 'IHDR') {
      width = data.readUInt32BE(0);
      height = data.readUInt32BE(4);
      colorType = data[9];
    } else if (type === 'IDAT') compressed.push(data);
    offset += length + 12;
  }
  if (width !== asset.width || height !== asset.height || colorType !== 6) {
    throw new Error(`Manifest dimensions or RGBA format mismatch: ${asset.file}`);
  }

  const pixels = inflateSync(Buffer.concat(compressed));
  let hasTransparentPixel = false;
  for (let y = 0; y < height; y++) {
    const row = y * (width * 4 + 1);
    if (pixels[row] !== 0) throw new Error(`Unexpected non-pixel PNG filter: ${asset.file}`);
    for (let x = 0; x < width; x++) {
      if (pixels[row + 1 + x * 4 + 3] === 0) hasTransparentPixel = true;
    }
  }
  // Wall modules deliberately fill their whole tile with glass/frame pixels;
  // ordinary furniture sprites must retain transparency around their silhouette.
  if (!hasTransparentPixel && !asset.isWallTile) throw new Error(`Sprite has no transparent pixels: ${asset.file}`);
  if (hasTransparentPixel) transparentSprites++;
}

console.log(`Validated ${manifest.assets.length} RGBA PNGs: dimensions match the manifest; ${transparentSprites} sprites have transparent pixels and opaque wall modules are allowed.`);
