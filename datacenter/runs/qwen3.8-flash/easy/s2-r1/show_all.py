import bpy
for o in bpy.data.objects:
    o.hide_render = False
    o.hide_viewport = False
print("all visible:", len(bpy.data.objects))
