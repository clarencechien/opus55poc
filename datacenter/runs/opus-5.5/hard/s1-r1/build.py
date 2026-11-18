import bpy, bmesh

# clear scene
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o, do_unlink=True)
for m in list(bpy.data.meshes):
    bpy.data.meshes.remove(m)

H = 3.6  # raised floor 0.6 + clear height 3.0


def prism(name, pts, z0, z1, props=None):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bot = [bm.verts.new((x, y, z0)) for x, y in pts]
    top = [bm.verts.new((x, y, z1)) for x, y in pts]
    n = len(pts)
    bm.faces.new(list(reversed(bot)))
    bm.faces.new(top)
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new([bot[i], bot[j], top[j], top[i]])
    bm.normal_update()
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    # set origin to bbox centre (x,y) and z0
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
    cx = (min(xs) + max(xs)) / 2; cy = (min(ys) + max(ys)) / 2
    me.transform(mathutils.Matrix.Translation((-cx, -cy, -z0)))
    ob.location = (cx, cy, z0)
    for k, v in (props or {}).items():
        ob[k] = v
    return ob


def box(name, x0, y0, x1, y1, z0, z1, props=None):
    return prism(name, [(x0, y0), (x1, y0), (x1, y1), (x0, y1)], z0, z1, props)


walls = [
    ("Wall_S_1", -0.1, -0.1, 8.1, 0.1, "S"),
    ("Wall_S_2", 9.9, -0.1, 25.3, 0.1, "S"),
    ("Wall_N", -0.1, 18.8, 25.3, 19.0, "N"),
    ("Wall_W", -0.1, 0.1, 0.1, 18.8, "W"),
    ("Wall_E", 25.1, 0.1, 25.3, 18.8, "E"),
    ("Wall_UPS_W", 18.8, 12.5, 19.0, 18.8, "UPS"),
    ("Wall_UPS_S_1", 19.0, 12.5, 21.45, 12.7, "UPS"),
    ("Wall_UPS_S_2", 22.65, 12.5, 25.1, 12.7, "UPS"),
]
for n, x0, y0, x1, y1, side in walls:
    box(n, x0, y0, x1, y1, 0.0, H, {"side": side, "thickness_mm": 200})

cols = {"B/2": (6.3, 6.3), "C/2": (12.6, 6.3), "D/2": (18.9, 6.3),
        "B/3": (6.3, 12.6), "C/3": (12.6, 12.6)}
for cid, (cx, cy) in cols.items():
    box("Column_" + cid.replace("/", "_"), cx - 0.3, cy - 0.3, cx + 0.3, cy + 0.3, 0.0, H,
        {"id": cid})

poly = [(0.1, 0.1), (25.1, 0.1), (25.1, 12.5), (18.8, 12.5), (18.8, 18.8), (0.1, 18.8)]
prism("RaisedFloor", poly, 0.0, 0.6, {"height_mm": 600})

for o in bpy.data.objects:
    print(o.name, tuple(round(v, 3) for v in o.location), tuple(round(v, 3) for v in o.dimensions))
