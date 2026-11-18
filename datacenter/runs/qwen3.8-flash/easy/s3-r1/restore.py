import bpy
for o in bpy.data.objects:
    if 'bench_hidden' in o:
        del o['bench_hidden']
    o.hide_viewport = False
    o.hide_render = False
    o.hide_select = False
print('all objects visible again:', len(bpy.data.objects))
print('any hidden:', [o.name for o in bpy.data.objects if o.hide_viewport or o.hide_render])
