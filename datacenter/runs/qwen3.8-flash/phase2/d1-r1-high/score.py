import bpy, json, math, os, numpy as np
from mathutils import Vector, Matrix

design = json.load(open('inputs/design.json'))
pred = json.load(open('pred.json'))
if pred.get('_from') == 'design':
    pred = {'racks': design['racks'], 'crah': design['crah']}
FACING = {'S': 0.0, 'N': math.pi, 'E': math.pi/2, 'W': -math.pi/2}
scene = bpy.context.scene

for o in [o for o in bpy.data.objects if o.name.startswith('P_') or o.name.startswith('S_')]:
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

for r in pred['racks']:
    src = templates['RackG' if r['size'][0] >= 700 else 'RackA']['src']
    root = dup_tree(src, None)
    root.name = 'P_' + r['id']
    root.matrix_basis = Matrix.Translation((r['center'][0]/1000.0, r['center'][1]/1000.0, FLOOR_Z)) @ Matrix.Rotation(FACING[r['facing']], 4, 'Z')
for c in pred['crah']:
    src = templates['CRAH']['src']
    root = dup_tree(src, None)
    root.name = 'P_' + c['id']
    root.matrix_basis = Matrix.Translation((c['center'][0]/1000.0, c['center'][1]/1000.0, FLOOR_Z)) @ Matrix.Rotation(FACING[c['facing']], 4, 'Z')
bpy.context.view_layer.update()

scene.render.engine = 'BLENDER_WORKBENCH'
scene.display.shading.light = 'FLAT'
scene.display.shading.color_type = 'MATERIAL'
scene.display.shading.show_shadows = False
scene.display.shading.show_cavity = False
scene.render.resolution_x = 1280
scene.render.resolution_y = 960
scene.render.resolution_percentage = 100
cams = json.load(open('inputs/cameras.json'))['cameras']
os.makedirs('renders', exist_ok=True)
for cam in cams:
    n = int(cam['photo'].split('_')[1].split('.')[0])
    scene.camera = bpy.data.objects[cam['camera_object']]
    scene.render.filepath = 'renders/score_%d.png' % n
    bpy.ops.render.render(write_still=True)

def load(p):
    img = bpy.data.images.load(p, check_existing=False)
    w, h = img.size[0], img.size[1]
    buf = np.empty(w*h*4, dtype=np.float32)
    img.pixels.foreach_get(buf)
    a = buf.reshape(h, w, 4)[:, :, :3].copy()
    bpy.data.images.remove(img)
    return a

def blue(mask_arr, thr=0.10):
    return (mask_arr[:, :, 2] - (mask_arr[:, :, 0]+mask_arr[:, :, 1])/2) > thr

def dilate(m, it):
    out = m.copy()
    for _ in range(it):
        o = out.copy()
        o[1:, :] |= out[:-1, :]; o[:-1, :] |= out[1:, :]
        o[:, 1:] |= out[:, :-1]; o[:, :-1] |= out[:, 1:]
        out = o
    return out

def comps(mask, minpix=6):
    ys, xs = np.where(mask)
    pix = set(zip(ys.tolist(), xs.tolist()))
    res = []
    while pix:
        y0, x0 = pix.pop()
        st = [(y0, x0)]; comp = [(y0, x0)]
        while st:
            y, x = st.pop()
            for dy in (-2, -1, 0, 1, 2):
                for dx in (-2, -1, 0, 1, 2):
                    p = (y+dy, x+dx)
                    if p in pix:
                        pix.remove(p); comp.append(p); st.append(p)
        if len(comp) >= minpix:
            res.append(comp)
    return res

LEDZ = 2.32
tot = [0, 0]
for cam in cams:
    n = int(cam['photo'].split('_')[1].split('.')[0])
    co = bpy.data.objects[cam['camera_object']]
    fx = cam['lens_mm']/cam['sensor_width_mm']*cam['resolution'][0]
    W, H = cam['resolution']
    ph = blue(load('inputs/photo_%d.jpg' % n))
    rn = blue(load('renders/score_%d.png' % n))
    miss_p = ph & ~dilate(rn, 5)
    miss_r = rn & ~dilate(ph, 5)
    tot[0] += int(miss_p.sum()); tot[1] += int(miss_r.sum())
    print('=== cam %d  photo_blue=%d render_blue=%d  missing_in_render=%d extra_in_render=%d' % (
        n, ph.sum(), rn.sum(), miss_p.sum(), miss_r.sum()))
    inv = co.matrix_world.inverted(); origin = co.matrix_world.translation
    for label, m in (('PHOTO-only', miss_p), ('RENDER-only', miss_r)):
        for c in comps(m):
            ys = np.array([p[0] for p in c]); xs = np.array([p[1] for p in c])
            u = xs.mean(); v = H - ys.mean()
            vx = (u - W/2)/fx; vy = -(v - H/2)/fx
            d = (co.matrix_world.to_3x3() @ Vector((vx, vy, -1))).normalized()
            t = (LEDZ - origin.z)/d.z if abs(d.z) > 1e-6 else 0
            p = origin + d*t if t > 0 else None
            print('   %s comp n=%4d u=%4d v=%4d  plan=(%6.0f,%6.0f)' % (
                label, len(c), u, v, p.x*1000 if p is not None else -1, p.y*1000 if p is not None else -1))
print('TOTAL missing_in_render=%d extra_in_render=%d' % tuple(tot))
print('DONE')
