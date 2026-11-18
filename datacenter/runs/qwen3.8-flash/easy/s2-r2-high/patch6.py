src = open("build.py").read()
old = """    pts = [(x0, -0.29, Z0B + 31 * U), (x0 - 0.02, -0.36, 1.1),
           (x0 - 0.05, -0.40, 0.7), (x0 - 0.06, -0.36, 0.3),
           (x0 - 0.05, -0.28, Z0B + 17 * U)]"""
new = """    pts = [(x0, -0.29, Z0B + 31 * U), (x0 - 0.02, -0.315, 1.1),
           (x0 - 0.05, -0.345, 0.7), (x0 - 0.06, -0.32, 0.3),
           (x0 - 0.05, -0.28, Z0B + 17 * U)]"""
assert old in src; src = src.replace(old, new)
open("build.py", "w").write(src)
print("patched6")
