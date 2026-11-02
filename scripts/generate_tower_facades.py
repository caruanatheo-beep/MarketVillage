"""Original modular pixel-art architecture; transparent PNGs at native scale."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parents[1] / "internships_project/city_assets/pixel-agents/assets/tower"
OUT.mkdir(parents=True, exist_ok=True)

def new(w,h):
    image=Image.new("RGBA",(w,h)); return image,ImageDraw.Draw(image)

# Glazed penthouse cornice, with warm internal light and dark structural supports.
im,d=new(288,40)
d.polygon([(0,11),(14,3),(272,3),(287,11),(282,33),(5,33)],fill="#091827",outline="#9a9d8b")
d.rectangle((7,11,280,31),fill="#173447")
for i,x in enumerate(range(9,280,30)):
    d.rectangle((x,13,x+25,29),fill="#31546a" if i%3 else "#755a3f")
    d.line((x+2,14,x+16,28),fill="#93bed27a")
    if i%3==0:d.rectangle((x+17,22,x+21,26),fill="#e7a951")
    d.rectangle((x+26,11,x+29,32),fill="#111a25")
d.line((9,7,278,7),fill="#d6b889",width=2);d.line((6,34,281,34),fill="#f2b461",width=2)
im.save(OUT/"md_penthouse_glass.png")

# Skylight frame leaves the lounge below completely visible.
im,d=new(256,32)
d.polygon([(0,9),(18,1),(238,1),(255,9),(240,27),(16,27)],fill="#142a3ad9",outline="#b9b39c")
d.polygon([(7,10),(21,4),(235,4),(248,10),(237,23),(19,23)],fill="#53819777")
for x in range(25,236,35):
    d.line((x,5,x+4,23),fill="#1a2832",width=3);d.line((x+4,5,x+8,23),fill="#a1bcc477")
d.line((15,27,240,27),fill="#e8bd79",width=2)
im.save(OUT/"md_atrium_canopy.png")

# Connected angled balcony module with glass panels and planter box.
im,d=new(128,32)
d.polygon([(0,8),(112,8),(127,16),(127,24),(10,24),(0,17)],fill="#0b1825",outline="#697c80")
d.polygon([(4,7),(110,7),(122,13),(16,13)],fill="#816744")
d.line((5,8,110,8),fill="#e4bc7b")
for x in range(8,110,22):
    d.rectangle((x,16,x+18,22),fill="#315365");d.line((x+2,17,x+12,21),fill="#6d9ca5")
    d.rectangle((x+19,14,x+21,25),fill="#152534")
d.line((10,26,126,26),fill="#efb15f")
d.rectangle((34,1,78,6),fill="#574d35")
for x in range(35,78,5):d.rectangle((x,0,x+3,4),fill=["#345f3c","#507e48","#7b9557"][x%3])
im.save(OUT/"md_setback_balcony.png")

# Modular facade bay with staggered illuminated windows and a cast shadow.
im,d=new(96,40)
d.rectangle((0,0,95,39),fill="#081521");d.rectangle((1,2,94,31),fill="#1d3444")
for i,x in enumerate(range(3,94,15)):
    d.rectangle((x,4,x+11,28),fill="#254b61" if i%3 else "#6b573e")
    d.line((x+2,5,x+9,24),fill="#618b9a")
    if i%3==0:d.rectangle((x+6,20,x+9,25),fill="#f0ad4d")
    d.rectangle((x+12,2,x+14,32),fill="#101c29")
d.rectangle((0,32,95,35),fill="#64717a");d.line((0,32,95,32),fill="#e6b363")
d.rectangle((2,36,93,39),fill="#050c1690")
im.save(OUT/"md_facade_bay.png")

# Front-facing wall sign: rendered on the backdrop so the perspective never squashes its letters.
im,d=new(28,118)
d.rectangle((0,0,27,117),fill="#071629",outline="#789aac",width=2)
d.rectangle((4,4,23,113),fill="#073ca6");d.rectangle((5,5,22,112),fill="#155be0")
d.line((6,6,6,111),fill="#80eaff");d.line((21,6,21,111),fill="#0a2d82")
font=ImageFont.load_default()
for i,ch in enumerate("MARKETDESK"):
    d.text((10,6+i*8),ch,font=font,fill="#e9faff",stroke_width=0)
for i,ch in enumerate("CITY"):
    d.text((10,87+i*7),ch,font=font,fill="#bceaff")
d.rectangle((6,111,21,113),fill="#f568c6")
im.save(OUT/"md_vertical_sign.png")
print("Created five original reusable tower facade PNGs.")
