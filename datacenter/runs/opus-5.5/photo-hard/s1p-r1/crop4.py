exec(open('/home/user/opus55poc/datacenter/runs/opus-5.5/photo-hard/s1p-r1/crop2.py').read().split('jobs = [')[0])
import sys
J = JOBS
for (nm,pa,pb,(x0,y0,x1,y1),s) in J:
    A = load(RUN+pa); B = load(RUN+pb)
    ca = A[y0:y1, x0:x1].copy(); cb = B[y0:y1, x0:x1].copy()
    sep = np.zeros((2, x1-x0, 4), dtype=np.float32); sep[...,0]=1; sep[...,3]=1
    comp = np.concatenate([ca, sep, cb], axis=0)
    comp = np.repeat(np.repeat(comp, s, axis=0), s, axis=1)
    comp[...,3] = 1.0
    save(comp, RUN+'crops/%s.png'%nm)
    print('saved', nm, comp.shape)
