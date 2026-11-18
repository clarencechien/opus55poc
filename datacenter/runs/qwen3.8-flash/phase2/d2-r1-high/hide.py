import bpy
for o in bpy.data.objects:
    if o.name.lower().startswith('ceiling') or o.name.lower().startswith('light'):
        o.hide_render=True; o.hide_viewport=True
print("hidden")
