"""Reference S2 solution (bench exec this file): a plain but complete closed cabinet and open frame rack.
Validates the S2 checks and provides the reference rack for S3.
"""
import bpy

for o in list(bpy.data.objects):
    bpy.data.objects.remove(o)


def mat(name, rgb):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.diffuse_color = (*rgb, 1)
    m.use_nodes = True
    m.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (*rgb, 1)
    return m


BLACK, STEEL, SERVER, LED, PERF = mat("black", (0.03, 0.03, 0.035)), mat("steel", (0.25, 0.25, 0.27)), \
    mat("server", (0.12, 0.12, 0.13)), mat("led", (0.1, 0.9, 0.3)), mat("perf", (0.06, 0.06, 0.07))


def box(name, parent, x0, x1, y0, y1, z0, z1, m):
    bpy.ops.mesh.primitive_cube_add(size=1, location=((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2))
    o = bpy.context.object
    o.name = name
    o.scale = (x1 - x0, y1 - y0, z1 - z0)
    bpy.ops.object.transform_apply(scale=True)
    o.data.materials.append(m)
    o.parent = parent
    return o


def empty(name, loc=(0, 0, 0)):
    e = bpy.data.objects.new(name, None)
    e.location = loc
    bpy.context.scene.collection.objects.link(e)
    return e


def perforated_door(name, parent, x0, x1, y, z0, z1, outward):
    d = box(name, parent, x0, x1, y - 0.01, y + 0.01, z0, z1, BLACK)
    # hole pattern: thin dark slots on the outer face, built as one arrayed mesh
    t = 0.002 * outward
    slot = box(name + "_Perf", d, x0 + 0.06, x0 + 0.075, y + 0.011 * outward - 0.001, y + 0.011 * outward + 0.001 + t,
               z0 + 0.12, z1 - 0.12, PERF)
    a = slot.modifiers.new("cols", "ARRAY")
    a.count, a.relative_offset_displace = 18, (1.6, 0, 0)
    return d


# ---------- Rack A: closed cabinet 0.6 x 1.2 x 2.0 at (0, 0) ----------
A = empty("RackA")
W, D, H = 0.6, 1.2, 2.0
x0, x1, y0, y1 = -W / 2, W / 2, -D / 2, D / 2
for i, (fx, fy) in enumerate([(x0 + 0.05, y0 + 0.08), (x1 - 0.05, y0 + 0.08), (x0 + 0.05, y1 - 0.08), (x1 - 0.05, y1 - 0.08)]):
    box(f"RackA_Foot_{i + 1}", A, fx - 0.02, fx + 0.02, fy - 0.02, fy + 0.02, 0, 0.03, STEEL)
box("RackA_Base", A, x0, x1, y0 + 0.02, y1 - 0.02, 0.03, 0.10, BLACK)
box("RackA_SideL", A, x0, x0 + 0.015, y0 + 0.02, y1 - 0.02, 0.03, H - 0.02, BLACK)
box("RackA_SideR", A, x1 - 0.015, x1, y0 + 0.02, y1 - 0.02, 0.03, H - 0.02, BLACK)
top = box("RackA_Top", A, x0, x1, y0 + 0.02, y1 - 0.02, H - 0.02, H, BLACK)
for k, cy in enumerate((y0 + 0.25, y1 - 0.25)):
    box(f"RackA_CableEntry_{k + 1}", top, -0.1, 0.1, cy - 0.05, cy + 0.05, H - 0.001, H + 0.002, PERF)
for k, (rx, ry) in enumerate([(-0.24, y0 + 0.12), (0.24, y0 + 0.12), (-0.24, y1 - 0.12), (0.24, y1 - 0.12)]):
    box(f"RackA_Rail_{k + 1}", A, rx - 0.008, rx + 0.008, ry - 0.008, ry + 0.008, 0.10, H - 0.02, STEEL)
perforated_door("RackA_FrontDoor", A, x0, x1, y0 + 0.01, 0.10, H - 0.02, -1)
perforated_door("RackA_RearDoor", A, x0, x1, y1 - 0.01, 0.10, H - 0.02, 1)
U = 0.04445
z = 0.12
for k, h in enumerate([2, 1, 1, 2, 4, 2, 1, 0, 0, 2, 2, 1, 4, 0, 2, 1, 1]):
    hu = max(h, 1)
    if h == 0:
        box(f"RackA_Blank_{k}", A, -0.225, 0.225, y0 + 0.11, y0 + 0.115, z, z + U - 0.002, BLACK)
    else:
        box(f"RackA_Server_{k}", A, -0.222, 0.222, y0 + 0.11, y0 + 0.11 + 0.75, z, z + hu * U - 0.002, SERVER)
        box(f"RackA_LED_{k}", A, 0.17, 0.18, y0 + 0.105, y0 + 0.11, z + 0.01, z + 0.018, LED)
    z += hu * U

# ---------- Rack B: open 4-post frame 0.6 x 1.0 x 2.0 at (1.5, 0) ----------
B = empty("RackB")
cx, W, D = 1.5, 0.6, 1.0
x0, x1, y0, y1 = cx - W / 2, cx + W / 2, -D / 2, D / 2
for i, (px, py) in enumerate([(x0, y0), (x1, y0), (x0, y1), (x1, y1)]):
    sx = 1 if px == x0 else -1
    sy = 1 if py == y0 else -1
    box(f"RackB_Post_{i + 1}", B, min(px, px + sx * 0.04), max(px, px + sx * 0.04), min(py, py + sy * 0.04),
        max(py, py + sy * 0.04), 0, H, BLACK)
for k, zz in enumerate((0.0, H - 0.05)):
    box(f"RackB_FrameFront_{k}", B, x0, x1, y0, y0 + 0.04, zz, zz + 0.05, BLACK)
    box(f"RackB_FrameRear_{k}", B, x0, x1, y1 - 0.04, y1, zz, zz + 0.05, BLACK)
    box(f"RackB_FrameSideL_{k}", B, x0, x0 + 0.04, y0, y1, zz, zz + 0.05, BLACK)
    box(f"RackB_FrameSideR_{k}", B, x1 - 0.04, x1, y0, y1, zz, zz + 0.05, BLACK)
z = 0.3
for k, (kind, hu) in enumerate([("Patch", 1), ("CableMgr", 1), ("Patch", 1), ("CableMgr", 1), ("Switch", 1), ("Server", 2)]):
    m = {"Patch": STEEL, "CableMgr": BLACK, "Switch": SERVER, "Server": SERVER}[kind]
    box(f"RackB_{kind}_{k}", B, x0 + 0.04, x1 - 0.04, y0 + 0.02, y0 + (0.08 if kind != "Server" else 0.7), z, z + hu * U - 0.002, m)
    z += hu * U + (0.02 if kind == "CableMgr" else 0)
box("RackB_VertCableMgr", B, x1 - 0.01, x1 + 0.0, y0, y0 + 0.15, 0.05, H - 0.05, BLACK)
print("objects:", len(bpy.data.objects))
