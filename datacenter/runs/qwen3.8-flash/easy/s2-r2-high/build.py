import bpy, bmesh, math
from mathutils import Vector, Matrix

scene = bpy.context.scene

# clean scene
for o in list(scene.objects):
    bpy.data.objects.remove(o, do_unlink=True)
for m in list(bpy.data.meshes):
    bpy.data.meshes.remove(m)

# ---------------- materials ----------------
def mkmat(name, col, rough=0.6, metal=0.0, emit=None, estr=1.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes.get("Principled BSDF")
    b.inputs["Base Color"].default_value = (*col, 1)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    if emit:
        b.inputs["Emission Color"].default_value = (*emit, 1)
        b.inputs["Emission Strength"].default_value = estr
    m.diffuse_color = (*col, 1)
    return m

MAT_FRAME   = mkmat("RackBlack",   (0.018, 0.018, 0.022), 0.55, 0.4)
MAT_PANEL   = mkmat("PanelBlack",  (0.022, 0.022, 0.026), 0.5, 0.3)
MAT_DOOR    = mkmat("DoorBlack",   (0.030, 0.030, 0.035), 0.45, 0.5)
MAT_SERVER  = mkmat("ServerBlack", (0.035, 0.035, 0.040), 0.4, 0.4)
MAT_BEZEL   = mkmat("Bezel",       (0.11, 0.11, 0.13),   0.35, 0.3)
MAT_BLANK   = mkmat("BlankBlack",  (0.012, 0.012, 0.014), 0.7, 0.1)
MAT_RAIL    = mkmat("RailGray",    (0.10, 0.10, 0.11),   0.5, 0.5)
MAT_MGR     = mkmat("MgrGray",     (0.45, 0.46, 0.47),   0.5, 0.3)
MAT_LED_G   = mkmat("LedGreen",    (0.1, 1.0, 0.2), 0.3, emit=(0.1, 1.0, 0.15), estr=4.0)
MAT_LED_B   = mkmat("LedBlue",     (0.1, 0.4, 1.0), 0.3, emit=(0.1, 0.35, 1.0), estr=4.0)
MAT_LED_A   = mkmat("LedAmber",    (1.0, 0.5, 0.05), 0.3, emit=(1.0, 0.45, 0.05), estr=3.0)
MAT_CAB_B   = mkmat("CableBlue",   (0.05, 0.12, 0.45), 0.5)
MAT_CAB_LB  = mkmat("CableLtBlue", (0.35, 0.65, 0.85), 0.5)
MAT_CAB_K   = mkmat("CableBlack",  (0.02, 0.02, 0.02), 0.6)
MAT_PORT    = mkmat("PortSilver",  (0.55, 0.55, 0.55), 0.4, 0.6)

# ---------------- helpers ----------------
def add_box(bm, c, d, mi=0):
    ret = bmesh.ops.create_cube(bm, size=1.0)
    vs = ret['verts']
    bmesh.ops.transform(bm, matrix=Matrix.Diagonal((d[0], d[1], d[2], 1.0)), verts=vs)
    bmesh.ops.translate(bm, vec=Vector(c), verts=vs)
    faces = set()
    for v in vs:
        faces.update(v.link_faces)
    for f in faces:
        f.material_index = mi
    return vs

def add_cyl(bm, c, r, h, segs=12, mi=0):
    ret = bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=segs,
                                radius1=r, radius2=r, depth=h)
    vs = ret['verts']
    bmesh.ops.translate(bm, vec=Vector(c), verts=vs)
    faces = set()
    for v in vs:
        faces.update(v.link_faces)
    for f in faces:
        f.material_index = mi

def finish(name, bm, parent, mats, loc=(0, 0, 0)):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me); bm.free()
    for m in mats:
        me.materials.append(m)
    o = bpy.data.objects.new(name, me)
    scene.collection.objects.link(o)
    o.location = loc
    if parent:
        o.parent = parent
        o.matrix_parent_inverse = parent.matrix_world.inverted()
    return o

def empty(name, loc):
    e = bpy.data.objects.new(name, None)
    scene.collection.objects.link(e)
    e.location = loc
    return e

