import os, sys
sys.path.append(os.getcwd())
import importlib, tool
importlib.reload(tool)
from tool import prof
L='inputs/view_left.png'
for py in [100,130,160,190,210,230,250,300,350,400,450,500,550,600,650,700,750,800,850,900,1000,1050,1100,1140,1160,1180,1200,1214]:
    prof(L,'row',py)
for px in [100,110,120,140,160,180,200,250,300,350,400,450,500,550,600,650,700,720,730,740,750,760,770,780]:
    prof(L,'col',px)
