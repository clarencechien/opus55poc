import os, sys
sys.path.insert(0, os.getcwd())
import bpy, math, random, importlib
import rl
rl = importlib.reload(rl)
from rl import box, boxes, cyl, tube, perf_xz, perf_yz, cable, mats

M = mats()
scene = bpy.context.scene

for o in list(bpy.data.objects):
    if o.name.startswith("RackA"):
        bpy.data.objects.remove(o, do_unlink=True)

root = bpy.data.objects.new("RackA", None)
scene.collection.objects.link(root)
root.location = (0, 0, 0)

X0, X1 = -0.30, 0.30
Y0, Y1 = -0.60, 0.60
ZB = 0.10                     # body bottom (above the feet)

# ---------------------------------------------------------------- leveling feet
fitems = []
for fx in (-0.25, 0.0, 0.25):
    for fy in (-0.50, 0.50):
        fitems.append((fx, fy, 0.004, 0.07, 0.07, 0.008))     # foot pad
        fitems.append((fx, fy, 0.030, 0.024, 0.024, 0.044))   # leveling stem
boxes("RackA_Feet", root, fitems, M['metalg'])
for fx in (-0.25, 0.0, 0.25):
    for fy in (-0.50, 0.50):
        cyl("RackA_Feet_Nut", root, (fx, fy, 0.048), 0.016, 0.010, M['frame'], 'Z', 12)

# ---------------------------------------------------------------- base + sides
box("RackA_Base", root, (0, 0, 0.075), (0.58, 1.18, 0.05), M['frame'])
for s in (-1, 1):
    box("RackA_SidePanel_%s" % ('L' if s < 0 else 'R'), root,
        (s*0.294, 0, (ZB + 1.99)/2), (0.012, 1.20, 1.99 - ZB), M['panel'])
box("RackA_FloorTray", root, (0, 0, 0.105), (0.576, 1.16, 0.010), M['frame'])

# ---------------------------------------------------------------- top panel with cable entries
ZT0, ZT1 = 1.99, 2.00
op_x = [(-0.225, -0.025), (0.025, 0.225)]
op_y = (-0.30, 0.30)
zc = (ZT0 + ZT1) / 2
box("RackA_TopPanel_F", root, (0, (Y0+op_y[0])/2, zc), ((X1-X0), op_y[0]-Y0, ZT1-ZT0), M['panel'])
box("RackA_TopPanel_B", root, (0, (op_y[1]+Y1)/2, zc), ((X1-X0), Y1-op_y[1], ZT1-ZT0), M['panel'])
box("RackA_TopPanel_L", root, ((X0+op_x[0][0])/2, 0, zc), (op_x[0][0]-X0, op_y[1]-op_y[0], ZT1-ZT0), M['panel'])
box("RackA_TopPanel_R", root, ((X1+op_x[1][1])/2, 0, zc), (X1-op_x[1][1], op_y[1]-op_y[0], ZT1-ZT0), M['panel'])
box("RackA_TopPanel_M", root, (0, 0, zc), (op_x[1][0]-op_x[0][1], op_y[1]-op_y[0], ZT1-ZT0), M['panel'])
for i, (a, b) in enumerate(op_x):        # brush grommets (dark bristle membrane + lip)
    box("RackA_Grommet_%d" % i, root, ((a+b)/2, 0, 1.984), (b-a, op_y[1]-op_y[0], 0.008), M['brush'])
    tube("RackA_GrommetLip_%d" % i, root, ((a+b)/2, 0, 1.9965),
         (b-a), (op_y[1]-op_y[0]), 0.007, 0.008, M['frame'])

# ---------------------------------------------------------------- front / rear face frames
def face_frame(tag, yc, t):
    zA, zB = ZB, 1.99
    b = 0.030
    items = [
        (0, yc, zA + b/2, (X1-X0), t, b),
        (0, yc, zB - b/2, (X1-X0), t, b),
        (X0 + b/2, yc, (zA+zB)/2, b, t, (zB-zA) - 2*b),
        (X1 - b/2, yc, (zA+zB)/2, b, t, (zB-zA) - 2*b),
    ]
    return boxes(tag, root, items, M['frame'])
face_frame("RackA_FrontFrame", -0.5925, 0.015)
face_frame("RackA_RearFrame",   0.5925, 0.015)

# ---------------------------------------------------------------- perforated doors
def door(name, yc, facing):
    dx0, dx1 = -0.270, 0.270
    dz0, dz1 = 0.130, 1.960
    d = perf_xz(name, root, dx0, dx1, dz0, dz1, yc, 0.018, 0.018, 0.005,
                M['door'], frame_w=0.030)
    o = lambda v: yc + facing * v          # v>0 = towards the outside of the rack
    boxes(name + "_Handle", d, [
        (0.235, o(0.012), 1.05, 0.030, 0.024, 0.24),
        (0.235, o(0.004), 0.92, 0.022, 0.012, 0.03),
        (0.235, o(0.004), 1.18, 0.022, 0.012, 0.03),
        (0.235, o(0.006), 0.80, 0.026, 0.016, 0.05),
    ], M['panel'])
    hinges = [(-0.278, o(0.004), z, 0.020, 0.014, 0.07) for z in (0.25, 1.00, 1.85)]
    boxes(name + "_Hinges", d, hinges, M['metalg'])
    return d

door("RackA_FrontDoor", -0.576, -1)
door("RackA_RearDoor",   0.576,  1)

