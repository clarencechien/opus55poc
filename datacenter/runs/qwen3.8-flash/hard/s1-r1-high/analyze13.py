import numpy as np, bpy
src = bpy.data.images.load('/home/user/opus55poc/datacenter/runs/qwen3.8-flash/hard/s1-r1-high/inputs/plan.png')
w, h = src.size
px = np.array(src.pixels[:]).reshape(h, w, 4)
g = px[:, :, :3].mean(axis=2)
X0, Y0 = 419.0, 699.0
S = 1601.0/25200.0
def mx(c): return round((c-X0)/S)
def my(r): return round((r-Y0)/S)
blk = g < 0.35
def runs(mask1d, minlen=1):
    out, i, n = [], 0, len(mask1d)
    while i < n:
        if mask1d[i]:
            j = i
            while j+1 < n and mask1d[j+1]: j += 1
            if j-i+1 >= minlen: out.append((i, j))
            i = j+1
        else: i += 1
    return out
for r in [780, 782, 800, 856, 858, 900, 932, 934, 1010, 1012, 1050]:
    print('row', r, 'y', my(r), [(a, b, mx(a), mx(b+1)) for a, b in runs(blk[r, 1200:2200], 4) if True])
print()
print('=== vertical black runs >=25px in region cols 1200-2200 ===')
for c in range(1200, 2200):
    rr = [t for t in runs(blk[:, c], 25) if t[0] > 700 and t[1] < 1100]
    if rr:
        print('col', c, 'x', mx(c), rr, [(my(a), my(b+1)) for a, b in rr])
