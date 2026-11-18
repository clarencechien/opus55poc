import bpy, numpy as np, os
exec(open('colcheck.py').read().split('def draw')[0])

def draw(cn, idx):
    img = bpy.data.images.load(os.path.abspath('inputs/photo_%d.jpg' % idx), check_existing=True)
    arr = np.array(img.pixels[:], dtype=np.float32).reshape(H, W, 4).copy()
    def seg(a, b, col, steps=900):
        pa, pb = proj(cn, a), proj(cn, b)
        if pa is None or pb is None: return
        for t in np.linspace(0, 1, steps):
            u, v = pa + (pb - pa) * t
            uu, vv = int(u), int(v)
            if 0 <= uu < W and 0 <= vv < H:
                arr[H - 1 - vv, uu] = col
    for x in np.arange(0, 24.01, 0.6):
        seg((x, 0, 0.6), (x, 18, 0.6), (1, 0, 0, 1))
    for y in np.arange(0, 18.01, 0.6):
        seg((0, y, 0.6), (24, y, 0.6), (0, 1, 0, 1))
    old = bpy.data.images.get('tg%d' % idx)
    if old: bpy.data.images.remove(old)
    im = bpy.data.images.new('tg%d' % idx, W, H, alpha=True)
    im.pixels = arr.reshape(-1).tolist()
    im.filepath_raw = os.path.abspath('out/tiles%d.png' % idx); im.file_format = 'PNG'; im.save()
    print('wrote out/tiles%d.png' % idx)

for idx in [2]:
    draw('Cam_%d' % idx, idx)