# ---------------------------------------------------------------- 19" mounting rails
UH, Z0U = 0.04445, 0.150
RAIL_Z0, RAIL_Z1 = 0.13, 1.96
for sx in (-1, 1):
    xr = sx * 0.2405
    tube("RackA_Rail_F_%d" % sx, root, (xr, -0.454, (RAIL_Z0+RAIL_Z1)/2),
         0.026, 0.048, RAIL_Z1-RAIL_Z0, 0.006, M['rail'])
    perf_xz("RackA_RailPlate_F_%d" % sx, root, xr-0.012, xr+0.012,
            RAIL_Z0, RAIL_Z1, -0.481, 0.004, 0.0159, 0.006, M['rail'])
    tube("RackA_Rail_R_%d" % sx, root, (xr, 0.454, (RAIL_Z0+RAIL_Z1)/2),
         0.026, 0.048, RAIL_Z1-RAIL_Z0, 0.006, M['rail'])
    rp = perf_xz("tmp", root, xr-0.012, xr+0.012,
                 RAIL_Z0, RAIL_Z1, 0.427, 0.004, 0.0318, 0.008, M['rail'])
    rp.name = "RackA_RailPlate_R_%d" % sx
    for z in (0.16, 1.93):
        box("RackA_RailBracket_%d_%s" % (sx, z), root, (xr, 0, z), (0.020, 0.88, 0.012), M['rail'])

# ---------------------------------------------------------------- servers + blanking panels
POP = [
    (1, 1, 'srv'), (2, 1, 'srv'), (3, 1, 'blk'), (4, 2, 'srv'),
    (6, 1, 'srv'), (7, 1, 'blk'), (8, 4, 'srv'), (12, 1, 'srv'),
    (13, 2, 'srv'), (15, 1, 'blk'), (16, 4, 'srv'), (20, 1, 'srv'),
    (21, 1, 'srv'), (22, 1, 'blk'), (23, 2, 'srv'), (25, 1, 'srv'),
    (26, 2, 'srv'), (28, 1, 'blk'), (29, 4, 'srv'), (33, 1, 'srv'),
    (34, 1, 'blk'), (35, 2, 'srv'), (37, 1, 'srv'), (38, 1, 'srv'),
    (39, 1, 'blk'), (40, 1, 'srv'),
]
led_cols = [M['led_g'], M['led_g'], M['led_b']]
for (u, nu, kind) in POP:
    zb = Z0U + (u - 1) * UH
    h = nu * UH
    if kind == 'blk':
        box("RackA_Blank_U%d" % u, root, (0, -0.474, zb + h/2), (0.4826, 0.008, h - 0.003), M['blank'])
        continue
    tag = "RackA_Server_U%d_%dU" % (u, nu)
    box(tag + "_Bezel", root, (0, -0.470, zb + h/2), (0.4826, 0.016, h - 0.004), M['bezel'])
    box(tag + "_Body",  root, (0, -0.06, zb + h/2), (0.455, 0.80, h - 0.008), M['server'])
    box(tag + "_Rear",  root, (0, 0.345, zb + h/2), (0.455, 0.012, h - 0.010), M['panel'])
    li = [(-0.05, -0.4785, zb + h * (0.30 + 0.4 * (k / max(1, nu))), 0.30, 0.004, 0.004)
          for k in range(max(1, nu))]
    boxes(tag + "_Trim", root, li, M['panel'])
    for k in range(3):
        box(tag + "_LED%d" % k, root, (0.185 - 0.012 * k, -0.4795, zb + h/2 + (0.004 if k == 0 else -0.004)),
            (0.006, 0.004, 0.004), led_cols[k])
    for sx in (-1, 1):
        box(tag + "_Ear%d" % sx, root, (sx*0.238, -0.479, zb + h/2), (0.008, 0.006, h - 0.006), M['metalg'])

# ---------------------------------------------------------------- rear PDU + cabling
box("RackA_PDU", root, (0.258, 0.50, 0.95), (0.045, 0.045, 1.50), M['panel'])
boxes("RackA_PDU_Outlets", root,
      [(0.258, 0.476, 0.32 + i * 0.17, 0.030, 0.008, 0.045) for i in range(8)], M['metalg'])
box("RackA_PDU_Cord", root, (0.258, 0.56, 1.72), (0.020, 0.06, 0.02), M['cbl_k'])
for i, u in enumerate([2, 8, 13, 20, 29, 35, 40]):
    zb = Z0U + (u - 1) * UH + 0.022
    pts = [(0.10 - 0.03 * (i % 4), 0.352, zb),
           (0.14 - 0.03 * (i % 4), 0.42, zb - 0.01),
           (0.21, 0.48, zb - 0.06 - 0.01 * (i % 3)),
           (0.258, 0.470, 0.30 + (i + 1) * 0.17)]
    cable("RackA_PowerCord_%d" % i, root, pts, 0.007, M['cbl_k'], res_u=6, bev_res=1)
for i in range(5):
    x = -0.18 + 0.05 * i
    pts = [(x, 0.30, 1.90), (x + 0.02, 0.42, 1.94), (x, 0.18, 1.985), (x - 0.02, -0.05, 1.993)]
    cable("RackA_TopCable_%d" % i, root, pts, 0.009,
          M['cbl_b'] if i % 2 else M['cbl_g'], res_u=6, bev_res=1)

rl.report(root)
print("RackA objects:", len([o for o in bpy.data.objects if o.name.startswith("RackA")]))
