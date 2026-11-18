import json
data = json.load(open("/home/user/opus55poc/datacenter/runs/qwen3.8-flash/hard/s3-r1-high/inputs/layout.json"))

counts = {"Rack_":0, "Containment_":0, "PerfTile_":0, "CableTray_":0}
props_ok = True
for ob in bpy.data.objects:
    for p in counts:
        if ob.name.startswith(p):
            counts[p] += 1
            if p == "Rack_" and ob.get("rackId") is None:
                props_ok = False
                print("no rackId:", ob.name)
print(counts, "props_ok:", props_ok)

# rack ids complete
ids = {f"Rack_{r['id']}" for r in data["racks"]}
names = {ob.name for ob in bpy.data.objects if ob.name.startswith("Rack_")}
print("missing:", ids - names, "extra:", names - ids)

# sample transforms
for nm in ("Rack_A01", "Rack_B01", "Rack_E01", "Rack_F01"):
    ob = bpy.data.objects[nm]
    print(nm, "loc", tuple(round(v,3) for v in ob.location),
          "rotZ", round(ob.rotation_euler.z,3), "rackId", ob["rackId"])

# containment / tray / tile summary bounds
import mathutils
def wbbox(ob):
    deps = bpy.context.evaluated_depsgraph_get()
    ev = ob.evaluated_get(deps)
    pts = [ev.matrix_world @ mathutils.Vector(c) for c in ev.bound_box]
    return (round(min(p.x for p in pts),2), round(max(p.x for p in pts),2),
            round(min(p.y for p in pts),2), round(max(p.y for p in pts),2),
            round(min(p.z for p in pts),2), round(max(p.z for p in pts),2))
for nm in ("Containment_Aisle1_Roof","Containment_Aisle1_DoorW","Containment_Aisle3_DoorS",
           "CableTray_A","CableTray_E"):
    print(nm, wbbox(bpy.data.objects[nm]))
