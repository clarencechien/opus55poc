src = open("/home/user/opus55poc/datacenter/runs/opus-5.5/phase2/d1-r1/proj.py").read().replace("CAMSEL", "[]")
exec(src)
def show(ci, it):
    cam = cams[ci-1]
    pts = box(it)
    s = []
    for p in pts:
        if p[2] < 1:  # only top corners
            continue
        q = proj(cam, p)
        s.append("(%.1f,%.1f)->%s" % (p[0], p[1], "behind" if q is None else "%d,%d" % q))
    print("cam%d %s %s %s: %s" % (ci, it["id"], it["center"], it["facing"], " ".join(s)))
for y in (3000, 2400, 1800, 1500):
    show(1, {"id": "CE", "center": [550, y], "size": [1800, 900], "facing": "E"})
for x in (1500, 2100, 2700, 3300):
    show(1, {"id": "CN", "center": [x, 550], "size": [1800, 900], "facing": "N"})
for it in [{"id": "E06", "row": "E", "center": [3000, 16800], "size": [600, 1200], "facing": "E"},
           {"id": "D15", "row": "D", "center": [11700, 8400], "size": [600, 1200], "facing": "S"},
           {"id": "D15g", "row": "D", "center": [11800, 8400], "size": [800, 1200], "facing": "S"}]:
    for ci in (3, 5, 7, 1, 4):
        show(ci, it)
