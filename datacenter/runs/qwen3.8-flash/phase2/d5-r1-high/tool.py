import bpy, numpy as np, os

def load(p):
    img = bpy.data.images.load(os.path.abspath(p))
    w, h = img.size
    a = np.array(img.pixels[:], dtype=np.float32).reshape(h, w, 4)
    bpy.data.images.remove(img)
    return (a[::-1, :, :3]*255).round().astype(np.int16)

NAMES = {0:'bg',1:'blue',2:'org',3:'red',4:'grn',5:'ylw',6:'wht',7:'lgry',8:'mgry',9:'dkry',10:'blk'}

def cls(a):
    r, g, b = a[...,0].astype(int), a[...,1].astype(int), a[...,2].astype(int)
    mx = np.maximum(np.maximum(r,g),b); mn = np.minimum(np.minimum(r,g),b)
    out = np.zeros(r.shape, dtype=np.int8)
    chrom = (mx-mn) > 30
    out[chrom & (b > r+10)] = 1
    out[chrom & (r>180) & (g>140) & (b<120)] = 5
    out[chrom & (r>150) & (g>60) & (g<=140) & (b<110)] = 2
    out[chrom & (r>110) & (g<=60) & (b<=80)] = 3
    out[chrom & (g>=r) & (g>b) & (g>90)] = 4
    gray = ~chrom
    bg = gray & (mn>=247) & (mx<=252)
    out[gray & ~bg & (mn>=150)] = 7
    out[gray & ~bg & (mn>=95) & (mn<150)] = 8
    out[gray & ~bg & (mn>=45) & (mn<95)] = 9
    out[gray & ~bg & (mn<45)] = 10
    out[gray & (mn>=253)] = 6
    return out

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

def bbox(img, names, xlo=0, xhi=9999, ylo=0, yhi=9999):
    a = load(img); c = cls(a)
    for n in names:
        k = [kk for kk, v in NAMES.items() if v == n][0]
        m = (c == k)
        mm = np.zeros_like(m); mm[ylo:yhi+1, xlo:xhi+1] = m[ylo:yhi+1, xlo:xhi+1]
        if not mm.any():
            print("  %s: none" % n); continue
        ys, xs = np.nonzero(mm)
        print("  %-5s n=%6d  x %d..%d   y %d..%d" % (n, mm.sum(), xs.min(), xs.max(), ys.min(), ys.max()))
