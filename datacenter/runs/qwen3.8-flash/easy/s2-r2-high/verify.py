import bpy
from mathutils import Vector

cam = bpy.data.objects.get("TmpCam")
if cam:
    bpy.data.objects.remove(cam, do_unlink=True)

dg = bpy.context.evaluated_depsgraph_get()

def world_bbox(root):
    lo = [1e9, 1e9, 1e9]; hi = [-1e9, -1e9, -1e9]
    def walk(o):
        for ch in o.children:
            if ch.type == 'MESH':
                oe = ch.evaluated_get(dg)
                for corner in oe.bound_box:
                    w = oe.matrix_world @ Vector(corner)
                    for i in range(3):
                        lo[i] = min(lo[i], w[i]); hi[i] = max(hi[i], w[i])
            walk(ch)
    walk(root)
    return Vector(lo), Vector(hi)

def tris(root):
    t = 0
    for o in root.children_recursive:
        if o.type == 'MESH':
            oe = o.evaluated_get(dg)
            me = oe.to_mesh()
            t += sum(len(p.vertices) - 2 for p in me.polygons)
            oe.to_mesh_clear()
    return t

for nm in ("RackA", "RackB"):
    r = bpy.data.objects[nm]
    mn, mx = world_bbox(r)
    print(nm, "min", tuple(round(v, 4) for v in mn), "max", tuple(round(v, 4) for v in mx),
          "size", tuple(round(mx[i] - mn[i], 4) for i in range(3)), "tris", tris(r),
          "children", len(r.children))

def top(o):
    while o.parent:
        o = o.parent
    return o.name
bad = [o.name for o in bpy.context.scene.objects
       if o.type not in ('EMPTY', 'CAMERA') and top(o) not in ("RackA", "RackB")]
print("bad-parented:", bad)
print("scene objects:", len(bpy.context.scene.objects))
