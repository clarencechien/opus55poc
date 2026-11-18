import bpy, json, math, os
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
    # report front LED side
    for ob in src.children:
        if 'FrontLED' in ob.name:
            c = sum((ob.matrix_world @ Vector(cc) for cc in ob.bound_box), Vector())/8
            print(tname, 'LED world center', [round(v, 3) for v in c], 'root', [round(v, 3) for v in src.matrix_world.translation])
FLOOR_Z = 0.6

def dup_tree(src, new_parent):
    c = src.copy(); c.data = src.data
    scene.collection.objects.link(c)
    if new_parent is not None:
        c.parent = new_parent
    for ch in src.children:
        dup_tree(ch, c)
    return c

def place(tag, tpl, cx, cy, facing):
    src = templates[tpl]['src']; zmin = templates[tpl]['zmin']
    root = dup_tree(src, None)
    root.name = 'P_' + tag
    root.matrix_basis = Matrix.Translation((cx/1000.0, cy/1000.0, FLOOR_Z - zmin)) @ Matrix.Rotation(FACING[facing], 4, 'Z')
    return root

items = list(pred['racks']) + list(pred['crah'])
cfg = json.load(open('cfg2.json'))
scene.render.engine = 'BLENDER_WORKBENCH'
scene.display.shading.light = 'FLAT'
scene.display.shading.color_type = 'MATERIAL'
scene.display.shading.show_shadows = False
scene.display.shading.show_cavity = True
scene.render.resolution_x = 1280
scene.render.resolution_y = 960
cams = {int(c['photo'].split('_')[1].split('.')[0]): c for c in json.load(open('inputs/cameras.json'))['cameras']}
for job in cfg['jobs']:
    for o in [o for o in bpy.data.objects if o.name.startswith('P_')]:
        bpy.data.objects.remove(o, do_unlink=True)
    rows = job['rows']
    for it in items:
        row = 'CRAH' if it['id'].startswith('CRAH') else it['id'][0]
        if row not in rows:
            continue
        tpl = 'CRAH' if row == 'CRAH' else ('RackG' if it['size'][0] >= 700 else 'RackA')
        place(it['id'], tpl, it['center'][0], it['center'][1], it['facing'])
    bpy.context.view_layer.update()
    for n in job['cams']:
        scene.camera = bpy.data.objects[cams[n]['camera_object']]
        out = 'renders/tpl_%s_%d.png' % ('_'.join(rows), n)
        scene.render.filepath = out
        bpy.ops.render.render(write_still=True)
        print('wrote', out, rows, n)
print('DONE')
