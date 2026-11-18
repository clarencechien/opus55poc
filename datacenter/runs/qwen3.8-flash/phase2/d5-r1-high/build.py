import bpy, bmesh, math
from mathutils import Matrix, Vector

MM = 0.001
S = bpy.context.scene
for o in list(S.objects):
    bpy.data.objects.remove(o, do_unlink=True)
for m in list(bpy.data.meshes):
    bpy.data.meshes.remove(m)

root = bpy.data.objects.new("Target", None)
S.collection.objects.link(root)
parts = []

def link(name, me):
    me.validate()
    bm = bmesh.new(); bm.from_mesh(me)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new(name, me)
    S.collection.objects.link(ob)
    ob.parent = root
    ob.matrix_parent_inverse = Matrix.Identity(4)
    parts.append(ob)
    return ob

def box(name, x0, x1, y0, y1, z0, z1):
    me = bpy.data.meshes.new(name)
    v = [(a*MM,b*MM,c*MM) for (a,b,c) in [
        (x0,y0,z0),(x1,y0,z0),(x1,y1,z0),(x0,y1,z0),
        (x0,y0,z1),(x1,y0,z1),(x1,y1,z1),(x0,y1,z1)]]
    f = [(0,1,2,3),(7,6,5,4),(0,4,5,1),(1,5,6,2),(2,6,7,3),(3,7,4,0)]
    me.from_pydata(v, [], f)
    return link(name, me)

def cyl(name, r, a, b, s0, s1, axis, seg=24):
    me = bpy.data.meshes.new(name); R = r*MM
    A = MM*a; B = MM*b; S0 = MM*s0; S1 = MM*s1
    vs = []
    for s in (S0, S1):
        for i in range(seg):
            t = 2*math.pi*i/seg
            u = R*math.cos(t); w = R*math.sin(t)
            if axis == 'z':   vs.append((A+u, B+w, s))
            elif axis == 'x': vs.append((s, A+u, B+w))
            else:             vs.append((A+u, s, B+w))
    if axis == 'z':   c0 = (A, B, S0); c1 = (A, B, S1)
    elif axis == 'x': c0 = (S0, A, B); c1 = (S1, A, B)
    else:             c0 = (A, S0, B); c1 = (A, S1, B)
    vs += [c0, c1]
    n = 2*seg; fs = []
    for i in range(seg):
        j = (i+1) % seg
        fs.append((j, i, n)); fs.append((seg+i, seg+j, n+1)); fs.append((i, j, seg+j, seg+i))
    me.from_pydata(vs, [], fs)
    return link(name, me)

def prism(name, prof, y0, y1):
    me = bpy.data.meshes.new(name)
    n = len(prof)
    vs = [(p[0]*MM, y0*MM, p[1]*MM) for p in prof] + [(p[0]*MM, y1*MM, p[1]*MM) for p in prof]
    fs = [tuple(range(n-1,-1,-1)), tuple(range(n, 2*n))]
    for i in range(n):
        j = (i+1) % n
        fs.append((i, j, j+n, i+n))
    me.from_pydata(vs, [], fs)
    return link(name, me)

# ---- cabinet body
box("Cabinet", -560, 440, -570, 530, 111, 2011)
# ---- plinth
box("Plinth", -511, 389, -509, 511, 31, 111)
# ---- feet
for k,(a,b) in enumerate([(x,y) for x in [(-489,-433),(311,367)] for y in [(430,490),(-490,-430)]]):
    box("Foot%d"%(k+1), a[0], a[1], b[0], b[1], 0, 33)
# ---- door
box("Door", -511, 179, -590, -565, 151, 1891)
# ---- display
box("Display", -353, -67, -621, -585, 1582, 1720)
# ---- door handle (bar z 820..1402, dia 41, y -639..-681 ; mounts y -592..-660)
cyl("HandleBar", 20.5, 109, -660, 820, 1402, 'z', 20)
box("HandleMount1", 92, 127, -662, -585, 1322, 1360)
box("HandleMount2", 92, 127, -662, -585, 862, 902)
# ---- control box
box("ControlBox", -321, -21, 341, 491, 2000, 2091)
# ---- pipe stubs on top
cyl("PipeA", 40, -341, -449, 2000, 2230, 'z', 24)
cyl("PipeB", 50, -131,   71, 2000, 2230, 'z', 24)
cyl("PipeC", 50,   79,  151, 2000, 2111, 'z', 24)
cyl("PipeD", 40,  209, -399, 2000, 2111, 'z', 24)
# ---- rear manifold with valves
cyl("Manifold", 40, 620, 351, -460, 340, 'x', 24)
cyl("Valve1", 62, 620, 351, -391, -329, 'x', 24)
cyl("Valve2", 62, 620, 351, -171, -109, 'x', 24)
cyl("Stub1", 20, -411, 351, 512, 624, 'y', 16)
cyl("Stub2", 20,  289, 351, 512, 624, 'y', 16)
# ---- louvre
for i,(z0,z1) in enumerate([(1011,1051),(1101,1141),(1191,1231),(1281,1321),(1371,1411)]):
    box("Louvre%d"%(i+1), -590, -550, -110, 311, z0, z1)
# ---- lifting eyes
def eye(cx, cy, hw, name):
    p = [(hw,2011),(-hw,2011),(-hw,2061)]
    for k in range(1,12):
        t = math.pi - math.pi*k/12
        p.append((hw*math.cos(t), 2061 + 50*math.sin(t)))
    p.append((hw,2061))
    p = [(x+cx, z) for (x,z) in p]
    return prism(name, p, cy-11, cy+11)
eye(-201, -430, 51, "Eye1")
eye( 189,  280, 50, "Eye2")
# ---- gland box
box("GlandBox", 438, 590, -367, 59, 800, 1390)

bpy.ops.object.select_all(action='DESELECT')
dg = bpy.context.evaluated_depsgraph_get()
tri = 0
for o in parts:
    ev = o.evaluated_get(dg); me = ev.to_mesh()
    tri += sum(len(p.vertices)-2 for p in me.polygons)
    ev.to_mesh_clear()
mn=[1e9]*3; mx=[-1e9]*3
for o in parts:
    ev = o.evaluated_get(dg)
    for c in ev.bound_box:
        w = ev.matrix_world @ Vector(c)
        for i in range(3):
            mn[i]=min(mn[i],w[i]); mx[i]=max(mx[i],w[i])
print("parts:", len(parts), "tris:", tri)
print("bbox mm:", [round(v*1000,1) for v in mn], [round(v*1000,1) for v in mx])
vol = 0
import numpy as np
for o in parts:
    bm = bmesh.new(); bm.from_mesh(o.data)
    vol += bm.calc_volume(signed=True)
    bm.free()
print("sum part volume m3 (overlaps counted twice):", round(vol,3))
