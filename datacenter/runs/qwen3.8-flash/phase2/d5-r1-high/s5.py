import os, sys
sys.path.append(os.getcwd())
import importlib, tool
importlib.reload(tool)
from tool import prof
B='inputs/view_back.png'
for py in [100,130,160,180,200,210,230,500,700,900,960,980,1000,1020,1040,1060,1080,1100,1120,1140,1160,1180,1200,1214]:
    prof(B,'row',py)
for px in [100,110,120,140,160,170,180,200,210,220,240,250,300,350,400,450,500,550,600,620,640,650,660,680]:
    prof(B,'col',px)
