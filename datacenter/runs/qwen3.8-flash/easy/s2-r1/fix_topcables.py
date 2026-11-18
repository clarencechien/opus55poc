import os, sys
sys.path.insert(0, os.getcwd())
import bpy, importlib
import rl
rl = importlib.reload(rl)
from rl import cable, mats
M = mats()
root = bpy.data.objects["RackA"]
for o in list(bpy.data.objects):
    if o.name.startswith("RackA_TopCable"):
        bpy.data.objects.remove(o, do_unlink=True)
for i in range(5):
    x = -0.18 + 0.05 * i
    pts = [(x, 0.30, 1.88), (x + 0.02, 0.42, 1.92), (x, 0.18, 1.950), (x - 0.02, -0.05, 1.962)]
    cable("RackA_TopCable_%d" % i, root, pts, 0.009,
          M['cbl_b'] if i % 2 else M['cbl_g'], res_u=6, bev_res=1)
rl.report(root)
