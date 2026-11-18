import os, sys
sys.path.insert(0, os.getcwd())
import bpy, math, random, importlib
import rl
rl = importlib.reload(rl)
from rl import box, boxes, cyl, tube, perf_xz, cable, mats, _cube, _from_bm

M = mats()
scene = bpy.context.scene

for o in list(bpy.data.objects):
    if o.name.startswith("RackB"):
        bpy.data.objects.remove(o, do_unlink=True)

root = bpy.data.objects.new("RackB", None)
scene.collection.objects.link(root)
root.location = (1.5, 0, 0)          # footprint centred at x=1.5, y=0

# local extents: x -0.30..0.30, y -0.50..0.50, z 0..2.0   (front faces -y)
UH, Z0U = 0.04445, 0.15
PX, PY = 0.275, 0.475

# ---------------------------------------------------------------- base flanges (floor plates)
fl = []
for sx in (-1, 1):
    for sy in (-1, 1):
        fl.append((sx*PX, sy*PY, 0.006, 0.05, 0.05, 0.012))
        fl.append((sx*PX, sy*PY, 0.022, 0.04, 0.04, 0.020))
boxes("RackB_BasePlates", root, fl, M['panel'])

# ---------------------------------------------------------------- four posts
def post(idx, sx, sy):
    cx, cy = sx*PX, sy*PY
    p = box("RackB_Post_%d" % idx, root, (cx, cy, 1.00), (0.050, 0.035, 1.90), M['frame'])
    perf_xz("RackB_Post_%d_MountPlate" % idx, p, cx-0.022, cx+0.022, 0.06, 1.94,
            cy-0.020, 0.005, 0.0159, 0.006, M['rail'])
    perf_xz("RackB_Post_%d_RearPlate" % idx, p, cx-0.020, cx+0.020, 0.06, 1.94,
            cy+0.020, 0.005, 0.0445, 0.010, M['rail'])
    box("RackB_Post_%d_Cap" % idx, p, (cx, cy, 1.948), (0.052, 0.037, 0.006), M['frame'])
    return p

post(1, -1, -1)   # front-left
post(2,  1, -1)   # front-right
post(3, -1,  1)   # rear-left
post(4,  1,  1)   # rear-right

# ---------------------------------------------------------------- top / bottom frame members
for zc, tag in ((0.030, 'Btm'), (1.970, 'Top')):
    for sy in (-1, 1):
        box("RackB_Frame_%s_X%d" % (tag, sy), root, (0, sy*PY, zc), (0.60, 0.05, 0.06), M['frame'])
    for sx in (-1, 1):
        box("RackB_Frame_%s_Y%d" % (tag, sx), root, (sx*PX, 0, zc), (0.05, 0.95, 0.06), M['frame'])

# ---------------------------------------------------------------- vertical cable managers
vm = boxes("RackB_CableMgr_Vert_R", root, [
    (0.205, -0.4075, 1.00, 0.05, 0.008, 1.80),
    (0.205, -0.3525, 1.00, 0.05, 0.008, 1.80),
], M['panel'])
rings = []
for i in range(14):
    z = 0.16 + i * 0.128
    rings.append((0.205, -0.404, z, 0.040, 0.007, 0.014))
    rings.append((0.205, -0.356, z, 0.040, 0.007, 0.014))
    rings.append((0.205, -0.380, z - 0.028, 0.040, 0.055, 0.012))
boxes("RackB_CableMgr_Vert_R_Fingers", vm, rings, M['metalg'])

vl = boxes("RackB_CableMgr_Vert_L", root, [
    (-0.2325, 0.36, 1.00, 0.008, 0.05, 1.80),
    (-0.1775, 0.36, 1.00, 0.008, 0.05, 1.80),
], M['panel'])
lr = []
for i in range(12):
    z = 0.20 + i * 0.145
    lr.append((-0.232, 0.36, z, 0.010, 0.040, 0.012))
    lr.append((-0.178, 0.36, z, 0.010, 0.040, 0.012))
    lr.append((-0.205, 0.36, z - 0.028, 0.065, 0.040, 0.010))
