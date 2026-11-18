import bpy
keep = set(['PerfTile_%02d' % i for i in range(1, 17)] +
           ['Containment_Door_1_W', 'Containment_Door_1_E', 'CableTray_A', 'CableTray_B'])
for o in bpy.data.objects:
    vis = o.name in keep
    o['bench_hidden'] = o.hide_viewport or o.hide_render
    o.hide_viewport = not vis
    o.hide_render = not vis
print('isolated', len(keep), 'objects')
