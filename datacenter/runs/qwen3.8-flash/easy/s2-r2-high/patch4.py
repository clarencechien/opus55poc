src = open("build.py").read()

# door: add second material slot so grille mi=1 is valid
old = "    return finish(name, bm, RA, [MAT_DOOR], loc=(0, y, 0))"
new = "    return finish(name, bm, RA, [MAT_DOOR, MAT_DOOR], loc=(0, y, 0))"
assert old in src; src = src.replace(old, new)

# bigger grille openings
old = "        add_box(bm, (x0 + i * 0.016, 0, zc), (0.006, 0.008, gh), 1)"
new = "        add_box(bm, (x0 + i * 0.016, 0, zc), (0.005, 0.008, gh), 1)"
assert old in src; src = src.replace(old, new)
old = "        add_box(bm, (0, 0, zz0 + j * 0.016), (gw, 0.008, 0.006), 1)"
new = "        add_box(bm, (0, 0, zz0 + j * 0.016), (gw, 0.008, 0.005), 1)"
assert old in src; src = src.replace(old, new)

# brighter bezel
old = 'MAT_BEZEL   = mkmat("Bezel",       (0.06, 0.06, 0.07),   0.35, 0.3)'
new = 'MAT_BEZEL   = mkmat("Bezel",       (0.11, 0.11, 0.13),   0.35, 0.3)'
assert old in src; src = src.replace(old, new)

# server front: move vents left, add LED dot rows
old = """        for k in range(6):
            add_box(bm, (-0.15 + k * 0.06, -0.274, zc), (0.035, 0.004, hgt * 0.5), 2)
        add_box(bm, (0.20, -0.275, zc), (0.008, 0.004, 0.006), 3)
        add_box(bm, (0.215, -0.275, zc), (0.008, 0.004, 0.006), 4)"""
new = """        for k in range(6):
            add_box(bm, (-0.20 + k * 0.036, -0.274, zc), (0.03, 0.004, hgt * 0.5), 2)
        for k in range(6):
            add_box(bm, (0.03 + k * 0.024, -0.275, zc), (0.006, 0.004, 0.005), 3 if k % 4 else 4)
        add_box(bm, (0.20, -0.275, zc), (0.008, 0.004, 0.006), 3)
        add_box(bm, (0.215, -0.275, zc), (0.008, 0.004, 0.006), 4)"""
assert old in src; src = src.replace(old, new)

open("build.py", "w").write(src)
print("patched4")