boxes("RackB_CableMgr_Vert_L_Fingers", vl, lr, M['metalg'])

# horizontal cable managers (1U) at U3 and U27
def hcm(u):
    zb = Z0U + (u - 1) * UH
    h = UH
    o = box("RackB_CableMgr_Horiz_U%d" % u, root, (0, -0.435, zb + h/2), (0.44, 0.02, h - 0.006), M['panel'])
    fng = [(-0.19 + k*0.076, -0.458, zb + h/2, 0.012, 0.026, h - 0.012) for k in range(6)]
    boxes("RackB_CableMgr_Horiz_U%d_Fingers" % u, o, fng, M['metalg'])
hcm(3)
hcm(27)

# ---------------------------------------------------------------- equipment (partially filled)
def unit(u, nu, kind, depth=0.62, yfront=-0.45):
    zb = Z0U + (u - 1) * UH
    h = nu * UH
    cy = yfront + depth/2
    tag = "RackB_%s_U%d_%dU" % (kind.upper(), u, nu)
    box(tag + "_Body", root, (0, cy, zb + h/2), (0.455, depth, h - 0.008), M['server'])
    box(tag + "_Front", root, (0, yfront + 0.006, zb + h/2), (0.4826, 0.012, h - 0.004), M['bezel'])
    for sx in (-1, 1):
        box(tag + "_Ear%d" % sx, root, (sx*0.246, yfront - 0.020, zb + h/2),
            (0.016, 0.050, h - 0.006), M['metalg'])
    return tag, zb, h, yfront

for u in (6, 10):
    tag, zb, h, yf = unit(u, 2, 'SRV')
    for k in range(2):
        box(tag + "_LED%d" % k, root, (0.19 - 0.02*k, yf - 0.001, zb + h/2), (0.007, 0.004, 0.005),
            M['led_g'] if k == 0 else M['led_b'])
    boxes(tag + "_Drives", root,
          [(-0.16 + k*0.05, yf + 0.005, zb + h/2, 0.04, 0.006, h - 0.014) for k in range(5)], M['panel'])

tag, zb, h, yf = unit(8, 1, 'SW')
boxes(tag + "_Ports", root,
      [(-0.19 + k*0.031, yf + 0.006, zb + 0.62*h, 0.020, 0.010, 0.014) for k in range(12)], M['port'])
boxes(tag + "_LEDs", root,
      [(-0.19 + k*0.031, yf + 0.003, zb + 0.30*h, 0.008, 0.004, 0.004) for k in range(12)], M['led_g'])

tag, zb, h, yf = unit(14, 4, 'SRV')
boxes(tag + "_Drives", root,
      [(-0.18 + k*0.045, yf + 0.005, zb + 0.68*h, 0.036, 0.006, 0.028) for k in range(7)] +
      [(-0.18 + k*0.045, yf + 0.005, zb + 0.40*h, 0.036, 0.006, 0.028) for k in range(7)], M['panel'])
box(tag + "_LED", root, (0.20, yf + 0.004, zb + 0.5*h), (0.02, 0.004, 0.02), M['led_g'])

# patch panels (1U) with RJ45 ports
for u in (20, 22):
    tag, zb, h, yf = unit(u, 1, 'PATCH', depth=0.10)
    po = []
    for k in range(12):
        x = -0.20 + k * (0.40 / 11)
        po.append((x, yf + 0.006, zb + 0.62 * h, 0.019, 0.010, 0.015))
        po.append((x, yf + 0.006, zb + 0.28 * h, 0.019, 0.010, 0.015))
    boxes(tag + "_Ports", root, po, M['port'])
    box(tag + "_Label", root, (0.0, yf + 0.003, zb + h/2), (0.08, 0.002, 0.010), M['metalg'])

# blanking panels in a few slots - the rest stays open
for u in (2, 12, 19, 24, 31):
    zb = Z0U + (u - 1) * UH
    box("RackB_Blank_U%d" % u, root, (0, -0.452, zb + UH/2), (0.4826, 0.008, UH - 0.004), M['blank'])

