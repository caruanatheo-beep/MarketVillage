"""Original 16px-grid architectural modules for the MarketDesk tower."""
from pathlib import Path
import random
from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parents[1] / 'internships_project/city_assets/pixel-agents/assets/tower'
OUT.mkdir(parents=True, exist_ok=True)
rng = random.Random(1938)

def canvas(w, h):
    im = Image.new('RGBA', (w, h))
    return im, ImageDraw.Draw(im)

# Native-size atrium: multiple bays, recessed glass, suspension lamps and
# structural columns. Its central bridge is rendered separately by the engine.
im, d = canvas(288, 64)
d.rectangle((0, 0, 287, 63), fill='#091725')
for x in range(4, 288, 32):
    d.rectangle((x, 5, x+25, 58), fill='#1b344b')
    for y in range(7, 56):
        d.line((x+2, y, x+23, y), fill=(23+y//3, 44+y//3, 61+y//4))
    d.polygon([(x+3,7),(x+12,7),(x+23,31),(x+23,45)], fill='#30485b')
    d.line((x,5,x,58), fill='#8b9695')
    d.rectangle((x+26,2,x+29,61),fill='#101c28')
    d.line((x+29,3,x+29,60),fill='#60717d')
for x, end in [(21,39),(53,46),(87,34),(201,38),(235,47),(267,35)]:
    d.line((x,5,x,end-14),fill='#a18d66')
    d.rectangle((x-3,end-15,x+3,end+2), fill='#7d582a')
    d.rectangle((x-1,end-14,x+1,end), fill='#ffcb69')
    d.line((x,end-13,x,end-1),fill='#fff2c3')
for y, color in [(0,'#75858a'),(2,'#233340'),(59,'#cfa260'),(61,'#172331'),(63,'#030b14')]:
    d.line((0,y,287,y),fill=color,width=2)
im.save(OUT/'atrium.png')

# Facade has a narrow amber cornice, deep glass and substantial contact shadow.
im,d=canvas(64,48)
d.rectangle((0,0,63,47),fill='#071222')
for x in [3,23,43]:
    d.rectangle((x,7,x+16,40),fill='#17354e')
    d.polygon([(x+2,9),(x+6,9),(x+14,27),(x+14,36)], fill='#23475e')
    d.line((x,7,x,41),fill='#637983')
    d.rectangle((x+17,5,x+19,43),fill='#101b27')
    d.line((x+1,39,x+15,39),fill='#bf8950')
    d.line((x+1,40,x+15,40),fill='#5b4d3c')
for y,col in [(0,'#809293'),(2,'#263844'),(4,'#e5b36c'),(43,'#293b48'),(45,'#040b15')]:
    d.line((0,y,63,y),fill=col,width=2)
im.save(OUT/'facade.png')

# Planter/parapet with individually drawn foliage, a stone lip and footlights.
im,d=canvas(64,32)
d.rectangle((2,22,61,29),fill='#142731')
d.rectangle((1,20,62,23),fill='#75817a')
d.line((3,30,60,30),fill='#020910',width=2)
for x in range(7,60,9):
    d.line((x,22,x,10),fill='#70613b',width=2)
    for _ in range(12):
        xx=x+rng.randint(-5,5); yy=rng.randint(5,19)
        d.rectangle((xx,yy,xx+2,yy+3),fill=rng.choice(['#264b31','#3e6335','#668345','#869b53']))
for x in [9,31,53]:
    d.rectangle((x,25,x+3,26),fill='#ffcc79')
im.save(OUT/'garden-parapet.png')

# Architectural terrace accent: no fabricated metrics or market quotations.
im,d=canvas(32,112)
d.rectangle((0,0,31,111),fill='#091426',outline='#7793a2')
d.rectangle((3,4,28,106),fill='#123ba0')
for y in range(5,105,3): d.line((4,y,27,y),fill='#1748ae')
for x,y in [(7,18),(14,14),(21,22),(7,38),(14,34),(21,42)]:
    d.rectangle((x,y,x+3,y+8),fill='#9eeaff')
d.line([(5,84),(9,78),(13,81),(17,66),(21,72),(26,57)],fill='#c6f6ff',width=2)
d.rectangle((4,96,27,102),fill='#d9489e')
im.save(OUT/'led-sign.png')
print('Premium architecture: atrium, facade, garden parapet, LED sign')
