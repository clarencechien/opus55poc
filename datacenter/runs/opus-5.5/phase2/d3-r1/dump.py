for o in sorted(bpy.data.objects, key=lambda o: o.name):
    if o.type == 'MESH':
        l = o.matrix_world.translation; d = o.dimensions
        r = o.rotation_euler
        print("%s %.3f %.3f %.3f | %.3f %.3f %.3f | z[%.3f,%.3f] rot%.1f,%.1f,%.1f" % (o.name, l.x, l.y, l.z, d.x, d.y, d.z, l.z-d.z/2, l.z+d.z/2, r.x, r.y, r.z))
    else:
        l = o.matrix_world.translation
        print("EMPTY %s %.3f %.3f %.3f" % (o.name, l.x, l.y, l.z))
