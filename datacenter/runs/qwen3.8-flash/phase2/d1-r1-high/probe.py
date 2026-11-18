import bpy, json, numpy as np

def load_arr(src):
    img = bpy.data.images.load(src, check_existing=False)
    w, h = img.size[0], img.size[1]
    buf = np.empty(w*h*4, dtype=np.float32)
    img.pixels.foreach_get(buf)
    arr = buf.reshape(h, w, 4)[:, :, :3]
    bpy.data.images.remove(img)
    return arr  # row 0 = bottom

for n in (6,):
    a = load_arr('inputs/photo_%d.jpg' % n)
    print('photo', n, a.shape, 'min', a.min(), 'max', a.max())
    R, G, B = a[:, :, 0], a[:, :, 1], a[:, :, 2]
    blueness = B - (R + G) / 2
    print('max blueness', blueness.max())
    for thr in (0.05, 0.1, 0.15, 0.2, 0.3):
        ys, xs = np.where(blueness > thr)
        print('thr', thr, 'count', len(xs))
    ys, xs = np.where(blueness > 0.15)
    if len(xs):
        # print some sample colors
        idx = np.random.RandomState(0).choice(len(xs), min(10, len(xs)), replace=False)
        for i in idx:
            y, x = ys[i], xs[i]
            print('px', x, y, 'rgb', a[y, x], 'top-left y', a.shape[0]-y)
print('DONE')
