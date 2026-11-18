import bpy, json, math, os, numpy as np
from mathutils import Vector, Matrix

pred = json.load(open('pred.json'))
design = json.load(open('inputs/design.json'))
if pred.get('_from') == 'design':
    pred = {'racks': design['racks'], 'crah': design['crah']}
FACING = {'S': 0.0, 'N': math.pi, 'E': math.pi/2, 'W': -math.pi/2}
scene = bpy.context.scene
for o in [o for o in bpy.data.objects if o.name.startswith('P_')]:
    bpy.data.objects.remove(o, do_unlink=True)
templates = {t: bpy.data.objects[t] for t in ('RackA', 'RackG', 'CRAH')}

def build(tag, tpl, cx, cy, facing):
    src = templates[tpl]
    root = src.copy(); root.data = None
    scene.collection.objects.link(root); root.name = 'P_' + tag
    def cp(s, p):
        c = s.copy(); c.data = s.data
        scene.collection.objects.link(c); c.parent = p
        for ch in s.children: cp(ch, c)
        return c
    for ch in src.children: cp(ch, root)
    root.matrix_basis = Matrix.Translation((cx/1000.0, cy/1000.0, 0.6)) @ Matrix.Rotation(FACING[facing], 4, 'Z')

for r in pred['racks']:
    build(r['id'], 'RackG' if r['size'][0] >= 700 else 'RackA', r['center'][0], r['center'][1], r['facing'])
for c in pred['crah']:
    build(c['id'], 'CRAH', c['center'][0], c['center'][1], c['facing'])
bpy.context.view_layer.update()

scene.render.engine = 'BLENDER_WORKBENCH'
scene.display.shading.light = 'FLAT'
scene.display.shading.color_type = 'MATERIAL'
scene.display.shading.show_shadows = False
scene.display.shading.show_cavity = False
scene.render.resolution_x = 1280
scene.render.resolution_y = 960
cams = json.load(open('inputs/cameras.json'))['cameras']

def load(p):
    img = bpy.data.images.load(p, check_existing=False)
    w, h = img.size[0], img.size[1]
    buf = np.empty(w*h*4, dtype=np.float32)
    img.pixels.foreach_get(buf)
    a = buf.reshape(h, w, 4)[:, :, :3].copy()
    bpy.data.images.remove(img)
    return a

def dil(m, it):
    o = m.copy()
    for _ in range(it):
        n = o.copy()
        n[1:, :] |= o[:-1, :]; n[:-1, :] |= o[1:, :]
        n[:, 1:] |= o[:, :-1]; n[:, :-1] |= o[:, 1:]
        o = n
    return o

def comps(mask, minpix=15):
    ys, xs = np.where(mask)
    pix = set(zip(ys.tolist(), xs.tolist()))
    res = []
    while pix:
        y0, x0 = pix.pop()
        st = [(y0, x0)]; comp = [(y0, x0)]
        while st:
            y, x = st.pop()
            for dy in range(-3, 4):
                for dx in range(-3, 4):
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
    scene.camera = co
    scene.render.filepath = 'renders/e_%d.png' % n
    bpy.ops.render.render(write_still=True)
    pa = load('inputs/photo_%d.jpg' % n)
    ra = load('renders/e_%d.png' % n)
    pm = (pa[:, :, 2] - (pa[:, :, 0]+pa[:, :, 1])/2) > 0.06
    rm = (ra[:, :, 2] - (ra[:, :, 0]+ra[:, :, 1])/2) > 0.06
    mp = pm & ~dil(rm, 12)
    mr = rm & ~dil(pm, 12)
    tot[0] += int(mp.sum()); tot[1] += int(mr.sum())
    inv = co.matrix_world.inverted(); origin = co.matrix_world.translation
    info = []
    for c in comps(mp):
        ys = np.array([p[0] for p in c]); xs = np.array([p[1] for p in c])
        u = xs.mean(); v = H - ys.mean()
        q = inv @ Vector(((u-W/2)/fx, -(v-H/2)/fx, -1))
        d = (co.matrix_world.to_3x3() @ Vector(((u-W/2)/fx, -(v-H/2)/fx, -1))).normalized()
        t = (LEDZ-origin.z)/d.z if abs(d.z) > 1e-6 else -1
        p = origin + d*t if t > 0 else None
        info.append((len(c), int(u), int(v), int(p.x*1000) if p is not None else -1, int(p.y*1000) if p is not None else -1))
    rinfo = []
    for c in comps(mr):
        ys = np.array([p[0] for p in c]); xs = np.array([p[1] for p in c])
        u = xs.mean(); v = H - ys.mean()
        d = (co.matrix_world.to_3x3() @ Vector(((u-W/2)/fx, -(v-H/2)/fx, -1))).normalized()
        t = (LEDZ-origin.z)/d.z if abs(d.z) > 1e-6 else -1
        p = origin + d*t if t > 0 else None
        rinfo.append((len(c), int(u), int(v), int(p.x*1000) if p is not None else -1, int(p.y*1000) if p is not None else -1))
    print('cam %d photo_only=%d render_only=%d' % (n, mp.sum(), mr.sum()))
    for a in sorted(info, reverse=True)[:8]:
        print('    P-only n=%4d u=%4d v=%4d plan=(%6d,%6d)' % a)
    for a in sorted(rinfo, reverse=True)[:8]:
        print('    R-only n=%4d u=%4d v=%4d plan=(%6d,%6d)' % a)
print('TOTAL photo_only=%d render_only=%d  sum=%d' % (tot[0], tot[1], tot[0]+tot[1]))
print('DONE')
