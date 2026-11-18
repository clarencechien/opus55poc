exec(open('/home/user/opus55poc/datacenter/runs/opus-5.5/photo-hard/s1p-r1/bp4.py').read().split("show('cam3 W1")[0])
exec(open('/home/user/opus55poc/datacenter/runs/opus-5.5/photo-hard/s1p-r1/crop2.py').read().split('jobs = [')[0])
def fwd(ci,X,Y,Z):
    p,d,r,up = basis(cams[ci])
    w = Vector((X,Y,Z))-p
    zc = w.dot(d)
    return (round(640+f*w.dot(r)/zc), round(480-f*w.dot(up)/zc))
std = [13.5+0.6*i for i in range(12)]
gpu = [13.6,14.4,15.2]+[15.9+0.6*i for i in range(8)]
for ci in (3,4,5):
    print('cam',ci,'std', [fwd(ci,x,2.4,2.5) for x in std])
    print('cam',ci,'gpu', [fwd(ci,x,2.4,2.5) for x in gpu])
    print('cam',ci,'R2top north edge', [fwd(ci,x,4.8,2.6) for x in (13.2,15.6,20.4)])
jobs = [
 ('p4r1w', 'inputs/photo_4.jpg', (330,410,560,470), 5),
 ('p5r1', 'inputs/photo_5.jpg', (0,395,320,445), 4),
]
for (nm,pa,(x0,y0,x1,y1),s) in jobs:
    A = load(RUN+pa)
    c = A[y0:y1, x0:x1].copy()
    c = np.repeat(np.repeat(c, s, axis=0), s, axis=1)
    c[...,3]=1
    c = grid(c, x0, y0, s, 10)
    save(c, RUN+'crops/%s.png'%nm)
    print(nm, c.shape)
