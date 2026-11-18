import bpy, numpy as np, json, os

jobs = json.load(open('zoomjobs.json'))
os.makedirs('out', exist_ok=True)
cache = {}
for job in jobs:
    src, box, name, scale = job[0], job[1], job[2], job[3]
    if src not in cache:
        p = os.path.abspath(src)
        im = bpy.data.images.load(p, check_existing=True)
        im.use_fake_user = True
        w, h = im.size
        arr = np.array(im.pixels[:], dtype=np.float32).reshape(h, w, 4)
        cache[src] = (arr, w, h)
        print('loaded', src, w, h)
    arr, w, h = cache[src]
    x0, y0, x1, y1 = [int(v) for v in box]
    x0 = max(0, x0); y0 = max(0, y0); x1 = min(w, x1); y1 = min(h, y1)
    sub = arr[h - y1:h - y0, x0:x1]          # box in top-origin coords; sub is bottom-up
    sub = np.repeat(np.repeat(sub, int(scale), axis=0), int(scale), axis=1)
    nh, nw = sub.shape[0], sub.shape[1]
    old = bpy.data.images.get(name)
    if old: bpy.data.images.remove(old)
    out = bpy.data.images.new(name, nw, nh, alpha=True, float_buffer=False)
    out.pixels = np.clip(sub, 0, 1).reshape(-1).tolist()
    out.filepath_raw = os.path.abspath('out/' + name + '.png')
    out.file_format = 'PNG'
    out.save()
    print('wrote out/%s.png' % name, nw, nh)
print('done')
