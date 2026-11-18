src = open('/home/user/opus55poc/datacenter/runs/opus-5.5/easy/s2-r1/lib.py').read()
src = src[src.index('MATS = {}'):].replace('MATS = {}', 'MATS = {m.name: m for m in bpy.data.materials}', 1)
import bpy, math
from mathutils import Vector
exec(src)

RA = bpy.data.objects['RackA']
for nm in ('RackA_SidePanel_L', 'RackA_SidePanel_R', 'RackA_TopPanel'):
    ob = bpy.data.objects[nm]; me = ob.data
    bpy.data.objects.remove(ob, do_unlink=True); bpy.data.meshes.remove(me)

for sx, nm in ((-1, 'L'), (1, 'R')):
    g = Geo()
    x0, x1 = sorted((sx * 0.285, sx * 0.2995))
    g.box(x0, x1, -0.6, -0.002, 0.05, 1.98, PANEL)
    g.box(x0, x1, 0.002, 0.6, 0.05, 1.98, PANEL)
    for yc in (-0.3, 0.3):
        g.qx(yc - 0.02, yc + 0.02, 1.0, 1.06, sx * 0.2997, BLK, sx)
        g.qx(yc - 0.006, yc + 0.006, 1.04, 1.052, sx * 0.2999, SILV, sx)
    build(g, 'RackA_SidePanel_' + nm, RA, {'part': 'side_panel_solid'})

g = Geo()
z0, z1 = 1.98, 2.0
for ya, yb in ((-0.6, -0.45), (-0.33, 0.33), (0.45, 0.6)):
    g.box(-0.3, 0.3, ya, yb, z0, z1, PANEL)
for ya, yb in ((-0.45, -0.33), (0.33, 0.45)):
    g.box(-0.3, -0.2, ya, yb, z0, z1, PANEL)
    g.box(0.2, 0.3, ya, yb, z0, z1, PANEL)
    g.box(-0.2, 0.2, ya, (ya + yb) / 2 - 0.006, 1.972, 1.978, RUB)
    g.box(-0.2, 0.2, (ya + yb) / 2 + 0.006, yb, 1.972, 1.978, RUB)
# raised lip around the openings (cable entry frame)
for ya, yb in ((-0.45, -0.33), (0.33, 0.45)):
    g.box(-0.2, 0.2, ya, ya + 0.004, 1.968, 1.98, BLK)
    g.box(-0.2, 0.2, yb - 0.004, yb, 1.968, 1.98, BLK)
# two round knock-out openings (dark interior seen through)
for sy in (-1, 1):
    g.cyl((0.0, sy * 0.15, 1.9999), 0.03, 0.0002, HOLE, n=16)
build(g, 'RackA_TopPanel', RA, {'part': 'top_panel_cable_entry'})

for r in (bpy.data.objects['RackA'], bpy.data.objects['RackB']):
    print(r.name, 'tris', tri_count(r), 'bbox', bbox(r))
print(len(bpy.data.materials), 'materials')
