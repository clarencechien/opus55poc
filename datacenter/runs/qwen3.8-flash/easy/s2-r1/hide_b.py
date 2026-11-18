import bpy
for o in bpy.data.objects:
    if o.name.startswith("RackB"):
        o.hide_render = True
        o.hide_viewport = True
print("RackB hidden")
