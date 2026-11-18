import os, sys
sys.path.append(os.getcwd())
import numpy as np, bpy
from tool import load, cls, NAMES

def rle(seq):
    res = []; s = seq[0]; st = 0
    for i in range(1, len(seq)+1):
        if i == len(seq) or seq[i] != s:
            res.append([s, st, i-1]); s = seq[i] if i < len(seq) else None; st = i
    return res

def prof(img, axis, idx, minlen=2):
    a = load(img)
    line = a[idx, :] if axis == 'row' else a[:, idx]
    c = cls(line)
    rs = [x for x in rle(c) if (x[2]-x[1] >= minlen-1)]
    print("  %s %s=%d: %s" % (img.split('/')[-1], axis, idx,
        "  ".join("%s[%d-%d]" % (NAMES[x[0]], x[1], x[2]) for x in rs)))

if __name__ == '__main__':
    pass
