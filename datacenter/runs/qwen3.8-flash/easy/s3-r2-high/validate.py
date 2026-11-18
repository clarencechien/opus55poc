import bpy, json, math
from mathutils import Vector

L = json.load(open("inputs/layout.json"))
MM = 0.001

def wbbox(objs):
    if isinstance(objs, bpy.types.Object):
        objs = [objs]
    mn = Vector((1e9,)*3); mx = Vector((-1e9,)*3)
    for o in objs:
        for p in o.bound_box:
            c = o.matrix_world @ Vector(p)
            mn = Vector(map(min, mn, c)); mx = Vector(map(max, mx, c))
    return mn, mx

groups = {}
for o in bpy.data.objects:
    for p in ("Rack_", "Containment_", "PerfTile_", "CableTray_"):
        if o.name.startswith(p):
            groups.setdefault(p, []).append(o)
for k in sorted(groups):
    print(k, len(groups[k]))

print("\n-- rack check --")
bad = 0
for r in L["racks"]:
    o = bpy.data.objects.get("Rack_" + r["id"])
    if o is None:
        print("MISSING", r["id"]); bad += 1; continue
    mn, mx = wbbox(o)
    cx, cy = r["center"][0]*MM, r["center"][1]*MM
    w, d = r["size"][0]*MM, r["size"][1]*MM
    tol = 0.03
    errs = []
    for got, exp in ((mn.x, cx-w/2), (mx.x, cx+w/2), (mn.y, cy-d/2), (mx.y, cy+d/2),
                     (mn.z, 0.6), (mx.z, 2.6)):
        if abs(got-exp) > tol:
            errs.append((round(got,3), round(exp,3)))
    if o.get("rackId") != r["id"]:
        errs.append("rackId=" + str(o.get("rackId")))
    if errs:
        print("PROBLEM", r["id"], errs, [round(v,3) for v in mn], [round(v,3) for v in mx]); bad += 1
print("rack problems:", bad)
o = bpy.data.objects["Rack_A01"]
print("sample Rack_A01 loc", tuple(round(v,3) for v in o.location), "rot", tuple(round(v,1) for v in o.rotation_euler))
o = bpy.data.objects["Rack_B01"]
print("sample Rack_B01 loc", tuple(round(v,3) for v in o.location), "rot", tuple(round(v,1) for v in o.rotation_euler))

print("\n-- collisions --")
def overlap(a, b, eps=1e-4):
    return (a[0].x < b[1].x-eps and a[1].x > b[0].x+eps and
            a[0].y < b[1].y-eps and a[1].y > b[0].y+eps and
            a[0].z < b[1].z-eps and a[1].z > b[0].z+eps)
rbs = {o.name: wbbox(o) for o in groups["Rack_"]}
names = sorted(rbs)
hits = [(names[i], names[j]) for i in range(len(names)) for j in range(i+1, len(names))
        if overlap(rbs[names[i]], rbs[names[j]])]
print("rack-rack overlaps:", hits)
shell = {o.name: wbbox(o) for o in bpy.data.objects if o.name.startswith(("Wall_", "Column_"))}
for rn, rb in rbs.items():
    for sn, sb in shell.items():
        if overlap(rb, sb):
            print("RACK/SHELL OVERLAP", rn, sn)
print("shell objects checked:", len(shell))
# racks must be inside the room
for rn, (mn, mx) in rbs.items():
    if not (mn.x > 0.1 and mx.x < 14.3 and mn.y > 0.1 and mx.y < 11.9):
        print("RACK OUTSIDE ROOM", rn)

print("\n-- containment --")
cold = [a for a in L["aisles"] if a["type"] == "cold"][0]
x0,y0,x1,y1 = [v*MM for v in cold["rect"]]
print("cold aisle rect", x0,y0,x1,y1)
for o in sorted(groups["Containment_"], key=lambda o:o.name):
    mn, mx = wbbox(o)
    print(" ", o.name, [round(v,3) for v in mn], "->", [round(v,3) for v in mx])

print("\n-- perf tiles --")
cells = set()
tops = set()
for o in groups["PerfTile_"]:
    mn, mx = wbbox(o)
    tops.add((round(mn.z,4), round(mx.z,4)))
    cells.add((round((mn.x+mx.x)/2, 3), round((mn.y+mx.y)/2, 3)))
    if abs(mx.x-mn.x-0.6) > 0.002 or abs(mx.y-mn.y-0.6) > 0.002:
        print("BAD TILE SIZE", o.name, round(mx.x-mn.x,4), round(mx.y-mn.y,4))
exp = set()
i = 0
while (i+1)*0.6 <= x1 + 1e-9 and i*0.6 >= x0 - 1e-9:
    j = 0
    while (j+1)*0.6 <= y1 + 1e-9 and j*0.6 >= y0 - 1e-9:
        exp.add((round((i+0.5)*0.6,3), round((j+0.5)*0.6,3)))
        j += 1
    i += 1
print("tile z spans:", tops)
print("expected cells", len(exp), "got", len(cells), "match:", cells == exp)
print("missing:", sorted(exp-cells), "extra:", sorted(cells-exp))

print("\n-- cable trays --")
for o in sorted(groups["CableTray_"], key=lambda o:o.name):
    mn, mx = wbbox(o)
    print(" ", o.name, [round(v,3) for v in mn], "->", [round(v,3) for v in mx],
          "w", round(mx.y-mn.y,3), "len", round(mx.x-mn.x,3), "bottom", round(mn.z,3))
print("\ntotal objects:", len(bpy.data.objects))
