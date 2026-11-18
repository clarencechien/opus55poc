import bpy, math
from mathutils import Matrix, Vector

tmpl = bpy.data.objects['RackA']
parts = []
def collect(ob):
    for c in ob.children:
        if c.type == 'MESH':
            parts.append(c)
        collect(c)
collect(tmpl)
print("uv/sk:", [(p.name, [l.name for l in p.data.uv_layers], bool(p.data.shape_keys)) for p in parts if p.data.uv_layers or p.data.shape_keys])
mats = {}
for p in parts:
    for m in p.data.materials:
        mats[m.name if m else None] = mats.get(m.name if m else None,0)+1
print("materials:", mats)
print("total verts:", sum(len(p.data.vertices) for p in parts), "polys:", sum(len(p.data.polygons) for p in parts))
print("tmpl items:", dict(tmpl.items()), "empty type:", tmpl.empty_display_type, tmpl.empty_display_size)

for n in ['Wall_N0','Wall_S0','Wall_W0','Wall_E0','Wall_E1','Wall_E_lintel','RaisedFloor','Column_B_2','Column_C_2']:
    o = bpy.data.objects[n]
    cs = [o.matrix_world @ Vector(c) for c in o.bound_box]
    mn = Vector((min(c[i] for c in cs) for i in range(3)))
    mx = Vector((max(c[i] for c in cs) for i in range(3)))
    print(n, tuple(round(v,3) for v in mn), tuple(round(v,3) for v in mx), dict(o.items()), [m.name for m in o.data.materials] if o.type=='MESH' else '')
