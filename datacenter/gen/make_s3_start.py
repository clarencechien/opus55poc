"""Build the S3 start scene: oracle room shell (from layout.json) + neutral template racks outside the room.

    blender -b --factory-startup --python make_s3_start.py -- LAYOUT.json OUT.blend
"""
import os
import sys

import bpy

here = os.path.dirname(os.path.abspath(__file__))
layout, out = sys.argv[sys.argv.index("--") + 1:][:2]
ns = {"__name__": "__s3__"}
exec(open(os.path.join(here, "..", "oracle", "s2_oracle.py")).read(), ns)  # builds RackA at (0,0), RackB at (1.5,0)
bpy.data.objects["RackA"].location = (-3.0, 2.0, 0.0)
bpy.data.objects["RackB"].location = (-4.5, 5.0, 0.0)  # its parts sit 1.5 m east of the root -> centred at x = -3
sys.path.insert(0, os.path.join(here, "..", "oracle"))
from s1_oracle import SHELL  # noqa: E402
shell = SHELL.replace("for o in list(bpy.data.objects):\n    bpy.data.objects.remove(o)\n", "")
exec(f"LAYOUT = {layout!r}\n" + shell, {"__name__": "__s3__"})
bpy.ops.wm.save_as_mainfile(filepath=out)
print("objects", len(bpy.data.objects))
