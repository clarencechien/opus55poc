import bpy, json, math, os, numpy as np
from mathutils import Vector, Matrix

design = json.load(open('inputs/design.json'))
FACING = {'S': (0, -1), 'N': (0, 1), 'E': (1, 0), 'W': (-1, 0)}
scene = bpy.context.scene

# LED height from template
src = bpy.data.objects['RackA']
mn = [1e9]*3; mx = [-1e9]*3
for ob in [src] + list(src.children_recursive):
    if 'FrontLED' in ob.name:
        for c in ob.bound_box:
            w = ob.matrix_world @ Vector(c)
            for i in range(3):
                mn[i] = min(mn[i], w[i]); mx[i] = max(mx[i], w[i])
LEDZ = (mn[2]+mx[2])/2 + 0.6
print('LED z (world, floor at 0.6):', LEDZ, mn[2], mx[2])

def load_arr(src_):
    img = bpy.data.images.load(src_, check_existing=False)
    w, h = img.size[0], img.size[1]
    buf = np.empty(w*h*4, dtype=np.float32)
    img.pixels.foreach_get(buf)
    arr = buf.reshape(h, w, 4)[:, :, :3].copy()
    bpy.data.images.remove(img)
    return arr

def components(mask, minpix=4, link=2):
    ys, xs = np.where(mask)
    pix = set(zip(ys.tolist(), xs.tolist()))
    comps = []
    while pix:
        y0, x0 = pix.pop()
        stack = [(y0, x0)]; comp = [(y0, x0)]
        while stack:
            y, x = stack.pop()
            for dy in range(-link, link+1):
                for dx in range(-link, link+1):
                    p = (y+dy, x+dx)
                    if p in pix:
                        pix.remove(p); comp.append(p); stack.append(p)
        if len(comp) >= minpix:
            comps.append((np.array([p[0] for p in comp]), np.array([p[1] for p in comp])))
    return comps

cams = json.load(open('inputs/cameras.json'))['cameras']
meas = {}
for cam in cams:
    n = int(cam['photo'].split('_')[1].split('.')[0])
    co = bpy.data.objects[cam['camera_object']]
    fx = cam['lens_mm']/cam['sensor_width_mm']*cam['resolution'][0]
    W, H = cam['resolution']
    arr = load_arr('inputs/photo_%d.jpg' % n)
    mask = (arr[:, :, 2] - (arr[:, :, 0]+arr[:, :, 1])/2) > 0.10
    comps = components(mask)
    inv = co.matrix_world.inverted()
    camloc = co.matrix_world.translation
    pts = []
    for ys, xs in comps:
        # use several pixels of the component: intersect each ray with z=LEDZ, take median
        rl = inv @ Vector((0, 0, -fx))     # camera forward direction in world
        cand = []
        for i in range(len(xs)):
            u = xs[i]; v = H - ys[i]
            # view-space direction for pixel (u,v)
            vx = (u - W/2)/fx
            vy = -(v - H/2)/fx
            d = (co.matrix_world.to_3x3() @ Vector((vx, vy, -1))).normalized()
            o = camloc
            if abs(d.z) < 1e-6:
                continue
            t = (LEDZ - o.z)/d.z
            if t <= 0:
                continue
            p = o + d*t
            cand.append((p.x*1000, p.y*1000))
        if not cand:
            continue
        cand = np.array(cand)
        pts.append((np.median(cand[:, 0]), np.median(cand[:, 1]), len(cand),
                    xs.min(), xs.max(), H-ys.max(), H-ys.min()))
    pts.sort(key=lambda t: (t[1], t[0]))
    meas[n] = pts
    print('--- cam %d: %d strips' % (n, len(pts)))
    for p in pts:
        print('    plan x=%7.0f y=%7.0f  npix=%4d  u=[%d,%d] v=[%d,%d]' % p)
json.dump({str(k): [[round(a), round(b), c] for a, b, c, *_ in v] for k, v in meas.items()},
          open('measure.json', 'w'), indent=1)
print('DONE')
