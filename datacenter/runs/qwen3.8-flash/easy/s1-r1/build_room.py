import bpy

def box(name, x0, x1, y0, y1, z0, z1):
    bpy.ops.mesh.primitive_cube_add(size=1)
    o = bpy.context.active_object
    o.name = name
    o.scale = ((x1 - x0), (y1 - y0), (z1 - z0))
    o.location = ((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2)
    bpy.ops.object.transform_apply(scale=True)
    return o

M = 0.001  # mm -> m
H = (600 + 3000) * M   # wall top = 3.6 m

# ---- Walls (centrelines on grid lines, 200 thick) ----
# South wall: spans full outer width
box("Wall_S", -100*M, 14500*M, -100*M, 100*M, 0, H)
# North wall
box("Wall_N", -100*M, 14500*M, 11900*M, 12000*M, 0, H)
# West wall
box("Wall_W", -100*M, 100*M, 100*M, 11900*M, 0, H)
# East wall with door opening D1: centre (14400, 9000), width 1800 -> opening y 8100..9900, height 2100
box("Wall_E_S", 14300*M, 14500*M, 100*M, 8100*M, 0, H)
box("Wall_E_N", 14300*M, 14500*M, 9900*M, 11900*M, 0, H)
box("Wall_E_Lintel", 14300*M, 14500*M, 8100*M, 9900*M, 2100*M, H)

# ---- Columns ----
for cid, (cx, cy) in {"B_2": (4800, 6000), "C_2": (9600, 6000)}.items():
    box("Column_" + cid, (cx-300)*M, (cx+300)*M, (cy-300)*M, (cy+300)*M, 0, H)

# ---- Raised floor (interior, top at 0.6) ----
box("RaisedFloor", 100*M, 14300*M, 100*M, 11900*M, 0, 600*M)

print("built:", [o.name for o in bpy.data.objects])
