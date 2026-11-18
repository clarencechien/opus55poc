import sys
print(sys.version)
try:
    import numpy as np
    print("numpy", np.__version__)
except Exception as e:
    print("no numpy", e)
import bpy
print([o.name for o in bpy.data.objects][:40])
