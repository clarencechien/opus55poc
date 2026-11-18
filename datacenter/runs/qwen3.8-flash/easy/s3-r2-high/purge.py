import bpy
for _ in range(3):
    bpy.data.orphans_purge(do_recursive=True)
print("objects:", len(bpy.data.objects), "meshes:", len(bpy.data.meshes))
print("zero-user meshes:", sum(1 for m in bpy.data.meshes if m.users == 0))
print("groups:", {p: sum(1 for o in bpy.data.objects if o.name.startswith(p))
                  for p in ("Rack_", "Containment_", "PerfTile_", "CableTray_")})