def catmull(pts, steps):
    P = [pts[0]] + list(pts) + [pts[-1]]
    out = []
    for i in range(1, len(P) - 2):
        p0, p1, p2, p3 = P[i-1], P[i], P[i+1], P[i+2]
        for t in range(steps):
            s = t / steps
            out.append(0.5 * ((2*p1) + (-p0+p2)*s + (2*p0-5*p1+4*p2-p3)*s*s +
                              (-p0+3*p1-3*p2+p3)*s*s*s))
    out.append(pts[-1])
    return out

def add_tube(bm, pts, r, segs=6, steps=6, mi=0):
    path = catmull([Vector(p) for p in pts], steps)
    n = len(path)
    rings = []
    nn = Vector((0, 0, 1))
    d0 = (path[1] - path[0]).normalized()
    if abs(nn.dot(d0)) > 0.95:
        nn = Vector((1, 0, 0))
    nn = (nn - d0 * nn.dot(d0)).normalized()
    for i in range(n):
        if i == 0:
            d = (path[1] - path[0]).normalized()
        elif i == n - 1:
            d = (path[-1] - path[-2]).normalized()
        else:
            d = (path[i+1] - path[i-1]).normalized()
        nn = (nn - d * nn.dot(d)).normalized()
        bb = d.cross(nn)
        ring = []
        for k in range(segs):
            a = 2 * math.pi * k / segs
            ring.append(bm.verts.new(path[i] + nn * math.cos(a) * r + bb * math.sin(a) * r))
        rings.append(ring)
    start = len(bm.faces)
    for i in range(n - 1):
        for k in range(segs):
            k2 = (k + 1) % segs
            bm.faces.new((rings[i][k], rings[i][k2], rings[i+1][k2], rings[i+1][k]))
    c0 = bm.verts.new(path[0]); c1 = bm.verts.new(path[-1])
    for k in range(segs):
        k2 = (k + 1) % segs
        bm.faces.new((c0, rings[0][k2], rings[0][k]))
        bm.faces.new((c1, rings[-1][k], rings[-1][k2]))
    for f in bm.faces[start:]:
        f.material_index = mi

# =====================================================================
# RACK A - closed server cabinet, 0.6 x 1.2 x 2.0, centre (0,0), front -y
# =====================================================================
RA = empty("RackA", (0, 0, 0))
bpy.context.view_layer.update()

# --- leveling feet ---
bm = bmesh.new()
for sx in (-1, 1):
    for sy in (-1, 1):
        add_cyl(bm, (sx * 0.25, sy * 0.52, 0.025), 0.028, 0.05, 12)
        add_box(bm, (sx * 0.25, sy * 0.52, 0.055), (0.09, 0.09, 0.02))
finish("RackA_Feet", bm, RA, [MAT_FRAME])

# --- frame: plinth, corner posts, top frame ---
bm = bmesh.new()
add_box(bm, (0, 0, 0.09), (0.58, 1.18, 0.06))
for sx in (-1, 1):
    for sy in (-1, 1):
        add_box(bm, (sx * 0.27, sy * 0.56, 1.02), (0.04, 0.04, 1.80))
add_box(bm, (0, -0.56, 1.96), (0.60, 0.04, 0.08))
add_box(bm, (0,  0.56, 1.96), (0.60, 0.04, 0.08))
add_box(bm, (-0.28, 0, 1.96), (0.04, 1.16, 0.08))
add_box(bm, ( 0.28, 0, 1.96), (0.04, 1.16, 0.08))
finish("RackA_Frame", bm, RA, [MAT_FRAME])

# --- solid side panels ---
bm = bmesh.new()
add_box(bm, (-0.294, 0, 1.05), (0.012, 1.14, 1.84))
add_box(bm, ( 0.294, 0, 1.05), (0.012, 1.14, 1.84))
finish("RackA_SidePanels", bm, RA, [MAT_PANEL])

# --- top panel with two cable-entry openings ---
bm = bmesh.new()
z = 1.99
add_box(bm, (-0.24, 0, z), (0.12, 1.16, 0.02))
add_box(bm, ( 0.24, 0, z), (0.12, 1.16, 0.02))
add_box(bm, (0, -0.45, z), (0.36, 0.26, 0.02))
add_box(bm, (0,  0.00, z), (0.36, 0.24, 0.02))
add_box(bm, (0,  0.45, z), (0.36, 0.26, 0.02))
for oy in (-0.20, 0.20):
    add_box(bm, (0, oy - 0.135, 1.988), (0.36, 0.03, 0.012))
    add_box(bm, (0, oy + 0.135, 1.988), (0.36, 0.03, 0.012))
    add_box(bm, (-0.18, oy, 1.988), (0.03, 0.30, 0.012))
    add_box(bm, ( 0.18, oy, 1.988), (0.03, 0.30, 0.012))
