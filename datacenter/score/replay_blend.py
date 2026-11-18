"""Rebuild a run's stage .blend by replaying every successful `bench exec` from bench_log.jsonl.

    blender -b --factory-startup --python replay_blend.py -- RUN_DIR STAGE
"""
import contextlib
import io
import json
import math
import os
import sys

import bpy
import mathutils

run, stage = sys.argv[sys.argv.index("--") + 1:][:2]
bpy.ops.wm.read_factory_settings(use_empty=True)
start = os.path.join(run, ".bench", "start.blend")
if os.path.exists(start):
    bpy.ops.wm.open_mainfile(filepath=start)
ns = {"bpy": bpy, "mathutils": mathutils, "math": math, "__name__": "__bench__"}
n = 0
for line in open(os.path.join(run, "bench_log.jsonl")):
    e = json.loads(line)
    if e.get("cmd") == "exec" and "code" in e:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            try:
                exec(compile(e["code"], "<replay>", "exec"), ns)
            except Exception:
                pass  # failed calls failed the same way live; their partial effects are kept, as live
        n += 1
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(run, f"{stage}.blend"))
print("replayed", n, "exec calls")
