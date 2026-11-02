"""Original glass corridor elevations at the native Pixel Agents scale."""
from pathlib import Path
from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parents[1] / 'internships_project/city_assets/pixel-agents/assets/tower'
OUT.mkdir(parents=True, exist_ok=True)
W,H=32,304
for side in ('west','east'):
    im=Image.new('RGBA',(W,H)); d=ImageDraw.Draw(im)
    d.rectangle((0,0,W-1,H-1),fill='#091421')
    d.rectangle((3,1,28,H-2),fill='#1b3240')
    # Different windows avoid the visually repetitive stacked sprite pattern.
    for i,y in enumerate(range(4,H-4,48)):
        end=min(y+43,H-4)
        d.rectangle((6,y,25,end),fill=['#274451','#213b4a','#304955'][i%3])
        d.polygon([(7,y+2),(9,y+2),(24,min(end,y+26)),(24,min(end,y+35))],fill='#3b5e6b')
        d.line((7,end-1,24,end-1),fill='#617477')
        d.rectangle((1,end+1,30,min(end+3,H-1)),fill='#10212a')
        d.line((2,end+1,29,end+1),fill='#6a7b78')
        if i in (0,2,4,6) and end-y>=10:
            d.rectangle((10,y+7,12,min(y+24,end-2)),fill='#a27332')
            d.line((11,y+8,11,min(y+23,end-2)),fill='#ffe4a0')
    # Continuous dark frame and shadow make the volume read as one structure.
    d.rectangle((0,0,3,H-1),fill='#091420');d.line((3,0,3,H-1),fill='#718589')
    d.rectangle((28,0,31,H-1),fill='#0b1722');d.line((28,0,28,H-1),fill='#879491')
    d.line((30,0,30,H-1),fill='#263c4c')
    d.line((4,0,27,0),fill='#b8a27c');d.line((4,H-1,27,H-1),fill='#0a131d')
    if side=='east':im=im.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    im.save(OUT/f'md_glass_corridor_{side}.png')
print('Created 2 full-height corridor elevations (32 x 304).')
