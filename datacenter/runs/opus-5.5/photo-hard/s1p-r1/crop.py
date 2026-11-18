import bpy, numpy as np, os
RUN = '/home/user/opus55poc/datacenter/runs/opus-5.5/photo-hard/s1p-r1/'
os.makedirs(RUN+'crops', exist_ok=True)
def load(path):
    im = bpy.data.images.load(path, check_existing=False)
    w,h = im.size
    a = np.empty(w*h*4, dtype=np.float32)
    im.pixels.foreach_get(a)
    a = a.reshape(h,w,4)[::-1]  # top-left origin
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
jobs = [
 ('c1', 'inputs/photo_1.jpg', 'renders/008_cam_0_450_0_450_3_250_10_800_7_200_0_900.png', (150,380,500,480), 3),
 ('c1b','inputs/photo_1.jpg', 'renders/008_cam_0_450_0_450_3_250_10_800_7_200_0_900.png', (760,380,1000,510), 3),
 ('c4', 'inputs/photo_4.jpg', 'renders/005_cam_23_550_11_550_3_250_7_200_5_400_0_90.png', (0,420,360,480), 3),
 ('c4b','inputs/photo_4.jpg', 'renders/005_cam_23_550_11_550_3_250_7_200_5_400_0_90.png', (590,400,800,540), 3),
 ('c5', 'inputs/photo_5.jpg', 'renders/007_cam_17_550_17_550_3_250_6_000_8_100_0_90.png', (380,395,740,540), 3),
 ('c2', 'inputs/photo_2.jpg', 'renders/002_cam_23_550_0_450_3_250_9_600_8_100_0_900.png', (470,395,800,470), 3),
]
for (nm,pa,pb,(x0,y0,x1,y1),s) in jobs:
    A = load(RUN+pa); B = load(RUN+pb)
    ca = A[y0:y1, x0:x1]; cb = B[y0:y1, x0:x1]
    sep = np.ones((4, x1-x0, 4), dtype=np.float32); sep[...,0]=1; sep[...,1]=0; sep[...,2]=0
    comp = np.concatenate([ca, sep, cb], axis=0)
    comp = np.repeat(np.repeat(comp, s, axis=0), s, axis=1)
    comp[...,3] = 1.0
    save(comp, RUN+'crops/%s.png'%nm)
    print('saved', nm, comp.shape)
