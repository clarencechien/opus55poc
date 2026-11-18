import os, sys
sys.path.append(os.getcwd())
import numpy as np
from tool import load
L = load('inputs/view_left.png')
for row in [510, 520, 530, 540, 545, 550, 560, 570, 580]:
    s = []
    for px in range(730, 790, 2):
        r,g,b = L[row, px]
        s.append("%3d,%3d,%3d" % (r,g,b))
    print("row", row, " | ".join(s[:12]))
print()
for row in [510,520,530,540,550,560,570,580,590,600]:
    print(row, [tuple(int(v) for v in L[row, px]) for px in [740,750,760,765,770,775,780]])
