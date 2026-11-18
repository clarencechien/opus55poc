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
    y0 = max(0, H-v-r); y1 = min(H, H-v+r)
    x0 = max(0, u-r); x1 = min(W, u+r)
    arr[y0:y1, x0:x0+2] = col; arr[y0:y1, x1-2:x1] = col
    arr[y0:y0+2, x0:x1] = col; arr[y1-2:y1, x0:x1] = col

def save(out, arr):
    nh, nw = arr.shape[0], arr.shape[1]
    im = bpy.data.images.new(os.path.basename(out), nw, nh, alpha=False)
    o = np.ones((nh, nw, 4), dtype=np.float32); o[:, :, :3] = arr
    im.pixels.foreach_set(o.ravel())
    im.filepath_raw = out; im.file_format = 'PNG'; im.save()
    bpy.data.images.remove(im)

GREEN = np.array([0, 1, 0]); RED = np.array([1, 0, 0]); MAG = np.array([1, 0, 1]); CYA = np.array([0, 1, 1])
cams = json.load(open('inputs/cameras.json'))['cameras']
sel = json.load(open('viz.json'))['cams']
os.makedirs('viz', exist_ok=True)
for cam in cams:
    n = int(cam['photo'].split('_')[1].split('.')[0])
    if n not in sel:
        continue
    co = bpy.data.objects[cam['camera_object']]
    fx = cam['lens_mm']/cam['sensor_width_mm']*cam['resolution'][0]
    W, H = cam['resolution']
    arr = load_arr('inputs/photo_%d.jpg' % n)
    mask = (arr[:, :, 2] - (arr[:, :, 0]+arr[:, :, 1])/2) > 0.15
    comps = components(mask)
    cents = []
    for c in comps:
        ys = np.array([p[0] for p in c]); xs = np.array([p[1] for p in c])
        cents.append([xs.mean(), H-ys.mean(), len(c), False])
    inv = co.matrix_world.inverted()
    origin = co.matrix_world.translation
    dbg = []
    for r in pred['racks']:
        p = led_point(placed[r['id']])
        v = inv @ p
        if v.z >= -0.01:
            continue
        u = W/2 + v.x*fx/(-v.z); vv = H/2 - v.y*fx/(-v.z)
        if not (0 <= u < W and 0 <= vv < H):
            continue
        hit, loc, nrm, idx, ob, mat = scene.ray_cast(deps, origin, (p-origin).normalized())
        vis = hit and ob.name.startswith('P_'+r['id'])
        if len(dbg) < 3:
            dbg.append((r['id'], ob.name if hit else None))
        best = None; bestd = 1e9
        for cc in cents:
            d = abs(cc[0]-u) + abs(cc[1]-vv)
            if d < bestd and d < 26:
                bestd = d; best = cc
        if best is not None:
            best[3] = True
            box(arr, int(u), int(vv), GREEN)
        else:
            box(arr, int(u), int(vv), RED if vis else CYA)
    for cc in cents:
        box(arr, int(cc[0]), int(cc[1]), MAG if cc[3] else np.array([1, 1, 0]))
    save('viz/v%d.png' % n, arr)
    print('cam', n, 'comps', len(cents), 'unmatched', sum(1 for c in cents if not c[3]), 'dbg', dbg)
print('DONE')
