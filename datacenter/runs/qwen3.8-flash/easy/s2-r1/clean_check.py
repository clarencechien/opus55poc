import bpy
others = [o.name for o in bpy.data.objects
          if not (o.name.startswith("RackA") or o.name.startswith("RackB"))]
print("non-rack objects:", others)
print("roots:", [(o.name, o.type, tuple(round(v,3) for v in o.location)) for o in bpy.data.objects
                 if o.name in ("RackA", "RackB")])
print("total:", len(bpy.data.objects))
print("meshes:", len(bpy.data.meshes), "curves:", len(bpy.data.curves))
