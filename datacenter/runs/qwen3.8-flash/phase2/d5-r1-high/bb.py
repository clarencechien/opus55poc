import bpy
from mathutils import Vector
S = bpy.context.scene
dg = bpy.context.evaluated_depsgraph_get()
mn=[1e9]*3; mx=[-1e9]*3
n=0
for ob in S.objects["Target"].children:
    n+=1
    ev = ob.evaluated_get(dg)
    for c in ev.bound_box:
        w = ev.matrix_world @ Vector(c)
        for i in range(3):
            mn[i]=min(mn[i],w[i]); mx[i]=max(mx[i],w[i])
print("children:", n)
print("bbox mm:", [round(v*1000,1) for v in mn], [round(v*1000,1) for v in mx])
tri=0
for ob in S.objects["Target"].children:
    ev=ob.evaluated_get(dg); me=ev.to_mesh()
    tri += sum(len(p.vertices)-2 for p in me.polygons); ev.to_mesh_clear()
print("tris:", tri)
