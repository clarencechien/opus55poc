import os, sys
sys.path.append(os.getcwd())
import importlib, tool
importlib.reload(tool)
from tool import load, cls, NAMES, prof
CH = {0:'.',1:'B',2:'O',3:'R',4:'G',5:'Y',6:'W',7:'g',8:'m',9:'d',10:'#'}
def dump(img, x0, x1, y0, y1, step=1):
    a = load(img); c = cls(a)
    print("--- %s x %d..%d y %d..%d step %d" % (img.split('/')[-1], x0, x1, y0, y1, step))
    for y in range(y0, y1+1, step):
        print("%4d " % y + "".join(CH[c[y, x]] for x in range(x0, x1+1, step)))
F='inputs/view_front.png'
dump(F, 262, 330, 158, 214, 1)
print()
dump(F, 460, 526, 158, 214, 1)
