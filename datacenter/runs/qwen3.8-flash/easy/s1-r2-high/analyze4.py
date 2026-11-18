import bpy, numpy as np

img = bpy.data.images.load('/home/user/opus55poc/datacenter/runs/qwen3.8-flash/easy/s1-r2-high/inputs/plan.png')
w, h = img.size[0], img.size[1]
px = np.array(img.pixels[:]).reshape(h, w, 4)
g = px[:, :, :3].mean(axis=2)
dark = g < 0.6

def gaps_along(fixed, lo, hi, horiz):
    """scan the wall band; report continuous stretches where wall is missing"""
    present = []
    for t in range(lo, hi):
        if horiz:  # wall runs along x, band in rows fixed
            band = dark[fixed[0]:fixed[1], t]
        else:      # wall runs along y, band in cols fixed
            band = dark[t, fixed[0]:fixed[1]]
        present.append(band.mean() > 0.5)
    present = np.array(present)
    out = []
    i = 0
    while i < len(present):
        if not present[i]:
            j = i
            while j+1 < len(present) and not present[j+1]: j += 1
            if j - i > 5: out.append((lo+i, lo+j))
            i = j+1
        else: i += 1
    return out

print('west wall (cols 350-370) gaps along rows 560..1975:', gaps_along((350, 370), 560, 1975, False))
print('east wall (cols 2062-2080) gaps along rows 560..1975:', gaps_along((2062, 2080), 560, 1975, False))
print('south wall (rows 550-568) gaps along cols 375..2055:', gaps_along((550, 568), 375, 2055, True))
print('north wall (rows 1978-1994) gaps along cols 375..2055:', gaps_along((1978, 1994), 375, 2055, True))

# scale calibration
x0, x1 = 360.0, 2070.0   # grid A, D centrelines (px)
y0, y1 = 559.0, 1985.0   # grid 1, 3 centrelines (rows)
sx = 14400.0/(x1-x0); sy = 12000.0/(y1-y0)
print('scale mm/px', round(sx,4), round(sy,4))
def tomm(px_, py_): return (round((px_-x0)*sx), round((py_-y0)*sy))
print('door gap mm:', [tomm(0, a) for a in (1521, 1735)], 'centre y', tomm(0, (1521+1735)/2))
