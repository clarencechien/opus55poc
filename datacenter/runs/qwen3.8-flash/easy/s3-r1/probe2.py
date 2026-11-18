import bpy, math
from mathutils import Matrix, Vector

dg = bpy.context.evaluated_depsgraph_get()
tmpl = bpy.data.objects['RackA']
parts = []
def collect(ob):
    for c in ob.children:
        if c.type == 'MESH':
            parts.append(c)
        collect(c)
collect(tmpl)
inv = tmpl.matrix_world.inverted()
ident = Matrix.Identity(4)
nonident = [p.name for p in parts if (inv @ p.matrix_world) != ident]
print("non-identity rel parts:", nonident)

mats = {}
for p in parts:
    for s in p.data.materials:
        mats[s.material.name if s.material else None] = mats.get(s.material.name if s.material else None,0)+1
    if p.data.uv_layers:
        print("uv:", p.name)
    if p.data.shape_keys:
        print("sk:", p.name)
print("materials:", mats)
print("total verts:", sum(len(p.data.vertices) for p in parts), "polys:", sum(len(p.data.polygons) for p in parts))
print("custom props on tmpl:", dict(tmpl.id_data.properties) if False else dict(tmpl.items()))

for n in ['Wall_N0','Wall_S0','Wall_W0','Wall_E0','Wall_E1','Wall_E_lintel','RaisedFloor','Column_B_2','Column_C_2']:
    o = bpy.data.objects[n]
    cs = [o.matrix_world @ Vector(c) for c in o.bound_box]
    mn = Vector((min(c[i] for c in cs) for i in range(3)))
    mx = Vector((max(c[i] for c in cs) for i in range(3)))
    print(n, tuple(round(v,3) for v in mn), tuple(round(v,3) for v in mx), dict(o.items()))
