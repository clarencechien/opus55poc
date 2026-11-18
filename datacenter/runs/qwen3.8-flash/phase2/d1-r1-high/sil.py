import bpy, json, math, os
from mathutils import Vector, Matrix
import bmesh, colorsys

design = json.load(open('inputs/design.json'))
pred = json.load(open('pred.json'))
if pred.get('_from') == 'design':
    pred = {'racks': design['racks'], 'crah': design['crah']}
FACING = {'S': 0.0, 'N': math.pi, 'E': math.pi/2, 'W': -math.pi/2}
scene = bpy.context.scene

for o in [o for o in bpy.data.objects if o.name.startswith('S_') or o.name.startswith('P_')]:
    bpy.data.objects.remove(o, do_unlink=True)

mesh_cache = {}
def boxmesh(w, d, h):
    key = (round(w, 4), round(d, 4), round(h, 4))
    if key not in mesh_cache:
        me = bpy.data.meshes.new('box')
        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=1.0)
        for v in bm.verts:
            v.co.x *= w; v.co.y *= d; v.co.z *= h
        bm.to_mesh(me); bm.free()
        mesh_cache[key] = me
    return mesh_cache[key]

def addbox(name, cx, cy, w_mm, d_mm, facing, frontcol, h=2.0, z=0.6):
    me = boxmesh(w_mm/1000.0, d_mm/1000.0, h)
    ob = bpy.data.objects.new(name, me)
    scene.collection.objects.link(ob)
    ob.matrix_basis = Matrix.Translation((cx/1000.0, cy/1000.0, z + h/2.0)) @ Matrix.Rotation(FACING[facing], 4, 'Z')
    ob.color = frontcol
    objs = [ob]
    # thin marker plate on the front face (front = -y in local frame)
    pme_key = ('plate', round(w_mm, 1), round(h, 1))
    if pme_key not in mesh_cache:
        me2 = bpy.data.meshes.new('plate')
        bm2 = bmesh.new()
        bmesh.ops.create_cube(bm2, size=1.0)
        for v in bm2.verts:
            v.co.x *= (w_mm/1000.0)*0.8; v.co.y *= 0.02; v.co.z *= 0.15
        bm2.to_mesh(me2); bm2.free()
        mesh_cache[pme_key] = me2
    p = bpy.data.objects.new(name + '_F', mesh_cache[pme_key])
    scene.collection.objects.link(p)
    p.parent = ob
    p.matrix_basis = Matrix.Translation((0, -d_mm/2000.0 - 0.01, h/2.0 - 0.25))
    p.color = (0, 0, 1, 1)
    return objs

items = list(pred['racks']) + list(pred['crah'])
cfg = json.load(open('sil.json'))
scene.render.engine = 'BLENDER_WORKBENCH'
scene.display.shading.light = 'FLAT'
scene.display.shading.color_type = 'OBJECT'
scene.display.shading.show_shadows = False
scene.display.shading.show_cavity = False
scene.render.resolution_x = 1280
scene.render.resolution_y = 960
cams = {int(c['photo'].split('_')[1].split('.')[0]): c for c in json.load(open('inputs/cameras.json'))['cameras']}

for job in cfg['jobs']:
    for ob in [o for o in bpy.data.objects if o.name.startswith('S_')]:
        bpy.data.objects.remove(ob, do_unlink=True)
    rows = job['rows']
    for it in items:
        row = 'CRAH' if it['id'].startswith('CRAH') else it['id'][0]
        if row not in rows:
            continue
        hue = (rows.index(row)*0.37) % 1.0
        r_, g_, b_ = colorsys.hsv_to_rgb(hue, 0.9, 1.0)
        addbox('S_' + it['id'], it['center'][0], it['center'][1], it['size'][0], it['size'][1], it['facing'],
               (r_, g_, b_, 1.0))
    bpy.context.view_layer.update()
    for n in job['cams']:
        scene.camera = bpy.data.objects[cams[n]['camera_object']]
        out = 'renders/sil_%s_%d.png' % ('_'.join(rows), n)
        scene.render.filepath = out
        bpy.ops.render.render(write_still=True)
        print('wrote', out, rows, n)
print('DONE')
