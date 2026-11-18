import numpy as np, bpy

img = bpy.data.images.load('/home/user/opus55poc/datacenter/runs/qwen3.8-flash/hard/s1-r1-high/inputs/plan.png')
w, h = img.size
px = np.array(img.pixels[:]).reshape(h, w, 4)
g = px[:, :, :3].mean(axis=2)
dark = g < 0.35

def runs(mask1d):
    out = []
    i = 0
    n = len(mask1d)
    while i < n:
        if mask1d[i]:
            j = i
            while j+1 < n and mask1d[j+1]:
                j += 1
            out.append((i, j, j-i+1))
            i = j+1
        else:
            i += 1
    return out

rowsum = dark.sum(axis=1)
print("=== rows with >0.15*w dark (bottom-origin) ===")
for r in range(h):
    if rowsum[r] > 0.15*w:
        rr = runs(dark[r])
        longest = max(rr, key=lambda t: t[2]) if rr else None
        print(r, rowsum[r], 'nruns', len(rr), 'longest', longest)

colsum = dark.sum(axis=0)
print("=== cols with >0.15*h dark ===")
for c in range(w):
    if colsum[c] > 0.15*h:
        rr = runs(dark[:, c])
        longest = max(rr, key=lambda t: t[2]) if rr else None
        print(c, colsum[c], 'nruns', len(rr), 'longest', longest)
