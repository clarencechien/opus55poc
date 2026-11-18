src = open("build.py").read()
old = """    hx = hinge_side * (w/2 - 0.09)
    add_box(bm, (hx, 0.022, zc), (0.02, 0.02, 0.30), 0)   # flush handle bar (inner side)
    add_box(bm, (hx - hinge_side*0.02, 0.02, zc + 0.12), (0.03, 0.02, 0.02), 0)
    add_box(bm, (hx - hinge_side*0.02, 0.02, zc - 0.12), (0.03, 0.02, 0.02), 0)
    for zz in (zc - h/2 + 0.08, zc + h/2 - 0.08):
        add_box(bm, (-hx, 0.005, zz), (0.03, 0.04, 0.06), 0)"""
new = """    hx = hinge_side * (w/2 - 0.09)
    inward = 1 if y < 0 else -1
    add_box(bm, (hx, 0.022 * inward, zc), (0.02, 0.02, 0.30), 0)   # flush handle bar (inner side)
    add_box(bm, (hx - hinge_side*0.02, 0.02 * inward, zc + 0.12), (0.03, 0.02, 0.02), 0)
    add_box(bm, (hx - hinge_side*0.02, 0.02 * inward, zc - 0.12), (0.03, 0.02, 0.02), 0)
    for zz in (zc - h/2 + 0.08, zc + h/2 - 0.08):
        add_box(bm, (-hx, 0.005 * inward, zz), (0.03, 0.04, 0.06), 0)"""
assert old in src, "pattern not found"
src = src.replace(old, new)
open("build.py", "w").write(src)
print("patched")
