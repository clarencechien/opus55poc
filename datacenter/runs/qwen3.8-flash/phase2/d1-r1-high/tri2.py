import bpy, json, math, os, numpy as np
from mathutils import Vector

scene = bpy.context.scene
LEDZ = 2.32

def load_arr(p):
    img = bpy.data.images.load(p, check_existing=False)
    w, h = img.size[0], img.size[1]
    buf = np.empty(w*h*4, dtype=np.float32)
    img.pixels.foreach_get(buf)
    arr = buf.reshape(h, w, 4)[:, :, :3].copy()
    bpy.data.images.remove(img)
    return arr

cams = json.load(open('inputs/cameras.json'))['cameras']
out = {}
for cam in cams:
    n = int(cam['photo'].split('_')[1].split('.')[0])
    co = bpy.data.objects[cam['camera_object']]
    fx = cam['lens_mm']/cam['sensor_width_mm']*cam['resolution'][0]
    W, H = cam['resolution']
    arr = load_arr('inputs/photo_%d.jpg' % n)
    bl = arr[:, :, 2] - (arr[:, :, 0]+arr[:, :, 1])/2
    mask = bl > 0.10
    camloc = co.matrix_world.translation
    cols = []
    for u in range(W):
        ys = np.where(mask[:, u])[0]
        if len(ys) == 0:
            continue
        wts = bl[ys, u]
        v = H - (ys*wts).sum()/wts.sum()
        vx = (u - W/2)/fx
        vy = -(v - H/2)/fx
        d = (co.matrix_world.to_3x3() @ Vector((vx, vy, -1))).normalized()
        if abs(d.z) < 1e-6:
            continue
        t = (LEDZ - camloc.z)/d.z
        p = camloc + d*t
        cols.append((u, p.x*1000, p.y*1000, len(ys)))
    groups = []
    cur = []
    for c in cols:
        if cur:
            dx = c[1]-cur[-1][1]; dy = c[2]-cur[-1][2]
            if abs(dx) > 200 or abs(dy) > 200 or c[0]-cur[-1][0] > 6:
                groups.append(cur); cur = []
        cur.append(c)
    if cur:
        groups.append(cur)
    print('=== cam %d' % n)
    recs = []
    for g in groups:
        if len(g) < 3:
            continue
        xs = [p[1] for p in g]; ys = [p[2] for p in g]
        recs.append((xs[0], ys[0], xs[-1], ys[-1], g[0][0], g[-1][0], len(g)))
    for x0, y0, x1, y1, u0, u1, nc in recs:
        L = math.hypot(x1-x0, y1-y0)
        ang = math.degrees(math.atan2(y1-y0, x1-x0)) % 180
        print('   seg (%7.0f,%7.0f)->(%7.0f,%7.0f) len=%5.0f ang=%3.0f u=[%d,%d] cols=%d' % (x0, y0, x1, y1, L, ang, u0, u1, nc))
    out[n] = recs
json.dump({str(k): v for k, v in out.items()}, open('segs.json', 'w'), indent=1)
print('DONE')
