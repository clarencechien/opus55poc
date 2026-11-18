import numpy as np, bpy

img = bpy.data.images.load('/home/user/opus55poc/datacenter/runs/qwen3.8-flash/hard/s1-r1-high/inputs/plan.png')
w, h = img.size
px = np.array(img.pixels[:]).reshape(h, w, 4)
g = px[:, :, :3].mean(axis=2)
dark = g < 0.35

def runs(mask1d):
    out, i, n = [], 0, len(mask1d)
    while i < n:
        if mask1d[i]:
            j = i
            while j+1 < n and mask1d[j+1]:
                j += 1
            out.append((i, j))
            i = j+1
        else:
            i += 1
    return out

for r in [700, 900, 1100, 1300, 1600, 1800, 1950, 2000]:
    print('row', r, runs(dark[r]))
print()
for c in [400, 420, 900, 1220, 1500, 1900, 2000, 2100, 2140]:
    print('col', c, runs(dark[:, c]))
