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
FX = fl / sw * W

def proj(cn, q):
    p, fwd, right, up = cam_basis(cn)
    v = np.array(q, float) - p
    x = v.dot(right); y = v.dot(up); z = v.dot(fwd)
    if z <= 1e-6: return None
    return np.array([W / 2.0 + x / z * FX, H / 2.0 - y / z * FX])

def draw(cn, idx):
    img = bpy.data.images.load(os.path.abspath('inputs/photo_%d.jpg' % idx), check_existing=True)
    arr = np.array(img.pixels[:], dtype=np.float32).reshape(H, W, 4).copy()
    def seg(a, b, col, steps=800):
        pa, pb = proj(cn, a), proj(cn, b)
        if pa is None or pb is None: return
        for t in np.linspace(0, 1, steps):
            u, v = pa + (pb - pa) * t
            uu, vv = int(u), int(v)
            if 0 <= uu < W and 0 <= vv < H:
                arr[H - 1 - vv, uu] = col
    cols = [(6, 6), (12, 6), (18, 6), (6, 12), (12, 12)]
    for cx, cy in cols:
        for dx in (-0.3, 0.3):
            for dy in (-0.3, 0.3):
                seg((cx + dx, cy + dy, 0.6), (cx + dx, cy + dy, 3.6), (1, 1, 0, 1))
        seg((cx - .3, cy - .3, 3.6), (cx + .3, cy - .3, 3.6), (1, 1, 0, 1))
        seg((cx - .3, cy + .3, 3.6), (cx + .3, cy + .3, 3.6), (1, 1, 0, 1))
    # wall corners / hall boundary at z=0.6 and ceiling
    for (a, b) in [((0.1, 0.1), (23.9, 0.1)), ((23.9, 0.1), (23.9, 17.9)), ((23.9, 17.9), (0.1, 17.9)), ((0.1, 17.9), (0.1, 0.1))]:
        seg((a[0], a[1], 0.6), (b[0], b[1], 0.6), (1, 0, 1, 1))
    # UPS room walls
    for (a, b) in [((18.0, 12.0), (18.0, 17.9)), ((18.0, 12.0), (23.9, 12.0))]:
        seg((a[0], a[1], 0.6), (b[0], b[1], 0.6), (0, 1, 1, 1))
    old = bpy.data.images.get('cv%d' % idx)
    if old: bpy.data.images.remove(old)
    im = bpy.data.images.new('cv%d' % idx, W, H, alpha=True)
    im.pixels = arr.reshape(-1).tolist()
    im.filepath_raw = os.path.abspath('out/cols%d.png' % idx); im.file_format = 'PNG'; im.save()
    print('wrote out/cols%d.png' % idx)

for idx in [2, 3]:
    draw('Cam_%d' % idx, idx)
