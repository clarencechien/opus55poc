src = open("build.py").read()
src = src.replace('RA = empty("RackA", (0, 0, 0))',
                  'RA = empty("RackA", (0, 0, 0))\nscene.view_layer.update()')
src = src.replace('RB = empty("RackB", (1.5, 0, 0))',
                  'RB = empty("RackB", (1.5, 0, 0))\nscene.view_layer.update()')
open("build.py", "w").write(src)
print("patched2")
