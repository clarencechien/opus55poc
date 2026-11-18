import bmesh

# --- rebuild perf tile master: 30 mm thick, top face z=0.6
old_mesh = bpy.data.meshes.get("PerfTileMesh")
mesh = bpy.data.meshes.new("PerfTileMesh")
bm = bmesh.new()
bmesh.ops.create_cube(bm, size=1.0)
for v in bm.verts:
    v.co.x *= 0.6; v.co.y *= 0.6; v.co.z *= 0.03; v.co.z -= 0.015
bm.to_mesh(mesh); bm.free()
c_mesh = bpy.data.meshes.new("hole")
cbm = bmesh.new()
for gx in (-0.2, -0.1, 0.0, 0.1, 0.2):
    for gy in (-0.2, -0.1, 0.0, 0.1, 0.2):
        mat = __import__("mathutils").Matrix.Translation((gx, gy, 0.0))
        bmesh.ops.create_cone(cbm, cap_ends=True, segments=12,
                              radius1=0.028, radius2=0.028, depth=0.2, matrix=mat)
cbm.to_mesh(c_mesh); cbm.free()
cutter = bpy.data.objects.new("hole", c_mesh)
bpy.context.scene.collection.objects.link(cutter)

master = bpy.data.objects["PerfTile_1_01"]
master.modifiers.clear()
master.data = mesh
master.location.z = 0.6 - 0.015
mod = master.modifiers.new("perf", 'BOOLEAN')
mod.operation = 'DIFFERENCE'
mod.solver = 'EXACT'
mod.object = cutter
bpy.context.view_layer.objects.active = master
bpy.ops.object.modifier_apply(modifier="perf")
bpy.data.objects.remove(cutter, do_unlink=True)
if old_mesh and old_mesh.users == 0:
    bpy.data.meshes.remove(old_mesh)
print("tiles rebuilt, users:", mesh.users)

# --- move containment doors flush outside the aisle ends
import json
data = json.load(open("/home/user/opus55poc/datacenter/runs/qwen3.8-flash/hard/s3-r1-high/inputs/layout.json"))
cold = [a for a in data["aisles"] if a["type"] == "cold"]
MM = 0.001; T = 0.05
for i, a in enumerate(cold, start=1):
    x0, y0, x1, y1 = [v*MM for v in a["rect"]]
    if (x1-x0) >= (y1-y0):
        w = bpy.data.objects[f"Containment_Aisle{i}_DoorW"]
        w.location.x = x0 - T/2
        e = bpy.data.objects[f"Containment_Aisle{i}_DoorE"]
        e.location.x = x1 + T/2
    else:
        s = bpy.data.objects[f"Containment_Aisle{i}_DoorS"]
        s.location.y = y0 - T/2
        n = bpy.data.objects[f"Containment_Aisle{i}_DoorN"]
        n.location.y = y1 + T/2
print("doors moved")
