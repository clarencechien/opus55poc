import bpy, json, math, os, numpy as np
from mathutils import Vector, Matrix

for o in [o for o in bpy.data.objects if o.name.startswith('P_') or o.name.startswith('B_')]:
    bpy.data.objects.remove(o, do_unlink=True)

design = json.load(open('inputs/design.json'))
items = list(design['racks']) + list(design['crah'])
racks = [it for it in items if not it['id'].startswith('CRAH')]
boxes = [(it['id'], it['center'][0]/1000.0, it['center'][1]/1000.0,
          it['size'][0]/2000.0, it['size'][1]/2000.0) for it in items]
Z0, Z1 = 0.6, 2.6

def occluded(ox, oy, oz, px, py, pz, skip):
    dx, dy, dz = px-ox, py-oy, pz-oz
    for bid, bx, by, hw, hd in boxes:
        if bid == skip:
            continue
        lo_x, hi_x = bx-hw-ox, bx+hw-ox
        lo_y, hi_y = by-hd-oy, by+hd-oy
        lo_z, hi_z = Z0-oz, Z1-oz
        tmin, tmax = 0.0, 1.0
        for lo, hi, dd in ((lo_x, hi_x, dx), (lo_y, hi_y, dy), (lo_z, hi_z, dz)):
            if abs(dd) < 1e-12:
                if lo > 0 or hi < 0:
                    tmin = 2.0
                    break
            else:
                t1 = lo/dd; t2 = hi/dd
                if t1 > t2:
                    t1, t2 = t2, t1
                if t1 > tmin: tmin = t1
                if t2 < tmax: tmax = t2
                if tmin > tmax:
                    break
        if tmin <= tmax and tmin > 0.001 and tmin < 1.0:
            return True
    return False

def load(p):
    img = bpy.data.images.load(p, check_existing=False)
    w, h = img.size[0], img.size[1]
    buf = np.empty(w*h*4, dtype=np.float32)
    img.pixels.foreach_get(buf)
    a = buf.reshape(h, w, 4)[:, :, :3].copy()
    bpy.data.images.remove(img)
    return a

def dil(m, it):
    o = m.copy()
    for _ in range(it):
        n = o.copy()
        n[1:, :] |= o[:-1, :]; n[:-1, :] |= o[1:, :]
        n[:, 1:] |= o[:, :-1]; n[:, :-1] |= o[:, 1:]
        o = n
    return o

FD = {'S': (0.0, -1.0), 'N': (0.0, 1.0), 'E': (1.0, 0.0), 'W': (-1.0, 0.0)}
LEDZ = 2.32
cams = json.load(open('inputs/cameras.json'))['cameras']
CD = []
for cam in cams:
    n = int(cam['photo'].split('_')[1].split('.')[0])
    a = load('inputs/photo_%d.jpg' % n)
    m = (a[:, :, 2] - (a[:, :, 0]+a[:, :, 1])/2) > 0.06
    CD.append((n, dil(m, 3), cam, Vector((cam['position_m'][0], cam['position_m'][1], cam['position_m'][2])),
               bpy.data.objects[cam['camera_object']].matrix_world))

print('%-6s %-4s %s' % ('id', 'des', 'facing: matched/visible (all cams)'))
for it in racks:
    w = it['size'][0]/1000.0; d = it['size'][1]/1000.0
    cx = it['center'][0]/1000.0; cy = it['center'][1]/1000.0
    out = []
    for f in ('N', 'S', 'E', 'W'):
        nx, ny = FD[f]
        tx, ty = -ny, nx
        half = 0.5*w*0.85
        c = Vector((cx + nx*(d/2 + 0.02), cy + ny*(d/2 + 0.02), LEDZ))
        p0 = c + Vector((tx*half, ty*half, 0)); p1 = c - Vector((tx*half, ty*half, 0))
        tot_v = 0; tot_m = 0
        for n, dm, cam, C, M in CD:
            fx = cam['lens_mm']/cam['sensor_width_mm']*cam['resolution'][0]
            W, H = cam['resolution']
            inv = M.inverted()
            nrm = Vector((nx, ny, 0))
            for s in range(7):
                p = p0.lerp(p1, s/6.0)
                vv = p - C
                if vv.dot(nrm) >= 0:
                    continue
                if occluded(C.x, C.y, C.z, p.x, p.y, p.z, it['id']):
                    continue
                q = inv @ p
                if q.z >= -0.01:
                    continue
                u = W/2 + q.x*fx/(-q.z); v = H/2 - q.y*fx/(-q.z)
                if not (0 <= u < W and 0 <= v < H):
                    continue
                tot_v += 1
                if dm[H-1-int(round(v)), int(round(u))]:
                    tot_m += 1
        out.append((f, tot_m, tot_v))
    cur = it['facing']
    curo = [o for o in out if o[0] == cur][0]
    best = max(out, key=lambda o: (o[1]/max(1, o[2]), o[1]))
    tag = 'OK' if curo[2] == 0 or curo[1]/curo[2] >= 0.75 else ('LOW' if curo[1] == 0 else 'part')
    flag = '' if best[0] == cur or best[2] == 0 or best[1] == 0 else '   <<< ' + best[0] + ' (%d/%d)' % (best[1], best[2])
    print('%-6s %-4s %s   [%s]%s' % (it['id'], cur, ' '.join('%s:%d/%d' % o for o in out), tag, flag))
print('DONE')
