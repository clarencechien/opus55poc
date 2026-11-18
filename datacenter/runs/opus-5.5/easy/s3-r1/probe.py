for o in bpy.data.objects:
    print(o.name, o.type, tuple(round(v,3) for v in o.location), tuple(round(math.degrees(v),1) for v in o.rotation_euler),
          tuple(round(v,3) for v in o.dimensions), 'parent=', o.parent.name if o.parent else None,
          'data=', o.data.name if o.data else None, 'coll=', [c.name for c in o.users_collection], dict(o.items()) if o.keys() else {})
o = bpy.data.objects.get('RackA')
if o and o.type == 'MESH':
    import mathutils
    vs = [v.co for v in o.data.vertices]
    print('RackA local bbox', [min(v[i] for v in vs) for i in range(3)], [max(v[i] for v in vs) for i in range(3)])
    print('materials', [m.name if m else None for m in o.data.materials])
print('collections', [(c.name, [x.name for x in c.objects][:5]) for c in bpy.data.collections])
