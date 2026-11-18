import bpy, math
from mathutils import Matrix, Vector

dg = bpy.context.evaluated_depsgraph_get()
scene = bpy.context.scene

tmpl = bpy.data.objects['RackA']
print("tmpl matrix_world:\n", tmpl.matrix_world)

parts = []
def collect(ob):
    for c in ob.children:
        if c.type == 'MESH':
            parts.append(c)
        collect(c)
collect(tmpl)
print("num mesh parts:", len(parts))

# local bbox of the whole template (relative to empty origin)
inv = tmpl.matrix_world.inverted()
mins = Vector((1e9,1e9,1e9)); maxs = Vector((-1e9,-1e9,-1e9))
for p in parts:
    M = inv @ p.matrix_world
    for corner in p.bound_box:
        w = M @ Vector(corner)
        for i in range(3):
            mins[i] = min(mins[i], w[i]); maxs[i] = max(maxs[i], w[i])
print("local bbox min", tuple(round(v,4) for v in mins), "max", tuple(round(v,4) for v in maxs))

print("rel transforms (non-identity ones):")
for p in parts:
    M = inv @ p.matrix_world
    if not M.is_identity(1e-6):
        print("  ", p.name, tuple(round(v,4) for v in M.translation), M.to_euler(), tuple(round(v,4) for v in M.to_scale()))

print("materials / uv layers:")
mats = []
for p in parts[:60]:
    ms = [s.material.name if s.material else None for s in p.data.materials]
    if ms: mats.append((p.name, ms))
    if p.data.uv_layers: print("  uv:", p.name, [l.name for l in p.data.uv_layers])
    if p.data.shape_keys: print("  shapekey:", p.name)
print("  with mats:", mats[:20], "count", len(mats))
tot_verts = sum(len(p.data.vertices) for p in parts)
print("total verts:", tot_verts)

# room bounds
for n in ['Wall_N0','Wall_S0','Wall_W0','Wall_E0','Wall_E1','Wall_E_lintel','RaisedFloor','Column_B_2','Column_C_2']:
    o = bpy.data.objects[n]
    cs = [o.matrix_world @ Vector(c) for c in o.bound_box]
    mn = Vector((min(c[i] for c in cs) for i in range(3)))
    mx = Vector((max(c[i] for c in cs) for i in range(3)))
    print(n, tuple(round(v,3) for v in mn), tuple(round(v,3) for v in mx))
