import bpy
S = bpy.context.scene
for n in ("Manifold","Valve1","Valve2"):
    o = S.objects[n]
    for v in o.data.vertices: v.co.y -= 0.002
o = S.objects["HandleBar"]
for v in o.data.vertices: v.co.y += 0.0005
o = S.objects["Stub1"]; 
for v in o.data.vertices: v.co.y -= 0.002
o = S.objects["Stub2"]
for v in o.data.vertices: v.co.y -= 0.002
bpy.context.view_layer.update()
from mathutils import Vector
mn=[1e9]*3; mx=[-1e9]*3
dg = bpy.context.evaluated_depsgraph_get()
for ob in S.objects["Target"].children_all:
    ev = ob.evaluated_get(dg)
    for c in ev.bound_box:
        w = ev.matrix_world @ Vector(c)
        for i in range(3):
            mn[i]=min(mn[i],w[i]); mx[i]=max(mx[i],w[i])
print("bbox mm:", [round(v*1000,1) for v in mn], [round(v*1000,1) for v in mx])
