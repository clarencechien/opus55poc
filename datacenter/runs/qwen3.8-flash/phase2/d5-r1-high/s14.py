import os, sys
sys.path.append(os.getcwd())
import numpy as np
from tool import load
L = load('inputs/view_left.png')
def ch(v):
    r,g,b = [int(x) for x in v]
    if r>246 and g>246 and b>244 and b<252: return '.'
    if r>=252 and g>=252 and b>=252: return 'W'
    if r<60 and g<60: return '#'
    if abs(r-g)<12 and abs(g-b)<12: return 'g'
    if b>r+20: return 'B'
    return '?'
print("     " + "".join(str((px//10)%10) for px in range(730,792)))
print("     " + "".join(str(px%10) for px in range(730,792)))
for row in range(505, 820, 3):
    print("%4d " % row + "".join(ch(L[row,px]) for px in range(730,792)))
