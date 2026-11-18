src = open('/home/user/opus55poc/datacenter/runs/opus-5.5/easy/s2-r1/lib.py').read()
src = src[src.index('MATS = {}'):].replace('MATS = {}', 'MATS = {m.name: m for m in bpy.data.materials}', 1)
import bpy, math
from mathutils import Vector
exec(src)

EQB = bpy.data.objects['RackB_Equipment']
u0b = 0.06
# extra patch field: PP (U13), finger manager (U14-15), PP (U16)
pp = {}
for k in (12, 15):
    ob, xs, zc = equip('RackB_PatchPanel_U%02d' % (k + 1), k, 1, 'PP', EQB, u0b, -0.47)
    pp[k] = (xs, zc)
k, n = 13, 2
zb = u0b + k * U; zt = zb + n * U
g = Geo()
g.box(-0.2413, 0.2413, -0.478, -0.470, zb + 0.001, zt - 0.001, BLK)
for i in range(7):
    x = -0.225 + i * 0.075
    g.box(x - 0.006, x + 0.006, -0.5, -0.478, zb + 0.004, zt - 0.004, BLK)
g.box(-0.235, 0.235, -0.5, -0.478, zb + 0.001, zb + 0.004, BLK)
build(g, 'RackB_HorizCableManager_U%02d' % (k + 1), EQB, {'u_start': k + 1, 'u_size': n, 'part': 'horizontal_cable_management'})
zh = (zb + zt) / 2

g = Geo()
for k2, (xs, zc) in pp.items():
    for i, xp in enumerate(xs):
        if i % 3 == 1:
            continue
        side = -1 if xp < 0 else 1
        xt = side * 0.27
        dz = zh - zc
        g.tube([(xp, -0.479, zc), (xp, -0.487, zc), (xp + (xt - xp) * 0.15, -0.490, zc + dz * 0.7),
                (xp + (xt - xp) * 0.5, -0.490, zh), (side * 0.288, -0.485, zh + 0.02 * side)], 0.0022,
               CBL_AQUA if k2 == 12 else CBL_BLUE, n=5)
    g.tube([(0.0, -0.40, zc), (-0.05, -0.2, zc - 0.01), (-0.15, 0.3, zc - 0.03), (-0.17, 0.44, zc - 0.08)], 0.011, CBL_BLUE, n=8)
build(g, 'RackB_Cabling_Lower', bpy.data.objects['RackB'], {'part': 'cabling'})

for r in (bpy.data.objects['RackA'], bpy.data.objects['RackB']):
    print(r.name, 'tris', tri_count(r), 'bbox', bbox(r))
