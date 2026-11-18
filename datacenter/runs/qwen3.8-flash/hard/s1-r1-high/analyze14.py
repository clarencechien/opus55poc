import numpy as np, bpy
src = bpy.data.images.load('/home/user/opus55poc/datacenter/runs/qwen3.8-flash/hard/s1-r1-high/inputs/plan.png')
w, h = src.size
px = np.array(src.pixels[:]).reshape(h, w, 4)
g = px[:, :, :3].mean(axis=2)
X0, Y0 = 419.0, 699.0
S = 1601.0/25200.0
def mx(c): return round((c-X0)/S)
def my(r): return round((r-Y0)/S)
blk = g < 0.3
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

def horiz_band(name, rN, rS, c0, c1):
    for side in ('N', 'S'):
        seg = blk[rN+2:rN+12, c0:c1] if side == 'N' else blk[rS-12:rS-2, c0:c1]
        marks = runs(seg.sum(axis=0) > 2, 3)
        print(name, 'marks outside', side, ':', [(mx(c0+a), mx(c0+b+1)) for a, b in marks])

def vert_band(name, cW, cE, r0, r1):
    for side in ('E', 'W'):
        seg = blk[r0:r1, cE+2:cE+12] if side == 'E' else blk[r0:r1, cW-12:cW-2]
        marks = runs(seg.sum(axis=1) > 2, 3)
        print(name, 'marks outside', side, ':', [(my(r0+a), my(r0+b+1)) for a, b in marks])

horiz_band('A row', 860, 782, 1258, 1678)
horiz_band('B row', 1011, 932, 1258, 1678)
horiz_band('C row', 1140, 1061, 610, 1106)
horiz_band('D row', 1290, 1212, 610, 1106)
print('--- E/F area: long horizontal runs rows 1400-1800 ---')
for r in range(1400, 1800):
    rr = runs(blk[r, 400:1300], 20)
    if rr:
        print('row', r, my(r), [(a+400, b+400) for a, b in rr])
