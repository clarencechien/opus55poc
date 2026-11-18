import bpy, numpy as np, os, json
exec(open('fit.py').read())

for o in bpy.data.objects:
    if o.name.startswith('Light_'):
        o.hide_render = True

def save_rgb(name, out):
    if out.ndim == 2:
        out = np.stack([out] * 3, -1)
    old = bpy.data.images.get(name)
    if old: bpy.data.images.remove(old)
    im = bpy.data.images.new(name, out.shape[1], out.shape[0], alpha=True)
    rgba = np.ones(out.shape[:2] + (4,), np.float32)
    rgba[..., :3] = out
    im.pixels = rgba.reshape(-1).tolist()
    im.filepath_raw = os.path.abspath('out/%s.png' % name); im.file_format = 'PNG'; im.save()
    print('wrote out/%s.png' % name)

def make(cams, w, h):
    panels = []; dpanels = []
    for i in cams:
        ph = img_lum('inputs/photo_%d.jpg' % i, w, h)
        rn = img_lum('cmp/r%d.png' % i, w, h)
        gap = np.ones((h, 4)) * 0.5
        panels.append(np.concatenate([ph, gap, rn], axis=1))
        a = (ph < 0.16).astype(np.float32)
        b = (rn < 0.30).astype(np.float32)
        rgb = np.zeros((h, w, 3), np.float32)
        rgb[..., 0] = a * (1 - b) + 0.10
        rgb[..., 1] = b * (1 - a) + 0.10
        rgb[..., 2] = (a * b) * 0.9 + 0.10
        dpanels.append(rgb)
    save_rgb('stack', np.concatenate(panels, axis=0))
    save_rgb('diff', np.concatenate(dpanels, axis=0))

def go(hypfile='hyp.json', cams=(1, 2, 3, 4, 5), res=(512, 384)):
    hyp = json.load(open(hypfile))
    render_all(hyp, res=res, cams=cams)
    make(cams, res[0], res[1])

go()
