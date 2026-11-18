import os, sys
sys.path.append(os.getcwd())
import importlib, tool
importlib.reload(tool)
from tool import load, cls, NAMES, prof
CH = {0:'.',1:'B',2:'O',3:'R',4:'G',5:'Y',6:'W',7:'g',8:'m',9:'d',10:'#'}

def dump(img, x0, x1, y0, y1, step=2):
    a = load(img); c = cls(a)
    print("--- %s x %d..%d y %d..%d step %d" % (img.split('/')[-1], x0, x1, y0, y1, step))
    for y in range(y0, y1+1, step):
        print("%4d " % y + "".join(CH[c[y, x]] for x in range(x0, x1+1, step)))

T='inputs/view_top.png'; L='inputs/view_left.png'; R='inputs/view_right.png'; F='inputs/view_front.png'
dump(T, 90, 200, 95, 200, 2)
dump(T, 590, 700, 95, 200, 2)
dump(T, 90, 700, 720, 790, 2)
dump(L, 90, 200, 990, 1110, 2)
