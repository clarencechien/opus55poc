import json, itertools
LAYOUT = "/home/user/opus55poc/datacenter/runs/qwen3.8-flash/hard/s3-r1-high/inputs/layout.json"
data = json.load(open(LAYOUT))
MM = 0.001

rack_boxes = []
for r in data["racks"]:
    w, d = r["size"][0]*MM, r["size"][1]*MM
    cx, cy = r["center"][0]*MM, r["center"][1]*MM
    if r["facing"] in ("N", "S"):
        rack_boxes.append((r["id"], cx-w/2, cx+w/2, cy-d/2, cy+d/2))
    else:
        rack_boxes.append((r["id"], cx-d/2, cx+d/2, cy-w/2, cy+w/2))

def overlap(a, b):  # a,b = (x0,x1,y0,y1)
    return min(a[1], b[1]) - max(a[0], b[0]) > 1e-4 and min(a[3], b[3]) - max(a[2], b[2]) > 1e-4

col_boxes = [(c["id"], (c["center"][0]-c["size"][0]/2)*MM, (c["center"][0]+c["size"][0]/2)*MM,
              (c["center"][1]-c["size"][1]/2)*MM, (c["center"][1]+c["size"][1]/2)*MM)
             for c in data["columns"]]

bad = 0
for a, b in itertools.combinations(rack_boxes, 2):
    if overlap(a[1:], b[1:]):
        print("RACK-RACK OVERLAP:", a[0], b[0]); bad += 1
for rb in rack_boxes:
    for cb in col_boxes:
        if overlap(rb[1:], cb[1:]):
            print("RACK-COLUMN OVERLAP:", rb[0], cb[0]); bad += 1
room = data["room"]["polygon"]
def pt_in(x, y):
    inside = False; j = len(room)-1
    for i in range(len(room)):
        xi, yi = room[i]; xj, yj = room[j]
        if ((yi > y) != (yj > y)) and (x < (xj-xi)*(y-yi)/(yj-yi)+xi):
            inside = True
        j = i
    return inside
for rb in rack_boxes:
    for px, py in ((rb[1], rb[2]), (rb[1], rb[3]), (rb[2], rb[2]), (rb[2], rb[3])):
        if not pt_in(px, py):
            print("RACK OUTSIDE ROOM:", rb[0]); bad += 1; break
print("collisions:", bad)

# verify scene objects: every rack exists with rackId, correct world bbox
deps = bpy.context.evaluated_depsgraph_get()
missing = []
for r in data["racks"]:
    ob = bpy.data.objects.get(f"Rack_{r['id']}")
    if not ob or ob.get("rackId") != r["id"] or abs(ob.location.z-0.6) > 1e-6:
        missing.append(r["id"])
print("missing/bad rack objects:", missing)

# world bbox check for a sample of racks (E-row rotated, G width)
def wbbox(root):
    xs=[];ys=[];zs=[]
    for o in [root]+list(root.children_recursive):
        ev = o.evaluated_get(deps)
        for c in o.bound_box if hasattr(o,'bound_box') else []:
            pass
        # use mesh world bbox
        import mathutils
        mw = ev.matrix_world
        for corner in ev.bound_box:
            p = mw @ mathutils.Vector(corner)
            xs.append(p.x); ys.append(p.y); zs.append(p.z)
    return min(xs),max(xs),min(ys),max(ys),min(zs),max(zs)

for rid in ("A01","B01","E01","F06","C13"):
    ob = bpy.data.objects[f"Rack_{rid}"]
    bb = wbbox(ob)
    print(rid, ["%.3f"%v for v in bb])

counts = {}
for ob in bpy.data.objects:
    for p in ("Rack_", "Containment_", "PerfTile_", "CableTray_"):
        if ob.name.startswith(p):
            counts[p] = counts.get(p, 0) + 1
print("object counts:", counts)