# pull-out LCD console tilted up on the top front (as in the photo)
con = box("RackB_Console", root, (0, 0, 0), (0.42, 0.30, 0.012), M['panel'])
con.location = (0, -0.30, 1.943)
con.rotation_euler = (math.radians(-16), 0, 0)
box("RackB_Console_Screen", con, (0, 0, 0.009), (0.36, 0.22, 0.005), M['cbl_k'])

# ---------------------------------------------------------------- rear PDU
box("RackB_PDU", root, (0.245, 0.43, 0.95), (0.045, 0.045, 1.50), M['panel'])
boxes("RackB_PDU_Outlets", root,
      [(0.245, 0.406, 0.32 + i*0.17, 0.030, 0.008, 0.045) for i in range(8)], M['metalg'])

# ---------------------------------------------------------------- cabling
for u in (20, 22):
    zb = Z0U + (u - 1) * UH
    for k in range(8):
        x = -0.20 + k * 0.05
        pts = [(x, -0.462, zb + 0.62*UH),
               (x + 0.01, -0.492, zb + 0.62*UH - 0.05),
               (0.08 + 0.015*k, -0.47, zb - 0.14),
               (0.19, -0.38, zb - 0.34),
               (0.205, -0.38, zb - 0.58)]
        cable("RackB_PatchCord_U%d_%d" % (u, k), root, pts, 0.0045, M['cbl_b'], res_u=5, bev_res=1)
zb = Z0U + 7 * UH
for k in range(6):
    x = -0.19 + k * 0.031
    pts = [(x, -0.462, zb + 0.62*UH),
           (x, -0.492, zb - 0.03),
           (-0.10 - 0.015*k, -0.47, zb - 0.14),
           (-0.205, -0.40, 0.34),
           (-0.205, -0.38, 0.22)]
    cable("RackB_SwitchCord_%d" % k, root, pts, 0.004, M['cbl_c'], res_u=5, bev_res=1)
# thick blue bundle down the left vertical manager
for k in range(6):
    x = -0.215 + 0.018 * (k % 3)
    y = 0.345 + 0.03 * (k // 3)
    pts = [(x, y, 1.86), (x - 0.004, y, 1.40), (x + 0.004, y, 0.90), (x, y, 0.22)]
    cable("RackB_Bundle_%d" % k, root, pts, 0.009, M['cbl_b'], res_u=4, bev_res=1)
# grey trunk running along the top to the right manager
pts = [(-0.205, 0.36, 1.84), (-0.205, 0.30, 1.90), (0.0, 0.28, 1.912),
       (0.205, 0.20, 1.90), (0.205, -0.30, 1.855), (0.205, -0.38, 1.80)]
cable("RackB_Trunk", root, pts, 0.020, M['cbl_g'], res_u=8, bev_res=1)
# black power cords at the rear
for i, u in enumerate((6, 8, 10, 14)):
    zb = Z0U + (u - 1) * UH + 0.02
    pts = [(0.05 - 0.05*i, 0.19, zb),
           (0.15, 0.34, zb - 0.04),
           (0.245, 0.40, 0.30 + (i + 1) * 0.17)]
    cable("RackB_PowerCord_%d" % i, root, pts, 0.007, M['cbl_k'], res_u=5, bev_res=1)
# loose cords hanging in an empty area
for i in range(3):
    pts = [(-0.10 + 0.06*i, 0.30, 1.30), (-0.10 + 0.06*i, 0.40, 1.05 - 0.05*i),
           (-0.06 + 0.05*i, 0.44, 0.80), (-0.02 + 0.04*i, 0.42, 0.62)]
    cable("RackB_LooseCord_%d" % i, root, pts, 0.005, M['cbl_k'], res_u=5, bev_res=1)

rl.report(root)
print("RackB objects:", len([o for o in bpy.data.objects if o.name.startswith("RackB")]))
