import json, os
from mathutils import Vector, Matrix

RUN = '/home/user/opus55poc/datacenter/runs/opus-5.5/easy/s3-r1'
L = json.load(open(os.path.join(RUN, 'inputs/layout.json')))

# cleanup previous generated objects
for o in list(bpy.data.objects):
    if o.name.startswith(('Rack_', 'RackPart_', 'Containment_', 'PerfTile_', 'CableTray_')):
        bpy.data.objects.remove(o, do_unlink=True)

tmpl = bpy.data.objects['RackA']
def descendants(o):
    out = []
    for c in o.children:
        out.append(c); out += descendants(c)
    return out
parts = descendants(tmpl)

# template bbox relative to template origin
inv = tmpl.matrix_world.inverted()
mn = Vector((1e9,)*3); mx = Vector((-1e9,)*3)
for p in parts:
    if p.type != 'MESH': continue
    for c in p.bound_box:
        v = inv @ (p.matrix_world @ Vector(c))
        for i in range(3):
            mn[i] = min(mn[i], v[i]); mx[i] = max(mx[i], v[i])
print('template local bbox', tuple(round(x,4) for x in mn), tuple(round(x,4) for x in mx))
# front door location to confirm front direction
fd = bpy.data.objects.get('RackA_FrontDoor')
if fd:
    c = sum((inv @ (fd.matrix_world @ Vector(b)) for b in fd.bound_box), Vector()) / 8
    print('front door local centre', tuple(round(x,3) for x in c))

coll = bpy.data.collections.get('Collection') or bpy.context.scene.collection
def link(o):
    coll.objects.link(o)

ROT = {'S': 0.0, 'N': math.pi, 'E': math.pi/2, 'W': -math.pi/2}
# offset so that the template footprint centre goes to the target and bottom sits on z=0.6
cx = (mn.x + mx.x) / 2; cy = (mn.y + mx.y) / 2; bz = mn.z
print('footprint centre offset', cx, cy, bz)

for r in L['racks']:
    rid = r['id']
    root = bpy.data.objects.new('Rack_' + rid, None)
    root.empty_display_type = 'PLAIN_AXES'
    root.empty_display_size = 0.2
    link(root)
    root['rackId'] = rid
    root.rotation_euler = (0, 0, ROT[r['facing']])
    # place so footprint centre lands on target
    off = Matrix.Rotation(ROT[r['facing']], 4, 'Z') @ Vector((cx, cy, 0))
    root.location = (r['center'][0]/1000 - off.x, r['center'][1]/1000 - off.y, 0.6 - bz)
    mapping = {tmpl: root}
    for p in parts:
        n = p.copy()  # linked duplicate (shares mesh data)
        n.name = 'RackPart_' + rid + '_' + p.name[len('RackA_'):]
        for k in list(n.keys()):
            del n[k]
        link(n)
        mapping[p] = n
    for p in parts:
        n = mapping[p]
        n.parent = mapping[p.parent]
        n.matrix_parent_inverse = p.matrix_parent_inverse.copy()
        n.matrix_basis = p.matrix_basis.copy()

def box(name, x0, y0, z0, x1, y1, z1, mat=None):
    me = bpy.data.meshes.new(name)
    vs = [(x, y, z) for x in (x0, x1) for y in (y0, y1) for z in (z0, z1)]
    # indices: x*4 + y*2 + z
    fs = [(0,1,3,2), (4,6,7,5), (0,4,5,1), (2,3,7,6), (0,2,6,4), (1,5,7,3)]
    cxx, cyy, czz = (x0+x1)/2, (y0+y1)/2, (z0+z1)/2
    me.from_pydata([(a-cxx, b-cyy, c-czz) for a,b,c in vs], [], fs)
    me.update()
    if mat: me.materials.append(mat)
    o = bpy.data.objects.new(name, me)
    o.location = (cxx, cyy, czz)
    link(o)
    return o

