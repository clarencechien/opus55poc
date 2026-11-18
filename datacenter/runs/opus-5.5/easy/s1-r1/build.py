import bpy

for o in list(bpy.data.objects):
    bpy.data.objects.remove(o, do_unlink=True)

H = 3.6

def box(name, x0, y0, z0, x1, y1, z1, props=None):
    bpy.ops.mesh.primitive_cube_add(size=1, location=((x0+x1)/2, (y0+y1)/2, (z0+z1)/2))
    o = bpy.context.active_object
    o.name = name
    o.data.name = name
    o.scale = (x1-x0, y1-y0, z1-z0)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    for k, v in (props or {}).items():
        o[k] = v
    return o

# Walls (200 thick, centred on grid lines A/D and 1/3)
box("Wall_S", -0.1, -0.1, 0, 14.5, 0.1, H, {"wall": "S", "thickness_mm": 200})
box("Wall_N", -0.1, 11.9, 0, 14.5, 12.1, H, {"wall": "N", "thickness_mm": 200})
box("Wall_W", -0.1, 0.1, 0, 0.1, 11.9, H, {"wall": "W", "thickness_mm": 200})
# East wall split around door D1 (centre y=9000, width 1800)
box("Wall_E_South", 14.3, 0.1, 0, 14.5, 8.1, H, {"wall": "E", "thickness_mm": 200})
box("Wall_E_North", 14.3, 9.9, 0, 14.5, 11.9, H, {"wall": "E", "thickness_mm": 200})

# Columns 600x600
for cid, (cx, cy) in {"B/2": (4.8, 6.0), "C/2": (9.6, 6.0)}.items():
    box("Column_" + cid.replace("/", "_"), cx-0.3, cy-0.3, 0, cx+0.3, cy+0.3, H, {"id": cid})

# Raised floor covering room interior, top at +0.6
box("RaisedFloor", 0.1, 0.1, 0, 14.3, 11.9, 0.6, {"height_mm": 600})

for o in bpy.data.objects:
    d = o.dimensions
    print(o.name, tuple(round(v, 3) for v in o.location), tuple(round(v, 3) for v in d))
