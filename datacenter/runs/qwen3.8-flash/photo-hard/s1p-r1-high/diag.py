import bpy, numpy as np, json, os, sys

sc = bpy.data.scenes[0]
print('engine', sc.render.engine, 'res', sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage)
vs = sc.view_settings
print('view', vs.view_transform, vs.look, vs.exposure)
try:
    sh = sc.display
    print('display', sh.type, sh.shading.type if hasattr(sh, 'shading') else '')
except Exception as e:
    print(e)
wr = sc.world
print('world', wr.name if wr else None)
if wr:
    bg = wr.node_tree.nodes.get('Background')
    print('bg strength', bg.inputs[0].default_value[:], bg.inputs[1].default_value if bg else '')
for nm in ['RackA', 'RackG', 'CRAH']:
    ob = bpy.data.objects[nm]
    print(nm, 'children', len(ob.children), 'loc', tuple(round(v, 3) for v in ob.location))
light = [o for o in bpy.data.objects if o.type == 'LIGHT']
print('lights', len(light))
print('cam1 lens', bpy.data.cameras['Cam_1'].lens, bpy.data.cameras['Cam_1'].sensor_width, bpy.data.cameras['Cam_1'].sensor_fit)
