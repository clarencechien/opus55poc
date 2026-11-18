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

F='inputs/view_front.png'; L='inputs/view_left.png'; R='inputs/view_right.png'; T='inputs/view_top.png'
prof(F,'row',545); prof(F,'row',790); prof(F,'row',1000)
prof(T,'row',745); prof(T,'row',765); prof(T,'row',779)
prof(L,'row',1150); prof(L,'row',1170); prof(L,'row',1205); prof(L,'row',1214)
prof(L,'col',200); prof(L,'col',690); prof(L,'col',700); prof(L,'col',710)
prof(R,'row',1170); prof(R,'row',1205); prof(R,'col',150); prof(R,'col',170)
dump(F, 265, 500, 345, 435, 4)
