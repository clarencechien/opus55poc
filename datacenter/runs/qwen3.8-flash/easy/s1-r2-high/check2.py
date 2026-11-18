import bpy
from mathutils import Vector

dg = bpy.context.evaluated_depsgraph_get()
for pt in [(14.4, 9.0, 1.0), (14.4, 9.0, 3.0), (14.4, 5.0, 1.0), (14.4, 9.0, 2.8)]:
    hit, loc, nrm, idx, ob, mat = bpy.context.scene.ray_cast(dg, Vector((20.0, pt[1], pt[2])), Vector((-1, 0, 0)))
    print('ray at y=%.1f z=%.1f ->' % (pt[1], pt[2]), hit, ob.name if ob else None, tuple(round(c, 2) for c in loc))

ob = bpy.data.objects['Wall_E']
print('Wall_E verts', len(ob.data.vertices), 'polys', len(ob.data.polygons))
print('z levels:', sorted({round(v.co.z, 3) for v in ob.data.vertices}))
print('y extents of separate shells:')
# quick check: are there faces at the doorway sides?
ys = sorted({round(v.co.y, 3) for v in ob.data.vertices})
print('y coords:', ys)
