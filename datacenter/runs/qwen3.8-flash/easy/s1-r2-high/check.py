import bpy
from mathutils import Vector

# verify the door opening in Wall_E with a point-inside test
ob = bpy.data.objects['Wall_E']
me = ob.data
def inside(pt):
    p = Vector(pt)
    # ray cast along -x from far outside
    hit, loc, nrm, idx, ob2, mat = bpy.context.scene.ray_cast(bpy.context.view_layer, Vector((20, p.y, p.z)), Vector((-1, 0, 0)))
    return hit, loc, ob2.name if ob2 else None
for pt in [(14.4, 9.0, 1.0), (14.4, 9.0, 3.0), (14.4, 5.0, 1.0), (14.4, 9.0, 2.6)]:
    print('door test at', pt, '->', inside(pt))

print('verts Wall_E:', len(me.vertices), 'polys:', len(me.polygons))
import collections
zs = sorted({round(v.co.z, 3) for v in me.vertices})
print('z levels in Wall_E:', zs)
