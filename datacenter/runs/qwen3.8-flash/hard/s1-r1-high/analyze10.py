import numpy as np, bpy
src = bpy.data.images.load('/home/user/opus55poc/datacenter/runs/qwen3.8-flash/hard/s1-r1-high/inputs/plan.png')
w, h = src.size
px = np.array(src.pixels[:]).reshape(h, w, 4)
R, Gc, B = px[:,:,0], px[:,:,1], px[:,:,2]
g = px[:, :, :3].mean(axis=2)
X0, Y0 = 419.0, 699.0
S = 1601.0/25200.0
def mx(c): return round((c-X0)*S)
def my(r): return round((r-Y0)*S)
def mm(p): return round(p/S)

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

# --- CRAH (light blue) ---
blue = (B > R + 0.05) & (B > 0.6)
boxes = []
for r in range(h):
    for (a, b) in runs(blue[r], 5):
        f = None
        for bx in boxes:
            if bx['r1'] >= r-2 and not (b < bx['a']-3 or a > bx['b']+3): f = bx; break
        if f: f['r1']=r; f['a']=min(f['a'],a); f['b']=max(f['b'],b)
        else: boxes.append({'r0':r,'r1':r,'a':a,'b':b})
print('=== CRAH ===')
for bx in boxes:
    if bx['r1']-bx['r0'] > 20:
        print('x', mx(bx['a']), mx(bx['b']+1), 'y', my(bx['r0']), my(bx['r1']+1),
              'center', ((mx(bx['a'])+mx(bx['b']+1))//2, (my(bx['r0'])+my(bx['r1']+1))//2),
              'size', (mm(bx['b']-bx['a']+1), mm(bx['r1']-bx['r0']+1)))

# --- GPU racks (light green) ---
green = (Gc > R + 0.03) & (Gc > B + 0.03)
boxes = []
for r in range(h):
    for (a, b) in runs(green[r], 5):
        f = None
        for bx in boxes:
            if bx['r1'] >= r-2 and not (b < bx['a']-3 or a > bx['b']+3): f = bx; break
        if f: f['r1']=r; f['a']=min(f['a'],a); f['b']=max(f['b'],b)
        else: boxes.append({'r0':r,'r1':r,'a':a,'b':b})
print('=== GREEN (GPU shaded racks) ===')
for bx in boxes:
    if bx['r1']-bx['r0'] > 10:
        print('x', mx(bx['a']), mx(bx['b']+1), 'y', my(bx['r0']), my(bx['r1']+1),
              'size', (mm(bx['b']-bx['a']+1), mm(bx['r1']-bx['r0']+1)))
