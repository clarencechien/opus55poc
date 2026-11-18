import bpy
from mathutils import Vector

tiles = [o for o in bpy.data.objects if o.name.startswith("PerfTile_")]
me = tiles[0].data
print("mesh before: z", round(min(v.co.z for v in me.vertices), 4), round(max(v.co.z for v in me.vertices), 4))
for v in me.vertices:
    v.co.z -= 0.6                      # top face now at local z = 0
me.update()
for o in tiles:
    o.location.z = 0.6                 # object sits on the raised floor top
print("mesh after: z", round(min(v.co.z for v in me.vertices), 4), round(max(v.co.z for v in me.vertices), 4))

def wbbox(objs):
    if isinstance(objs, bpy.types.Object):
        objs = [objs]
    mn = Vector((1e9,)*3); mx = Vector((-1e9,)*3)
    for o in objs:
        for p in o.bound_box:
            c = o.matrix_world @ Vector(p)
            mn = Vector(map(min, mn, c)); mx = Vector(map(max, mx, c))
    return mn, mx

for o in sorted(tiles, key=lambda o: o.name)[:3]:
    mn, mx = wbbox(o)
    print(o.name, "loc", tuple(round(v,3) for v in o.location),
          "world", [round(v,3) for v in mn], [round(v,3) for v in mx])
allmn = [wbbox(t) for t in tiles]
print("all tile tops:", sorted({round(mx.z, 4) for mn, mx in allmn}),
      "bottoms:", sorted({round(mn.z, 4) for mn, mx in allmn}))
print("footprints:", sorted({(round((mn.x+mx.x)/2,2), round((mn.y+mx.y)/2,2)) for mn, mx in allmn}))
