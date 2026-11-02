"""Native modules for attached tower piers and slab edges (original artwork)."""
from pathlib import Path
from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parents[1] / 'internships_project/city_assets/pixel-agents/assets/tower'


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    # N/E/S/W auto-tiles: a real raised partition, bottom-anchored by the
    # Pixel Agents wall renderer. The cream sill and blue glass are original.
    for mask in range(16):
        image = Image.new('RGBA', (16, 24))
        d = ImageDraw.Draw(image)
        north, east, south, west = (bool(mask & bit) for bit in (1, 2, 4, 8))
        horizontal, vertical = east or west, north or south
        if horizontal or not vertical:
            left, right = (0 if west else 3), (15 if east else 12)
            # Clear glass: the indoor foundation stays visible. No repeated
            # diagonal symbols or opaque blue fills on adjacent tile modules.
            for y in range(6, 21):
                d.line((left,y,right,y), fill=(78,122,151,145 if y<10 else 118))
            d.rectangle((left, 3, right, 5), fill='#22323f')
            d.line((left, 3, right, 3), fill='#8c999e')
            d.line((left, 6, right, 6), fill='#a6c0c142')
            d.rectangle((left, 21, right, 23), fill='#253542')
            d.line((left, 21, right, 21), fill='#9b9989')
            d.line((left, 23, right, 23), fill='#101d29')
            if not west: d.rectangle((left, 4, left+1, 22), fill='#32424e')
            if not east: d.rectangle((right-1, 4, right, 22), fill='#32424e')
        if vertical:
            top, bottom = (0 if north else 14), (23 if south else 21)
            d.rectangle((5, top, 9, bottom), fill='#6590aa88')
            d.line((4, top, 4, bottom), fill='#89979d')
            d.line((5, top, 5, bottom), fill='#2c3d49')
            d.line((10, top, 10, bottom), fill='#2c3d49')
            d.line((11, top, 11, bottom), fill='#a19b83')
            if not north: d.line((4, top, 11, top), fill='#b4b7ae')
            if not south: d.line((4, bottom, 11, bottom), fill='#192735')
        if horizontal and vertical:
            # One aligned junction post closes L/T corners without overhangs.
            d.rectangle((5, 3, 10, 5), fill='#344652')
            d.line((5, 3, 10, 3), fill='#a5b1b5')
        image.save(OUT / f'md_partition_{mask:02x}.png')

    # An open sliding glass entrance. The clear centre is a genuine doorway.
    image = Image.new('RGBA', (64, 32))
    d = ImageDraw.Draw(image)
    for left, right in ((1, 21), (42, 62)):
        d.rectangle((left, 6, right, 28), outline='#32434e', width=2)
        d.rectangle((left+2, 8, right-2, 24), fill='#84a9bd70')
        d.line((left+3, 9, left+3, 23), fill='#cad9d333')
        d.line((left, 6, right, 6), fill='#94aabb')
        d.line((left+1, 27, right-1, 27), fill='#c7ad7b')
    d.rectangle((0, 4, 63, 6), fill='#1a324c')
    d.line((1, 4, 62, 4), fill='#9cabb3')
    d.line((0, 29, 63, 29), fill='#172b3f')
    image.save(OUT / 'md_entry_glass.png')

    image = Image.new('RGBA', (16, 32))
    d = ImageDraw.Draw(image)
    for x in (1, 13):
        d.rectangle((x, 5, x+1, 29), fill='#1b354d')
        d.line((x, 6, x, 28), fill='#8fa9b6')
    d.line((1, 4, 14, 4), fill='#adb7ba', width=2)
    d.line((2, 29, 13, 29), fill='#c9af7e')
    image.save(OUT / 'md_entry_jamb.png')

    image = Image.new('RGBA', (16, 32))
    d = ImageDraw.Draw(image)
    for top, bottom in ((0, 6), (25, 31)):
        d.rectangle((4, top, 11, bottom), fill='#152e47')
        d.line((4, top, 4, bottom), fill='#91afbf')
        d.line((11, top, 11, bottom), fill='#c0aa80')
        d.rectangle((6, top+1, 8, bottom-1), fill='#507b96')
    d.line((4, 7, 4, 11), fill='#7597a9')
    d.line((11, 20, 11, 24), fill='#7597a9')
    image.save(OUT / 'md_side_entry.png')

    image = Image.new('RGBA', (32, 32))
    d = ImageDraw.Draw(image)
    d.rectangle((0, 5, 31, 7), fill='#142d47')
    d.line((1, 5, 30, 5), fill='#9aaeb8')
    for left, right in ((1, 7), (24, 30)):
        d.rectangle((left, 8, right, 28), outline='#32434e')
        d.rectangle((left+1, 9, right-1, 26), fill='#84a9bd70')
        d.line((left+1, 10, left+1, 25), fill='#cad9d344')
    d.line((0, 29, 31, 29), fill='#b99f74')
    image.save(OUT / 'md_entry_pair.png')
    image = Image.new('RGBA', (16, 48))
    d = ImageDraw.Draw(image)
    d.rectangle((1, 0, 14, 47), fill='#132638')
    d.rectangle((3, 0, 12, 47), fill='#2b485b')
    d.rectangle((4, 0, 10, 47), fill='#35566b')
    d.line((3, 0, 3, 47), fill='#a2b2b4')
    d.line((12, 0, 12, 47), fill='#071725', width=2)
    # Glass reflections and slender mullions repeat cleanly at the native scale.
    for y in (0, 24):
        d.polygon(((4, y+2), (6, y+2), (10, y+12), (10, y+17)), fill='#688897')
        d.rectangle((3, y+22, 12, y+23), fill='#162b3c')
        d.line((4, y+22, 11, y+22), fill='#87958e')
    d.rectangle((7, 6, 8, 14), fill='#e0ad61')
    d.line((8, 7, 8, 13), fill='#ffe3a8')
    image.save(OUT / 'md_corridor_pier.png')

    image = Image.new('RGBA', (64, 16))
    d = ImageDraw.Draw(image)
    d.rectangle((0, 0, 63, 15), fill='#132638')
    d.line((0, 0, 63, 0), fill='#8b9fa4')
    for x in (0, 16, 32, 48):
        d.rectangle((x+2, 2, x+13, 11), fill='#365565')
        d.polygon(((x+3, 3), (x+5, 3), (x+12, 9), (x+10, 9)), fill='#67838b')
        d.line((x+15, 1, x+15, 12), fill='#091a29')
    d.rectangle((0, 12, 63, 15), fill='#0e2030')
    d.line((0, 13, 63, 13), fill='#d2ad72')
    image.save(OUT / 'md_glass_transom.png')

    image = Image.new('RGBA', (64, 9))
    d = ImageDraw.Draw(image)
    d.rectangle((0, 0, 63, 8), fill='#091522')
    d.line((0, 0, 63, 0), fill='#a6aba3')
    d.line((0, 1, 63, 1), fill='#d6ac71')
    d.rectangle((0, 3, 63, 6), fill='#234866')
    for x in (0, 16, 32, 48):
        d.line((x, 3, x+7, 6), fill='#5e849c')
        d.line((x+15, 2, x+15, 7), fill='#0d1e2d')
    d.line((0, 8, 63, 8), fill='#040b13')
    image.save(OUT / 'md_slab_edge.png')
    # Guard the material and open portals, not only PNG dimensions.
    with Image.open(OUT / 'md_partition_0a.png') as glass:
        assert glass.size == (16, 24)
        assert 0 < glass.getpixel((8, 14))[3] < 200, 'Glass must stay translucent'
        assert glass.getpixel((8, 3))[3] == 255, 'Frame must stay solid'
    for name, point in [('md_side_entry', (8, 16)), ('md_entry_pair', (16, 16)), ('md_entry_glass', (31, 16))]:
        with Image.open(OUT / f'{name}.png') as door:
            assert door.getpixel(point)[3] == 0, f'{name}: doorway is visually obstructed'
    print('Created 16 raised partition auto-tiles, 4 open glass doors and 3 facade modules.')


if __name__ == '__main__':
    main()
