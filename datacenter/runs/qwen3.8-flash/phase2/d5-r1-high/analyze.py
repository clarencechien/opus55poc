import bpy, numpy as np, os

def load(p):
    img = bpy.data.images.load(os.path.abspath(p))
    w, h = img.size
    a = np.array(img.pixels[:], dtype=np.float32).reshape(h, w, 4)
    bpy.data.images.remove(img)
    # flip: bpy pixels start at bottom-left
    return a[::-1].copy(), w, h   # row 0 = top

def q(a, bits=4):
    r = (a[..., 0]*255).astype(np.uint8)
    g = (a[..., 1]*255).astype(np.uint8)
    b = (a[..., 2]*255).astype(np.uint8)
    return np.stack([r>>bits, g>>bits, b>>bits], -1)

def stats(p):
    a, w, h = load(p)
    print("=== %s  %dx%d" % (p, w, h))
    K = q(a, 4)
    keys = (K[...,0].astype(np.int32)<<8) | (K[...,1].astype(np.int32)<<4) | K[...,2].astype(np.int32)
    vals, cnts = np.unique(keys, return_counts=True)
    order = np.argsort(-cnts)
    for i in order[:14]:
        v = vals[i]; c = cnts[i]
        r_ = (v>>8)&15; g_ = (v>>4)&15; b_ = v&15
        rgb = (r_*16, g_*16, b_*16)
        m = keys == v
        ys, xs = np.nonzero(m)
        print("  rgb~%-16s cnt=%7d  bbox x %d..%d  y %d..%d" % (rgb, c, xs.min(), xs.max(), ys.min(), ys.max()))
    return a, w, h

for p in ["inputs/view_front.png", "inputs/view_back.png", "inputs/view_left.png", "inputs/view_right.png", "inputs/view_top.png"]:
    stats(p)
