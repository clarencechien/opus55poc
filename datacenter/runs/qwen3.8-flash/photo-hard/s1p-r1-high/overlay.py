import bpy, numpy as np, os

W, H = 1280, 960

def cam_basis(name):
    M = bpy.data.objects[name].matrix_world
    R = np.array([[M[a][b] for b in range(3)] for a in range(3)])
    p = np.array([M[0][3], M[1][3], M[2][3]])
    fwd = -(R @ np.array([0, 0, 1.0])); right = R @ np.array([1, 0, 0.0]); up = R @ np.array([0, 1, 0.0])
    return p, fwd / np.linalg.norm(fwd), right / np.linalg.norm(right), up / np.linalg.norm(up)

cam = bpy.data.cameras['Cam_1']
fl, sw = cam.lens, cam.sensor_width
print('lens', fl, 'sensor', sw, 'fit', cam.sensor_fit)
FX = fl / sw * W

def proj(cn, q):
    p, fwd, right, up = cam_basis(cn)
    v = np.array(q, float) - p
    x = v.dot(right); y = v.dot(up); z = v.dot(fwd)
    if z <= 1e-6: return None
    return np.array([W / 2.0 + x / z * FX, H / 2.0 - y / z * FX])

def draw_overlay(cn, idx):
    img = bpy.data.images.load(os.path.abspath('inputs/photo_%d.jpg' % idx), check_existing=True)
    arr = np.array(img.pixels[:], dtype=np.float32).reshape(H, W, 4).copy()
    def seg(a, b, col, steps=600):
        pa, pb = proj(cn, a), proj(cn, b)
        if pa is None or pb is None: return
        for t in np.linspace(0, 1, steps):
            u, v = pa + (pb - pa) * t
            uu, vv = int(u), int(v)
            if 0 <= uu < W and 0 <= vv < H:
                arr[H - 1 - vv, uu] = col
    for x in np.arange(0, 24.01, 1.2):
        seg((x, 0, 0.6), (x, 18, 0.6), (1, 0, 0, 1))
    for y in np.arange(0, 18.01, 1.2):
        seg((0, y, 0.6), (24, y, 0.6), (0, 1, 0, 1))
    for x in np.arange(0, 24.01, 2.4):
        seg((x, 0, 2.0), (x, 18, 2.0), (0, 0, 1, 1))
    old = bpy.data.images.get('ov%d' % idx)
    if old: bpy.data.images.remove(old)
    im = bpy.data.images.new('ov%d' % idx, W, H, alpha=True)
    im.pixels = arr.reshape(-1).tolist()
    im.filepath_raw = os.path.abspath('out/overlay%d.png' % idx)
    im.file_format = 'PNG'
    im.save()
    print('wrote out/overlay%d.png' % idx)

for idx in [2, 3]:
    draw_overlay('Cam_%d' % idx, idx)
print('done')
