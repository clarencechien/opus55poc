import os, sys
sys.path.append(os.getcwd())
import importlib, tool
importlib.reload(tool)
from tool import prof, bbox
T='inputs/view_top.png'
bbox(T, ['blue','org','red','grn','ylw','wht','lgry','mgry','dkry','blk'], xlo=90, xhi=700, ylo=90, yhi=790)
print()
for py in [100,110,130,150,170,180,200,230,250,270,300,320,330,350,400,450,500,550,600,650,680,700,710,720,730,750,779]:
    prof(T,'row',py)
for px in [100,105,110,120,140,160,180,200,250,300,350,400,450,500,520,550,570,590,600,610,620,640,660,680,690]:
    prof(T,'col',px)
