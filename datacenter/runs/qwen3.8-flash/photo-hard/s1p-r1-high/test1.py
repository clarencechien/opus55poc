import bpy, numpy as np, os
exec(open('fit.py').read())

for o in bpy.data.objects:
    if o.name.startswith('Light_'):
        o.hide_render = False

hyp = {"rows": [{"axis": "EW", "c": 6.77, "a": 6.0, "b": 18.0, "face": "S", "w": 0.6}]}
out = render_all(hyp, res=(1280, 960), cams=(2,), save_cmp=True)

# blend overlay photo vs render
ph = img_lum('inputs/photo_2.jpg')
rn = img_lum('cmp/r2.png')
old = bpy.data.images.get('bl2')
if old: bpy.data.images.remove(old)
im = bpy.data.images.new('bl2', rn.shape[1], rn.shape[0], alpha=True)
rgba = np.ones(rn.shape + (4,), np.float32)
mix = 0.5 * ph + 0.5 * rn
rgba[..., :3] = np.stack([mix] * 3, -1)
im.pixels = rgba.reshape(-1).tolist()
im.filepath_raw = os.path.abspath('out/blend2.png'); im.file_format = 'PNG'; im.save()
print('wrote out/blend2.png')
