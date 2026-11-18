import bpy, json, math, os, colorsys
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
    return root

for r in pred['racks']:
    place(r['id'], 'RackG' if r['size'][0] >= 700 else 'RackA', r['center'][0], r['center'][1], r['facing'])
for c in pred['crah']:
    place(c['id'], 'CRAH', c['center'][0], c['center'][1], c['facing'])

cfg = json.load(open('cfg.json'))
mode = cfg.get('mode', 'flat')
scene.render.engine = 'BLENDER_WORKBENCH'
scene.display.shading.show_shadows = True
scene.display.shading.show_cavity = True
scene.render.resolution_x = 1280
scene.render.resolution_y = 960
scene.render.resolution_percentage = 100
if mode == 'idmap':
    scene.display.shading.light = 'FLAT'; scene.display.shading.color_type = 'OBJECT'
else:
    scene.display.shading.light = 'STUDIO' if mode == 'photo' else 'FLAT'
    scene.display.shading.color_type = 'MATERIAL'

jobs = cfg.get('jobs', [{'cams': [1,2,3,4,5,6,7], 'tag': 'all'}])
cams = {int(c['photo'].split('_')[1].split('.')[0]): c for c in json.load(open('inputs/cameras.json'))['cameras']}
for j in jobs:
    only = j.get('only')
    for tag, ob in placed.items():
        show = (only is None) or (tag in only) or (j.get('group') and tag[0] in j['group'])
        for o in [ob] + list(ob.children_recursive):
            o.hide_render = not show
            o.hide_viewport = not show
    for n in j['cams']:
        co = bpy.data.objects[cams[n]['camera_object']]
        scene.camera = co
        out = 'renders/%s_%d.png' % (j['tag'], n)
        scene.render.filepath = out
        bpy.ops.render.render(write_still=True)
        print('wrote', out)
print('DONE')
