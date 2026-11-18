import bpy, json, math, os, numpy as np
from mathutils import Vector, Matrix

design = json.load(open('inputs/design.json'))
pred = json.load(open('pred.json'))
if pred.get('_from') == 'design':
    pred = {'racks': design['racks'], 'crah': design['crah']}
FACING = {'S': 0.0, 'N': math.pi, 'E': math.pi/2, 'W': -math.pi/2}
scene = bpy.context.scene

for o in [o for o in bpy.data.objects if o.name.startswith('P_')]:
    bpy.data.objects.remove(o, do_unlink=True)
templates = {}
for tname in ('RackA', 'RackG', 'CRAH'):
    src = bpy.data.objects[tname]
    mn = [1e9]*3; mx = [-1e9]*3
    for ob in [src] + list(src.children_recursive):
        if ob.type == 'MESH':
            for c in ob.bound_box:
                w = ob.matrix_world @ Vector(c)
                for i in range(3):
                    mn[i] = min(mn[i], w[i]); mx[i] = max(mx[i], w[i])
    templates[tname] = {'src': src, 'zmin': mn[2]}
FLOOR_Z = 0.6

def dup_tree(src, new_parent):
    c = src.copy(); c.data = src.data
    scene.collection.objects.link(c)
    if new_parent is not None:
        c.parent = new_parent
    for ch in src.children:
        dup_tree(ch, c)
    return c

placed = {}
def place(tag, tpl, cx, cy, facing):
    src = templates[tpl]['src']; zmin = templates[tpl]['zmin']
    root = dup_tree(src, None)
    root.name = 'P_' + tag
    root.matrix_basis = Matrix.Translation((cx/1000.0, cy/1000.0, FLOOR_Z - zmin)) @ Matrix.Rotation(FACING[facing], 4, 'Z')
    placed[tag] = root

for r in pred['racks']:
    place(r['id'], 'RackG' if r['size'][0] >= 700 else 'RackA', r['center'][0], r['center'][1], r['facing'])
for c in pred['crah']:
    place(c['id'], 'CRAH', c['center'][0], c['center'][1], c['facing'])
deps = bpy.context.evaluated_depsgraph_get()

def root_name(ob):
    while ob.parent is not None:
        ob = ob.parent
    return ob.name

def led_point(root):
    for ob in root.children_recursive:
        if 'FrontLED' in ob.name:
            return sum((ob.matrix_world @ Vector(cc) for cc in ob.bound_box), Vector())/8
    return None

def load_arr(src):
    img = bpy.data.images.load(src, check_existing=False)
    w, h = img.size[0], img.size[1]
    buf = np.empty(w*h*4, dtype=np.float32)
    img.pixels.foreach_get(buf)
    arr = buf.reshape(h, w, 4)[:, :, :3].copy()
    bpy.data.images.remove(img)
    return arr

def components(mask, minpix=4, link=2):
    ys, xs = np.where(mask)
    pix = set(zip(ys.tolist(), xs.tolist()))
    comps = []
    while pix:
        y0, x0 = pix.pop()
        stack = [(y0, x0)]; comp = [(y0, x0)]
        while stack:
            y, x = stack.pop()
            for dy in range(-link, link+1):
                for dx in range(-link, link+1):
                    p = (y+dy, x+dx)
                    if p in pix:
                        pix.remove(p); comp.append(p); stack.append(p)
        if len(comp) >= minpix:
            comps.append(comp)
    return comps

def box(arr, u, v, col, r=7):
    H, W = arr.shape[0], arr.shape[1]
    y0 = max(0, H-v-r); y1 = min(H, H-v+r); x0 = max(0, u-r); x1 = min(W, u+r)
    arr[y0:y1, x0:x0+2] = col; arr[y0:y1, x1-2:x1] = col
    arr[y0:y0+2, x0:x1] = col; arr[y1-2:y1, x0:x1] = col

GREEN = np.array([0, 1, 0]); RED = np.array([1, 0.1, 0.1]); MAG = np.array([1, 0, 1]); CYA = np.array([0, 1, 1]); YEL = np.array([1, 1, 0])
cams = json.load(open('inputs/cameras.json'))['cameras']
cfg = json.load(open('viz.json'))
sel = cfg['cams']; saveimg = cfg.get('img', [])
os.makedirs('viz', exist_ok=True)
items = [(r['id'], r) for r in pred['racks']]
summary = {}
for cam in cams:
    n = int(cam['photo'].split('_')[1].split('.')[0])
    if n not in sel:
        continue
    co = bpy.data.objects[cam['camera_object']]
    fx = cam['lens_mm']/cam['sensor_width_mm']*cam['resolution'][0]
    W, H = cam['resolution']
    arr = load_arr('inputs/photo_%d.jpg' % n)
    mask = (arr[:, :, 2] - (arr[:, :, 0]+arr[:, :, 1])/2) > 0.10
    comps = [[xs.mean(), H-ys.mean(), len(c), False] for c in components(mask)
             for ys, xs in [ (np.array([p[0] for p in c]), np.array([p[1] for p in c])) ]]
    inv = co.matrix_world.inverted(); origin = co.matrix_world.translation
    out = []
    for tag, it in items:
        p = led_point(placed[tag]); v = inv @ p
        if v.z >= -0.01:
            continue
        u = W/2 + v.x*fx/(-v.z); vv = H/2 - v.y*fx/(-v.z)
        if not (-20 <= u < W+20 and 0 <= vv < H):
            continue
        hit, loc, nrm, idx, ob, mat = scene.ray_cast(deps, origin, (p-origin).normalized())
        vis = hit and root_name(ob) == 'P_'+tag
        best = None; bestd = 1e9
        for cc in comps:
            d = abs(cc[0]-u) + abs(cc[1]-vv)
            if d < bestd and d < 30:
                bestd = d; best = cc
        st = 'M' if best is not None else ('X' if vis else 'o')
        if best is not None:
            best[3] = True
            box(arr, int(u), int(vv), GREEN if n in saveimg else None) if False else None
        if n in saveimg:
            box(arr, int(u), int(vv), GREEN if best else (RED if vis else CYA))
        out.append('%s%s(%d,%d,%d)' % (tag, st, u, vv, bestd if best else -1))
    un = [(int(c[0]), int(c[1]), c[2]) for c in comps if not c[3]]
    if n in saveimg:
        for c in comps:
            box(arr, int(c[0]), int(c[1]), MAG if c[3] else YEL)
        save_path = 'viz/v%d.png' % n
        nh, nw = arr.shape[0], arr.shape[1]
        im = bpy.data.images.new('v%d' % n, nw, nh, alpha=False)
        o = np.ones((nh, nw, 4), dtype=np.float32); o[:, :, :3] = arr
        im.pixels.foreach_set(o.ravel()); im.filepath_raw = save_path
        im.file_format = 'PNG'; im.save(); bpy.data.images.remove(im)
    print('--- cam', n, 'unmatched comps:', un)
    print('   ', ' '.join(out))
print('DONE')
