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

crop('crow', 590, 1130, 1150, 1250)
crop('drow', 590, 1130, 1000, 1100)
crop('arow', 1240, 1700, 1430, 1530)
crop('brow', 1240, 1700, 1280, 1380)
crop('efrow', 540, 830, 460, 720, zoom=3)
crop('crah_wl', 400, 540, 1340, 1480)
crop('crah_wu', 400, 540, 900, 1040)
crop('crah_e', 1910, 2050, 940, 1080)
crop('d1', 850, 1130, 1490, 1660)
crop('d2', 1690, 1960, 760, 940)
crop('topdims', 380, 2060, 180, 330, zoom=2)
crop('bottomdims', 380, 2060, 1670, 1830, zoom=2)
crop('leftdims', 150, 430, 380, 1620, zoom=2)
crop('rightdims', 2050, 2400, 380, 1620, zoom=2)
bpy.data.images.remove(src)
