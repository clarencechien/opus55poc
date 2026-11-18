import bpy, numpy as np, os
RUN = '/home/user/opus55poc/datacenter/runs/opus-5.5/photo-hard/s1p-r1/'
def load(path):
    im = bpy.data.images.load(path, check_existing=False)
    w,h = im.size
    a = np.empty(w*h*4, dtype=np.float32)
    im.pixels.foreach_get(a)
    a = a.reshape(h,w,4)[::-1]
    bpy.data.images.remove(im)
    return a
def save(arr, path):
    h,w,_ = arr.shape
    im = bpy.data.images.new('tmpc', w, h, alpha=True)
    im.pixels.foreach_set(np.ascontiguousarray(arr[::-1]).ravel())
    im.filepath_raw = path
    im.file_format = 'PNG'
    im.save()
    bpy.data.images.remove(im)
def grid(c, x0, y0, s, step):
    # draw tick marks every `step` original px along top and left edges (red), labelled by position
    h,w,_ = c.shape
    for gx in range((x0//step+1)*step, x0 + w//s, step):
        X = (gx-x0)*s
        c[0:12, X:X+2, :] = (1,0,0,1)
        c[h-12:h, X:X+2, :] = (1,0,0,1)
    for gy in range((y0//step+1)*step, y0 + h//s, step):
        Y = (gy-y0)*s
        c[Y:Y+2, 0:12, :] = (0,1,0,1)
        c[Y:Y+2, w-12:w, :] = (0,1,0,1)
    return c
jobs = [
 ('p2r2', 'inputs/photo_2.jpg', (510,420,820,520), 4),
 ('p1r2', 'inputs/photo_1.jpg', (770,385,900,500), 6),
 ('p3w1', 'inputs/photo_3.jpg', (40,440,680,720), 2),
 ('p1ef', 'inputs/photo_1.jpg', (250,400,730,670), 2),
]
for (nm,pa,(x0,y0,x1,y1),s) in jobs:
    A = load(RUN+pa)
    c = A[y0:y1, x0:x1].copy()
    c = np.repeat(np.repeat(c, s, axis=0), s, axis=1)
    c[...,3]=1
    c = grid(c, x0, y0, s, 10)
    save(c, RUN+'crops/%s.png'%nm)
    print(nm, c.shape)
