import os, sys
sys.path.append(os.getcwd())
import tool
from tool import load, cls, prof, bbox, NAMES

VIEWS = {
 'front': 'inputs/view_front.png',
 'back':  'inputs/view_back.png',
 'left':  'inputs/view_left.png',
 'right': 'inputs/view_right.png',
 'top':   'inputs/view_top.png',
}
for v, p in VIEWS.items():
    print("###", v)
    bbox(p, ['blue','org','red','grn','ylw','wht','lgry','mgry','dkry','blk'])
