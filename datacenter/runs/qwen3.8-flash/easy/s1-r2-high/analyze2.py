import bpy, numpy as np

img = bpy.data.images.load('/home/user/opus55poc/datacenter/runs/qwen3.8-flash/easy/s1-r2-high/inputs/plan.png')
w, h = img.size[0], img.size[1]
px = np.array(img.pixels[:]).reshape(h, w, 4)
g = px[:, :, :3].mean(axis=2)

def runs(mask_1d, gap=3, minlen=2):
    idx = np.where(mask_1d)[0]
    if len(idx) == 0: return []
    out = [[idx[0], idx[0]]]
    for v in idx[1:]:
        if v - out[-1][1] <= gap: out[-1][1] = v
        else: out.append([v, v])
    return [(a, b) for a, b in out if b - a + 1 >= minlen]

dark = g < 0.5
print('--- vertical scan at x=1200 (through rack rows) : y runs')
print(runs(dark[:, 1200]))
print('--- vertical scan at x=1900 (open area east of racks): y runs')
print(runs(dark[:, 1900]))
print('--- vertical scan at x=2070 (east wall): y runs')
print(runs(dark[:, 2070]))
print('--- horizontal scan at y=1000 (between rows): x runs')
print(runs(dark[1000, :]))
print('--- horizontal scan at y=600 (north area): x runs')
print(runs(dark[600, :]))
print('--- horizontal scan at y=760 (through racks): x runs')
print(runs(dark[760, :]))
