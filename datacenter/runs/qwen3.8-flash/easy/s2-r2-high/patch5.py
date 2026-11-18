src = open("closeups.py").read()
src = src.replace("'WORKBENCH'", "'BLENDER_WORKBENCH'")
open("closeups.py", "w").write(src)
print("ok")
