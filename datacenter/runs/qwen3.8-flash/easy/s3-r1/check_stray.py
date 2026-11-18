import bpy
known = ('Rack_', 'RackA', 'RackB', 'Wall_', 'Column_', 'RaisedFloor', 'Containment_', 'PerfTile_', 'CableTray_')
odd = [o.name for o in bpy.data.objects if not o.name.startswith(known)]
print('odd objects:', odd)
for n in odd:
    o = bpy.data.objects[n]
    print('  ', n, o.type, tuple(round(v,3) for v in o.location), o.data.name if o.data else None,
          len(o.data.vertices) if o.type=='MESH' else '')
print('meshes users=0:', [m.name for m in bpy.data.meshes if m.users == 0])
print('total objects:', len(bpy.data.objects))