finish("RackA_TopPanel", bm, RA, [MAT_PANEL])

# --- interior liner (dark) ---
bm = bmesh.new()
add_box(bm, (0, 0.55, 1.05), (0.55, 0.01, 1.84))
add_box(bm, (0, 0, 0.13), (0.55, 1.05, 0.01))
finish("RackA_Interior", bm, RA, [MAT_BLANK])

# --- 19" mounting rails ---
bm = bmesh.new()
for ry in (-0.42, 0.42):
    for sx in (-1, 1):
        add_box(bm, (sx * 0.2475, ry, 1.06), (0.015, 0.03, 1.867))
        for j in range(42):
            zz = 0.132 + j * 0.04445
            add_box(bm, (sx * 0.2385, ry, zz), (0.004, 0.012, 0.006))
finish("RackA_Rails", bm, RA, [MAT_RAIL])

# --- servers / blanks ---
U = 0.04445
Z0 = 0.13
def server_obj(idx, ustart, usize, kind="server", led="g"):
    bm = bmesh.new()
    zb = Z0 + ustart * U
    hgt = usize * U - 0.004
    zc = zb + hgt / 2
    if kind == "server":
        add_box(bm, (0, 0.05, zc), (0.483, 0.60, hgt), 0)
        add_box(bm, (0, -0.262, zc), (0.483, 0.024, hgt * 0.92), 1)
        for k in range(6):
            add_box(bm, (-0.20 + k * 0.036, -0.274, zc), (0.03, 0.004, hgt * 0.5), 2)
        for k in range(6):
            add_box(bm, (0.03 + k * 0.024, -0.275, zc), (0.006, 0.004, 0.005), 3 if k % 4 else 4)
        add_box(bm, (0.20, -0.275, zc), (0.008, 0.004, 0.006), 3)
        add_box(bm, (0.215, -0.275, zc), (0.008, 0.004, 0.006), 4)
        if usize >= 2:
            add_box(bm, (-0.20, -0.275, zc), (0.05, 0.004, hgt * 0.35), 2)
    else:
        add_box(bm, (0, -0.268, zc), (0.483, 0.012, hgt), 0)
    lm = [MAT_SERVER, MAT_BEZEL, MAT_BLANK, MAT_LED_G, MAT_LED_B]
    if led == "a":
        lm[3] = MAT_LED_A
    return finish(f"RackA_Server_{idx:02d}", bm, RA, lm)

layout = [
    (0, 4, "server"), (4, 1, "server"), (5, 1, "server"), (6, 1, "blank"),
    (7, 2, "server"), (9, 4, "server"), (13, 1, "blank"), (14, 1, "server"),
    (15, 2, "server"), (17, 1, "blank"), (18, 1, "server"), (19, 4, "server"),
    (23, 2, "server"), (25, 2, "blank"), (27, 1, "server"), (28, 1, "server"),
    (29, 1, "blank"), (30, 2, "server"), (32, 4, "server"), (36, 1, "blank"),
    (37, 1, "server"), (38, 2, "server"), (40, 1, "blank"), (41, 1, "server"),
]
for i, (us, uz, kd) in enumerate(layout):
    server_obj(i, us, uz, kd, led="a" if i % 5 == 0 else "g")

