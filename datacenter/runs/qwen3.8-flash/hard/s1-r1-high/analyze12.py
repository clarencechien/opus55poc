import numpy as np, bpy
src = bpy.data.images.load('/home/user/opus55poc/datacenter/runs/qwen3.8-flash/hard/s1-r1-high/inputs/plan.png')
w, h = src.size
px = np.array(src.pixels[:]).reshape(h, w, 4)
g = px[:, :, :3].mean(axis=2)
X0, Y0 = 419.0, 699.0
S = 1601.0/25200.0
def mx(c): return round((c-X0)/S)
def my(r): return round((r-Y0)/S)

blk = g < 0.2
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

print('=== long horizontal black runs (>=80px) ===')
r = 0
while r < h:
    rr = runs(blk[r], 80)
    if rr:
        r2 = r
        while r2+1 < h and runs(blk[r2+1], 80) == rr: r2 += 1
        print('rows', r, r2, [(a, b, mx(a), mx(b+1)) for a, b in rr])
        r = r2+1
    else: r += 1
