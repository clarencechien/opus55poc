master = bpy.data.objects["PerfTile_1_01"]
target = master.data
print("target mesh:", target.name, "users:", target.users)
n = 0
for ob in bpy.data.objects:
    if ob.name.startswith("PerfTile_"):
        ob.data = target
        ob.location.z = 0.6 - 0.015   # 30 mm thick, top face at 0.6
        n += 1
for m in list(bpy.data.meshes):
    if m.name.startswith("PerfTileMesh") and m != target and m.users == 0:
        bpy.data.meshes.remove(m)
print("tiles:", n, "final users:", target.users)
deps = bpy.context.evaluated_depsgraph_get()
import mathutils
for name in ("PerfTile_1_01", "PerfTile_2_13", "PerfTile_3_10"):
    ob = bpy.data.objects[name]
    ev = ob.evaluated_get(deps)
    pts = [ev.matrix_world @ mathutils.Vector(c) for c in ev.bound_box]
    print(name, "x:", round(min(p.x for p in pts),3), round(max(p.x for p in pts),3),
          "y:", round(min(p.y for p in pts),3), round(max(p.y for p in pts),3),
          "z:", round(min(p.z for p in pts),3), round(max(p.z for p in pts),3))
