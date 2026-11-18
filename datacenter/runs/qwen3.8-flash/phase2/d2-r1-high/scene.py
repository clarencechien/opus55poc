import json, bpy, math
from mathutils import Vector
d=json.load(open('layout_design.json'))
# remove old rack objects
for o in list(bpy.data.objects):
    if o.name.startswith('GPU_') or o.name.startswith('STD_'):
        bpy.data.objects.remove(o, do_unlink=True)
coll=bpy.data.collections.get('Racks') or bpy.data.collections.new('Racks')
if coll.name not in [c.name for c in bpy.context.scene.collection.children]:
    bpy.context.scene.collection.children.link(coll)
for e in d['racks']:
    w=e['size'][0]; x,y=e['center']
    me=bpy.data.meshes.new('b')
    o=bpy.data.objects.new(('GPU_' if w==800 else 'STD_')+e['id'], me)
    import bmesh
    bm=bmesh.new()
    bmesh.ops.create_cube(bm,size=1.0)
    bm.to_mesh(me); bm.free()
    me.update()
    o.scale=(1.2 if False else (w/1000.0), 1.2/1.0 if e['facing'] in 'NS' else (w/1000.0), 2.0)
    # footprint: w along row axis, 1200 depth
    if e['facing'] in 'NS':
        o.scale=(w/1000.0,1.2,2.0)
    else:
        o.scale=(1.2,w/1000.0,2.0)
    o.location=(x/1000.0, y/1000.0, 0.6+1.0)
    coll.objects.link(o)
print("placed",len(d['racks']))
