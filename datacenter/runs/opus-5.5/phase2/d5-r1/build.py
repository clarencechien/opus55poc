import bpy, bmesh, math
from mathutils import Matrix, Vector

for o in list(bpy.data.objects):
    bpy.data.objects.remove(o, do_unlink=True)

root = bpy.data.objects.new("Target", None)
bpy.context.scene.collection.objects.link(root)

def make(name, bm):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    ob.parent = root
    return ob

def box(name, x0, x1, y0, y1, z0, z1):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    m = Matrix.Translation(((x0+x1)/2, (y0+y1)/2, (z0+z1)/2)) @ Matrix.Diagonal((x1-x0, y1-y0, z1-z0, 1))
    bmesh.ops.transform(bm, matrix=m, verts=bm.verts)
    return make(name, bm)

def cyl(name, c, r, length, axis='z', seg=32):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=seg, radius1=r, radius2=r, depth=length)
    rot = Matrix.Identity(4)
    if axis == 'x':
        rot = Matrix.Rotation(math.pi/2, 4, 'Y')
    elif axis == 'y':
        rot = Matrix.Rotation(math.pi/2, 4, 'X')
    bmesh.ops.transform(bm, matrix=Matrix.Translation(c) @ rot, verts=bm.verts)
    return make(name, bm)

# cabinet body
box("Cabinet", -0.56, 0.44, -0.57, 0.53, 0.11, 2.01)
# plinth
box("Plinth", -0.51, 0.39, -0.51, 0.51, 0.03, 0.11)
# feet (dia 60, h 30)
for i, (x, y) in enumerate([(-0.40, -0.46), (0.40, -0.46), (-0.40, 0.46), (0.40, 0.46)]):
    pass
fx = [(-0.41, -0.46), (0.39, -0.46), (-0.41, 0.46), (0.39, 0.46)]
for i, (x, y) in enumerate(fx):
    cyl("Foot%d" % i, (x, y, 0.015), 0.03, 0.03)
# door
box("Door", -0.51, 0.18, -0.59, -0.57, 0.15, 1.89)
# display
box("Display", -0.35, -0.07, -0.62, -0.59, 1.58, 1.72)
# handle: bar + standoffs
cyl("HandleBar", (0.11, -0.66, 1.11), 0.02, 0.58)
box("HandleStandoffTop", 0.09, 0.13, -0.66, -0.59, 1.32, 1.36)
box("HandleStandoffBot", 0.09, 0.13, -0.66, -0.59, 0.86, 0.90)
# control box (right side)
box("ControlBox", 0.44, 0.59, -0.37, 0.06, 0.80, 1.39)
# louvre slats (left side)
for i, zc in enumerate([1.39, 1.30, 1.21, 1.12, 1.03]):
    box("Louvre%d" % i, -0.59, -0.56, -0.11, 0.31, zc-0.02, zc+0.02)
# gland box (top)
box("GlandBox", -0.32, -0.02, 0.34, 0.49, 2.01, 2.09)
# pipe stubs on top
cyl("Pipe1", (-0.13, 0.07, 2.12), 0.05, 0.22)
cyl("Pipe2", (0.08, 0.15, 2.06), 0.05, 0.10)
cyl("Pipe3", (-0.34, -0.45, 2.12), 0.04, 0.22)
cyl("Pipe4", (0.21, -0.40, 2.06), 0.04, 0.10)
# lifting eyes: plate 100 wide, 20 thick, rect 50 high + half-disc r 50
for i, (xc, yc) in enumerate([(0.19, 0.28), (-0.20, -0.43)]):
    box("EyePlate%d" % i, xc-0.05, xc+0.05, yc-0.01, yc+0.01, 2.01, 2.06)
    bm = bmesh.new()
    seg = 16
    verts = []
    for k in range(seg+1):
        a = math.pi * k / seg
        verts.append((xc + 0.05*math.cos(a), 2.06 + 0.05*math.sin(a)))
    front = [bm.verts.new((u, yc-0.01, w)) for u, w in verts]
    back = [bm.verts.new((u, yc+0.01, w)) for u, w in verts]
    bm.faces.new(front[::-1])
    bm.faces.new(back)
    n = len(verts)
    for k in range(n):
        k2 = (k+1) % n
        bm.faces.new((front[k], front[k2], back[k2], back[k]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    make("EyeTop%d" % i, bm)
# rear manifold
cyl("ManifoldHeader", (-0.06, 0.62, 0.35), 0.04, 0.80, axis='x')
cyl("Valve1", (-0.36, 0.62, 0.35), 0.06, 0.06, axis='x')
cyl("Valve2", (-0.14, 0.62, 0.35), 0.06, 0.06, axis='x')
cyl("ManifoldConn1", (-0.41, 0.575, 0.35), 0.02, 0.09, axis='y')
cyl("ManifoldConn2", (0.29, 0.575, 0.35), 0.02, 0.09, axis='y')

# report bbox
mn = [1e9]*3; mx = [-1e9]*3
for o in root.children:
    for v in o.data.vertices:
        w = o.matrix_world @ v.co
        for j in range(3):
            mn[j] = min(mn[j], w[j]); mx[j] = max(mx[j], w[j])
print("bbox", [round(a, 4) for a in mn], [round(a, 4) for a in mx])
print("tris", sum(sum(len(p.vertices)-2 for p in o.data.polygons) for o in root.children))
