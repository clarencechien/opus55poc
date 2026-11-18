import numpy as np, bpy
src = bpy.data.images.load('/home/user/opus55poc/datacenter/runs/qwen3.8-flash/hard/s1-r1-high/inputs/plan.png')
w, h = src.size
px = np.array(src.pixels[:]).reshape(h, w, 4)
g = px[:, :, :3].mean(axis=2)
blk = g < 0.45
S = 1601.0/25200.0
Y0 = 699.0
def my(r): return round((r-Y0)/S)
for c in range(2080, 2400, 5):
    left = blk[:, c-7:c-2].sum(axis=1)
    right = blk[:, c+3:c+8].sum(axis=1)
    m = (left > 0) | (right > 0)
    rows = np.where(m)[0]
    rows = rows[(rows > 600) & (rows < 2000)]
    groups = []
    for r in rows:
        if groups and r - groups[-1][-1] <= 3: groups[-1].append(r)
        else: groups.append([r])
    if len(groups) >= 3:
        print('col', c, [my((gp[0]+gp[-1])/2) for gp in groups])
