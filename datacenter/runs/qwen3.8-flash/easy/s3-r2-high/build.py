import bpy, json, math
from mathutils import Vector

L = json.load(open("inputs/layout.json"))
MM = 0.001
ZF = L["room"]["raised_floor_height"] * MM          # 0.6 top of raised floor
RACK_H = 2.0
TOP = ZF + RACK_H                                    # 2.6 rack top

# ---------- helpers ---------------------------------------------------------
def coll():
    return bpy.data.collections.get("Collection") or bpy.context.scene.collection

def link(obj):
    c = coll()
    if obj.name not in c.objects:
        c.objects.link(obj)

def new_mat(name, col, alpha=1.0):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes.get("Principled BSDF")
    if b:
        b.inputs["Base Color"].default_value = (*col[:3], 1.0)
        b.inputs["Alpha"].default_value = alpha
        if alpha < 1.0:
            m.blend_method = 'BLEND'
    m.diffuse_color = (*col[:3], alpha)
    return m

def box(name, x0, x1, y0, y1, z0, z1, mat=None):
    me = bpy.data.meshes.new(name)
    v = [(-0.5,-0.5,-0.5),(0.5,-0.5,-0.5),(0.5,0.5,-0.5),(-0.5,0.5,-0.5),
         (-0.5,-0.5,0.5),(0.5,-0.5,0.5),(0.5,0.5,0.5),(-0.5,0.5,0.5)]
    f = [(0,1,2,3),(7,6,5,4),(0,4,5,1),(1,5,6,2),(2,6,7,3),(3,7,4,0)]
    me.from_pydata(v, [], f); me.update()
    ob = bpy.data.objects.new(name, me)
    ob.location = ((x0+x1)/2, (y0+y1)/2, (z0+z1)/2)
    ob.scale = (x1-x0, y1-y0, z1-z0)
    link(ob)
    if mat is not None:
        ob.data.materials.append(mat)
    return ob

def bake(ob, loc=False):
    bpy.ops.object.select_all(action='DESELECT')
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.transform_apply(location=loc, rotation=False, scale=True)

def wbbox(objs):
    mn = Vector((1e9,)*3); mx = Vector((-1e9,)*3)
    for o in objs:
        for c in (o.matrix_world @ Vector(p) for p in o.bound_box):
            mn = Vector(map(min, mn, c)); mx = Vector(map(max, mx, c))
    return mn, mx

tmpl = [o for o in bpy.data.objects if o.name.startswith("RackA")]
before = wbbox(tmpl)

# ---------- 1. racks --------------------------------------------------------
meshes = [o for o in tmpl if o.type == 'MESH']
dups = []
for o in meshes:
    d = o.copy(); link(d); d.matrix_world = o.matrix_world.copy(); dups.append(d)
bpy.ops.object.select_all(action='DESELECT')
for d in dups:
    d.select_set(True)
bpy.context.view_layer.objects.active = dups[0]
bpy.ops.object.parent_clear(type='CLEAR_KEEP_TRANSFORM')
bpy.ops.object.join()
proto = bpy.context.view_layer.objects.active
proto.name = "RackProto"
print("proto mesh users:", proto.data.users)
lb = [proto.matrix_world.inverted() @ Vector(c) for c in proto.bound_box]
print("proto origin", tuple(round(v,4) for v in proto.matrix_world.translation))
print("proto local zmin/zmax", round(min(v.z for v in lb), 4), round(max(v.z for v in lb), 4),
      "x", round(min(v.x for v in lb),4), round(max(v.x for v in lb),4),
      "y", round(min(v.y for v in lb),4), round(max(v.y for v in lb),4))
print("template bbox before:", tuple(round(v,4) for v in before[0]), tuple(round(v,4) for v in before[1]))

FACE_ROT = {"N": math.pi, "S": 0.0, "E": math.pi/2, "W": -math.pi/2}
for r in L["racks"]:
    ob = bpy.data.objects.new("Rack_" + r["id"], proto.data)
    link(ob)
    ob.location = (r["center"][0]*MM, r["center"][1]*MM, ZF)
    ob.rotation_euler = (0.0, 0.0, FACE_ROT[r["facing"]])
    ob["rackId"] = r["id"]
bpy.data.objects.remove(proto, do_unlink=True)
print("racks placed:", len(L["racks"]))

