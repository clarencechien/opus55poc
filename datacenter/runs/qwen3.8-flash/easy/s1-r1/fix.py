import bpy

# Report world bounds of each object
for o in bpy.data.objects:
    bb = [o.matrix_world @ __import__('mathutils').Vector(c) for c in o.bound_box]
    xs=[v.x for v in bb]; ys=[v.y for v in bb]; zs=[v.z for v in bb]
    print(o.name, [round(min(xs),3),round(max(xs),3),round(min(ys),3),round(max(ys),3),round(min(zs),3),round(max(zs),3)])

# Fix north wall: rebuild it centred on grid line y=12000 (11.9..12.1)
old = bpy.data.objects.get("Wall_N")
if old: bpy.data.objects.remove(old, do_unlink=True)

def box(name, x0, x1, y0, y1, z0, z1):
    bpy.ops.mesh.primitive_cube_add(size=1)
    o = bpy.context.active_object
    o.name = name
    o.scale = ((x1-x0),(y1-y0),(z1-z0))
    o.location = ((x0+x1)/2,(y0+y1)/2,(z0+z1)/2)
    bpy.ops.object.transform_apply(location=True, scale=True)
    return o

box("Wall_N", -0.1, 14.5, 11.9, 12.1, 0, 3.6)
print("fixed")
