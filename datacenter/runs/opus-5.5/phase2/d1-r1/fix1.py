import json
RUN = "/home/user/opus55poc/datacenter/runs/opus-5.5/phase2/d1-r1/"
p = RUN + "asbuilt_pred.json"
lay = json.load(open(p))
for r in lay["racks"]:
    if r["id"] == "F05":
        r["center"] = [5400, 16300.0]
        r["size"] = [800, 1200]
json.dump(lay, open(p, "w"), indent=1)
exec(open(RUN + "build.py").read())
