"""Original 16-pixel-grid terrace sprites; deterministic, no external artwork."""
from pathlib import Path
import json
import random
from PIL import Image, ImageDraw

DEST = Path(__file__).resolve().parents[1] / 'internships_project/city_assets/pixel-agents/assets/furniture/MARKETDESK_GOLF'
DEST.mkdir(parents=True, exist_ok=True)
assets = []

def sprite(key, size, footprint, background=0):
    im = Image.new('RGBA', size)
    return im, ImageDraw.Draw(im), dict(id=key, name=key.replace('MD_GOLF_', '').replace('_', ' ').title(),
        file=key.lower()+'.png', width=size[0], height=size[1], footprintW=footprint[0], footprintH=footprint[1],
        backgroundTiles=background, category='decor', isDesk=False)

def save(im, entry):
    im.save(DEST / entry['file'])
    assets.append(entry)

# Right-facing bay: stance left, ball/tee right, divider and basket below.
im,d,e=sprite('MD_GOLF_MAT',(80,32),(5,2),2)
d.rounded_rectangle((0,1,79,31),radius=3,fill='#132a2a',outline='#59674d')
d.rectangle((3,4,76,28),fill='#24603c',outline='#9aa962')
d.rectangle((6,6,28,26),fill='#3f804b')
d.line((32,6,32,26),fill='#769667')
for x in (10,22): d.line((x,11,x,22),fill='#457354')
d.line((45,16,63,16),fill='#517d59')
d.polygon([(64,14),(69,16),(64,18)],fill='#91af76')
d.ellipse((42,14,45,17),fill='#fff6d9')
for x,y in [(61,23),(65,24),(69,23),(64,20),(68,20)]: d.ellipse((x,y,x+2,y+2),fill='#ede9d2')
# Raised mat lip, east-facing stance, tightly drawn net posts and ball tray.
d.line((0,31,79,31),fill='#081b21',width=2)
d.line((3,4,76,4),fill='#83a966')
d.line((3,28,76,28),fill='#123b2c',width=2)
for x in [1,78]:
    d.rectangle((x,1,x+1,28),fill='#263d3d')
    d.line((x,1,x+1,1),fill='#b2bba0')
for y in range(7,25,4):
    d.point((78,y),fill='#76958a')
save(im,e)

im,d,e=sprite('MD_GOLF_BAG',(16,32),(1,2))
d.ellipse((1,27,15,31),fill=(3,12,19,110))
d.polygon([(4,10),(12,10),(14,27),(3,27)],fill='#1c4954',outline='#71979c')
d.rectangle((5,17,12,22),fill='#aa8851')
for x,y in [(5,1),(8,3),(11,0)]:
    d.line((x,y+2,x,12),fill='#b2c1c5')
    d.rectangle((x-2,y,x+1,y+2),fill='#637a8a')
d.arc((1,12,8,25),90,270,fill='#c1a46c')
save(im,e)

im,d,e=sprite('MD_GOLF_BASKET',(16,16),(1,1))
d.ellipse((2,11,14,15),fill=(3,12,19,100))
d.polygon([(2,4),(14,4),(12,13),(4,13)],fill='#304d49',outline='#829e89')
for x in (5,8,11): d.line((x,5,x,12),fill='#718d7e')
d.arc((2,0,14,10),180,360,fill='#91a998')
for x,y in [(4,3),(8,2),(11,4),(7,5)]:d.ellipse((x,y,x+2,y+2),fill='#fff1d1')
save(im,e)

im,d,e=sprite('MD_GOLF_GREEN',(80,48),(5,3))
d.ellipse((1,5,79,47),fill='#17352f')
d.ellipse((3,3,77,44),fill='#3e713b',outline='#7d9757',width=2)
d.ellipse((12,9,70,37),fill='#548641')
d.ellipse((10,10,27,20),fill='#c9b074',outline='#94764c')
d.ellipse((55,29,61,32),fill='#112c27')
d.line((58,9,58,29),fill='#ece5c2',width=1)
d.polygon([(59,9),(69,12),(59,15)],fill='#ec684d')
d.ellipse((34,31,36,33),fill='#fff5d2')
save(im,e)

im,d,e=sprite('MD_GOLF_LANTERN',(16,32),(1,2))
d.ellipse((2,27,15,31),fill=(3,12,19,110))
d.rectangle((7,11,9,28),fill='#8c7752');d.rectangle((4,28,12,30),fill='#35434b')
d.line((8,13,8,27),fill='#d6b477')
d.polygon([(3,4),(7,2),(11,3),(13,6),(12,12),(8,15),(4,12)],fill='#b7833e',outline='#7b6037')
d.polygon([(5,5),(8,3),(11,5),(11,11),(8,13),(5,11)],fill='#ffd36f')
d.line((8,4,8,11),fill='#fff6ca',width=2)
d.line((4,5,4,11),fill='#ffe2a1');d.line((12,5,12,11),fill='#e6ad4f')
d.polygon([(2,4),(8,0),(14,4),(12,5),(4,5)],fill='#34434c')
d.line((5,2,10,2),fill='#b8ac80')
save(im,e)

im,d,e=sprite('MD_GOLF_PLANTER',(48,16),(3,1))
d.rectangle((0,6,47,15),fill='#4b4438',outline='#9a805a')
d.line((2,11,45,11),fill='#715941')
for x in range(3,46,6):
    d.ellipse((x,0,x+5,8),fill='#3f6241');d.line((x+2,2,x+2,7),fill='#6d8550')
save(im,e)

im,d,e=sprite('MD_GOLF_BENCH',(48,24),(3,1))
for y in (3,7,11):d.rectangle((1,y,46,y+2),fill='#9c734b',outline='#bc9467')
d.rectangle((1,15,46,19),fill='#ad8254');d.line((1,19,46,19),fill='#573f31')
for x in (4,41): d.rectangle((x,20,x+2,23),fill='#475561')
save(im,e)

# Seamless original skyline/fence module, with restrained blue city windows.
im,d,e=sprite('MD_GOLF_SKYLINE',(96,32),(6,2),2)
d.rectangle((0,0,95,31),fill='#0a1830')
rng=random.Random(2107)
for x in range(0,96,9):
    top=rng.randrange(2,14);d.rectangle((x,top,x+8,30),fill='#14243b')
    for y in range(top+3,28,5):
        for dx in (2,5):
            if rng.random()<.57:d.rectangle((x+dx,y,x+dx+1,y+1),fill=rng.choice(['#bc995c','#ecc480','#769ca7']))
for x in range(0,96,4):d.line((x,13,x,31),fill=(102,132,145,65))
for y in range(15,32,4):d.line((0,y,95,y),fill=(102,132,145,65))
d.rectangle((0,30,95,31),fill='#54717a')
save(im,e)

im,d,e=sprite('MD_GOLF_DECK',(128,64),(8,4),4)
d.rectangle((0,0,127,63),fill='#74563e')
for y in range(0,64,8):
    d.line((0,y,127,y),fill='#4f4034');d.line((0,y+1,127,y+1),fill='#93714d')
    for x in range(4,125,13):d.line((x,y+5,min(x+7,127),y+5),fill='#7e6043')
    d.line(((y*7)%128,y,(y*7)%128,y+7),fill='#594635')
save(im,e)
(DEST/'manifest.json').write_text(json.dumps({'pack':'MarketDesk Golf · original art','tileSize':16,'assets':assets},indent=2),encoding='utf-8')
print(f'Created {len(assets)} original Golf Practice PNG assets in {DEST.name}')
