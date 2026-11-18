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
sel = json.load(open('viz.json'))['cams']
os.makedirs('masks', exist_ok=True)

def load(p):
    img = bpy.data.images.load(p, check_existing=False)
    w, h = img.size[0], img.size[1]
    buf = np.empty(w*h*4, dtype=np.float32)
    img.pixels.foreach_get(buf)
    a = buf.reshape(h, w, 4)[:, :, :3].copy()
    bpy.data.images.remove(img)
    return a

def bluemask(a, thr=0.06):
    return (a[:, :, 2] - (a[:, :, 0]+a[:, :, 1])/2) > thr

def dil(m, it):
    o = m.copy()
    for _ in range(it):
        n = o.copy()
        n[1:, :] |= o[:-1, :]; n[:-1, :] |= o[1:, :]
        n[:, 1:] |= o[:, :-1]; n[:, :-1] |= o[:, 1:]
        o = n
    return o

def saveimg(out, arr):
    nh, nw = arr.shape[0], arr.shape[1]
    im = bpy.data.images.new(os.path.basename(out)[:30], nw, nh, alpha=False)
    o = np.ones((nh, nw, 4), dtype=np.float32); o[:, :, :3] = arr
    im.pixels.foreach_set(o.ravel()); im.filepath_raw = out; im.file_format = 'PNG'; im.save()
    bpy.data.images.remove(im)

tot = [0, 0]
for cam in cams:
    n = int(cam['photo'].split('_')[1].split('.')[0])
    if n not in sel:
        continue
    scene.camera = bpy.data.objects[cam['camera_object']]
    scene.render.filepath = 'renders/score_%d.png' % n
    bpy.ops.render.render(write_still=True)
    pa = load('inputs/photo_%d.jpg' % n)
    ra = load('renders/score_%d.png' % n)
    pm = bluemask(pa); rm = bluemask(ra)
    miss_p = pm & ~dil(rm, 6); miss_r = rm & ~dil(pm, 6)
    tot[0] += int(miss_p.sum()); tot[1] += int(miss_r.sum())
    g = pa.mean(axis=2)[:, :, None].repeat(3, axis=2)*0.5
    g[:, :, 2] *= 0.7
    g[:, :, 0] = np.clip(g[:, :, 0] + miss_p*0.95 + (pm & ~miss_p)*0.30, 0, 1)
    g[:, :, 1] = np.clip(g[:, :, 1] + miss_r*0.95 + (rm & ~miss_r)*0.30, 0, 1)
    saveimg('masks/m%d.png' % n, g)
    print('cam %d photo_blue=%d render_blue=%d photo_only=%d render_only=%d' % (n, pm.sum(), rm.sum(), miss_p.sum(), miss_r.sum()))
print('TOTAL photo_only=%d render_only=%d' % tuple(tot))
print('DONE')
