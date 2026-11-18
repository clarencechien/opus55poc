import bpy, math
from mathutils import Vector
cams = {
1: ((0.45,0.45,3.25),(10.8,7.2,0.9)),
2: ((23.55,0.45,3.25),(9.6,8.1,0.9)),
3: ((0.45,17.55,3.25),(8.4,6.3,0.9)),
4: ((23.55,11.55,3.25),(7.2,5.4,0.9)),
5: ((17.55,17.55,3.25),(6.0,8.1,0.9)),
}
f = 1280*16/36.0
def basis(c):
    p = Vector(c[0]); t = Vector(c[1])
    d = (t-p).normalized()
    r = d.cross(Vector((0,0,1))).normalized()
    u = r.cross(d)
    return p,d,r,u
def ray(ci,u,v):
    p,d,r,up = basis(cams[ci])
    x=(u-640)/f; y=-(v-480)/f
    return p, d + r*x + up*y
def plane(ci,u,v,axis,val):
    p,rd = ray(ci,u,v)
    i = 0 if axis=='x' else 1
    t = (val-p[i])/rd[i]
    q = p+rd*t
    return (round(q.x,3),round(q.y,3),round(q.z,2))
def show(name, ci, us, vs, axis, val):
    if not isinstance(vs, list): vs=[vs]*len(us)
    res = [plane(ci,u,v,axis,val) for u,v in zip(us,vs)]
    k = 1 if axis=='x' else 0
    vals = [r[k] for r in res]
    print(name, [round(a,3) for a in vals], 'z', [r[2] for r in res])
    print('   diffs', [round(vals[i+1]-vals[i],3) for i in range(len(vals)-1)])
show('cam3 W1 bnd x=3.0', 3, [50,306,427,514,581,632,665], 650, 'x', 3.0)
show('cam3 W2 lbl x=5.4', 3, [77,177,271,346,408,460], [520,500,487,477,468,462], 'x', 5.4)
show('cam2 R2 lbl y=3.6', 2, [532.5,547.75,565.5,583,600,619.75,643,669.75,701,739,786], [439.5,445,447,450,454,457.5,461,467.5,474,482.5,494], 'y', 3.6)
show('cam1 R2 door y=3.6', 1, [834.2,841.7,850,857.5,865,871.7,877.5,882.5,887.5,891.3,894.2], 450, 'y', 3.6)
show('cam1 A2 back y=5.4', 1, [555,590,617,645,670,690,710,727], 480, 'y', 5.4)
show('cam1 A1 back y=5.4', 1, [345,395,450,485,525], 540, 'y', 5.4)
