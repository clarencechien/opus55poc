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

print("=== horizontal bands: (row_start,row_end) x-runs ===")
r = 0
while r < h:
    rr = runs(gray[r], 30)
    if rr:
        r2 = r
        while r2+1 < h and runs(gray[r2+1], 30) == rr:
            r2 += 1
        print((r, r2), rr)
        r = r2+1
    else:
        r += 1

print("=== vertical bands: (col_start,col_end) y-runs ===")
c = 0
while c < w:
    rr = runs(gray[:, c], 30)
    if rr:
        c2 = c
        while c2+1 < w and runs(gray[:, c2+1], 30) == rr:
            c2 += 1
        print((c, c2), rr)
        c = c2+1
    else:
        c += 1
