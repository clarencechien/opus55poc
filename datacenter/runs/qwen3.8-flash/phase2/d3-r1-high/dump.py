import bpy, json, os
from mathutils import Vector

obs = []
empties = []
for o in bpy.data.objects:
    if o.type == 'MESH':
        # world-space AABB from local bbox corners (handles scale/parent/rotation)
        corners = [o.matrix_world @ Vector(c) for c in o.bound_box]
        mn = Vector((min(c.x for c in corners), min(c.y for c in corners), min(c.z for c in corners)))
        mx = Vector((max(c.x for c in corners), max(c.y for c in corners), max(c.z for c in corners)))
        obs.append({"name": o.name,
                    "min": list(mn), "max": list(mx),
                    "loc": [o.location.x, o.location.y, o.location.z],
                    "dims": [o.dimensions.x, o.dimensions.y, o.dimensions.z]})
    else:
        empties.append({"name": o.name, "type": o.type,
                        "loc": [o.matrix_world.translation.x, o.matrix_world.translation.y, o.matrix_world.translation.z]})

with open(os.path.join(os.getcwd(), "obstacles.json"), "w") as f:
    json.dump({"obstacles": obs, "empties": empties}, f, indent=1)
print("meshes", len(obs), "empties", len(empties))
print("x", min(o["min"][0] for o in obs), max(o["max"][0] for o in obs))
print("y", min(o["min"][1] for o in obs), max(o["min"][1] for o in obs), max(o["max"][1] for o in obs))
print("z", min(o["min"][2] for o in obs), max(o["max"][2] for o in obs))
