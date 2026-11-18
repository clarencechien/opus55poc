import os, sys
sys.path.insert(0, os.getcwd())
import bpy, importlib
import rl
rl = importlib.reload(rl)
from rl import box, cable, mats

M = mats()
A = bpy.data.objects["RackA"]
B = bpy.data.objects["RackB"]
UH, Z0U = 0.04445, 0.15

# ---- 1) bigger, brighter status LEDs on Rack A ---------------------------
for o in list(bpy.data.objects):
    if o.name.startswith("RackA") and "_LED" in o.name:
        bpy.data.objects.remove(o, do_unlink=True)
POP = [(1,1),(2,1),(4,2),(6,1),(8,4),(12,1),(13,2),(16,4),(20,1),(21,1),
       (23,2),(25,1),(26,2),(29,4),(33,1),(35,2),(37,1),(38,1),(40,1)]
cols = [M['led_g'], M['led_g'], M['led_b'], M['led_a']]
for (u, nu) in POP:
    zb = Z0U + (u-1)*UH
    h = nu*UH
    for k in range(4):
        box("RackA_LED_U%d_%d" % (u, k), A,
            (0.198 - 0.017*k, -0.4815, zb + h/2 + (0.007 if k % 2 == 0 else -0.007)),
            (0.012, 0.004, 0.006), cols[k])
    # activity LED on the left of the bezel
    box("RackA_LED_U%d_L" % u, A, (-0.205, -0.4815, zb + h/2), (0.010, 0.004, 0.006),
        M['led_g'] if u % 2 else M['led_b'])

# ---- 2) tidier patch cords on Rack B -------------------------------------
for o in list(bpy.data.objects):
    if o.name.startswith(("RackB_PatchCord", "RackB_SwitchCord")):
        bpy.data.objects.remove(o, do_unlink=True)
for u in (20, 22):
    zb = Z0U + (u-1)*UH
    zc = zb + 0.62*UH
    for k in range(6):
        x = -0.16 + k*0.062
        pts = [(x, -0.468, zc),
               (x + 0.01, -0.482, zc - 0.05),
               (x + 0.07, -0.470, zc - 0.12),
               (0.16, -0.42, zc - 0.20),
               (0.205, -0.38, zc - 0.32)]
        cable("RackB_PatchCord_U%d_%d" % (u, k), B, pts, 0.0045, M['cbl_b'], res_u=5, bev_res=1)
zb = Z0U + 7*UH
zc = zb + 0.62*UH
for k in range(5):
    x = -0.19 + k*0.038
    pts = [(x, -0.468, zc),
           (x - 0.01, -0.480, zc - 0.06),
           (-0.13, -0.470, 0.34),
           (-0.19, -0.42, 0.20),
           (-0.205, -0.38, 0.12)]
    cable("RackB_SwitchCord_%d" % k, B, pts, 0.004, M['cbl_c'], res_u=5, bev_res=1)

rl.report(A)
rl.report(B)
