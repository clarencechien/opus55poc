import bpy, json, math
from mathutils import Matrix, Vector

MM = 0.001
L = json.load(open('/home/user/opus55poc/datacenter/runs/qwen3.8-flash/easy/s3-r1/inputs/layout.json'))
coll = bpy.data.collections.get('Collection') or bpy.context.scene.collection
FLOOR_Z = L['room']['raised_floor_height'] * MM      # 0.6 : top of raised floor
RACK_TOP = FLOOR_Z + 2.0                             # 2.6
TILE = 0.6

def ob_new(name, me, x=0, y=0, z=0, rz=0.0):
    o = bpy.data.objects.new(name, me)
    o.location = (x, y, z); o.rotation_euler = (0, 0, rz)
    coll.objects.link(o)
    return o

def boxes_me(name, boxes, mat='steel'):
    """one mesh made of several axis-aligned boxes"""
    vs, fs = [], []
    for (x0, y0, z0, x1, y1, z1) in boxes:
        b = len(vs)
        vs += [(x0,y0,z0),(x1,y0,z0),(x1,y1,z0),(x0,y1,z0),
               (x0,y0,z1),(x1,y0,z1),(x1,y1,z1),(x0,y1,z1)]
        fs += [(b+0,b+1,b+2,b+3),(b+7,b+6,b+5,b+4),(b+0,b+4,b+5,b+1),
               (b+1,b+5,b+6,b+2),(b+2,b+6,b+7,b+3),(b+3,b+7,b+4,b+0)]
    me = bpy.data.meshes.new(name)
    me.from_pydata(vs, [], fs)
    me.update()
    m = bpy.data.materials.get(mat)
    if m:
        me.materials.append(m)
    return me

# ---------------- clean a previous attempt (keep racks / templates) --------------
for o in list(bpy.data.objects):
    if o.name.startswith(('Containment_', 'PerfTile_', 'CableTray_', '_tmp')):
        bpy.data.objects.remove(o, do_unlink=True)
for me in list(bpy.data.meshes):
    if me.users == 0:
        bpy.data.meshes.remove(me)

cold = [a for a in L['aisles'] if a['type'] == 'cold']

# ---------------- 1. cold-aisle containment ----------------
for i, a in enumerate(cold, start=1):
    x0, y0, x1, y1 = [c * MM for c in a['rect']]
    t = 0.05
    me = boxes_me('Containment_Roof_%d' % i, [(x0, y0, RACK_TOP, x1, y1, RACK_TOP + t)])
    o = ob_new('Containment_Roof_%d' % i, me); o['aisle'] = i; o['part'] = 'roof'
    for tag, (dx0, dx1) in (('W', (x0, x0 + t)), ('E', (x1 - t, x1))):
        nm = 'Containment_Door_%d_%s' % (i, tag)
        me = boxes_me(nm, [(dx0, y0, FLOOR_Z, dx1, y1, RACK_TOP)], mat='perf')
        d = ob_new(nm, me); d['aisle'] = i; d['end'] = tag; d['part'] = 'door'
        print(nm, 'x', round(dx0,3), round(dx1,3))

# ---------------- 2. perforated tiles ----------------
th = 0.03
tm = boxes_me('PerfTileProto', [(-TILE/2, -TILE/2, -th, TILE/2, TILE/2, 0.0)], mat='perf')
tobj = bpy.data.objects.new('_tmp_tile', tm)
coll.objects.link(tobj)
ok = False
try:
    cutters = []
    n, pitch = 5, 0.1
    for a in range(n):
        for b in range(n):
            px = (a - (n - 1) / 2) * pitch
            py = (b - (n - 1) / 2) * pitch
            bpy.ops.mesh.primitive_cylinder_add(vertices=12, radius=0.03, depth=th * 4,
                                                location=(px, py, -th / 2))
            cutters.append(bpy.context.object)
    bpy.ops.object.select_all(action='DESELECT')
    for c in cutters:
        c.select_set(True)
    bpy.context.view_layer.objects.active = cutters[0]
    bpy.ops.object.join()
    cut = bpy.context.view_layer.objects.active
    bpy.ops.object.select_all(action='DESELECT')
    tobj.select_set(True)
    bpy.context.view_layer.objects.active = tobj
    mo = tobj.modifiers.new('perf', 'BOOLEAN')
    mo.operation = 'DIFFERENCE'; mo.object = cut; mo.solver = 'EXACT'
    bpy.ops.object.modifier_apply(modifier=mo.name)
    bpy.data.objects.remove(cut, do_unlink=True)
    ok = True
except Exception as e:
    print('boolean failed, plain tiles instead:', e)
print('tile mesh: verts %d polys %d perforated %s' % (len(tm.vertices), len(tm.polygons), ok))
bpy.data.objects.remove(tobj, do_unlink=True)

n_tile = 0
for a in cold:
    x0, y0, x1, y1 = [c * MM for c in a['rect']]
    ix0, ix1 = math.ceil(x0 / TILE - 1e-7), math.floor(x1 / TILE + 1e-7)
    iy0, iy1 = math.ceil(y0 / TILE - 1e-7), math.floor(y1 / TILE + 1e-7)
    for ixs in range(ix0, ix1):
        for iys in range(iy0, iy1):
            n_tile += 1
            t = ob_new('PerfTile_%02d' % n_tile, tm, (ixs + 0.5) * TILE, (iys + 0.5) * TILE, FLOOR_Z)
            t['cell'] = [ixs, iys]
            t['aisleX'] = ixs
print('perf tiles:', n_tile)

# ---------------- 3. cable trays over each rack row ----------------
rows = {}
for r in L['racks']:
    rows.setdefault(r['row'], []).append(r)
W, CLR, PLATE, RAIL = 0.3, 0.3, 0.04, 0.14
for row, rs in sorted(rows.items()):
    xs = []
    for r in rs:
        xs += [r['center'][0] * MM - r['size'][0] * MM / 2, r['center'][0] * MM + r['size'][0] * MM / 2]
    x0, x1 = min(xs), max(xs)
    cy = sum(r['center'][1] for r in rs) / len(rs) * MM
    y0, y1 = cy - W / 2, cy + W / 2
    z0 = RACK_TOP + CLR
    me = boxes_me('CableTray_%s' % row, [
        (x0, y0, z0, x1, y1, z0 + PLATE),          # bottom plate
        (x0, y0, z0, x1, y0 + 0.02, z0 + RAIL),    # side rail
        (x0, y1 - 0.02, z0, x1, y1, z0 + RAIL)])   # side rail
    o = ob_new('CableTray_%s' % row, me)
    o['row'] = row
    print('tray', row, 'x', round(x0, 3), round(x1, 3), 'y', round(y0, 3), round(y1, 3),
          'z', round(z0, 3), round(z0 + RAIL, 3))

print('built. scene objects:', len(bpy.data.objects))
