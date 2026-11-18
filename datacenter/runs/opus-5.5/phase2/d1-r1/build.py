import json, os
RUN = "/home/user/opus55poc/datacenter/runs/opus-5.5/phase2/d1-r1/"
p = RUN + "asbuilt_pred.json"
if not os.path.exists(p):
    p = RUN + "inputs/design.json"
lay = json.load(open(p))
print("using", p)
for o in list(bpy.data.objects):
    if o.name.startswith("P_"):
        bpy.data.objects.remove(o, do_unlink=True)
rot = {"S": 0.0, "N": math.pi, "E": math.pi/2, "W": -math.pi/2}
coll = bpy.context.scene.collection
def place(item, tmpl):
    t = bpy.data.objects[tmpl]
    o = t.copy()
    o.name = "P_" + item["id"]
    o.location = (item["center"][0]/1000.0, item["center"][1]/1000.0, 0.6)
    o.rotation_euler = (0, 0, rot[item["facing"]])
    coll.objects.link(o)
    for c in t.children:
        cc = c.copy()
        coll.objects.link(cc)
        cc.parent = o
        cc.name = "P_" + item["id"] + "_" + c.name
for r in lay["racks"]:
    place(r, "RackG" if r["size"][0] > 700 else "RackA")
for c in lay["crah"]:
    place(c, "CRAH")
print("placed", len(lay["racks"]), len(lay["crah"]))
print("tmpl", [(o.name, tuple(round(v,3) for v in o.location), len(o.children), o.type) for o in bpy.data.objects if o.name in ("RackA","RackG","CRAH")])
