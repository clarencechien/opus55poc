import json, math, bpy
from collections import defaultdict

RUN = "/home/user/opus55poc/datacenter/runs/opus-5.5/hard/s3-r1"
L = json.load(open(RUN + "/inputs/layout.json"))

FLOOR = 0.6
RACK_H = 2.0
TOP = FLOOR + RACK_H

# ---------- cleanup previous runs ----------
prefixes = ("Rack_", "Containment_", "PerfTile_", "CableTray_")
ids = {r["id"] for r in L["racks"]}
for o in list(bpy.data.objects):
    n = o.name
    if n.startswith(prefixes) or any(n.startswith(i + "_") for i in ids):
        bpy.data.objects.remove(o, do_unlink=True)
for m in list(bpy.data.meshes):
    if m.users == 0:
        bpy.data.meshes.remove(m)

def get_coll(name):
    c = bpy.data.collections.get(name)
    if c is None:
        c = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(c)
    return c

c_racks = get_coll("Racks")
c_cont = get_coll("Containment")
c_tiles = get_coll("PerfTiles")
c_trays = get_coll("CableTrays")

def box(name, x0, y0, z0, x1, y1, z1, coll, mesh=None):
    if mesh is None:
        mesh = bpy.data.meshes.new(name + "_mesh")
        sx, sy, sz = (x1 - x0) / 2, (y1 - y0) / 2, (z1 - z0) / 2
        v = [(-sx, -sy, -sz), (sx, -sy, -sz), (sx, sy, -sz), (-sx, sy, -sz),
             (-sx, -sy, sz), (sx, -sy, sz), (sx, sy, sz), (-sx, sy, sz)]
        f = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
        mesh.from_pydata(v, [], f)
        mesh.update()
    o = bpy.data.objects.new(name, mesh)
    o.location = ((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2)
    coll.objects.link(o)
    return o

# ---------- racks ----------
ROT = {"S": 0.0, "N": math.pi, "E": math.pi / 2, "W": -math.pi / 2}

def dup_tree(src, parent, name, coll):
    o = src.copy()  # shares mesh data (linked duplicate)
    o.name = name
    coll.objects.link(o)
    if parent is not None:
        o.parent = parent
        o.matrix_parent_inverse = src.matrix_parent_inverse.copy()
    else:
        o.parent = None
    for ch in src.children:
        tpl = src.name.split("_")[0] if parent is not None else src.name
        dup_tree(ch, o, name.split("_")[0] if False else None, coll) if False else None
    return o

def copy_rack(tpl_name, rid, coll):
    tpl = bpy.data.objects[tpl_name]
    root = tpl.copy()
    root.name = "Rack_" + rid
    root.parent = None
    coll.objects.link(root)
    def rec(src, newparent):
        for ch in src.children:
            o = ch.copy()
            suffix = ch.name[len(tpl_name) + 1:] if ch.name.startswith(tpl_name + "_") else ch.name
            o.name = rid + "_" + suffix
            coll.objects.link(o)
            o.parent = newparent
            o.matrix_parent_inverse = ch.matrix_parent_inverse.copy()
            o.matrix_basis = ch.matrix_basis.copy()
            rec(ch, o)
    rec(tpl, root)
    return root

for r in L["racks"]:
    w, d = r["size"]
    tpl = "RackG" if abs(w - 800) < 1 else "RackA"
    root = copy_rack(tpl, r["id"], c_racks)
    cx, cy = r["center"]
    root.location = (cx / 1000.0, cy / 1000.0, FLOOR)
    root.rotation_mode = "XYZ"
    root.rotation_euler = (0.0, 0.0, ROT[r["facing"]])
    root.scale = (1, 1, 1)
    root["rackId"] = r["id"]
    root["row"] = r["row"]
    root["facing"] = r["facing"]
    root["template"] = tpl

# ---------- containment ----------
ROOF_T = 0.03
DOOR_T = 0.04
for i, a in enumerate([a for a in L["aisles"] if a["type"] == "cold"], start=1):
    x0, y0, x1, y1 = [v / 1000.0 for v in a["rect"]]
    roof = box(f"Containment_Roof_{i}", x0, y0, TOP, x1, y1, TOP + ROOF_T, c_cont)
    roof["aisle"] = i
    if (x1 - x0) >= (y1 - y0):  # runs east-west, open ends at west/east
        box(f"Containment_Door_{i}_W", x0, y0, FLOOR, x0 + DOOR_T, y1, TOP, c_cont)["aisle"] = i
        box(f"Containment_Door_{i}_E", x1 - DOOR_T, y0, FLOOR, x1, y1, TOP, c_cont)["aisle"] = i
    else:  # runs north-south, open ends at south/north
        box(f"Containment_Door_{i}_S", x0, y0, FLOOR, x1, y0 + DOOR_T, TOP, c_cont)["aisle"] = i
        box(f"Containment_Door_{i}_N", x0, y1 - DOOR_T, FLOOR, x1, y1, TOP, c_cont)["aisle"] = i

# ---------- perforated tiles ----------
T = 600
TILE_T = 0.02
tile_mesh = None
count = 0
for i, a in enumerate([a for a in L["aisles"] if a["type"] == "cold"], start=1):
    x0, y0, x1, y1 = a["rect"]
    gx0 = math.ceil(x0 / T - 1e-9)
    gx1 = math.floor(x1 / T + 1e-9)
    gy0 = math.ceil(y0 / T - 1e-9)
    gy1 = math.floor(y1 / T + 1e-9)
    for gx in range(gx0, gx1):
        for gy in range(gy0, gy1):
            tx0, ty0 = gx * T / 1000.0, gy * T / 1000.0
            o = box(f"PerfTile_{gx}_{gy}", tx0, ty0, FLOOR - TILE_T, tx0 + 0.6, ty0 + 0.6, FLOOR, c_tiles, tile_mesh)
            if tile_mesh is None:
                tile_mesh = o.data
            o["aisle"] = i
            count += 1
print("tiles", count)

# ---------- cable trays ----------
rows = defaultdict(list)
for r in L["racks"]:
    rows[r["row"]].append(r)
TRAY_W = 0.3
TRAY_T = 0.1
TRAY_Z0 = TOP + 0.3
for row, rs in sorted(rows.items()):
    # footprint extents in plan (respecting orientation)
    exts = []
    for r in rs:
        w, d = r["size"]
        cx, cy = r["center"]
        if r["facing"] in ("N", "S"):
            exts.append((cx - w / 2, cy - d / 2, cx + w / 2, cy + d / 2))
        else:
            exts.append((cx - d / 2, cy - w / 2, cx + d / 2, cy + w / 2))
    X0 = min(e[0] for e in exts) / 1000; Y0 = min(e[1] for e in exts) / 1000
    X1 = max(e[2] for e in exts) / 1000; Y1 = max(e[3] for e in exts) / 1000
    if rs[0]["facing"] in ("N", "S"):  # east-west row
        yc = (Y0 + Y1) / 2
        o = box(f"CableTray_{row}", X0, yc - TRAY_W / 2, TRAY_Z0, X1, yc + TRAY_W / 2, TRAY_Z0 + TRAY_T, c_trays)
    else:
        xc = (X0 + X1) / 2
        o = box(f"CableTray_{row}", xc - TRAY_W / 2, Y0, TRAY_Z0, xc + TRAY_W / 2, Y1, TRAY_Z0 + TRAY_T, c_trays)
    o["row"] = row
    print("tray", row, round(X0, 3), round(Y0, 3), round(X1, 3), round(Y1, 3))

bpy.context.view_layer.update()

# ---------- verification: rack world bboxes ----------
from mathutils import Vector
def world_bbox(root):
    pts = []
    def rec(o):
        if o.type == "MESH":
            for c in o.bound_box:
                pts.append(o.matrix_world @ Vector(c))
        for ch in o.children:
            rec(ch)
    rec(root)
    xs = [p.x for p in pts]; ys = [p.y for p in pts]; zs = [p.z for p in pts]
    return (min(xs), min(ys), min(zs), max(xs), max(ys), max(zs))

bad = 0
boxes = {}
for r in L["racks"]:
    root = bpy.data.objects["Rack_" + r["id"]]
    bb = world_bbox(root)
    boxes[r["id"]] = bb
    w, d = r["size"]
    cx, cy = r["center"]
    if r["facing"] in ("N", "S"):
        ex, ey = w / 2000, d / 2000
    else:
        ex, ey = d / 2000, w / 2000
    exp = (cx / 1000 - ex, cy / 1000 - ey, FLOOR, cx / 1000 + ex, cy / 1000 + ey, TOP)
    err = max(abs(a - b) for a, b in zip(bb, exp))
    if err > 0.025:
        bad += 1
        print("MISMATCH", r["id"], [round(v, 3) for v in bb], [round(v, 3) for v in exp])
    # front direction check
    fwd = root.matrix_world.to_3x3() @ Vector((0, -1, 0))
print("racks", len(L["racks"]), "bbox mismatches", bad)
# overlaps between racks
ov = 0
ks = list(boxes)
for i in range(len(ks)):
    for j in range(i + 1, len(ks)):
        a, b = boxes[ks[i]], boxes[ks[j]]
        if a[0] < b[3] - 1e-4 and b[0] < a[3] - 1e-4 and a[1] < b[4] - 1e-4 and b[1] < a[4] - 1e-4:
            ov += 1
            print("OVERLAP", ks[i], ks[j])
# vs walls / columns
for o in bpy.data.objects:
    if o.name.startswith(("Wall_", "Column_")):
        pts = [o.matrix_world @ Vector(c) for c in o.bound_box]
        wb = (min(p.x for p in pts), min(p.y for p in pts), max(p.x for p in pts), max(p.y for p in pts))
        for k, a in boxes.items():
            if a[0] < wb[2] - 1e-4 and wb[0] < a[3] - 1e-4 and a[1] < wb[3] - 1e-4 and wb[1] < a[4] - 1e-4:
                ov += 1
                print("HIT", k, o.name, [round(v, 3) for v in wb])
print("overlaps", ov)
print("objects", len(bpy.data.objects))
