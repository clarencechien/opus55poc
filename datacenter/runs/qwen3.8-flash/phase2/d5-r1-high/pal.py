import bpy, numpy as np, os
from collections import Counter

def load(p):
    img = bpy.data.images.load(os.path.abspath(p))
    w, h = img.size
    a = np.array(img.pixels[:], dtype=np.float32).reshape(h, w, 4)
    bpy.data.images.remove(img)
    return a[::-1].copy(), w, h

a, w, h = load("inputs/view_front.png")
rgb = (a[..., :3]*255).round().astype(np.uint8)
flat = rgb.reshape(-1, 3)
c = Counter(map(tuple, flat[::7]))
for col, n in c.most_common(30):
    print(col, n)
