import bpy, json, math
from mathutils import Matrix, Vector

MM = 0.001
L = json.load(open('/home/user/opus55poc/datacenter/runs/qwen3.8-flash/easy/s3-r1/inputs/layout.json'))
scene = bpy.context.scene
coll = bpy.data.collections.get('Collection') or scene.collection
FLOOR_Z = L['room']['raised_floor_height'] * MM
RAD = {'N': (0, 1), 'S': (0, -1), 'E': (1, 0), 'W': (-1, 0)}

def rot_z(d):
    v = RAD[d]
    return math.atan2(v[0], -v[1])

def new_obj(name, me, x=0, y=0, z=0, rz=0.0):
    ob = bpy.data.objects.new(name, me)
    ob.location = (x, y, z)
    ob.rotation_euler = (0.0, 0.0, rz)
    coll.objects.link(ob)
    return ob

def box_me(name, x0, y0, z0, x1, y1, z1, mat=None):
    v = [(x0,y0,z0),(x1,y0,z0),(x1,y1,z0),(x0,y1,z0),(x0,y0,z1),(x1,y0,z1),(x1,y1,z1),(x0,y1,z1)]
    f = [(0,1,2,3),(7,6,5,4),(0,4,5,1),(1,5,6,2),(2,6,7,3),(3,7,4,0)]
    me = bpy.data.meshes.new(name)
    me.from_pydata(v, [], f)
    me.update()
    if mat and bpy.data.materials.get(mat):
        me.materials.append(bpy.data.materials[mat])
    return me

# ---------- build one joined prototype mesh from the RackA template ----------
tmpl = bpy.data.objects['RackA']
inv = tmpl.matrix_world.inverted()
parts = []
def collect(ob):
    for c in ob.children:
        if c.type == 'MESH':
            parts.append(c)
        collect(c)
collect(tmpl)
parts.sort(key=lambda o: o.name)

verts, faces, face_mats, face_uvs, mat_list = [], [], [], [], []
mat_index = {}
for p in parts:
    M = inv @ p.matrix_world
    me = p.data
    uv = me.uv_layers.active.data if me.uv_layers else None
    base = len(verts)
    for v in me.vertices:
        verts.append(M @ v.co)
    for poly in me.polygons:
        faces.append([base + i for i in poly.vertices])
        m = me.materials[poly.material_index] if me.materials else None
        key = m.name if m else None
        if key not in mat_index:
            mat_index[key] = len(mat_list)
            mat_list.append(m)
        face_mats.append(mat_index[key])
        face_uvs.append([tuple(uv[li].uv) for li in range(poly.loop_start, poly.loop_start + poly.loop_total)] if uv else None)

proto = bpy.data.meshes.new('RackProto')
proto.from_pydata([(v.x, v.y, v.z) for v in verts], [], faces)
proto.update()
for m in mat_list:
    if m is not None:
        proto.materials.append(m)
for i, mi in enumerate(face_mats):
    if mi < len(proto.materials):
        proto.polygons[i].material_index = mi
if any(u is not None for u in face_uvs):
    uvl = proto.uv_layers.new(name='UVMap')
    for poly, poly_uvs in zip(proto.polygons, face_uvs):
        if poly_uvs:
            for j, uvv in enumerate(poly_uvs):
                uvl.data[poly.loop_start + j].uv = uvv
proto.update()
xs = [v.co.x for v in proto.vertices]; ys = [v.co.y for v in proto.vertices]; zs = [v.co.z for v in proto.vertices]
print('proto verts %d polys %d mats %d  x[%.3f,%.3f] y[%.3f,%.3f] z[%.3f,%.3f]' % (
    len(proto.vertices), len(proto.polygons), len(proto.materials), min(xs), max(xs), min(ys), max(ys), min(zs), max(zs)))

# ---------- place the racks (linked duplicates of the prototype mesh) ----------
for r in L['racks']:
    ob = new_obj('Rack_%s' % r['id'], proto, r['center'][0]*MM, r['center'][1]*MM, FLOOR_Z, rot_z(r['facing']))
    ob['rackId'] = r['id']
    ob['row'] = r.get('row', '')
    ob['facing'] = r['facing']
print('racks placed:', len(L['racks']))
