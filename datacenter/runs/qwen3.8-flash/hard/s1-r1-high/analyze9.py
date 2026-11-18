import numpy as np, bpy
src = bpy.data.images.load('/home/user/opus55poc/datacenter/runs/qwen3.8-flash/hard/s1-r1-high/inputs/plan.png')
w, h = src.size
px = np.array(src.pixels[:]).reshape(h, w, 4)
sub = px[835:946, 428:481]
cols, cnt = np.unique(sub.reshape(-1,4).round(3), axis=0, return_counts=True)
for c, n in sorted(zip(cols.tolist(), cnt.tolist()), key=lambda t: -t[1])[:10]:
    print([round(v,3) for v in c], n)
print('---- rack box sample (D row area) ----')
sub2 = px[1150:1250, 620:700]
cols, cnt = np.unique(sub2.reshape(-1,4).round(3), axis=0, return_counts=True)
for c, n in sorted(zip(cols.tolist(), cnt.tolist()), key=lambda t: -t[1])[:10]:
    print([round(v,3) for v in c], n)
print('---- GPU rack B row sample ----')
sub3 = px[900:1000, 1270:1350]
cols, cnt = np.unique(sub3.reshape(-1,4).round(3), axis=0, return_counts=True)
for c, n in sorted(zip(cols.tolist(), cnt.tolist()), key=lambda t: -t[1])[:10]:
    print([round(v,3) for v in c], n)
print('---- UPS room sample ----')
sub4 = px[1600:1800, 1700:1900]
cols, cnt = np.unique(sub4.reshape(-1,4).round(3), axis=0, return_counts=True)
for c, n in sorted(zip(cols.tolist(), cnt.tolist()), key=lambda t: -t[1])[:6]:
    print([round(v,3) for v in c], n)
