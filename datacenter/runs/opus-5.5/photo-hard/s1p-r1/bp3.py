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
def fwd(ci,X,Y,Z):
    p,d,r,up = basis(cams[ci])
    w = Vector((X,Y,Z))-p
    zc = w.dot(d)
    return (round(640+f*w.dot(r)/zc), round(480-f*w.dot(up)/zc))
for y0 in [7.2,7.5,7.8,8.1,8.4,8.7]:
    y1=y0+1.8
    print('y0',y0,'cam1 top SW',fwd(1,23.0,y0,2.55),'NW',fwd(1,23.0,y1,2.55),'floor SW',fwd(1,23.0,y0,0.6),
          '| cam3 top NW',fwd(3,23.0,y1,2.55),'SW',fwd(3,23.0,y0,2.55),'floor SW',fwd(3,23.0,y0,0.6),'floor SE',fwd(3,23.9,y0,0.6))
