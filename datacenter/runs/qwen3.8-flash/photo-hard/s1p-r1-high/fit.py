import bpy, numpy as np, json, os

os.makedirs('cmp', exist_ok=True)
sc = bpy.data.scenes[0]
coll = bpy.data.collections['Collection']
LUMA = np.array([0.299, 0.587, 0.114])
ZFL = 0.6          # raised floor top
_phcache = {}

def clear():
    for ob in list(bpy.data.objects):
        if ob.get('placed'):
            bpy.data.objects.remove(ob, do_unlink=True)

def copy_tree(src, parent, tag):
    c = src.copy()
    c.name = 'P_%s_%s' % (tag, src.name)
    coll.objects.link(c)
    if parent is not None:
        c.parent = parent
    c['placed'] = 1
    for ch in src.children:
        copy_tree(ch, c, tag)
    return c

FACE = {'S': 0.0, 'N': 180.0, 'E': 90.0, 'W': -90.0}

def place(tname, cx, cy, rz, tag):
    root = copy_tree(bpy.data.objects[tname], None, tag)
    root.location = (cx, cy, ZFL)
    root.rotation_euler = (0.0, 0.0, float(np.radians(rz)))
    return root

def build(hyp):
    clear()
    nr = 0
    for n, r in enumerate(hyp.get('rows', [])):
        axis = r.get('axis', 'EW')
        w = r.get('w', 0.6)
        tname = 'RackG' if abs(w - 0.8) < 1e-6 else 'RackA'
        a, b, c, rz = r['a'], r['b'], r['c'], FACE[r['face']]
        cnt = int(round((b - a) / w))
        for i in range(cnt):
            s = a + w * (i + 0.5)
            if axis == 'EW':
                place(tname, s, c, rz, 'r%d_%d' % (n, i))
            else:
                place(tname, c, s, rz, 'r%d_%d' % (n, i))
        nr += cnt
    for k, cc in enumerate(hyp.get('crah', [])):
        place('CRAH', cc[0], cc[1], FACE[cc[2]], 'c%d' % k)
    return nr

def img_lum(path, W=None, H=None):
    key = (path, W)
    if key in _phcache:
        return _phcache[key]
    im = bpy.data.images.load(os.path.abspath(path), check_existing=False)
    h, w = im.size[1], im.size[0]
    a = np.array(im.pixels[:], dtype=np.float32).reshape(h, w, 4)[..., :3] @ LUMA
    bpy.data.images.remove(im)
    if W:
        ys = np.clip(((np.arange(H) + 0.5) * h / H).astype(int), 0, h - 1)
        xs = np.clip(((np.arange(W) + 0.5) * w / W).astype(int), 0, w - 1)
        a = a[np.ix_(ys, xs)]
    _phcache[key] = a
    return a

def render_all(hyp, res=(512, 384), cams=(1, 2, 3, 4, 5), verbose=True):
    W, H = res
    nr = build(hyp)
    sc.render.resolution_x, sc.render.resolution_y = W, H
    sc.render.resolution_percentage = 100
    out = {}
    for i in cams:
        sc.camera = bpy.data.objects['Cam_%d' % i]
        p = 'cmp/r%d.png' % i
        sc.render.filepath = os.path.abspath(p)
        bpy.ops.render.render(write_still=True)
        r = img_lum(p, W, H)
        ph = img_lum('inputs/photo_%d.jpg' % i, W, H)
        d = np.abs(r - ph)
        out[i] = (float(d.mean()), float((d > 0.12).mean()))
    if verbose:
        for i in sorted(out):
            print('  cam%d MAD %.4f frac %.3f' % (i, out[i][0], out[i][1]))
        print('TOTAL MAD %.4f  racks %d' % (sum(v[0] for v in out.values()) / len(out), nr))
    return out
