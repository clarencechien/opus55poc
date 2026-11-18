import json, math, itertools, re

LAYOUT = "/home/user/opus55poc/datacenter/runs/qwen3.8-flash/hard/s3-r1-high/inputs/layout.json"
data = json.load(open(LAYOUT))

MM = 0.001
FLOOR_Z = 0.6
RACK_H = 2.0
RACK_TOP = FLOOR_Z + RACK_H          # 2.6

scn = bpy.context.scene
root_col = scn.collection

# cleanup of any partial previous run (linked copies have .00N suffixes)
for ob in list(bpy.data.objects):
    if re.match(r'^Rack[ABG](_\w+)*\.\d+$', ob.name) or \
       ob.name.startswith(("Containment_", "PerfTile_", "CableTray_", "Rack_", "hole")):
        bpy.data.objects.remove(ob, do_unlink=True)

ROT = {"N": math.pi, "S": 0.0, "E": math.pi/2, "W": -math.pi/2}

def dup_tree(src):
    """recursive linked duplicate (shares mesh data), returns new root"""
    new = src.copy()                      # linked duplicate: no children
    root_col.objects.link(new)
    stack = [(src, new)]
    while stack:
        s, n = stack.pop()
        for ch in s.children:
            nc = ch.copy()
            root_col.objects.link(nc)
            nc.parent = n
            nc.matrix_parent_inverse = ch.matrix_parent_inverse.copy()
            stack.append((ch, nc))
    return new

def setbox(name, x0, x1, y0, y1, z0, z1):
    """cube with exact world bounds, origin at centre"""
    import bmesh
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new(name, me)
    ob.location = ((x0+x1)/2, (y0+y1)/2, (z0+z1)/2)
    ob.scale = (x1-x0, y1-y0, z1-z0)
    root_col.objects.link(ob)
    return ob

# ---------------------------------------------------------------- 1. RACKS
templates = {"RackA": bpy.data.objects["RackA"], "RackG": bpy.data.objects["RackG"]}
rack_boxes = []   # for collision check
for r in data["racks"]:
    w, d = r["size"][0]*MM, r["size"][1]*MM
    tpl = templates["RackG" if abs(r["size"][0]-800) < 1 else "RackA"]
    new = dup_tree(tpl)
    new.name = f"Rack_{r['id']}"
    cx, cy = r["center"][0]*MM, r["center"][1]*MM
    new.location = (cx, cy, FLOOR_Z)
    new.rotation_euler = (0.0, 0.0, ROT[r["facing"]])
    new["rackId"] = r["id"]
    if r["facing"] in ("N", "S"):
        rack_boxes.append((r["id"], cx-w/2, cx+w/2, cy-d/2, cy+d/2))
    else:
        rack_boxes.append((r["id"], cx-d/2, cx+d/2, cy-w/2, cy+w/2))
print(f"racks placed: {len(rack_boxes)}")

# ------------------------------------------------- 2. COLD-AISLE CONTAINMENT
cold = [a for a in data["aisles"] if a["type"] == "cold"]
DOOR_T = 0.05
for i, a in enumerate(cold, start=1):
    x0, y0, x1, y1 = [v*MM for v in a["rect"]]
    setbox(f"Containment_Aisle{i}_Roof", x0, x1, y0, y1, RACK_TOP, RACK_TOP+0.05)
    if (x1-x0) >= (y1-y0):        # east-west aisle -> doors at W and E ends
        setbox(f"Containment_Aisle{i}_DoorW", x0, x0+DOOR_T, y0, y1, FLOOR_Z, RACK_TOP)
        setbox(f"Containment_Aisle{i}_DoorE", x1-DOOR_T, x1, y0, y1, FLOOR_Z, RACK_TOP)
    else:                          # north-south aisle -> doors at S and N ends
        setbox(f"Containment_Aisle{i}_DoorS", x0, x1, y0, y0+DOOR_T, FLOOR_Z, RACK_TOP)
        setbox(f"Containment_Aisle{i}_DoorN", x0, x1, y1-DOOR_T, y1, FLOOR_Z, RACK_TOP)
print("containment done")

# --------------------------------------------------------- 3. FLOOR TILES
import bmesh
mesh = bpy.data.meshes.new("PerfTileMesh")
bm = bmesh.new()
bmesh.ops.create_cube(bm, size=1.0)
for v in bm.verts:
    v.co.x *= 0.6; v.co.y *= 0.6; v.co.z *= 0.04; v.co.z -= 0.02  # local z -0.02..0.02
