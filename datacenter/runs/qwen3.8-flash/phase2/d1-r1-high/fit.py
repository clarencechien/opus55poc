import bpy, json, math, os, numpy as np, bmesh
from mathutils import Vector, Matrix

design = json.load(open('inputs/design.json'))
items = list(design['racks']) + list(design['crah'])
scene = bpy.context.scene

# --- collision boxes for all design items (footprint extruded) ---
for o in [o for o in bpy.data.objects if o.name.startswith('B_')]:
    bpy.data.objects.remove(o, do_unlink=True)
bm = bmesh.new()
me = bpy.data.meshes.new('unit')
bmesh.ops.create_cube(bm, size=1.0)
bm.to_mesh(me); bm.free()
boxes = {}
for it in items:
    ob = bpy.data.objects.new('B_' + it['id'], me)
    scene.collection.objects.link(ob)
    w, d = it['size'][0]/1000.0, it['size'][1]/1000.0
    ob.scale = (w, d, 2.0)
    ob.location = (it['center'][0]/1000.0, it['center'][1]/1000.0, 0.6 + 1.0)
    boxes[it['id']] = ob
deps = bpy.context.evaluated_depsgraph_get()

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

FD = {'S': (0.0, -1.0, 0.0), 'N': (0.0, 1.0, math.pi), 'E': (1.0, 0.0, math.pi/2), 'W': (-1.0, 0.0, -math.pi/2)}
LEDZ = 2.32
cams = json.load(open('inputs/cameras.json'))['cameras']
masks = {}
for cam in cams:
    n = int(cam['photo'].split('_')[1].split('.')[0])
    a = load('inputs/photo_%d.jpg' % n)
    m = (a[:, :, 2] - (a[:, :, 0]+a[:, :, 1])/2) > 0.06
    masks[n] = (dil(m, 3), m, cam)

res = {}
for it in items:
    if it['id'].startswith('CRAH'):
        continue
    w = it['size'][0]/1000.0; d = it['size'][1]/1000.0
    cx = it['center'][0]/1000.0; cy = it['center'][1]/1000.0
    row = []
    for f in ('N', 'S', 'E', 'W'):
        nx, ny, rot = FD[f]
        half = 0.5*w*0.85
        tx, ty = -ny, nx
        c = Vector((cx + nx*(d/2 + 0.02), cy + ny*(d/2 + 0.02), LEDZ))
        p0 = c + Vector((tx*half, ty*half, 0)); p1 = c - Vector((tx*half, ty*half, 0))
        tot_v = 0; tot_m = 0
        for n, (dm, raw, cam) in masks.items():
            co = bpy.data.objects[cam['camera_object']]
            fx = cam['lens_mm']/cam['sensor_width_mm']*cam['resolution'][0]
            W, H = cam['resolution']
            inv = co.matrix_world.inverted(); origin = co.matrix_world.translation
            nrm = Vector((nx, ny, 0))
            nvis = 0; nmatch = 0
            for s in range(13):
                t = s/12.0
                p = p0.lerp(p1, t)
                viewv = (p - origin)
                if viewv.dot(nrm) >= 0:      # back-facing
                    continue
                hit, loc, nlo, idx, ob, mat = scene.ray_cast(deps, origin, viewv.normalized())
                if hit and ob.name != 'B_' + it['id'] and ob.name.startswith('B_'):
                    continue
                v = inv @ p
                if v.z >= -0.01:
                    continue
                u = W/2 + v.x*fx/(-v.z); vv = H/2 - v.y*fx/(-v.z)
                if not (0 <= u < W and 0 <= vv < H):
                    continue
                nvis += 1
                if dm[int(round(vv)), int(round(u))]:
                    nmatch += 1
            tot_v += nvis; tot_m += nmatch
        row.append((f, tot_m, tot_v))
    res[it['id']] = row
    best = max(row, key=lambda r: (r[1]/max(1, r[2]), r[1]))
    cur = it['facing']
    curo = [r for r in row if r[0] == cur][0]
    flag = '' if best[0] == cur else '  <<< BEST ' + best[0]
    print('%-6s design=%s %s  %s%s' % (it['id'], cur,
          ' '.join('%s:%d/%d' % (f, m, v) for f, m, v in row),
          'OK' if curo[1] >= 0.8*max(1, curo[2]) else 'LOW', flag))
print('DONE')
