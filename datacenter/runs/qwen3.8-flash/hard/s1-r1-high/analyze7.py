import numpy as np, bpy

src = bpy.data.images.load('/home/user/opus55poc/datacenter/runs/qwen3.8-flash/hard/s1-r1-high/inputs/plan.png')
w, h = src.size
px = np.array(src.pixels[:]).reshape(h, w, 4)
R, G, B = px[:,:,0], px[:,:,1], px[:,:,2]
g = px[:, :, :3].mean(axis=2)

X0, Y0, S = 419.0, 699.0, 1601.0/25200.0   # col,row(bottom-origin) -> mm
def tomm(c, r):  return (round((c-X0)/S), round((r-Y0)/S))

# --- black filled blobs (columns) ---
blk = g < 0.25
lab = np.zeros((h, w), dtype=np.int32)
cur = 0
import collections
boxes = []
for i in range(h):
    for j in range(w):
        pass
# too slow in python; use simple projection approach instead:
# find rows/cols where blk forms solid squares via scanning
def runs(mask1d, minlen):
    out, i, n = [], 0, len(mask1d)
    while i < n:
        if mask1d[i]:
            j = i
            while j+1 < n and mask1d[j+1]: j += 1
            if j-i+1 >= minlen: out.append((i, j))
            i = j+1
        else: i += 1
    return out

print("=== black horizontal runs 20..60 px (candidate column tops/bottoms) ===")
seen = []
for r in range(h):
    for (a, b) in runs(blk[r], 20):
        if b-a <= 60:
            seen.append((r, a, b))
# group consecutive rows
groups = []
for (r, a, b) in seen:
    placed = False
    for gr in groups:
        if abs(gr['r1']-r) <= 1 and abs(gr['a']-a) < 5 and abs(gr['b']-b) < 5:
            gr['r1'] = r; placed = True; break
    if not placed:
        groups.append({'r0': r, 'r1': r, 'a': a, 'b': b})
for gr in groups:
    if gr['r1']-gr['r0'] >= 15:
        c = (gr['a']+gr['b'])/2; rr = (gr['r0']+gr['r1'])/2
        print('square rows', gr['r0'], gr['r1'], 'cols', gr['a'], gr['b'],
              'center_mm', tomm(c, rr), 'size_mm', (round((gr['b']-gr['a']+1)/S), round((gr['r1']-gr['r0']+1)/S)))

# --- blue-ish (CRAH) ---
blue = (B > R + 0.05) & (B > 0.5)
print('blue px', blue.sum())
rowsb = np.where(blue.sum(axis=1) > 3)[0]
print('blue rows', rowsb.min(), rowsb.max())
# group
gr = []
for r in rowsb:
    if gr and r - gr[-1][1] <= 2: gr[-1][1] = r
    else: gr.append([r, r])
for (r0, r1) in gr:
    cols = np.where(blue[r0:r1+1].sum(axis=0) > 1)[0]
    gc = []
    for c in cols:
        if gc and c - gc[-1][1] <= 3: gc[-1][1] = c
        else: gc.append([c, c])
    print('blue band rows', r0, r1, 'col groups', gc, [tomm((a+b)/2, (r0+r1)/2) for a, b in gc],
          [(round((b-a+1)/S), round((r1-r0+1)/S)) for a, b in gc])
