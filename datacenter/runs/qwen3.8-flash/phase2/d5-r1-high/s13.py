import os, sys
sys.path.append(os.getcwd())
import numpy as np
from tool import load, prof
F='inputs/view_front.png'
L=load(F)
for px in [435,440,445,450,455,460,465,470]:
    col = L[:, px]
    # report runs of dark(25,25,30)-ish and white in rows 500..820
    seg=[]
    prev=None; st=None
    for r in range(500,825):
        v = col[r]
        k = 'K' if (v[0]<60 and v[1]<60) else ('W' if min(v)>252 else ('B' if (v[2]>v[0]+20) else '.'))
        if k!=prev:
            if prev is not None: seg.append((prev,st,r-1))
            prev=k; st=r
    seg.append((prev,st,824))
    print("x=%+4d (z %d..%d): %s" % ((px-395)*2, (1215-824)*2, (1215-500)*2,
        " ".join("%s[%d-%d]z%d..%d"%(a,b,c,(1215-c)*2,(1215-b)*2) for a,b,c in seg if c-b>=1)))
