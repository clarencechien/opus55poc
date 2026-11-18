import os, sys
sys.path.insert(0, os.getcwd())
import bpy, importlib
import rl
rl = importlib.reload(rl)
A = bpy.data.objects["RackA"]; B = bpy.data.objects["RackB"]
print("front door parent:", bpy.data.objects["RackA_FrontDoor"].parent.name,
      "perforated:", bpy.data.objects["RackA_FrontDoor"].get("perforated"))
print("rear door parent:", bpy.data.objects["RackA_RearDoor"].parent.name)
print("posts:", [(n, bpy.data.objects[n].parent.name) for n in
                 ("RackB_Post_1","RackB_Post_2","RackB_Post_3","RackB_Post_4")])
print("hidden:", [o.name for o in bpy.data.objects if o.hide_render][:5])
rl.report(A); rl.report(B)
# per-part tri totals
def tris(pref):
    return sum(rl.tri_count(bpy.data.objects[pref]) )
print("tris A/B:", rl.tri_count(A), rl.tri_count(B))