# ---------- 2. cold-aisle containment --------------------------------------
mat_cont = new_mat("MatContainment", (0.55, 0.70, 0.85), alpha=0.5)
mat_door = new_mat("MatContainmentDoor", (0.78, 0.88, 0.95), alpha=0.7)
T_ROOF, T_DOOR = 0.05, 0.05
ci = 0
for a in L["aisles"]:
    if a["type"] != "cold":
        continue
    ci += 1
    x0, y0, x1, y1 = [v*MM for v in a["rect"]]
    bake(box("Containment_Roof_%d" % ci, x0, x1, y0, y1, TOP, TOP+T_ROOF, mat_cont))
    for tag, xx in (("W", x0), ("E", x1)):
        bake(box("Containment_Door_%d_%s" % (ci, tag), xx-T_DOOR/2, xx+T_DOOR/2,
                 y0, y1, ZF, TOP, mat_door))
print("containment parts:", ci, "aisles ->", 3*ci)

# ---------- 3. perforated floor tiles ---------------------------------------
mat_perf = new_mat("MatPerfTile", (0.90, 0.92, 0.95))
TILE, T_TILES = 0.6, 0.03
prot = box("PerfProto", -TILE/2, TILE/2, -TILE/2, TILE/2, ZF-T_TILES, ZF, mat_perf)
bake(prot, loc=True)            # origin at world origin, mesh z 0.57..0.60
cutters = []
n, pitch, rad = 7, 0.075, 0.024
span = (n-1)*pitch
for i in range(n):
    for j in range(n):
        bpy.ops.mesh.primitive_cylinder_add(radius=rad, depth=0.2, vertices=12,
                                            location=(-span/2+i*pitch, -span/2+j*pitch, ZF-T_TILES/2))
        cutters.append(bpy.context.active_object)
bpy.ops.object.select_all(action='DESELECT')
for c in cutters:
    c.select_set(True)
bpy.context.view_layer.objects.active = cutters[0]
bpy.ops.object.join()
cutter = bpy.context.view_layer.objects.active
mod = prot.modifiers.new("perf", 'BOOLEAN')
mod.operation = 'DIFFERENCE'; mod.object = cutter; mod.solver = 'EXACT'
bpy.ops.object.select_all(action='DESELECT')
prot.select_set(True); bpy.context.view_layer.objects.active = prot
bpy.ops.object.modifier_apply(modifier="perf")
bpy.data.objects.remove(cutter, do_unlink=True)

placed, ais_i = 0, 0
for a in L["aisles"]:
    if a["type"] != "cold":
        continue
    ais_i += 1
    x0, y0, x1, y1 = [v*MM for v in a["rect"]]
    for i in range(math.ceil(x0/TILE - 1e-9), math.floor(x1/TILE + 1e-9)):
        for j in range(math.ceil(y0/TILE - 1e-9), math.floor(y1/TILE + 1e-9)):
            ob = bpy.data.objects.new("PerfTile_%d_%d_%d" % (ais_i, i, j), prot.data)
            link(ob)
            ob.location = ((i+0.5)*TILE, (j+0.5)*TILE, 0.0)
            placed += 1
print("perf tile verts:", len(prot.data.vertices), "faces:", len(prot.data.polygons))
bpy.data.objects.remove(prot, do_unlink=True)
print("perf tiles:", placed)

# ---------- 4. cable trays --------------------------------------------------
mat_tray = new_mat("MatCableTray", (0.85, 0.55, 0.15))
W_TRAY, T_BOT, H_SIDE, T_SIDE = 0.3, 0.02, 0.08, 0.02
Z_BOT = TOP + 0.3
rows = {}
for r in L["racks"]:
    rows.setdefault(r["row"], []).append(r)
for name, rs in sorted(rows.items()):
    xs = [v*MM for r in rs for v in (r["center"][0]-r["size"][0]/2, r["center"][0]+r["size"][0]/2)]
    x0, x1 = min(xs), max(xs)
    ycen = sum(r["center"][1]*MM for r in rs)/len(rs)
    parts = [box("CT_base", x0, x1, ycen-W_TRAY/2, ycen+W_TRAY/2, Z_BOT, Z_BOT+T_BOT, mat_tray)]
    for sgn in (-1, 1):
        ye = ycen + sgn*W_TRAY/2
        y0_, y1_ = (ye, ye+T_SIDE) if sgn < 0 else (ye-T_SIDE, ye)
        parts.append(box("CT_rail", x0, x1, y0_, y1_, Z_BOT, Z_BOT+H_SIDE, mat_tray))
    for p in parts:
        bake(p)
    bpy.ops.object.select_all(action='DESELECT')
    for p in parts:
        p.select_set(True)
    bpy.context.view_layer.objects.active = parts[0]
    bpy.ops.object.join()
    tray = bpy.context.view_layer.objects.active
    tray.name = "CableTray_%s" % name
    mn, mx = wbbox([tray])
    print("tray", tray.name, "world", tuple(round(v,3) for v in mn), tuple(round(v,3) for v in mx))

print("objects now:", len(bpy.data.objects))
