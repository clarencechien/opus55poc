import json
from mathutils import Vector, Matrix
RUN = "/home/user/opus55poc/datacenter/runs/opus-5.5/phase2/d1-r1/"
cams = json.load(open(RUN + "inputs/cameras.json"))["cameras"]
d = json.load(open(RUN + "inputs/design.json"))
items = d["racks"] + d["crah"]
W, H = 1280, 960
def proj(cam, p):
    pos = Vector(cam["position_m"]); tgt = Vector(cam["target_m"])
    fwd = (tgt - pos).normalized()
    right = fwd.cross(Vector((0, 0, 1))).normalized()
    up = right.cross(fwd)
    v = Vector(p) - pos
    z = v.dot(fwd)
    if z <= 0.05:
        return None
    f = cam["lens_mm"] / cam["sensor_width_mm"] * W
    return (W/2 + f * v.dot(right)/z, H/2 - f * v.dot(up)/z)
def box(it):
    cx, cy = it["center"][0]/1000, it["center"][1]/1000
    w, dd = it["size"][0]/1000, it["size"][1]/1000
    if it["facing"] in ("E", "W"):
        w, dd = dd, w
    h = 2.6 if "row" in it else 2.55
    return [(cx+sx*w/2, cy+sy*dd/2, z) for sx in (-1, 1) for sy in (-1, 1) for z in (0.6, h)]
SEL = CAMSEL
for ci in SEL:
    cam = cams[ci-1]
    out = []
    for it in items:
        ps = [proj(cam, p) for p in box(it)]
        if any(p is None for p in ps):
            continue
        xs = [p[0] for p in ps]; ys = [p[1] for p in ps]
        if max(xs) < 0 or min(xs) > W:
            continue
        out.append("%s:%d-%d/%d-%d" % (it["id"], min(xs), max(xs), min(ys), max(ys)))
    print("CAM", ci, " ".join(out))
