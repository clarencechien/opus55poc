import numpy as np, bpy

src = bpy.data.images.load('/home/user/opus55poc/datacenter/runs/qwen3.8-flash/hard/s1-r1-high/inputs/plan.png')
w, h = src.size
px = np.array(src.pixels[:]).reshape(h, w, 4)
R, G, B = px[:,:,0], px[:,:,1], px[:,:,2]
g = px[:, :, :3].mean(axis=2)
X0, Y0, S = 419.0, 699.0, 1601.0/25200.0
def mx(c): return round((c-X0)/S)
def my(r): return round((r-Y0)/S)

blue = (B > R + 0.12) & (B > 0.5)
print('strong blue px', blue.sum())
# bounding boxes via simple 2-pass labeling on rows
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

# collect boxes: for each row, blue col-runs; merge with previous rows
boxes = []
for r in range(h):
    for (a, b) in runs(blue[r], 3):
        found = None
        for bx in boxes:
            if bx['r1'] >= r-2 and not (b < bx['a']-2 or a > bx['b']+2):
                found = bx; break
        if found:
            found['r1'] = r; found['a'] = min(found['a'], a); found['b'] = max(found['b'], b)
        else:
            boxes.append({'r0': r, 'r1': r, 'a': a, 'b': b})
for bx in boxes:
    if bx['r1']-bx['r0'] > 20:
        print('CRAH box cols', bx['a'], bx['b'], 'rows', bx['r0'], bx['r1'],
              'x', mx(bx['a']), mx(bx['b']+1), 'y', my(bx['r0']), my(bx['r1']+1),
              'center', (mx((bx['a']+bx['b']+1)/2), my((bx['r0']+bx['r1']+1)/2)),
              'size', (round((bx['b']-bx['a']+1)/S), round((bx['r1']-bx['r0']+1)/S)))
