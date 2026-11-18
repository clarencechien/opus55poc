import json
L = json.load(open('/home/user/opus55poc/datacenter/runs/opus-5.5/easy/s3-r1/inputs/layout.json'))
for r in L['racks']:
    o = bpy.data.objects['Rack_' + r['id']]
    o.location = (r['center'][0]/1000, r['center'][1]/1000, 0.6)
# nominal rack top 2.6
for o in bpy.data.objects:
    if o.name.startswith('Containment_') and o.name.endswith('_Roof'):
        o.location.z = 2.6 + 0.015
    elif o.name.startswith('Containment_') and '_Door_' in o.name:
        pass
    elif o.name.startswith('CableTray_'):
        o.location.z = 2.9 + 0.05
bpy.context.view_layer.update()
for o in bpy.data.objects:
    if o.name.startswith(('Containment_', 'CableTray_')):
        bb = [o.matrix_world @ mathutils.Vector(c) for c in o.bound_box]
        print(o.name, [round(min(v[i] for v in bb),3) for i in range(3)], [round(max(v[i] for v in bb),3) for i in range(3)])
