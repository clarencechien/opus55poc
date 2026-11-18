import bpy, bmesh, json, os
from mathutils import Matrix

RUN = '/home/user/opus55poc/datacenter/runs/qwen3.8-flash/hard/s1-r1-high'

# ------------------------------------------------------------------ data ----
GRID_X = {'A': 0, 'B': 6300, 'C': 12600, 'D': 18900, 'E': 25200}
GRID_Y = {'1': 0, '2': 6300, '3': 12600, '4': 18900}
WT, CH, RFH = 200, 3000, 600

columns = [('B/2', 6300, 6300), ('C/2', 12600, 6300), ('D/2', 18900, 6300),
           ('B/3', 6300, 12600), ('C/3', 12600, 12600)]

doors = [{'id': 'D1', 'center': [9000, 0], 'width': 1800, 'wall': 'S'},
         {'id': 'D2', 'center': [22050, 12600], 'width': 1200, 'wall': 'N'}]

crah = [{'id': 'CRAH-1', 'center': [550, 3000],   'size': [1800, 900], 'facing': 'E'},
        {'id': 'CRAH-2', 'center': [550, 9900],   'size': [1800, 900], 'facing': 'E'},
        {'id': 'CRAH-3', 'center': [24650, 9300], 'size': [1800, 900], 'facing': 'W'}]

racks = []
for i in range(6):
    racks.append({'id': 'E%02d' % (i+1), 'center': [3000, 14400 + 600*i],
                  'size': [600, 1200], 'facing': 'E'})
for i in range(6):
    racks.append({'id': 'F%02d' % (i+1), 'center': [5400, 14400 + 600*i],
                  'size': [600, 1200], 'facing': 'W'})
for i in range(13):
    racks.append({'id': 'D%02d' % (i+1), 'center': [3300 + 600*i, 8700],
                  'size': [600, 1200], 'facing': 'S'})
xs = [3300 + 600*i for i in range(13)]
for i, x in enumerate(xs):
    if i == 5:
        continue                      # C06 position occupied by column B/2 (not drawn)
    racks.append({'id': 'C%02d' % (i+1), 'center': [x, 6300],
                  'size': [600, 1200], 'facing': 'N'})
bx = [13600, 14400, 15200] + [15900 + 600*i for i in range(7)]
for i, x in enumerate(bx):
    racks.append({'id': 'B%02d' % (i+1), 'center': [x, 4300],
                  'size': [800, 1200] if i < 3 else [600, 1200], 'facing': 'S'})
for i in range(11):
    racks.append({'id': 'A%02d' % (i+1), 'center': [13500 + 600*i, 1900],
                  'size': [600, 1200], 'facing': 'N'})

aisles = [{'type': 'cold', 'rect': [3600, 14100, 4800, 17700]},
          {'type': 'cold', 'rect': [3000, 6900, 10800, 8100]},
          {'type': 'cold', 'rect': [13200, 2500, 19800, 3700]}]

polygon = [[100, 100], [25100, 100], [25100, 12500],
           [18800, 12500], [18800, 18800], [100, 18800]]

layout = {
    'units': 'mm',
    'grid': {'x': GRID_X, 'y': GRID_Y},
    'room': {'polygon': polygon, 'wall_thickness': WT,
             'clear_height': CH, 'raised_floor_height': RFH},
    'columns': [{'id': c[0], 'center': [c[1], c[2]], 'size': [600, 600]} for c in columns],
    'doors': doors, 'crah': crah, 'racks': racks, 'aisles': aisles,
}
with open(os.path.join(RUN, 'layout_pred.json'), 'w') as f:
    json.dump(layout, f, indent=2)
print('json ok')

# --------------------------------------------------------------- blender ----
for ob in list(bpy.data.objects):
    bpy.data.objects.remove(ob, do_unlink=True)
for me in list(bpy.data.meshes):
    bpy.data.meshes.remove(me)

M = 1000.0
H = (RFH + CH) / M
T = WT / M


def add_box(bm, x0, x1, y0, y1, z0, z1):
    mat = Matrix.Translation(((x0+x1)/2, (y0+y1)/2, (z0+z1)/2)) @ \
          Matrix.Diagonal(((x1-x0)/2, (y1-y0)/2, (z1-z0)/2, 1.0))
    bmesh.ops.create_cube(bm, size=2.0, matrix=mat)


def make(name, boxes):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    for b in boxes:
        add_box(bm, *b)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(ob)
    return ob


make('Wall_W', [(-0.1, 0.1, 0.1, 18.8, 0, H)])
make('Wall_E', [(25.1, 25.3, 0.1, 18.8, 0, H)])
make('Wall_S', [(-0.1, 8.1, -0.1, 0.1, 0, H), (9.9, 25.3, -0.1, 0.1, 0, H)])
make('Wall_N', [(-0.1, 25.3, 18.8, 19.0, 0, H)])
make('Wall_UPS_W', [(18.8, 19.0, 12.5, 18.8, 0, H)])
make('Wall_UPS_S', [(19.0, 21.45, 12.5, 12.7, 0, H), (22.65, 25.1, 12.5, 12.7, 0, H)])
for cid, cx, cy in columns:
    make('Column_' + cid.replace('/', '_'),
         [(cx/M - 0.3, cx/M + 0.3, cy/M - 0.3, cy/M + 0.3, 0, H)])
make('RaisedFloor', [(0.1, 25.1, 0.1, 12.5, 0, 0.6), (0.1, 18.8, 12.5, 18.8, 0, 0.6)])

for ob in sorted(bpy.data.objects, key=lambda o: o.name):
    bb = [ob.matrix_world @ __import__('mathutils').Vector(c) for c in ob.bound_box]
    xs = [v.x for v in bb]; ys = [v.y for v in bb]; zs = [v.z for v in bb]
    print('%-14s' % ob.name, 'x %.2f..%.2f' % (min(xs), max(xs)),
          'y %.2f..%.2f' % (min(ys), max(ys)), 'z %.2f..%.2f' % (min(zs), max(zs)))
