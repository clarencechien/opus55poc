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
def back(ci,u,v,h=0.6):
    p,d,r,up = basis(cams[ci])
    x=(u-640)/f; y=-(v-480)/f
    ray = d + r*x + up*y
    tt = (h-p.z)/ray.z
    q = p+ray*tt
    return (round(q.x,2),round(q.y,2))
def fwd(ci,X,Y,Z):
    p,d,r,up = basis(cams[ci])
    w = Vector((X,Y,Z))-p
    zc = w.dot(d)
    return (round(640+f*w.dot(r)/zc), round(480-f*w.dot(up)/zc))
q = [
 (3,40,540,2.6),(3,665,460,2.6),(3,665,690,0.6),(3,130,960,0.6),
 (5,833,525,0.6),(5,1058,555,0.6),(5,1075,535,0.6),(5,833,422,2.6),(5,1058,422,2.6),(5,1075,420,2.6),
 (1,215,650,2.55),(1,0,540,2.55),(1,190,575,2.55),(1,245,960,0.6),
 (1,765,432,0.6),(1,748,432,0.6),(1,785,432,0.6),(1,765,390,2.55),
 (2,380,460,0.6),(2,430,460,0.6),(2,405,415,2.55),
]
for (ci,u,v,h) in q:
    print(ci,(u,v),h,'->',back(ci,u,v,h))
# CRAH candidates on west wall: corners
for y0 in [1.2,1.5,1.8,2.4,3.0]:
    print('crah y0',y0,'cam1 NE top',fwd(1,1.0,y0+1.8,2.55),'SE top',fwd(1,1.0,y0,2.55),'cam2 box',fwd(2,1.0,y0,2.55),fwd(2,1.0,y0+1.8,0.6))
