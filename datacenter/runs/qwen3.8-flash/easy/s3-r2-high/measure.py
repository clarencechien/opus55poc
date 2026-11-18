import bpy
from mathutils import Vector

def world_bbox(obj):
    return [obj.matrix_world @ Vector(c) for c in obj.bound_box]

def union_bbox(objs):
    mn = Vector((1e9,1e9,1e9)); mx = Vector((-1e9,-1e9,-1e9))
    n = 0
    for o in objs:
        if o.type != 'MESH':
            continue
        for c in world_bbox(o):
            mn = Vector((min(mn[i], c[i]) for i in range(3)))
            mx = Vector((max(mx[i], c[i]) for i in range(3)))
        n += 1
    return mn, mx, n

empt = bpy.data.objects['RackA']
kids = [o for o in bpy.data.objects if o.name.startswith('RackA')]
print("num RackA objects:", len(kids))
mn, mx, n = union_bbox(kids)
print("RackA world bbox min", tuple(round(v,4) for v in mn), "max", tuple(round(v,4) for v in mx), "meshcount", n)
O = empt.matrix_world.translation
print("empty origin", tuple(round(v,4) for v in O))
print("bbox rel to origin: min", tuple(round(v,4) for v in (mn-O)), "max", tuple(round(v,4) for v in (mx-O)))
print("verts total:", sum(len(o.data.vertices) for o in kids if o.type=='MESH'))

for nm in ['RackA_FrontDoor','RackA_RearDoor','RackA_Base','RackA_Top','RackA_Foot_1']:
    o = bpy.data.objects[nm]
    a,b,_ = union_bbox([o])
    print(nm, "rel min", tuple(round(v,4) for v in (a-O)), "rel max", tuple(round(v,4) for v in (b-O)))

# check floor and ceiling heights
for nm in ['RaisedFloor','Wall_N0']:
    o = bpy.data.objects[nm]
    a,b,_ = union_bbox([o])
    print(nm, "min", tuple(round(v,4) for v in a), "max", tuple(round(v,4) for v in b))
for nm in ['Column_B_2','Column_C_2']:
    o = bpy.data.objects[nm]
    a,b,_ = union_bbox([o])
    print(nm, "min", tuple(round(v,4) for v in a), "max", tuple(round(v,4) for v in b))
print("scene objects:", len(bpy.data.objects))