bm.to_mesh(mesh); bm.free()
master = bpy.data.objects.new("PerfTile_master", mesh)
master.location = (0, 0, FLOOR_Z - 0.02)
root_col.objects.link(master)

c_mesh = bpy.data.meshes.new("hole")
cbm = bmesh.new()
for gx in (-0.2, -0.1, 0.0, 0.1, 0.2):
    for gy in (-0.2, -0.1, 0.0, 0.1, 0.2):
        mat = __import__("mathutils").Matrix.Translation((gx, gy, FLOOR_Z - 0.02))
        bmesh.ops.create_cone(cbm, cap_ends=True, segments=12,
                              radius1=0.028, radius2=0.028, depth=0.2, matrix=mat)
cbm.to_mesh(c_mesh); cbm.free()
cutter = bpy.data.objects.new("hole", c_mesh)
root_col.objects.link(cutter)

mod = master.modifiers.new("perf", 'BOOLEAN')
mod.operation = 'DIFFERENCE'
mod.solver = 'EXACT'
mod.object = cutter
bpy.context.view_layer.objects.active = master
bpy.ops.object.modifier_apply(modifier="perf")
bpy.data.objects.remove(cutter, do_unlink=True)

tile_cells = []
for i, a in enumerate(cold, start=1):
    X0, Y0, X1, Y1 = a["rect"]
    gx = X0 if X0 % 600 == 0 else ((X0 // 600) + 1) * 600
    x = gx
    while x + 600 <= X1 + 1e-9:
        gy = Y0 if Y0 % 600 == 0 else ((Y0 // 600) + 1) * 600
        y = gy
        while y + 600 <= Y1 + 1e-9:
            tile_cells.append((i, x, y))
            y += 600
        x += 600

first = True
for n, (a_idx, x, y) in enumerate(tile_cells):
    if first:
        ob = master
        first = False
    else:
        ob = master.copy()
        root_col.objects.link(ob)
    ob.name = f"PerfTile_{a_idx}_{n+1:02d}"
    ob.location = ((x+300)*MM, (y+300)*MM, FLOOR_Z - 0.02)
print(f"perforated tiles: {len(tile_cells)}")

# --------------------------------------------------------- 4. CABLE TRAYS
rows = {}
for r in data["racks"]:
    rows.setdefault(r["row"], []).append(r)
TRAY_W, TRAY_H = 0.3, 0.1
TRAY_BOT = RACK_TOP + 0.3          # 2.9
for row, rs in sorted(rows.items()):
    if rs[0]["facing"] in ("N", "S"):
        lo = min(r["center"][0] - r["size"][0]/2 for r in rs) * MM
        hi = max(r["center"][0] + r["size"][0]/2 for r in rs) * MM
        cy = rs[0]["center"][1] * MM
        setbox(f"CableTray_{row}", lo, hi, cy-TRAY_W/2, cy+TRAY_W/2, TRAY_BOT, TRAY_BOT+TRAY_H)
    else:
        lo = min(r["center"][1] - r["size"][0]/2 for r in rs) * MM
        hi = max(r["center"][1] + r["size"][0]/2 for r in rs) * MM
        cx = rs[0]["center"][0] * MM
        setbox(f"CableTray_{row}", cx-TRAY_W/2, cx+TRAY_W/2, lo, hi, TRAY_BOT, TRAY_BOT+TRAY_H)
print("cable trays done")

# --------------------------------------------------------- 5. COLLISIONS
def overlap(a, b):
    return min(a[2], b[2]) - max(a[0], b[0]) > 1e-4 and min(a[4], b[4]) - max(a[3], b[3]) > 1e-4

col_boxes = [(c["id"],
              (c["center"][0]-c["size"][0]/2)*MM, (c["center"][0]+c["size"][0]/2)*MM,
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
def pt_in_room(x, y):
    inside = False
    j = len(room)-1
    for i in range(len(room)):
        xi, yi = room[i]; xj, yj = room[j]
        if ((yi > y) != (yj > y)) and (x < (xj-xi)*(y-yi)/(yj-yi)+xi):
            inside = True
        j = i
    return inside
for rb in rack_boxes:
    for px, py in ((rb[1], rb[3]), (rb[1], rb[4]), (rb[2], rb[3]), (rb[2], rb[4])):
        if not pt_in_room(px, py):
            print("RACK OUTSIDE ROOM:", rb[0]); bad += 1; break
print("collisions:", bad)
print("ALL DONE")
