import json, os, collections
d = json.load(open("obstacles.json"))
obs = d["obstacles"]
groups = collections.defaultdict(list)
for o in obs:
    n = o["name"]
    key = n.split('_')[0] if '_' in n else n
    groups[key].append(o)
for k in sorted(groups):
    g = groups[k]
    print("=== %s  n=%d" % (k, len(g)))
    if k in ("Rack", "Wall", "Column", "RaisedFloor", "Ceiling", "Manifold", "CableTray", "Beam", "Duct", "CRAH", "Containment"):
        pass
    for o in sorted(g, key=lambda o: o["name"])[:200]:
        print("   %-18s min=%s max=%s" % (o["name"],
              ["%.2f" % v for v in o["min"]], ["%.2f" % v for v in o["max"]]))
print("EMPTIES")
for e in d["empties"]:
    print("  ", e["name"], ["%.2f" % v for v in e["loc"]])
