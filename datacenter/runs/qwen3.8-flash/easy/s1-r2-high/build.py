import bpy, math

# ---- clear scene ----
for ob in list(bpy.data.objects):
    bpy.data.objects.remove(ob, do_unlink=True)
for coll in (bpy.data.meshes, bpy.data.curves, bpy.data.materials):
    for d in list(coll):
        if d.users == 0:
            coll.remove(d)

S = 0.001  # mm -> m
RF = 600 * S          # raised floor height 0.6
CH = 3000 * S         # clear height
TOP = RF + CH         # 3.6 m wall top

def box(name, x0, x1, y0, y1, z0, z1):
    bpy.ops.mesh.primitive_cube_add(size=1)
    ob = bpy.context.active_object
    ob.name = name
    ob.scale = ((x1-x0), (y1-y0), (z1-z0))
    ob.location = ((x0+x1)/2, (y0+y1)/2, (z0+z1)/2)
    bpy.ops.object.transform_apply(scale=True, location=True)
    return ob

# ---------------- walls (200 thick, centrelines on grid) ----------------
wt = 200 * S          # 0.2
h = wt / 2
xmin, xmax = -h, 14.4 + h          # outer faces of N/S walls
ymin, ymax = -h, 12.0 + h
iymin, iymax = h, 12.0 - h         # inner faces of W/E walls

box('Wall_S', xmin, xmax, ymin, h, 0, TOP)
box('Wall_N', xmin, xmax, 12.0 - h, ymax, 0, TOP)
box('Wall_W', xmin, h, iymin, iymax, 0, TOP)

# East wall with 1800 door opening centred y=9000, opening 0..2400 high
d0, d1 = (9000 - 900) * S, (9000 + 900) * S
dh = 2400 * S
ex0, ex1 = 14.4 - h, 14.4 + h
w1 = box('Wall_E', ex0, ex1, iymin, d0, 0, TOP)
w2 = box('Wall_E_seg2', ex0, ex1, d1, iymax, 0, TOP)
w3 = box('Wall_E_lintel', ex0, ex1, d0, d1, dh, TOP)
for o in (w2, w3):
    o.select_set(True)
w1.select_set(True)
bpy.context.view_layer.objects.active = w1
bpy.ops.object.join()
bpy.ops.object.transform_apply(scale=True, location=True)

# ---------------- columns 600 x 600 ----------------
for cid, cx, cy in (('B_2', 4800, 6000), ('C_2', 9600, 6000)):
    s = 600 * S / 2
    box('Column_' + cid, cx*S - s, cx*S + s, cy*S - s, cy*S + s, 0, TOP)

# ---------------- raised floor ----------------
box('RaisedFloor', 100*S, 14300*S, 100*S, 11900*S, 0, RF)

print('objects:')
for ob in bpy.data.objects:
    bb = [ob.matrix_world @ mathutils.Vector(c) for c in ob.bound_box]
    xs = [v.x for v in bb]; ys = [v.y for v in bb]; zs = [v.z for v in bb]
    print('  %-14s x %.3f..%.3f  y %.3f..%.3f  z %.3f..%.3f' %
          (ob.name, min(xs), max(xs), min(ys), max(ys), min(zs), max(zs)))