# --- perforated doors ---
def door(name, y, hinge_side):
    bm = bmesh.new()
    w, h = 0.56, 1.86
    zc = 0.12 + h / 2
    bw = 0.05
    add_box(bm, (0, 0, zc + h/2 - bw/2), (w, 0.03, bw), 0)
    add_box(bm, (0, 0, zc - h/2 + bw/2), (w, 0.03, bw), 0)
    add_box(bm, (-w/2 + bw/2, 0, zc), (bw, 0.03, h - 2*bw), 0)
    add_box(bm, ( w/2 - bw/2, 0, zc), (bw, 0.03, h - 2*bw), 0)
    gw, gh = w - 2*bw, h - 2*bw
    nv = int(gw / 0.016); nh = int(gh / 0.016)
    x0 = -(nv - 1) * 0.016 / 2
    zz0 = zc - (nh - 1) * 0.016 / 2
    for i in range(nv):
        add_box(bm, (x0 + i * 0.016, 0, zc), (0.005, 0.008, gh), 1)
    for j in range(nh):
        add_box(bm, (0, 0, zz0 + j * 0.016), (gw, 0.008, 0.005), 1)
    hx = hinge_side * (w/2 - 0.09)
    inward = 1 if y < 0 else -1
    add_box(bm, (hx, 0.022 * inward, zc), (0.02, 0.02, 0.30), 0)   # flush handle bar (inner side)
    add_box(bm, (hx - hinge_side*0.02, 0.02 * inward, zc + 0.12), (0.03, 0.02, 0.02), 0)
    add_box(bm, (hx - hinge_side*0.02, 0.02 * inward, zc - 0.12), (0.03, 0.02, 0.02), 0)
    for zz in (zc - h/2 + 0.08, zc + h/2 - 0.08):
        add_box(bm, (-hx, 0.005 * inward, zz), (0.03, 0.04, 0.06), 0)
    return finish(name, bm, RA, [MAT_DOOR, MAT_DOOR], loc=(0, y, 0))

door("RackA_FrontDoor", -0.585, 1)
door("RackA_RearDoor",  0.585, -1)

# =====================================================================
# RACK B - open 4-post frame, 0.6 x 1.0 x 2.0, centre (1.5, 0)
# =====================================================================
RB = empty("RackB", (1.5, 0, 0))
bpy.context.view_layer.update()
CX = 1.5

bm = bmesh.new()
add_box(bm, (CX, 0, 0.01), (0.60, 1.00, 0.02))
finish("RackB_BasePlate", bm, RB, [MAT_FRAME])

post_pos = {"1": (CX - 0.28, -0.48), "2": (CX + 0.28, -0.48),
            "3": (CX + 0.28,  0.48), "4": (CX - 0.28,  0.48)}
for k, (px, py) in post_pos.items():
    bm = bmesh.new()
    add_box(bm, (px, py, 1.00), (0.04, 0.04, 1.96))
    for j in range(46):
        zz = 0.08 + j * 0.042
        if py < 0:
            add_box(bm, (px, py + 0.021, zz), (0.02, 0.004, 0.012), 1)
        else:
            add_box(bm, (px, py - 0.021, zz), (0.02, 0.004, 0.012), 1)
    finish(f"RackB_Post_{k}", bm, RB, [MAT_FRAME, MAT_RAIL])

bm = bmesh.new()
for zz in (0.05, 1.95):
    for sy in (-0.48, 0.48):
        add_box(bm, (CX, sy, zz), (0.56, 0.04, 0.04))
    for sx in (CX - 0.28, CX + 0.28):
        add_box(bm, (sx, 0, zz), (0.04, 0.92, 0.04))
finish("RackB_Frame", bm, RB, [MAT_FRAME])

bm = bmesh.new()
for ry in (-0.40, 0.40):
    for sx in (-1, 1):
        rx = CX + sx * 0.24
        add_box(bm, (rx, ry, 1.00), (0.03, 0.008, 1.86), 0)
        for j in range(42):
            zz = 0.13 + j * 0.04445
            add_box(bm, (rx, ry - sx * 0.006, zz), (0.012, 0.004, 0.008), 1)
finish("RackB_Rails", bm, RB, [MAT_RAIL, MAT_FRAME])

bm = bmesh.new()
for mz in (0.42, 0.72, 1.02, 1.32, 1.62):
    add_box(bm, (CX, -0.46, mz), (0.52, 0.07, 0.012), 0)
    for i in range(9):
        fx = CX - 0.24 + i * 0.06
        add_box(bm, (fx, -0.46, mz + 0.03), (0.012, 0.06, 0.05), 1)
vx = CX + 0.20
add_box(bm, (vx, 0.44, 1.00), (0.05, 0.01, 1.80), 1)
add_box(bm, (vx - 0.03, 0.40, 1.00), (0.008, 0.08, 1.80), 1)
add_box(bm, (vx + 0.03, 0.40, 1.00), (0.008, 0.08, 1.80), 1)
for j in range(7):
    zz = 0.25 + j * 0.25
    add_box(bm, (vx, 0.40, zz), (0.05, 0.06, 0.01), 0)
