import bpy
for n in ('Containment_Roof_1', 'CableTray_A', 'CableTray_B'):
    o = bpy.data.objects[n]
    o.hide_render = True
    o.hide_viewport = True
print('hidden for inspection')
