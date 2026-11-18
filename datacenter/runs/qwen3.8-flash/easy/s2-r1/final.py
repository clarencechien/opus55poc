import os, sys
sys.path.insert(0, os.getcwd())
import bpy, importlib
import rl
rl = importlib.reload(rl)
from rl import cable, mats

M = mats()
B = bpy.data.objects["RackB"]
A = bpy.data.objects["RackA"]
UH, Z0U = 0.04445, 0.15

# ---- tidy the loose rear cords so they hang off real equipment -----------
for o in list(bpy.data.objects):
    if o.name.startswith("RackB_LooseCord"):
        bpy.data.objects.remove(o, do_unlink=True)
zb14 = Z0U + 13*UH          # 4U chassis rear edge
for i in range(3):
    x = -0.12 + 0.09*i
    pts = [(x, 0.165, zb14 + 0.03*i),
           (x + 0.02, 0.30, zb14 - 0.10),
           (x, 0.42, zb14 - 0.30 - 0.04*i),
           (x - 0.03, 0.44, zb14 - 0.48)]
    cable("RackB_LooseCord_%d" % i, B, pts, 0.005, M['cbl_k'], res_u=5, bev_res=1)

# ---- make sure everything is visible --------------------------------------
for o in bpy.data.objects:
    o.hide_render = False
    o.hide_viewport = False

# ---- descriptive custom properties ---------------------------------------
A["model"] = "closed server cabinet"
A["width_mm"] = 600; A["depth_mm"] = 1200; A["height_mm"] = 2000
A["rack_units"] = 42; A["front"] = "-y"
A["finish"] = "black / dark grey"
A["door_front"] = "RackA_FrontDoor"; A["door_rear"] = "RackA_RearDoor"
B["model"] = "open 4-post frame rack"
B["width_mm"] = 600; B["depth_mm"] = 1000; B["height_mm"] = 2000
B["rack_units"] = 42; B["front"] = "-y"; B["posts"] = 4
for nm in ("RackA_FrontDoor", "RackA_RearDoor"):
    bpy.data.objects[nm]["perforated"] = True
for i in range(1, 5):
    bpy.data.objects["RackB_Post_%d" % i]["mounting_holes"] = True

# ---- hierarchy / naming verification --------------------------------------
roots = {"RackA": A, "RackB": B}
bad = []
for o in bpy.data.objects:
    if o.name.startswith("RackA") or o.name.startswith("RackB"):
        if o in (A, B):
            continue
        p = o.parent
        top = None
        while p is not None:
            if p.name in roots:
                top = p.name; break
            p = p.parent
        if top != o.name.split("_")[0][:5] and top != ("RackA" if o.name.startswith("RackA") else "RackB"):
            bad.append((o.name, top))
print("objects:", len(bpy.data.objects), "mis-parented:", bad)
print("RackA_FrontDoor:", A["RackA_FrontDoor"] is not None,
      bpy.data.objects["RackA_FrontDoor"].parent.name)
print("posts:", [n for n in ("RackB_Post_1","RackB_Post_2","RackB_Post_3","RackB_Post_4")
                 if n in bpy.data.objects])
rl.report(A)
rl.report(B)
