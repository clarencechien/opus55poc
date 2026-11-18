import bpy, json, os, numpy as np

os.makedirs('cmp', exist_ok=True)
specs = json.load(open('cmp.json'))

def load_arr(src):
    img = bpy.data.images.load(src, check_existing=False)
    w, h = img.size[0], img.size[1]
    buf = np.empty(w*h*4, dtype=np.float32)
    img.pixels.foreach_get(buf)
    arr = buf.reshape(h, w, 4)[:, :, :3]
    bpy.data.images.remove(img)
    return arr

def crop(arr, box):
    x0, y0, x1, y1 = box
    h, w = arr.shape[0], arr.shape[1]
    ry0 = max(0, h - y1); ry1 = min(h, h - y0)
    x0 = max(0, min(w-1, x0)); x1 = max(x0+1, min(w, x1))
    return arr[ry0:ry1, x0:x1]

def save(out, sub, sc=1):
    if sc != 1:
        sub = np.repeat(np.repeat(sub, sc, axis=0), sc, axis=1)
    nh, nw = sub.shape[0], sub.shape[1]
    im = bpy.data.images.new(os.path.splitext(os.path.basename(out))[0], nw, nh, alpha=False)
    o = np.ones((nh, nw, 4), dtype=np.float32)
    o[:, :, :3] = sub
    im.pixels.foreach_set(o.ravel())
    im.filepath_raw = out; im.file_format = 'PNG'; im.save()
    bpy.data.images.remove(im)
    print('wrote', out, nw, nh)

cache = {}
def get(src):
    if src not in cache:
        cache[src] = load_arr(src)
    return cache[src]

for s in specs:
    a = crop(get(s['a']), s['box'])
    b = crop(get(s['b']), s['box'])
    hh = min(a.shape[0], b.shape[0]); ww = min(a.shape[1], b.shape[1])
    a = a[:hh, :ww]; b = b[:hh, :ww]
    if s.get('stack'):
        sep = np.ones((6, ww, 3), dtype=np.float32)
        comb = np.concatenate([a, sep, b], axis=0)
    else:
        sep = np.ones((hh, 6, 3), dtype=np.float32)
        comb = np.concatenate([a, sep, b], axis=1)
    save(s['out'], comb, s.get('scale', 1))
print('DONE')
