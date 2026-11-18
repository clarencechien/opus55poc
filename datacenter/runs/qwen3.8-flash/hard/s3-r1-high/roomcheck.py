import json
data = json.load(open("/home/user/opus55poc/datacenter/runs/qwen3.8-flash/hard/s3-r1-high/inputs/layout.json"))
room = data["room"]["polygon"]  # mm
def pt_in(x, y):
    inside = False; j = len(room)-1
    for i in range(len(room)):
        xi, yi = room[i]; xj, yj = room[j]
        if ((yi > y) != (yj > y)) and (x < (xj-xi)*(y-yi)/(yj-yi)+xi):
            inside = True
        j = i
    return inside
bad = 0
for r in data["racks"]:
    w, d = r["size"][0], r["size"][1]
    cx, cy = r["center"]
    if r["facing"] in ("N", "S"):
        x0, x1, y0, y1 = cx-w/2, cx+w/2, cy-d/2, cy+d/2
    else:
        x0, x1, y0, y1 = cx-d/2, cx+d/2, cy-w/2, cy+w/2
    for px, py in ((x0,y0),(x0,y1),(x1,y0),(x1,y1)):
        if not pt_in(px, py):
            print("OUTSIDE:", r["id"]); bad += 1; break
print("outside-room count:", bad)
