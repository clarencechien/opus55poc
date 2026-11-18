import numpy as np, bpy, os

SRC = '/home/user/opus55poc/datacenter/runs/qwen3.8-flash/hard/s1-r1-high/inputs/plan.png'
OUT = '/home/user/opus55poc/datacenter/runs/qwen3.8-flash/hard/s1-r1-high/crops'
os.makedirs(OUT, exist_ok=True)

src = bpy.data.images.load(SRC)
w, h = src.size
px = np.array(src.pixels[:]).reshape(h, w, 4)   # bottom-origin rows

def crop(name, x0, x1, y0t, y1t, zoom=2):
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

crop('A_NW',   380, 900,  380, 1000)
crop('B_N',    900, 1450, 380, 1000)
crop('C_NE',  1450, 2100, 380, 1000)
crop('D_SW',   380, 900,  1000, 1650)
crop('E_S',    900, 1450, 1000, 1650)
crop('F_SE',  1450, 2100, 1000, 1650)
bpy.data.images.remove(src)
