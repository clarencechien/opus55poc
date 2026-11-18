for o in bpy.data.objects:
    if o.type == 'MESH':
        o.hide_render = False
        o.hide_viewport = False
print("restored visibility")
import json
d = json.load(open("routes.json"))
for r in d["routes"]:
    print(r["id"], len(r["points"]), "pts")
