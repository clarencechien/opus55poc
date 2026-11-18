import json, bmesh
RUN = "/home/user/opus55poc/datacenter/runs/opus-5.5/phase2/d2-r1"
lay = json.load(open(RUN + "/layout_design.json"))
room = json.load(open(RUN + "/inputs/room.json"))
for o in list(bpy.data.objects):
    if o.name.startswith("P_") or o.name.startswith("V_"):
        bpy.data.objects.remove(o, do_unlink=True)

def box(bm, x0, y0, x1, y1, z0, z1):
    vs = [bm.verts.new((x, y, z)) for z in (z0, z1) for (x, y) in ((x0, y0), (x1, y0), (x1, y1), (x0, y1))]
    for f in ((0, 1, 2, 3), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)):
        bm.faces.new([vs[i] for i in f])

def make(name, rects, z0, z1, color):
    bm = bmesh.new()
    for r in rects:
        box(bm, r[0]/1000, r[1]/1000, r[2]/1000, r[3]/1000, z0, z1)
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new(name, me); ob.color = color
    bpy.context.scene.collection.objects.link(ob)

A, G, FR = [], [], []
for k in lay["racks"]:
    w = k["size"][0]; cx, cy = k["center"]; f = k["facing"]
    if f in "NS": r = (cx-w/2, cy-600, cx+w/2, cy+600)
    else: r = (cx-600, cy-w/2, cx+600, cy+w/2)
    (G if w == 800 else A).append((r[0]+15, r[1]+15, r[2]-15, r[3]-15))
    t = 200
    if f == "N": FR.append((r[0]+50, r[3]-t, r[2]-50, r[3]))
    if f == "S": FR.append((r[0]+50, r[1], r[2]-50, r[1]+t))
    if f == "E": FR.append((r[2]-t, r[1]+50, r[2], r[3]-50))
    if f == "W": FR.append((r[0], r[1]+50, r[0]+t, r[3]-50))
make("V_racks", A, 0.6, 2.6, (0.2, 0.4, 0.9, 1))
make("V_gpu", G, 0.6, 2.6, (0.9, 0.3, 0.1, 1))
make("V_front", FR, 0.6, 2.7, (1, 1, 0.2, 1))
CR = []
for u in room["crah"]:
    cx, cy = u["center"]
    CR.append((cx-450, cy-900, cx+450, cy+900))
make("V_crah", CR, 0.6, 2.6, (0.1, 0.8, 0.2, 1))
sh = bpy.context.scene.display.shading
sh.color_type = "OBJECT"
print("ok", len(A), len(G))
