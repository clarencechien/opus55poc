import os, sys
sys.path.insert(0, os.getcwd())
import bpy, importlib
import rl
rl = importlib.reload(rl)

# 1) post caps were 2 mm too wide in x
for o in bpy.data.objects:
    if o.name.startswith("RackB_Post_") and o.name.endswith("_Cap"):
        for v in o.data.vertices:
            cx = 0.275 if v.co.x > 0 else -0.275
            v.co.x = cx + (v.co.x - cx) * (0.048 / 0.052)

# 2) front patch/switch cords bulged past y = -0.5
n = 0
for o in bpy.data.objects:
    if o.name.startswith(("RackB_PatchCord", "RackB_SwitchCord")):
        for v in o.data.vertices:
            if v.co.y < -0.4955:
                v.co.y = -0.4955 + (v.co.y + 0.4955) * 0.25
                n += 1
print("cord verts moved:", n)

rl.report(bpy.data.objects["RackB"])
rl.report(bpy.data.objects["RackA"])
