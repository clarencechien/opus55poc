import numpy as np, bpy

src = bpy.data.images.load('/home/user/opus55poc/datacenter/runs/qwen3.8-flash/hard/s1-r1-high/inputs/plan.png')
w, h = src.size
px = np.array(src.pixels[:]).reshape(h, w, 4)
g = px[:, :, :3].mean(axis=2)
print('hist', np.histogram(g, bins=10, range=(0,1))[0])

# sample a vertical strip near west wall at bottom-origin row 1000
for c in range(240, 460):
    v = g[1000, c]
    if v < 0.9:
        print('row1000 col', c, round(float(v), 3))
