import bpy, json, math, os
from mathutils import Vector, Matrix
print('floor color', bpy.data.objects['RaisedFloor'].color[:], 'hide_render', bpy.data.objects['RaisedFloor'].hide_render)
print('wall color', bpy.data.objects['Wall_S'].color[:] if 'Wall_S' in [o.name for o in bpy.data.objects] else 'n/a')
print([o.name for o in bpy.data.objects if o.name.startswith('S_')][:5])
for o in bpy.data.objects:
    if o.name.startswith('S_'):
        bb = [o.matrix_world @ Vector(c) for c in o.bound_box]
        print(o.name, [round(v, 2) for v in o.matrix_world.translation], 'dims', [round(o.dimensions[i], 2) for i in range(3)], 'hide', o.hide_render, 'col', [round(c, 2) for c in o.color])
print('scene camera', bpy.context.scene.camera.name if bpy.context.scene.camera else None)
print('collection objects', len(bpy.context.scene.collection.objects), 'viewlayer', [l.name for l in bpy.context.scene.view_layers])
vl = bpy.context.scene.view_layers[0]
print('exclude', [c.name for c in vl.layer_collection.children if c.exclude])
print('DONE')
