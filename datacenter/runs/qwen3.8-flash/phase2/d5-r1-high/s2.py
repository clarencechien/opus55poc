import os, sys
sys.path.append(os.getcwd())
import importlib, tool
importlib.reload(tool)
from tool import prof
F='inputs/view_front.png'
for py in [100,110,130,160,180,200,210,230,700,1140,1150,1160,1175,1190,1200,1210,1215]:
    prof(F,'row',py)
for px in [100,120,140,145,200,215,240,250,300,345,380,390,420,430,455,470,480,500,510,530,560,590,600,610,620,640,660,680,690]:
    prof(F,'col',px)
