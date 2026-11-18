import bpy
S = bpy.context.scene
o = S.objects.get("HandleBar")
me = o.data
# rebuild handle bar & mounts with corrected geometry
import math
from mathutils import Matrix
def kill(n):
    ob = S.objects.get(n)
    if ob:
        m = ob.data
        S.objects.remove(ob, do_unlink=True)
        bpy.data.meshes.remove(m)
for n in ("HandleBar","HandleMount1","HandleMount2"):
    kill(n)

MM=0.001
parts=[]
root = S.objects["Target"]
def link(name, me):
    me.validate()
    import bmesh
    bm=bmesh.new(); bm.from_mesh(me); bmesh.ops.recalc_face_normals(bm,faces=bm.faces); bm.to_mesh(me); bm.free()
    ob=bpy.data.objects.new(name, me); S.collection.objects.link(ob)
    ob.parent=root; ob.matrix_parent_inverse=Matrix.Identity(4)
    return ob

def cyl(name, r, a, b, s0, s1, axis, seg=20):
    me = bpy.data.meshes.new(name); R=r*MM; A=MM*a; B=MM*b; S0=MM*s0; S1=MM*s1
    vs=[]
    for s in (S0,S1):
        for i in range(seg):
            t=2*math.pi*i/seg; u=R*math.cos(t); w=R*math.sin(t)
            if axis=='z': vs.append((A+u,B+w,s))
            elif axis=='x': vs.append((s,A+u,B+w))
            else: vs.append((A+u,s,B+w))
    if axis=='z': c0=(A,B,S0); c1=(A,B,S1)
    elif axis=='x': c0=(S0,A,B); c1=(S1,A,B)
    else: c0=(A,S0,B); c1=(A,S1,B)
    vs+= [c0,c1]; n=2*seg; fs=[]
    for i in range(seg):
        j=(i+1)%seg
        fs.append((j,i,n)); fs.append((seg+i,seg+j,n+1)); fs.append((i,j,seg+j,seg+i))
    me.from_pydata(vs,[],fs); return link(name,me)

def box(name, x0,x1,y0,y1,z0,z1):
    me=bpy.data.meshes.new(name)
    v=[(a*MM,b*MM,c*MM) for (a,b,c) in [(x0,y0,z0),(x1,y0,z0),(x1,y1,z0),(x0,y1,z0),(x0,y0,z1),(x1,y0,z1),(x1,y1,z1),(x0,y1,z1)]]
    f=[(0,1,2,3),(7,6,5,4),(0,4,5,1),(1,5,6,2),(2,6,7,3),(3,7,4,0)]
    me.from_pydata(v,[],f); return link(name,me)

cyl("HandleBar", 20.5, 109, -660, 820, 1402, 'z', 20)
box("HandleMount1", 92, 127, -660, -585, 1322, 1360)
box("HandleMount2", 92, 127, -660, -585, 862, 902)
bpy.ops.object.select_all(action='DESELECT')
print([o.name for o in root.children_all])
print("n parts:", len([o for o in root.children_all]))