finish("RackB_CableMgmt", bm, RB, [MAT_MGR, MAT_FRAME])

Z0B = 0.13
def rackB_unit(idx, ustart, usize, kind):
    bm = bmesh.new()
    zb = Z0B + ustart * U
    hgt = usize * U - 0.004
    zc = zb + hgt / 2
    if kind == "server":
        add_box(bm, (CX, 0.02, zc), (0.483, 0.55, hgt), 0)
        add_box(bm, (CX, -0.27, zc), (0.483, 0.02, hgt * 0.9), 1)
        add_box(bm, (CX + 0.19, -0.281, zc), (0.008, 0.004, 0.006), 3)
        add_box(bm, (CX + 0.205, -0.281, zc), (0.008, 0.004, 0.006), 4)
        if usize >= 2:
            add_box(bm, (CX - 0.15, -0.281, zc), (0.12, 0.004, hgt * 0.4), 2)
        mats = [MAT_SERVER, MAT_BEZEL, MAT_BLANK, MAT_LED_G, MAT_LED_B]
    elif kind == "patch":
        add_box(bm, (CX, -0.27, zc), (0.483, 0.03, hgt), 0)
        for i in range(12):
            add_box(bm, (CX - 0.22 + i * 0.04, -0.286, zc), (0.014, 0.006, 0.012), 1)
        mats = [MAT_BLANK, MAT_PORT]
    else:
        add_box(bm, (CX, -0.27, zc), (0.483, 0.012, hgt), 0)
        mats = [MAT_BLANK]
    return finish(f"RackB_Unit_{idx:02d}", bm, RB, mats)

rackB_unit(0, 2, 1, "server")
rackB_unit(1, 3, 1, "server")
rackB_unit(2, 6, 2, "server")
rackB_unit(3, 10, 4, "server")
rackB_unit(4, 16, 1, "patch")
rackB_unit(5, 22, 1, "blank")
rackB_unit(6, 26, 2, "server")
rackB_unit(7, 30, 1, "patch")
rackB_unit(8, 34, 1, "server")
rackB_unit(9, 38, 2, "blank")

bm = bmesh.new()
import random
rng = random.Random(7)
for i in range(5):
    x = CX - 0.24 + rng.uniform(-0.015, 0.015)
    y = 0.36 + rng.uniform(-0.03, 0.03)
    pts = [(x, y, 1.92), (x + rng.uniform(-0.03, 0.03), y - 0.02, 1.5),
           (x + rng.uniform(-0.03, 0.03), y + 0.02, 0.9),
           (x, y - 0.02, 0.35), (x, y + 0.05, 0.05)]
    add_tube(bm, pts, 0.006, segs=6, steps=8, mi=0)
for i in range(4):
    x0 = CX - 0.10 + i * 0.04
    pts = [(x0, -0.29, Z0B + 31 * U), (x0 - 0.02, -0.315, 1.1),
           (x0 - 0.05, -0.345, 0.7), (x0 - 0.06, -0.32, 0.3),
           (x0 - 0.05, -0.28, Z0B + 17 * U)]
    add_tube(bm, pts, 0.004, segs=6, steps=8, mi=1)
for i in range(3):
    x = CX - 0.15 + i * 0.15
    pts = [(x, 0.40, 0.5), (x + 0.02, 0.45, 0.25), (x, 0.42, 0.04)]
    add_tube(bm, pts, 0.005, segs=6, steps=6, mi=2)
finish("RackB_Cables", bm, RB, [MAT_CAB_B, MAT_CAB_LB, MAT_CAB_K])

bm = bmesh.new()
add_box(bm, (CX, 0, 1.975), (0.20, 1.00, 0.02))
add_box(bm, (CX - 0.10, 0, 1.99), (0.008, 1.00, 0.02))
add_box(bm, (CX + 0.10, 0, 1.99), (0.008, 1.00, 0.02))
finish("RackB_TopTray", bm, RB, [MAT_FRAME])

# ---------------- report ----------------
def tri_count(root):
    tot = 0
    for o in root.children_recursive:
        if o.type == 'MESH':
            for p in o.data.polygons:
                tot += len(p.vertices) - 2
    return tot

print("RackA tris:", tri_count(RA))
print("RackB tris:", tri_count(RB))
print("objects:", len(scene.objects))
