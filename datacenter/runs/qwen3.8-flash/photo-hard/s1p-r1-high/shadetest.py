import bpy, numpy as np, os
exec(open('fit.py').read())

for o in bpy.data.objects:
    if o.name.startswith('Light_'):
        o.hide_render = False

hyp = {"rows": [{"axis": "EW", "c": 6.77, "a": 6.0, "b": 18.0, "face": "S", "w": 0.6}]}
ph = img_lum('inputs/photo_2.jpg')
print('photo percentiles', np.round(np.percentile(ph, [1, 5, 25, 50, 75, 95, 99]), 3))
sc = bpy.data.scenes[0]
res = []
for vt in ['AgX', 'Standard', 'Filmic', 'Khronos PBR Neutral']:
    for lt in ['STUDIO', 'FLAT', 'MATCAP']:
        try:
            sc.view_settings.view_transform = vt
            sc.display.shading.light = lt
            out = render_all(hyp, res=(320, 240), cams=(2,), save_cmp=False, verbose=False)
            print('%-20s %-8s MAD %.4f frac %.3f' % (vt, lt, out[2][0], out[2][1]))
        except Exception as e:
            print(vt, lt, 'ERR', e)
r = img_lum('cmp/r2.png')
print('render percentiles', np.round(np.percentile(r, [1, 5, 25, 50, 75, 95, 99]), 3))
