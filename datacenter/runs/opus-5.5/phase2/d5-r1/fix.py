root = bpy.data.objects["Target"]
for i, (x, y) in enumerate([(-0.46, -0.46), (0.34, -0.46), (-0.46, 0.46), (0.34, 0.46)]):
    o = bpy.data.objects["Foot%d" % i]
    me = o.data
    # recenter: shift verts by delta from current centroid
    cx = sum(v.co.x for v in me.vertices) / len(me.vertices)
    cy = sum(v.co.y for v in me.vertices) / len(me.vertices)
    for v in me.vertices:
        v.co.x += x - cx
        v.co.y += y - cy
    me.update()
    print(o.name, round(x, 3), round(y, 3))
