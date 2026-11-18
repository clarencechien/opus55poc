import json, math
# hide walls / floor / ceiling so an elevation render shows the pipe band clearly
hidden = []
for o in bpy.data.objects:
    if o.type == 'MESH' and (o.name.startswith("Wall") or o.name in ("RaisedFloor", "Ceiling")):
        if not o.hide_render:
            o.hide_render = True; o.hide_viewport = True
            hidden.append(o.name)
print("hidden:", hidden)
