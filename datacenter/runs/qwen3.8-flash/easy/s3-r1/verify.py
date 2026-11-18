import bpy, json, math, collections
from mathutils import Vector

MM = 0.001
L = json.load(open('/home/user/opus55poc/datacenter/runs/qwen3.8-flash/easy/s3-r1/inputs/layout.json'))
FLOOR_Z = L['room']['raised_floor_height'] * MM

def wbbox(o):
    cs = [o.matrix_world @ Vector(c) for c in o.bound_box]
    mn = Vector((min(c[i] for c in cs) for i in range(3)))
    mx = Vector((max(c[i] for c in cs) for i in range(3)))
    return mn, mx

def overlap(a, b):
    return all(a[0][i] < b[1][i] - 1e-4 and b[0][i] < a[1][i] - 1e-4 for i in range(3))

def fac_of(rz):
    for k, v in {'S': 0.0, 'E': math.pi/2, 'N': math.pi, 'W': 1.5*math.pi}.items():
        if abs((rz - v) % (2*math.pi)) < 1e-3:
            return k
    return '?%.3f' % rz

problems = []
racks = []
for r in L['racks']:
    o = bpy.data.objects.get('Rack_%s' % r['id'])
    if o is None:
        problems.append('missing Rack_%s' % r['id']); continue
    mn, mx = wbbox(o)
    d = abs(o.location.x - r['center'][0]*MM) + abs(o.location.y - r['center'][1]*MM) + abs(o.location.z - FLOOR_Z)
    fac = fac_of(round(o.rotation_euler.z, 6) % (2*math.pi))
    props = dict(o.items())
    if d > 1e-4: problems.append('rack %s position' % r['id'])
    if fac != r['facing']: problems.append('rack %s facing %s want %s' % (r['id'], fac, r['facing']))
    if props.get('rackId') != r['id']: problems.append('rack %s rackId prop' % r['id'])
    if abs(mn.z - FLOOR_Z) > 1e-3: problems.append('rack %s bottom z %.4f' % (r['id'], mn.z))
    if mx.z > 2.61: problems.append('rack %s too tall %.4f' % (r['id'], mx.z))
    racks.append((r['id'], mn, mx))
print('racks ok-ish, count %d' % len(racks))

for i in range(len(racks)):
    for j in range(i+1, len(racks)):
        if overlap((racks[i][1], racks[i][2]), (racks[j][1], racks[j][2])):
            problems.append('rack overlap %s/%s' % (racks[i][0], racks[j][0]))
struct = [(o.name,) + wbbox(o) for o in bpy.data.objects if o.name.startswith(('Wall_', 'Column_'))]
for rid, mn, mx in racks:
    for nm, bmn, bmx in struct:
        if overlap((mn, mx), (bmn, bmx)):
            problems.append('rack %s hits %s' % (rid, nm))

print('--- containment / trays ---')
aisle = [a for a in L['aisles'] if a['type'] == 'cold'][0]
ax0, ay0, ax1, ay1 = [c*MM for c in aisle['rect']]
names = sorted(o.name for o in bpy.data.objects if o.name.startswith(('Containment_', 'CableTray_')))
for n in names:
    mn, mx = wbbox(bpy.data.objects[n])
    print('%-24s x[%.3f,%.3f] y[%.3f,%.3f] z[%.3f,%.3f]' % (n, mn.x, mx.x, mn.y, mx.y, mn.z, mx.z))
rmn, rmx = wbbox(bpy.data.objects['Containment_Roof_1'])
if rmn.x > ax0+1e-3 or rmx.x < ax1-1e-3 or rmn.y > ay0+1e-3 or rmx.y < ay1-1e-3: problems.append('roof coverage')
if not (2.5 < rmn.z < 2.75): problems.append('roof z')
for tag in ('W', 'E'):
    dmn, dmx = wbbox(bpy.data.objects['Containment_Door_1_%s' % tag])
    if dmn.y > ay0+1e-3 or dmx.y < ay1-1e-3: problems.append('door %s span' % tag)
    if abs(dmn.z - FLOOR_Z) > 1e-3 or abs(dmx.z - 2.6) > 1e-3: problems.append('door %s z' % tag)
    if dmx.x <= ax0 or dmn.x >= ax1: problems.append('door %s at end' % tag)

print('--- tiles ---')
tl = [o for o in bpy.data.objects if o.name.startswith('PerfTile_')]
cells = set()
for o in tl:
    mn, mx = wbbox(o)
    cells.add((round(mn.x, 3), round(mn.y, 3)))
    if abs(mx.z - FLOOR_Z) > 1e-3: problems.append('%s top z %.4f' % (o.name, mx.z))
    if abs((mx.x-mn.x)-0.6) > 1e-3 or abs((mx.y-mn.y)-0.6) > 1e-3: problems.append('%s size' % o.name)
    if mn.x < ax0-1e-6 or mx.x > ax1+1e-6 or mn.y < ay0-1e-6 or mx.y > ay1+1e-6: problems.append('%s outside aisle' % o.name)
    for rid, rm2, rm3 in racks:
        if overlap((mn, mx), (rm2, rm3)): problems.append('tile %s hits rack %s' % (o.name, rid))
exp = set()
for i in range(math.ceil(ax0/0.6-1e-7), math.floor(ax1/0.6+1e-7)):
    for j in range(math.ceil(ay0/0.6-1e-7), math.floor(ay1/0.6+1e-7)):
        exp.add((round(i*0.6, 3), round(j*0.6, 3)))
print('tiles %d, cell set matches: %s (expected %d)' % (len(tl), cells == exp, len(exp)))
if cells != exp:
    problems.append('tile cells missing %s extra %s' % (sorted(exp-cells), sorted(cells-exp)))

print('--- trays ---')
for row in ('A', 'B'):
    mn, mx = wbbox(bpy.data.objects['CableTray_%s' % row])
    rs = [r for r in L['racks'] if r['row'] == row]
    rx0 = min(r['center'][0] for r in rs)*MM - 0.3; rx1 = max(r['center'][0] for r in rs)*MM + 0.3
    cy = rs[0]['center'][1]*MM
    if abs(mn.x-rx0) > 1e-3 or abs(mx.x-rx1) > 1e-3: problems.append('tray %s length' % row)
    if abs((mn.y+mx.y)/2 - cy) > 1e-3 or abs((mx.y-mn.y)-0.3) > 1e-3: problems.append('tray %s width/centre' % row)
    if abs(mn.z - 2.9) > 1e-3: problems.append('tray %s bottom' % row)

c = collections.Counter()
for o in bpy.data.objects:
    for p in ('Rack_', 'Containment_', 'PerfTile_', 'CableTray_'):
        if o.name.startswith(p): c[p] += 1
print(dict(c))
print('PROBLEMS:', problems if problems else 'none')
