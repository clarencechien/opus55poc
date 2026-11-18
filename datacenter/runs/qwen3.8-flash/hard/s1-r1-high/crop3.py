import numpy as np, bpy, os
SRC = '/home/user/opus55poc/datacenter/runs/qwen3.8-flash/hard/s1-r1-high/inputs/plan.png'
OUT = '/home/user/opus55poc/datacenter/runs/qwen3.8-flash/hard/s1-r1-high/crops'
os.makedirs(OUT, exist_ok=True)
src = bpy.data.images.load(SRC)
w, h = src.size
px = np.array(src.pixels[:]).reshape(h, w, 4)

def crop(name, x0, x1, y0t, y1t, zoom=4):
    r0, r1 = h - y1t, h - y0t
    sub = px[r0:r1, x0:x1]
    big = np.repeat(np.repeat(sub, zoom, axis=0), zoom, axis=1).astype('float32')
    bh, bw = big.shape[:2]
    im = bpy.data.images.new(name, bw, bh, alpha=True, float_buffer=True)
    im.pixels.foreach_set(big.ravel())
    im.filepath_raw = os.path.join(OUT, name + '.png')
    im.file_format = 'PNG'
    im.save()
    bpy.data.images.remove(im)
    print(name, bw, bh)

crop('d1', 850, 1130, 1490, 1660)
crop('d2', 1690, 1960, 760, 940)
crop('topdims', 380, 2060, 180, 330, zoom=2)
crop('bottomdims', 380, 2060, 1670, 1830, zoom=2)
crop('leftdims', 150, 430, 380, 1620, zoom=2)
crop('rightdims', 2050, 2400, 380, 1620, zoom=2)
bpy.data.images.remove(src)
