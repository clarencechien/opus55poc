import numpy as np, bpy

src = bpy.data.images.load('/home/user/opus55poc/datacenter/runs/qwen3.8-flash/hard/s1-r1-high/inputs/plan.png')
w, h = src.size
px = np.array(src.pixels[:]).reshape(h, w, 4)
g = px[:, :, :3].mean(axis=2)
gray = (g > 0.25) & (g < 0.6)

def runs(mask1d, minlen):
    out, i, n = [], 0, len(mask1d)
    while i < n:
        if mask1d[i]:
            j = i
            while j+1 < n and mask1d[j+1]:
                j += 1
            if j-i+1 >= minlen:
                out.append((i, j))
            i = j+1
        else:
            i += 1
    return out

print("=== horizontal wall bands (row: runs of gray >=30px) ===")
prev = None
for r in range(h):
    rr = runs(gray[r], 30)
    if rr:
        print('row', r, rr)

print("=== vertical wall bands (col: runs of gray >=30px) ===")
for c in range(w):
    rr = runs(gray[:, c], 30)
    if rr:
        print('col', c, rr)
