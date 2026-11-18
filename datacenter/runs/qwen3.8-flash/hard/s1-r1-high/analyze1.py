import numpy as np, bpy

img = bpy.data.images.load('/home/user/opus55poc/datacenter/runs/qwen3.8-flash/hard/s1-r1-high/inputs/plan.png')
w, h = img.size
print('size', w, h)
px = np.array(img.pixels[:]).reshape(h, w, 4)
g = px[:, :, :3].mean(axis=2)   # 0..1, row 0 = BOTTOM of image
dark = g < 0.35
print('dark frac', dark.mean())

# long horizontal dark runs (in image-row terms, flip later)
rowsum = dark.sum(axis=1)
cands = [r for r in range(h) if rowsum[r] > 0.35*w]
print('rows with many dark px (bottom-origin):', cands)

colsum = dark.sum(axis=0)
candc = [c for c in range(w) if colsum[c] > 0.35*h]
print('cols with many dark px:', candc)
