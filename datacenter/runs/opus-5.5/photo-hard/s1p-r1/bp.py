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
# sanity: compare with blender camera object
for i in range(1,6):
    ob = bpy.data.objects.get('Cam_%d'%i)
    if ob:
        print(i, tuple(round(a,3) for a in ob.location), ob.data.lens, ob.data.sensor_width, ob.data.sensor_fit)
q = {
1:[(345,660),(525,590),(275,615),(727,495),(570,555),(160,520),(65,528),(780,480),(830,492),(893,462),(945,502),(978,480),(215,600),(265,595)],
2:[(520,820),(680,770),(800,715),(910,690),(395,560),(1040,540),(1210,575)],
3:[(665,690),(130,960),(962,622),(1058,636),(825,555),(668,535),(880,520)],
4:[(120,670),(352,598),(40,655),(425,558),(518,528),(710,522),(776,487),(608,515),(385,620),(590,522),(872,545),(945,600)],
5:[(295,520),(0,565),(485,530),(728,485),(833,525),(1058,555),(1075,535),(583,590),(775,512),(362,520),(420,515)],
}
for ci,pts in q.items():
    print('cam',ci)
    for (u,v) in pts:
        print('  ',(u,v),'->',back(ci,u,v))
cols=[(6,6),(12,6),(18,6),(6,12),(12,12)]
for ci in cams:
    print('cols cam',ci,[fwd(ci,x,y,0.6) for x,y in cols])