def mat(name, rgba):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.diffuse_color = rgba
    return m
m_cont = mat('M_Containment', (0.6, 0.8, 1.0, 0.5))
m_tile = mat('M_PerfTile', (0.3, 0.5, 0.9, 1.0))
m_tray = mat('M_CableTray', (0.9, 0.7, 0.1, 1.0))

RACK_TOP = 0.6 + (mx.z - mn.z)
print('rack top', RACK_TOP)
T = 0.6
ci = 0
for a in L['aisles']:
    if a['type'] != 'cold': continue
    ci += 1
    x0, y0, x1, y1 = [v/1000 for v in a['rect']]
    box(f'Containment_C{ci}_Roof', x0, y0, RACK_TOP, x1, y1, RACK_TOP + 0.03, m_cont)
    th = 0.04
    box(f'Containment_C{ci}_Door_W', x0 - th/2, y0, 0.6, x0 + th/2, y1, RACK_TOP, m_cont)
    box(f'Containment_C{ci}_Door_E', x1 - th/2, y0, 0.6, x1 + th/2, y1, RACK_TOP, m_cont)
    # perforated tiles
    import math as _m
    ix0 = _m.ceil(a['rect'][0]/600 - 1e-9); ix1 = _m.floor(a['rect'][2]/600 + 1e-9)
    iy0 = _m.ceil(a['rect'][1]/600 - 1e-9); iy1 = _m.floor(a['rect'][3]/600 + 1e-9)
    n = 0
    for i in range(ix0, ix1):
        for j in range(iy0, iy1):
            box(f'PerfTile_C{ci}_{i:02d}_{j:02d}', i*T, j*T, 0.58, (i+1)*T, (j+1)*T, 0.6, m_tile)
            n += 1
    print('cold aisle', ci, 'tiles', n)

# cable trays per row
rows = {}
for r in L['racks']:
    rows.setdefault(r['row'], []).append(r)
for row, rs in sorted(rows.items()):
    xs0 = []; xs1 = []; ys0 = []; ys1 = []
    for r in rs:
        w, d = r['size']
        if r['facing'] in ('E', 'W'): w, d = d, w
        xs0.append(r['center'][0] - w/2); xs1.append(r['center'][0] + w/2)
        ys0.append(r['center'][1] - d/2); ys1.append(r['center'][1] + d/2)
    X0, X1, Y0, Y1 = min(xs0)/1000, max(xs1)/1000, min(ys0)/1000, max(ys1)/1000
    if X1 - X0 >= Y1 - Y0:
        yc = (Y0 + Y1)/2
        box(f'CableTray_{row}', X0, yc - 0.15, RACK_TOP + 0.3, X1, yc + 0.15, RACK_TOP + 0.4, m_tray)
    else:
        xc = (X0 + X1)/2
        box(f'CableTray_{row}', xc - 0.15, Y0, RACK_TOP + 0.3, xc + 0.15, Y1, RACK_TOP + 0.4, m_tray)
    print('row', row, X0, X1, Y0, Y1)

bpy.context.view_layer.update()
# verify racks world bboxes
for r in L['racks']:
    root = bpy.data.objects['Rack_' + r['id']]
    mn2 = Vector((1e9,)*3); mx2 = Vector((-1e9,)*3)
    for c in root.children_recursive:
        if c.type != 'MESH': continue
        for b in c.bound_box:
            v = c.matrix_world @ Vector(b)
            for i in range(3):
                mn2[i] = min(mn2[i], v[i]); mx2[i] = max(mx2[i], v[i])
    fdc = None
    for c in root.children:
        if c.name.endswith('_FrontDoor'):
            fdc = c.matrix_world @ (sum((Vector(b) for b in c.bound_box), Vector())/8)
    print(r['id'], r['facing'], 'bbox', tuple(round(x,3) for x in mn2), tuple(round(x,3) for x in mx2),
          'door', tuple(round(x,2) for x in fdc) if fdc else None)
