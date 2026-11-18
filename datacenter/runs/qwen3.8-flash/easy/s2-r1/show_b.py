import bpy
for o in bpy.data.objects:
    a = o.name.startswith("RackA")
    b = o.name.startswith("RackB")
    o.hide_render = a
    o.hide_viewport = a
    if b:
        o.hide_render = False
        o.hide_viewport = False
print("showing RackB only")
