import numpy as np, os

RES = 0.1
NX, NY = 240, 180

def comb(tag, mode):
    gs = [np.load('npy/Cam_%d_%s.npy' % (i, tag)) for i in [1, 2, 3, 4, 5]]
    st = np.stack(gs)
    valid = st >= 0
    if mode == 'mean':
        out = np.where(valid.any(0), np.where(valid, st, 0).sum(0) / np.maximum(valid.sum(0), 1), -1)
    else:
        out = np.where(valid.any(0), np.where(valid, st, -1).max(0), -1)
    return out

def save_img(name, g2, scale=4, mode='gray'):
    v = np.clip(np.array(g2, np.float32), 0, 1)
    rgb = np.zeros(list(v.shape) + [3], np.float32)
    if mode == 'gray':
        b = np.where(g2 >= 0, v, 0.05)
        rgb[..., 0] = b; rgb[..., 1] = b; rgb[..., 2] = b
    elif mode == 'hot':
        hot = np.where(g2 >= 0, g2 > 0.5, False)
        rgb[..., 0] = np.where(hot, 1.0, 0.05)
        rgb[..., 1] = np.where(hot, 0.15, 0.05)
        rgb[..., 2] = np.where(hot, 0.15, 0.05)
    nh, nw = rgb.shape[0], rgb.shape[1]
    for iy in range(0, nh, 12):
        rgb[iy, :, 2] = np.maximum(rgb[iy, :, 2], 0.4)
    for ix in range(0, nw, 12):
        rgb[:, ix, 1] = np.maximum(rgb[:, ix, 1], 0.4)
    for iy in range(0, nh, 60):
        rgb[iy, :, :] = 0.2
        rgb[iy, :, 2] = 1.0
    for ix in range(0, nw, 60):
        rgb[:, ix, :] = 0.2
        rgb[:, ix, 1] = 1.0
    r = np.repeat(np.repeat(rgb, scale, 0), scale, 1)
    h2, w2 = r.shape[0], r.shape[1]
    rgba = np.ones((h2, w2, 4), np.float32)
    rgba[..., :3] = r
    im = bpy.data.images.get(name)
    if im: bpy.data.images.remove(im)
    im = bpy.data.images.new(name, w2, h2, alpha=True)
    im.pixels = rgba.reshape(-1).tolist()
    im.filepath_raw = os.path.abspath('out/%s.png' % name)
    im.file_format = 'PNG'
    im.save()
    print('wrote out/%s.png' % name)

import bpy
save_img('comb_top', comb('top', 'mean'), mode='gray')
save_img('comb_lab', comb('lab', 'max'), mode='hot')
save_img('comb_floor', comb('floor', 'mean'), mode='gray')
print('done')
