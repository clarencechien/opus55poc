import bmesh, mathutils

master = bpy.data.objects["PerfTile_1_01"]
master.modifiers.clear()
# give master its own single-user mesh copy
old = master.data
target = old.copy()
master.data = target
mx, my = master.location.x, master.location.y

c_mesh = bpy.data.meshes.new("hole")
cbm = bmesh.new()
for gx in (-0.2, -0.1, 0.0, 0.1, 0.2):
    for gy in (-0.2, -0.1, 0.0, 0.1, 0.2):
        mat = mathutils.Matrix.Translation((mx+gx, my+gy, 0.6))
        bmesh.ops.create_cone(cbm, cap_ends=True, segments=12,
                              radius1=0.028, radius2=0.028, depth=0.2, matrix=mat)
cbm.to_mesh(c_mesh); cbm.free()
cutter = bpy.data.objects.new("hole", c_mesh)
bpy.context.scene.collection.objects.link(cutter)

mod = master.modifiers.new("perf", 'BOOLEAN')
mod.operation = 'DIFFERENCE'
mod.solver = 'EXACT'
mod.object = cutter
bpy.context.view_layer.objects.active = master
bpy.ops.object.modifier_apply(modifier="perf")
bpy.data.objects.remove(cutter, do_unlink=True)

for ob in bpy.data.objects:
    if ob.name.startswith("PerfTile_"):
        ob.data = target
        ob.location.z = 0.6
if old.users == 0:
    bpy.data.meshes.remove(old)
print("faces in tile mesh:", len(target.polygons), "users:", target.users)

deps = bpy.context.evaluated_depsgraph_get()
for name in ("PerfTile_1_01", "PerfTile_2_13", "PerfTile_3_34"):
    ob = bpy.data.objects[name]
    ev = ob.evaluated_get(deps)
    pts = [ev.matrix_world @ mathutils.Vector(c) for c in ev.bound_box]
    print(name, "x:", round(min(p.x for p in pts),3), round(max(p.x for p in pts),3),
          "y:", round(min(p.y for p in pts),3), round(max(p.y for p in pts),3),
          "z:", round(min(p.z for p in pts),3), round(max(p.z for p in pts),3))
