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
def vert_band(name, cW, cE, r0, r1):
    for side in ('E', 'W'):
        seg = blk[r0:r1, cE+2:cE+12] if side == 'E' else blk[r0:r1, cW-12:cW-2]
        marks = runs(seg.sum(axis=1) > 2, 3)
        print(name, 'marks outside', side, ':', [(my(r0+a), my(r0+b+1)) for a, b in marks])

# E row cols 572..650, F row cols 722..800, rows 1595..1825
vert_band('E row', 572, 650, 1593, 1827)
vert_band('F row', 722, 800, 1593, 1827)
# CRAH west lower: cols 426..482 rows ~833..947 ; west upper rows 1233..1347? ; east cols 1957..2013
print('--- CRAH box extents (blue fill incl outline) ---')
blue = (px[:,:,2] > px[:,:,0] + 0.04) & (px[:,:,2] > 0.6)
for (r0, r1, c0, c1) in [(800,1000,415,500), (1200,1420,415,500), (800,1100,1930,2020)]:
    sub = blue[r0:r1, c0:c1]
    rr = np.where(sub.sum(axis=1) > 3)[0]; cc = np.where(sub.sum(axis=0) > 3)[0]
    if len(rr):
        print('region', (r0,c0), 'rows', r0+rr.min(), r0+rr.max(), 'cols', c0+cc.min(), c0+cc.max(),
              'x', mx(c0+cc.min()), mx(c0+cc.max()+1), 'y', my(r0+rr.min()), my(r0+rr.max()+1))
        vert_band('CRAH', c0+cc.min()-1, c0+cc.max()+1, r0+rr.min(), r0+rr.max()+1)
        # horizontal marks
        for side in ('N', 'S'):
            seg = blk[r0+rr.max()+3:r0+rr.max()+13, c0:c1] if side == 'N' else blk[r0+rr.min()-13:r0+rr.min()-3, c0:c1]
            print('   marks outside', side, [(mx(c0+a), mx(c0+b+1)) for a, b in runs(seg.sum(axis=0) > 2, 3)])
