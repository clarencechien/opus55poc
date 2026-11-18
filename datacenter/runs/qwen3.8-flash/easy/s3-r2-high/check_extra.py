import bpy
known = ("Rack_", "Containment_", "PerfTile_", "CableTray_", "RackA", "RackB",
         "Wall_", "Column_", "RaisedFloor")
extra = [o.name for o in bpy.data.objects if not any(o.name.startswith(k) for k in known)]
print("extras:", extra)
print("counts:", {p: sum(1 for o in bpy.data.objects if o.name.startswith(p))
                  for p in known})
print("mesh datablocks:", [(m.name, m.users, len(m.vertices)) for m in bpy.data.meshes if m.users == 0])
