import bpy, json, os, numpy as np

os.makedirs('crops', exist_ok=True)
specs = json.load(open('crops.json'))

for s in specs:
    src = s['src']
    img = bpy.data.images.load(src, check_existing=False)
    w, h = img.size[0], img.size[1]
    buf = np.empty(w*h*4, dtype=np.float32)
    img.pixels.foreach_get(buf)
    arr = buf.reshape(h, w, 4)          # row 0 = bottom of image
    x0, y0, x1, y1 = s['box']           # in top-left origin coords
    x0 = max(0, min(w-1, x0)); x1 = max(x0+1, min(w, x1))
    ry0 = h - y1; ry1 = h - y0
    ry0 = max(0, ry0); ry1 = min(h, ry1)
    sub = arr[ry0:ry1, x0:x1, :3]
    sc = s.get('scale', 1)
    if sc != 1:
        sub = np.repeat(np.repeat(sub, sc, axis=0), sc, axis=1)
    nh, nw = sub.shape[0], sub.shape[1]
    out = bpy.data.images.new(os.path.splitext(os.path.basename(s['out']))[0], nw, nh, alpha=False)
    o = np.ones((nh, nw, 4), dtype=np.float32)
    o[:, :, :3] = sub
    out.pixels.foreach_set(o.ravel())
    out.filepath_raw = s['out']
    out.file_format = 'PNG'
    out.save()
    bpy.data.images.remove(img)
    bpy.data.images.remove(out)
    print('wrote', s['out'], nw, nh)
print('DONE')
