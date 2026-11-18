import bpy, numpy as np

img = bpy.data.images.load('/home/user/opus55poc/datacenter/runs/qwen3.8-flash/easy/s1-r2-high/inputs/plan.png')
w, h = img.size[0], img.size[1]
print('size', w, h)
px = np.array(img.pixels[:]).reshape(h, w, 4)
g = px[:, :, :3].mean(axis=2)
dark = g < 0.45
verydark = g < 0.25

# find long vertical dark runs (walls)
col_counts = dark.sum(axis=0)
row_counts = dark.sum(axis=1)
cand_c = [x for x in range(w) if col_counts[x] > 300]
cand_r = [y for y in range(h) if row_counts[y] > 300]
def group(lst):
    out = []
    for v in lst:
        if out and v - out[-1][-1] <= 2:
            out[-1].append(v)
        else:
            out.append([v])
    return [(a[0], a[-1], sum(a)/len(a)) for a in out]
print('vertical wall cols (x px):', group(cand_c))
print('horizontal wall rows (y px):', group(cand_r))
