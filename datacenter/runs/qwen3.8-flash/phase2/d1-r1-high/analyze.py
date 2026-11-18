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
def place(tag, tpl, cx_mm, cy_mm, facing):
    src = templates[tpl]['src']; zmin = templates[tpl]['zmin']
    root = dup_tree(src, None)
    root.name = 'P_' + tag
    root.matrix_basis = Matrix.Translation((cx_mm/1000.0, cy_mm/1000.0, FLOOR_Z - zmin)) @ Matrix.Rotation(FACING[facing], 4, 'Z')
    placed[tag] = root
    return root

for r in pred['racks']:
    place(r['id'], 'RackG' if r['size'][0] >= 700 else 'RackA', r['center'][0], r['center'][1], r['facing'])
for c in pred['crah']:
    place(c['id'], 'CRAH', c['center'][0], c['center'][1], c['facing'])

deps = bpy.context.evaluated_depsgraph_get()

def led_point(root):
    for ob in root.children_recursive:
        if 'FrontLED' in ob.name:
            ctr = sum((ob.matrix_world @ Vector(c) for c in ob.bound_box), Vector()) / 8
            return ctr
    return None

def load_arr(src):
    img = bpy.data.images.load(src, check_existing=False)
    w, h = img.size[0], img.size[1]
    buf = np.empty(w*h*4, dtype=np.float32)
    img.pixels.foreach_get(buf)
    arr = buf.reshape(h, w, 4)[:, :, :3]
    bpy.data.images.remove(img)
    return arr  # row0 = bottom

def components(mask):
    h, w = mask.shape
    seen = np.zeros((h, w), bool)
    comps = []
    ys, xs = np.where(mask)
    pix = set(zip(ys.tolist(), xs.tolist()))
    while pix:
        y0, x0 = pix.pop()
        stack = [(y0, x0)]; comp = [(y0, x0)]
        while stack:
            y, x = stack.pop()
            for dy in (-2, -1, 0, 1, 2):
                for dx in (-2, -1, 0, 1, 2):
                    p = (y+dy, x+dx)
                    if p in pix:
                        pix.remove(p); comp.append(p); stack.append(p)
        comps.append(comp)
    return comps

cams = json.load(open('inputs/cameras.json'))['cameras']
report = {}
for cam in cams:
    n = int(cam['photo'].split('_')[1].split('.')[0])
    co = bpy.data.objects[cam['camera_object']]
    fx = cam['lens_mm'] / cam['sensor_width_mm'] * cam['resolution'][0]
    W, H = cam['resolution']
    arr = load_arr('inputs/photo_%d.jpg' % n)
    B = arr[:, :, 2]; Rr = arr[:, :, 0]; Gg = arr[:, :, 1]
    blueness = B - (Rr + Gg)/2
    mask = blueness > 0.15
    comps = components(mask)
    comps = [c for c in comps if len(c) >= 4]
    centroids = []
    for c in comps:
        ys = np.array([p[0] for p in c]); xs = np.array([p[1] for p in c])
        centroids.append((xs.mean(), H - ys.mean(), len(c), xs.min(), xs.max(), H-ys.min(), H-ys.max()))
    inv = co.matrix_world.inverted()
    def project(p):
        v = inv @ p
        if v.z >= -0.01:
            return None
        u = W/2 + v.x * fx / (-v.z)
        vv = H/2 - v.y * fx / (-v.z)
        return (u, vv)
    print('=== photo', n, 'blue components:', len(centroids))
    for c in sorted(centroids, key=lambda t: t[0]):
        print('   comp u=%.0f v=%.0f npix=%d ubox=[%.0f,%.0f] vbox=[%.0f,%.0f]' % c)
    lines = []
    for r in pred['racks']:
        root = placed[r['id']]
        p = led_point(root)
        pr = project(p)
        if pr is None:
            continue
        u, vv = pr
        if not (0 <= u < W and 0 <= vv < H):
            continue
        # visibility raycast
        origin = co.matrix_world.translation
        direction = (p - origin).normalized()
        hit, loc, nrm, idx, ob, mat = scene.ray_cast(deps, origin, direction)
        vis = hit and ob.name.startswith('P_' + r['id'])
        # check blue in window
        wu, wv = 14, 9
        u0 = int(max(0, u-wu)); u1 = int(min(W, u+wu))
        v0 = int(max(0, vv-wv)); v1 = int(min(H, vv+wv))
        sub = mask[H-v1:H-v0, u0:u1]
        nblue = int(sub.sum())
        lines.append((r['id'], round(u), round(vv), vis, nblue))
    print('   items: id u v visible nblue')
    for L in lines:
        print('   ', L)
    report[n] = lines
json.dump({str(k): v for k, v in report.items()}, open('analysis.json', 'w'), indent=1)
print('DONE')
