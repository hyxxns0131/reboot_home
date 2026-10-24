"""Extract original artwork, never generate/recolor product designs. Requires Pillow, numpy."""
from pathlib import Path
import sys
import numpy as np
from PIL import Image
from collections import deque
from PIL import ImageDraw
ROOT=Path(__file__).resolve().parents[1]
BOXES={'front':(.065,.02,.235,.49),'side':(.30,.02,.43,.49),'back':(.48,.02,.66,.49),'quarter':(.57,.55,.77,.94),'top':(.69,.18,.96,.40)}
kind = sys.argv[1] if len(sys.argv)>1 else 'beverage'
if kind not in ('beverage','jelly'): raise ValueError('Expected beverage or jelly')
if kind=='jelly':
    BOXES={'front':(.045,.125,.29,.40),'side':(.345,.125,.42,.40),'back':(.485,.125,.73,.40),'quarter':(.57,.54,.84,.86)}
for path in (ROOT/f'images/{kind}').glob('*_lime_3D.png' if kind=='jelly' else '*_3D.png'):
    src=Image.open(path).convert('RGB'); w,h=src.size
    for name,box in BOXES.items():
        crop=src.crop(tuple(round(v*(w if i%2==0 else h)) for i,v in enumerate(box)))
        a=np.array(crop); mask=np.min(a,axis=2)<225
        # Keep the largest connected silhouette, excluding measurement lines.
        seen=np.zeros(mask.shape,dtype=bool); best=[]
        for sy,sx in zip(*np.where(mask)):
            if seen[sy,sx]: continue
            seen[sy,sx]=True; q=deque([(sy,sx)]); component=[]
            while q:
                y,x=q.popleft(); component.append((y,x))
                for ny,nx in ((y-1,x),(y+1,x),(y,x-1),(y,x+1)):
                    if 0<=ny<mask.shape[0] and 0<=nx<mask.shape[1] and mask[ny,nx] and not seen[ny,nx]:
                        seen[ny,nx]=True; q.append((ny,nx))
            if len(component)>len(best): best=component
        mask[:]=False
        for y,x in best: mask[y,x]=True
        # Fill enclosed highlights so white cap/glass pixels are retained.
        m=Image.fromarray((mask*255).astype('uint8')); padded=Image.new('L',(m.width+2,m.height+2));padded.paste(m,(1,1))
        ImageDraw.floodfill(padded,(0,0),128)
        mask=np.array(padded)[1:-1,1:-1]!=128
        ys,xs=np.where(mask); bounds=(xs.min(),ys.min(),xs.max()+1,ys.max()+1)
        rgba=np.dstack((a,(mask*255).astype('uint8')))
        cut=Image.fromarray(rgba).crop(bounds); cut.thumbnail((440,720),Image.Resampling.LANCZOS)
        cut.save(ROOT/'images/showcase'/f"{'gummy_' if kind=='jelly' else ''}{path.stem[:-3]}-{name}.webp",quality=92)
