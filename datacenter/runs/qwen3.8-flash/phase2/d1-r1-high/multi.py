import bpy, json, math, os, numpy as np
from mathutils import Vector, Matrix

design = json.load(open('inputs/design.json'))
base = list(design['racks']) + list(design['crah'])
FACING = {'S': 0.0, 'N': math.pi, 'E': math.pi/2, 'W': -math.pi/2}
scene = bpy.context.scene
for o in [o for o in bpy.data.objects if o.name.startswith('P_')]:
    bpy.data.objects.remove(o, do_unlink=True)
templates = {t: bpy.data.objects[t] for t in ('RackA', 'RackG', 'CRAH')}
roots = {}
def build(tag, tpl):
    src = templates[tpl]
    root = src.copy(); root.data = None
    scene.collection.objects.link(root); root.name = 'P_' + tag
    def cp(s, p):
        c = s.copy(); c.data = s.data
        scene.collection.objects.link(c); c.parent = p
        for ch in s.children: cp(ch, c)
        return c
    for ch in src.children: cp(ch, root)
    roots[tag] = root
for it in base:
    build(it['id'], 'CRAH' if it['id'].startswith('CRAH') else ('RackG' if it['size'][0] >= 700 else 'RackA'))

def apply(ch):
    for it in base:
        r = roots[it['id']]
        for o in [r] + list(r.children_recursive):
            o.hide_render = False; o.hide_viewport = False
        r.matrix_basis = Matrix.Translation((it['center'][0]/1000.0, it['center'][1]/1000.0, 0.6)) @ Matrix.Rotation(FACING[it['facing']], 4, 'Z')
    for k, v in ch.items():
        r = roots[k]; it = [x for x in base if x['id'] == k][0]
        if v.get('del'):
            for o in [r] + list(r.children_recursive):
                o.hide_render = True; o.hide_viewport = True
            continue
        cx = v.get('center', it['center']); f = v.get('facing', it['facing'])
        r.matrix_basis = Matrix.Translation((cx[0]/1000.0, cx[1]/1000.0, 0.6)) @ Matrix.Rotation(FACING[f], 4, 'Z')
    bpy.context.view_layer.update()

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

camsel = json.load(open('hyp.json')).get('cams', [3, 5, 6])
cams = [c for c in json.load(open('inputs/cameras.json'))['cameras']
        if int(c['photo'].split('_')[1].split('.')[0]) in camsel]
PM = {}
for cam in cams:
    n = int(cam['photo'].split('_')[1].split('.')[0])
    m = (load('inputs/photo_%d.jpg' % n)[:, :, 2] - (load('inputs/photo_%d.jpg' % n)[:, :, 0]+load('inputs/photo_%d.jpg' % n)[:, :, 1])/2) > 0.06
    m[:370, :] = False
    PM[n] = m
scene.render.engine = 'BLENDER_WORKBENCH'
scene.display.shading.light = 'FLAT'
scene.display.shading.color_type = 'MATERIAL'
scene.display.shading.show_shadows = False
scene.display.shading.show_cavity = False
scene.render.resolution_x = 1280
scene.render.resolution_y = 960
for name, ch in json.load(open('hyp.json'))['hyps'].items():
    apply(ch)
    tp = tr = 0; det = []
    for cam in cams:
        n = int(cam['photo'].split('_')[1].split('.')[0])
        scene.camera = bpy.data.objects[cam['camera_object']]
        scene.render.filepath = 'renders/h_%d.png' % n
        bpy.ops.render.render(write_still=True)
        rm = (load('renders/h_%d.png' % n)[:, :, 2] - (load('renders/h_%d.png' % n)[:, :, 0]+load('renders/h_%d.png' % n)[:, :, 1])/2) > 0.06
        rm[:370, :] = False
        pm = PM[n]
        a = int((pm & ~dil(rm, 12)).sum()); b = int((rm & ~dil(pm, 12)).sum())
        tp += a; tr += b; det.append((n, a, b))
    print('%-24s photo_only=%5d render_only=%5d SUM=%6d %s' % (name, tp, tr, tp+tr, det))
