import os, sys
sys.path.append(os.getcwd())
import importlib, tool
importlib.reload(tool)
from tool import load, cls, NAMES
CH = {0:'.',1:'B',2:'O',3:'R',4:'G',5:'Y',6:'W',7:'g',8:'m',9:'d',10:'#'}

def dump(img, x0, x1, y0, y1, step=1):
    a = load(img); c = cls(a)
    print("--- %s x %d..%d y %d..%d" % (img.split('/')[-1], x0, x1, y0, y1))
    for y in range(y0, y1+1, step):
        print("%4d " % y + "".join(CH[c[y, x]] for x in range(x0, x1+1, step)))

T='inputs/view_top.png'
dump(T, 255, 350, 630, 680, 1)
dump(T, 450, 530, 280, 330, 1)
