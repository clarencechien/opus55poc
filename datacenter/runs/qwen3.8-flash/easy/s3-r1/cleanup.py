import bpy
for m in list(bpy.data.meshes):
    if m.users == 0 and m.name.startswith(('Cylinder', 'Cube', '_tmp')):
        bpy.data.meshes.remove(m)
print('orphans left:', [m.name for m in bpy.data.meshes if m.users == 0])
print('objects:', len(bpy.data.objects))
print('rack mesh users:', bpy.data.meshes['RackProto'].users)
