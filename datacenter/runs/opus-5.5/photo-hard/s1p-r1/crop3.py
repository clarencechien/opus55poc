exec(open('/home/user/opus55poc/datacenter/runs/opus-5.5/photo-hard/s1p-r1/crop2.py').read().split('jobs = [')[0])
jobs = [
 ('p1h', 'inputs/photo_1.jpg', (880,385,990,510), 7),
 ('p2r1', 'inputs/photo_2.jpg', (370,420,530,600), 5),
]
for (nm,pa,(x0,y0,x1,y1),s) in jobs:
    A = load(RUN+pa)
    c = A[y0:y1, x0:x1].copy()
    c = np.repeat(np.repeat(c, s, axis=0), s, axis=1)
    c[...,3]=1
    c = grid(c, x0, y0, s, 10)
    save(c, RUN+'crops/%s.png'%nm)
    print(nm, c.shape)
