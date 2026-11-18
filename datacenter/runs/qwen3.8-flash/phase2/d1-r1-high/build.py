import bpy, json, math, os, colorsys
from mathutils import Vector, Matrix

PRED = 'pred.json'
OUTDIR = 'renders'
os.makedirs(OUTDIR, exist_ok=True)
cfg = {}
if os.path.exists('cfg.json'):
    cfg = json.load(open('cfg.json'))
mode = cfg.get('mode', 'photo')
cams_sel = cfg.get('cams', [1, 2, 3, 4, 5, 6, 7])
hide = set(cfg.get('hide', []))
only = cfg.get('only', None)

design = json.load(open('inputs/design.json'))
pred = json.load(open(PRED))
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
    c = src.copy()
    c.data = src.data
    scene.collection.objects.link(c)
    if new_parent is not None:
        c.parent = new_parent
    for ch in src.children:
        dup_tree(ch, c)
    return c

def place(tag, tpl, cx_mm, cy_mm, facing, idx):
    src = templates[tpl]['src']
    zmin = templates[tpl]['zmin']
    root = dup_tree(src, None)
    root.name = 'P_' + tag
    root.matrix_basis = Matrix.Translation((cx_mm/1000.0, cy_mm/1000.0, FLOOR_Z - zmin)) @ Matrix.Rotation(FACING[facing], 4, 'Z')
    hue = (idx * 0.6180339887498949) % 1.0
    r, g, b = colorsys.hsv_to_rgb(hue, 0.85, 1.0)
    col = (r, g, b, 1.0)
    for ob in [root] + list(root.children_recursive):
        ob.color = col
        if tag in hide or (only is not None and tag not in only):
            ob.hide_render = True
            ob.hide_viewport = True
    return root

count = 0
for r in pred['racks']:
    tpl = 'RackG' if r['size'][0] >= 700 else 'RackA'
    place(r['id'], tpl, r['center'][0], r['center'][1], r['facing'], count)
    count += 1
for c in pred['crah']:
    place(c['id'], 'CRAH', c['center'][0], c['center'][1], c['facing'], count)
    count += 1
print('placed', count, 'items, mode', mode, 'cams', cams_sel)

cams = [c for c in json.load(open('inputs/cameras.json'))['cameras']
        if int(c['photo'].split('_')[1].split('.')[0]) in cams_sel]
scene.render.engine = 'BLENDER_WORKBENCH'
scene.display.shading.show_shadows = True
scene.display.shading.show_cavity = True
scene.render.resolution_x = 1280
scene.render.resolution_y = 960
scene.render.resolution_percentage = 100
if mode == 'idmap':
    scene.display.shading.light = 'FLAT'
    scene.display.shading.color_type = 'OBJECT'
else:
    scene.display.shading.light = 'STUDIO' if mode == 'photo' else 'FLAT'
    scene.display.shading.color_type = 'MATERIAL'
for cam in cams:
    co = bpy.data.objects[cam['camera_object']]
    scene.camera = co
    n = cam['photo'].split('_')[1].split('.')[0]
    out = os.path.join(OUTDIR, mode + '_' + n + '.png')
    scene.render.filepath = out
    bpy.ops.render.render(write_still=True)
    print('wrote', out)
print('DONE')
