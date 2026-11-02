"""Original native-resolution facade modules for the playable MarketDesk tower.

These sprites occupy non-walkable facade cells. No reference image is used as
the office floor, furniture, or navigation surface.
"""
from pathlib import Path
import random
from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parents[1] / 'internships_project/city_assets/pixel-agents/assets/tower'
OUT.mkdir(parents=True, exist_ok=True)
rng = random.Random(241101)


def canvas(w, h):
    im = Image.new('RGBA', (w, h))
    return im, ImageDraw.Draw(im)


def leaf_cluster(d, x, y, radius=8):
    d.line((x, y + radius, x, y), fill='#776043', width=2)
    for _ in range(30):
        xx, yy = x + rng.randint(-radius, radius), y + rng.randint(-radius, radius)
        d.ellipse((xx, yy, xx + 3, yy + 3), fill=rng.choice(['#173b2b', '#31583a', '#547744', '#7f9252']))


# A double-height glazed atrium, with varied hanging lights and a recessed base.
im, d = canvas(288, 80)
d.rectangle((0, 0, 287, 79), fill='#06111e')
for x in range(4, 288, 36):
    d.rectangle((x, 4, x + 29, 71), fill='#173145')
    for y in range(6, 70):
        d.line((x + 2, y, x + 27, y), fill=(17 + y // 7, 36 + y // 5, 52 + y // 4))
    d.polygon([(x + 3, 5), (x + 7, 5), (x + 27, 48), (x + 27, 64)], fill='#294857')
    d.line((x + 1, 5, x + 1, 70), fill='#5c7380')
    d.rectangle((x + 30, 0, x + 34, 77), fill='#0b1722')
    d.line((x + 34, 2, x + 34, 74), fill='#3e5363')
for x, y in [(40, 12), (83, 27), (198, 17), (248, 6)]:
    d.line((x, 1, x, y), fill='#9b8359')
    d.rectangle((x - 3, y, x + 3, y + 30), fill='#654729')
    d.rectangle((x - 1, y + 1, x + 1, y + 28), fill='#ffc35e')
    d.line((x, y + 2, x, y + 27), fill='#fff2cb')
    d.rectangle((x - 4, y + 31, x + 4, y + 32), fill='#c08a46')
for y, color in [(0, '#79868a'), (2, '#182b3b'), (73, '#9a7448'), (75, '#edb765'), (78, '#020811')]:
    d.line((0, y, 287, y), fill=color, width=2)
im.save(OUT / 'atrium-premium.png')

# Tall side returns make each inhabited wing read as an independent volume.
im, d = canvas(24, 96)
d.polygon([(0, 5), (17, 0), (23, 5), (23, 95), (0, 90)], fill='#08121f')
d.rectangle((3, 7, 16, 89), fill='#1a3344')
for y in range(10, 88, 22):
    d.rectangle((5, y, 14, y + 17), fill='#28495a')
    d.line((6, y, 13, y + 14), fill='#426273')
    d.rectangle((17, y + 6, 19, y + 15), fill='#ffcb76')
d.line((1, 7, 1, 90), fill='#667782')
d.line((21, 6, 21, 94), fill='#030a12', width=2)
im.save(OUT / 'bay-return.png')

# Balconies: dark metal cap, translucent blue glass, brushed posts, warm footlight.
im, d = canvas(128, 20)
d.rectangle((0, 6, 127, 18), fill='#0a1621')
d.rectangle((2, 5, 125, 14), fill='#3c586566')
for x in range(0, 128, 24):
    d.line((x, 1, x, 17), fill='#8d9c9c', width=2)
    d.line((x + 2, 4, min(x + 20, 127), 12), fill='#749ca23a')
d.line((0, 1, 127, 1), fill='#a4b8b9', width=2)
d.line((0, 16, 127, 16), fill='#c18a43')
d.line((0, 19, 127, 19), fill='#02070c')
im.save(OUT / 'balcony-glass.png')

# Climbing vegetation, used on facade ledges and columns rather than walkways.
im, d = canvas(64, 48)
d.rectangle((2, 32, 61, 43), fill='#18272b')
d.rectangle((1, 31, 62, 34), fill='#8c8870')
for x, y, r in [(9, 24, 7), (22, 18, 9), (37, 23, 9), (53, 17, 8)]:
    leaf_cluster(d, x, y, r)
    for yy in range(33, rng.randint(38, 47)):
        d.rectangle((x + yy % 3, yy, x + yy % 3 + 2, yy + 1), fill='#416541')
for x in [8, 30, 52]:
    d.rectangle((x, 38, x + 3, 39), fill='#ffd391')
im.save(OUT / 'hanging-garden.png')

# Real structural LED fin, with architectural copy only (no invented quotes).
for name, words, color in [('market-fin', ['MARKETS', 'IDEAS', 'PEOPLE', 'TECH'], '#1e69df'),
                           ('research-fin', ['GLOBAL', 'MARKETS', 'AI', 'RESEARCH'], '#284cc9')]:
    im, d = canvas(40, 144)
    d.rectangle((0, 0, 39, 143), fill='#071323', outline='#70899a')
    d.rectangle((4, 4, 35, 137), fill=color)
    # A continuous saturated LED surface; former scanlines drowned the lettering.
    d.polygon([(5, 5), (16, 5), (34, 137), (28, 137)], fill='#2b83ed')
    for i, word in enumerate(words):
        # Fit the real glyph bounds, then quantize the mask to keep crisp pixels.
        font = ImageFont.load_default(size=9)
        while d.textbbox((0, 0), word, font=font)[2] > 30:
            font = ImageFont.load_default(size=font.size - 1)
        bounds = d.textbbox((0, 0), word, font=font)
        mask = Image.new('1', (40, 14))
        ImageDraw.Draw(mask).text(((40 - bounds[2]) // 2, -bounds[1]), word, font=font, fill=1)
        im.paste('#d7faff', (0, 10 + i * 17), mask)
    if name == 'market-fin':
        for points in [[(7, 94), (15, 90), (20, 96), (16, 101), (12, 103)],
                       [(15, 106), (21, 107), (24, 117), (20, 125)],
                       [(23, 92), (32, 93), (34, 99), (29, 104), (25, 100)]]:
            d.polygon(points, fill='#a0d9f5')
    else:
        d.line([(6, 117), (11, 111), (16, 113), (23, 98), (28, 101), (33, 90)], fill='#c2f3ff', width=2)
    d.rectangle((4, 132, 35, 138), fill='#cc5799')
    im.save(OUT / f'{name}.png')

# The building entrance sits behind the real, navigable centre staircase.
im, d = canvas(128, 40)
d.rectangle((0, 0, 127, 39), fill='#091523')
for x in range(4, 128, 20):
    d.rectangle((x, 4, x + 15, 34), fill='#233a47')
    d.line((x + 2, 5, x + 13, 29), fill='#5d6d704a')
    d.line((x, 4, x, 34), fill='#6e7d83')
d.rectangle((44, 2, 83, 38), fill='#907241')
d.rectangle((47, 5, 80, 37), fill='#c9a968')
d.line((64, 7, 64, 37), fill='#4d514d')
for x in [60, 68]:
    d.line((x, 21, x, 30), fill='#303c44', width=2)
d.line((0, 1, 127, 1), fill='#ffcd7c', width=2)
im.save(OUT / 'lobby-entry.png')

# Transparent elevated walkway: the four existing navigation columns stay clear.
im, d = canvas(64, 64)
d.rectangle((3, 0, 60, 63), fill='#172d3b')
for y in range(2, 64, 12):
    d.rectangle((8, y, 55, y + 9), fill='#355465')
    d.line((10, y + 1, 51, y + 8), fill='#658088')
    d.line((8, y + 10, 55, y + 10), fill='#0e202d')
for x in [3, 59]:
    d.rectangle((x, 0, x + 2, 63), fill='#73868a')
    d.line((x + 1, 1, x + 1, 62), fill='#b3c0b6')
for y in [4, 52]:
    d.rectangle((4, y, 6, y + 7), fill='#ffcf7c')
    d.rectangle((57, y, 59, y + 7), fill='#ffcf7c')
im.save(OUT / 'glass-bridge.png')

# Fine protective mesh with explicit stanchions; the entry gap is kept in code.
im, d = canvas(64, 24)
for x in range(-20, 85, 6):
    d.line((x, 2, x + 22, 22), fill='#78958d70')
    d.line((x, 22, x + 22, 2), fill='#78958d70')
for x in [0, 62]:
    d.rectangle((x, 0, x + 1, 23), fill='#526971')
d.line((0, 1, 63, 1), fill='#94a397')
d.line((0, 23, 63, 23), fill='#152829')
im.save(OUT / 'practice-net.png')

# Stepped roof crown and stone-capped vegetation give the penthouse a silhouette.
im, d = canvas(224, 32)
for left, right, top in [(0, 223, 24), (20, 203, 15), (42, 181, 7), (67, 156, 0)]:
    d.rectangle((left, top, right, 31), fill='#122431', outline='#596e77')
    d.line((left + 1, top + 1, right - 1, top + 1), fill='#d4a96b')
    d.line((left + 2, top + 4, right - 2, top + 4), fill='#09131e')
for x in [30, 58, 91, 127, 163, 191]:
    leaf_cluster(d, x, 23, 5)
im.save(OUT / 'penthouse-crown.png')

im, d = canvas(32, 64)
d.ellipse((4, 53, 29, 63), fill='#09111a80')
d.polygon([(7, 45), (26, 45), (23, 59), (11, 59)], fill='#524b37', outline='#a28d61')
d.ellipse((7, 42, 26, 48), fill='#b19c6e')
d.ellipse((10, 43, 24, 46), fill='#253d2a')
d.line((16, 15, 17, 46), fill='#7c653a', width=3)
for x, y, r in [(16, 12, 9), (12, 23, 8), (20, 27, 9), (15, 36, 7)]:
    leaf_cluster(d, x, y, r)
d.line((11, 55, 23, 55), fill='#332e27')
im.save(OUT / 'terrace-topiary.png')
furniture = OUT.parent / 'furniture/MARKETDESK_PACK/premium'
furniture.mkdir(parents=True, exist_ok=True)
im.save(furniture / 'terrace_topiary.png')

im, d = canvas(160, 48)
d.rectangle((3, 9, 156, 45), fill='#09131e')
for x in range(5, 156, 25):
    d.rectangle((x, 12, x + 21, 41), fill='#233d4c')
    d.line((x + 2, 13, x + 18, 37), fill='#63818b')
for x in [0, 154]:
    d.rectangle((x, 8, x + 5, 47), fill='#67716e')
    d.line((x + 1, 10, x + 1, 45), fill='#b3ae94')
d.rectangle((58, 13, 101, 46), fill='#b79456')
d.rectangle((61, 15, 98, 46), fill='#caad73')
d.line((80, 16, 80, 45), fill='#4b534f')
for x in [75, 85]:
    d.line((x, 28, x, 38), fill='#263b45', width=2)
d.polygon([(0, 6), (13, 0), (147, 0), (159, 6), (153, 12), (7, 12)], fill='#172a38', outline='#6b7e81')
d.line((8, 10, 151, 10), fill='#ffd07b', width=2)
for x in range(18, 145, 21):
    d.rectangle((x, 5, x + 2, 6), fill='#ffedb1')
im.save(OUT / 'entrance-canopy.png')

for file in OUT.glob('*.png'):
    with Image.open(file) as check:
        assert check.width > 0 and check.height > 0
print('Created 12 original tower identity modules at native pixel resolution.')
