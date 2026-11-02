"""Original modular Manhattan pixel art, native 16 px grid (no borrowed art)."""
from pathlib import Path
import random
from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parents[1] / 'internships_project/city_assets/pixel-agents/assets/tower'
OUT.mkdir(parents=True, exist_ok=True)
rng = random.Random(871)

def image(w, h):
    im = Image.new('RGBA', (w, h))
    return im, ImageDraw.Draw(im)

# Three independently assembled skyscrapers, not a building-wide background.
for n in range(3):
    im, d = image(96, 128)
    d.rectangle((8, 30, 87, 127), fill='#09182b', outline='#28425b')
    d.rectangle((18, 16+n*3, 77, 34), fill='#102039', outline='#29465e')
    d.rectangle((30, 9, 65, 18+n*3), fill='#182d44')
    d.line((48, 0, 48, 9), fill='#76b1c3')
    d.point((48, 0), fill='#ff9b9b')
    for x in range(12, 85, 8):
        d.line((x, 32, x, 127), fill='#223b52')
        for y in range(36, 125, 8):
            color = rng.choice(['#f0b45f', '#b5793c', '#4e8cad', '#152b43', '#152b43'])
            d.rectangle((x+2, y, x+4, y+3), fill=color)
    for y in range(32, 128, 16): d.line((8, y, 87, y), fill='#375269')
    im.save(OUT / f'skyline-{n}.png')

# Dark blue curtain wall, with inset mullions and warm reflected light.
im, d = image(64, 32)
d.rectangle((0, 0, 63, 31), fill='#101d2d')
for x in range(0, 64, 16):
    d.rectangle((x+2, 3, x+13, 27), fill='#1b3550')
    for y in range(4,28):
        d.line((x+3,y,x+12,y),fill=(20+y//2,40+y//2,61+y//2,255))
    d.line((x+3,4,x+3,26),fill='#446579')
    d.line((x+14,1,x+14,29), fill='#425362')
    d.line((x+5,8,x+11,8),fill='#37596c')
    d.rectangle((x+5,23,x+10,25), fill='#d99442')
d.rectangle((0,0,63,2), fill='#596877')
d.line((0,3,63,3), fill='#9bc4c9')
d.rectangle((0,29,63,31), fill='#07111f')
im.save(OUT/'facade.png')

# Tall atrium glazing: suspended amber pendants against layered blue glass.
im,d=image(192,64)
d.rectangle((0,0,191,63),fill='#0b1827')
for x in range(4,192,24):
    d.rectangle((x,5,x+19,57),fill='#20384c')
    d.rectangle((x+2,7,x+17,55),fill='#294658')
    d.line((x+3,9,x+3,53),fill='#567383')
    d.rectangle((x+20,2,x+23,61),fill='#101b28')
    d.line((x+20,3,x+20,60),fill='#69747a')
for x,y in [(29,21),(66,32),(104,20),(150,30)]:
    d.line((x,3,x,y),fill='#b5a179')
    d.rectangle((x-2,y,x+2,y+17),fill='#9b6534')
    d.rectangle((x-1,y,x+1,y+15),fill='#ffd17a')
    d.line((x,y+1,x,y+14),fill='#fff0c0')
for y in (1,59):
    d.rectangle((0,y,191,y+2),fill='#5e6b70')
    d.line((0,y+3,191,y+3),fill='#c49c61')
im.save(OUT/'atrium.png')

im,d=image(64,16)
d.rectangle((0,5,63,14), fill='#254557')
for x in (0,21,42,63): d.rectangle((x,1,min(x+1,63),15),fill='#879695')
d.line((0,1,63,1),fill='#cad4c9');d.line((0,12,63,12),fill='#78bbc8')
d.line((0,15,63,15),fill='#0b1421')
im.save(OUT/'railing.png')

im,d=image(64,32)
d.rectangle((0,0,63,31), fill='#26333e')
for y in range(0,32,4):
    d.rectangle((3,y,60,y+2),fill='#758080')
    d.line((3,y,60,y),fill='#bac1b5')
    d.line((3,y+3,60,y+3),fill='#142331')
for x in (0,62):d.line((x,0,x,31),fill='#e6b56b')
im.save(OUT/'stairs.png')

im,d=image(32,96)
d.rectangle((0,0,31,95),fill='#081c37',outline='#65cded')
for y in range(4,92,3):d.line((3,y,28,y),fill='#12355b')
# Chart is decorative signage, deliberately has no market values.
d.line([(4,70),(9,61),(13,65),(18,46),(24,49),(28,28)],fill='#63dce8',width=2)
for x,y in [(6,80),(12,76),(18,70),(24,73)]:d.rectangle((x,y,x+3,89),fill='#536cba')
d.rectangle((2,2,29,5),fill='#99deed')
im.save(OUT/'led-sign.png')

im,d=image(128,64)
d.rectangle((0,0,127,63),fill='#34454a')
for y in range(0,64,16):
    for x in range(0,128,32):
        d.rectangle((x,y,x+31,y+15),fill=rng.choice(['#34454a','#38494c','#304247']))
        d.line((x,y+15,x+31,y+15),fill='#25363d')
        d.line((x+31,y,x+31,y+15),fill='#293b42')
im.save(OUT/'terrace.png')
im,d=image(48,24)
d.rectangle((2,15,45,23),fill='#101d27')
d.rectangle((3,14,44,20),fill='#627576')
d.line((3,14,44,14),fill='#adc1aa')
for x in range(5,44,5):
    d.rectangle((x,5,x+2,14),fill='#365448')
    d.ellipse((x-3,2,x+4,10),fill=rng.choice(['#3c654e','#547a52','#688650']))
    d.point((x,3),fill='#a0ad64')
d.line((5,21,42,21),fill='#d9a756')
im.save(OUT/'planter.png')
im,d=image(128,64)
d.rectangle((0,0,127,63),fill='#315b35')
for _ in range(950):
    x,y=rng.randrange(128),rng.randrange(64)
    d.point((x,y),fill=rng.choice(['#345f38','#3b653c','#2d5232','#426e40']))
im.save(OUT/'turf.png')
print('Created 10 original modular tower assets')
