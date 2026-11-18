"""Long-lived headless Blender that executes bench requests over a unix socket.

Started by bench.py, never by the model:
    blender -b --factory-startup --python blender_server.py -- --sock S --run DIR [--load FILE.blend]

Protocol: one request per connection; 8-byte big-endian length + UTF-8 JSON in both directions.
Scene units are metres (1 Blender unit = 1 m).
"""
from __future__ import annotations

import contextlib
import io
import json
import math
import os
import socket
import struct
import sys
import time
import traceback

import bpy
import mathutils

argv = sys.argv[sys.argv.index("--") + 1:]
opts = {argv[i].lstrip("-"): argv[i + 1] for i in range(0, len(argv) - 1, 2)}
SOCK, RUN = opts["sock"], opts["run"]
RENDERS = os.path.join(RUN, "renders")
AUTOSAVE = os.path.join(RUN, ".bench", "autosave.blend")
os.makedirs(RENDERS, exist_ok=True)

if opts.get("load") and os.path.exists(opts["load"]):
    bpy.ops.wm.open_mainfile(filepath=opts["load"])
else:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.context.scene.unit_settings.system = "METRIC"
    bpy.context.scene.unit_settings.scale_length = 1.0

NS: dict = {"bpy": bpy, "mathutils": mathutils, "math": math, "__name__": "__bench__"}
MAX_OUT = 8000


def clip(s: str) -> str:
    return s if len(s) <= MAX_OUT else s[:MAX_OUT // 2] + f"\n... [{len(s) - MAX_OUT} chars cut] ...\n" + s[-MAX_OUT // 2:]


def do_exec(req):
    code = req["code"]
    out, err = io.StringIO(), io.StringIO()
    ok = True
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            exec(compile(code, req.get("filename", "<bench>"), "exec"), NS)
        except Exception:
            ok = False
            traceback.print_exc()
    try:
        bpy.ops.wm.save_as_mainfile(filepath=AUTOSAVE, copy=True)
    except Exception:
        pass
    return {"ok": ok, "stdout": clip(out.getvalue()), "stderr": clip(err.getvalue())}


sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from render_common import do_render as _render, scene_bounds, sync_viewport_colors  # noqa: E402


def do_render(req):
    return _render(req, renders_dir=RENDERS)


def do_inspect(req):
    flt = (req.get("filter") or "").lower()
    rows = []
    for o in sorted(bpy.context.scene.objects, key=lambda o: o.name):
        if o.name.startswith("__bench"):
            continue
        if flt and flt not in o.name.lower():
            continue
        rows.append({
            "name": o.name, "type": o.type,
            "loc": [round(v, 3) for v in o.matrix_world.translation],
            "rot_deg": [round(math.degrees(v), 1) for v in o.matrix_world.to_euler()],
            "dims": [round(v, 3) for v in o.dimensions],
            "parent": o.parent.name if o.parent else None,
            "collection": o.users_collection[0].name if o.users_collection else None,
            "props": {k: (v if isinstance(v, (int, float, str, bool)) else str(v)) for k, v in o.items()
                      if not k.startswith("_")},
        })
    total = len(rows)
    lim = int(req.get("limit", 200))
    return {"ok": True, "count": total, "shown": min(total, lim), "objects": rows[:lim]}


def do_save(req):
    path = req.get("path") or os.path.join(RUN, "scene.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path, copy=True)
    out = {"ok": True, "blend": path}
    if req.get("glb"):
        bpy.ops.export_scene.gltf(filepath=req["glb"], export_format="GLB", export_extras=True,
                                  export_apply=True, use_visible=True)
        out["glb"] = req["glb"]
    return out


HANDLERS = {"exec": do_exec, "render": do_render, "inspect": do_inspect, "save": do_save,
            "ping": lambda r: {"ok": True}}


def recv(conn):
    n = struct.unpack(">Q", conn.recv(8, socket.MSG_WAITALL))[0]
    buf = b""
    while len(buf) < n:
        buf += conn.recv(n - len(buf))
    return json.loads(buf.decode())


def send(conn, obj):
    data = json.dumps(obj).encode()
    conn.sendall(struct.pack(">Q", len(data)) + data)


if os.path.exists(SOCK):
    os.unlink(SOCK)
srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
srv.bind(SOCK)
srv.listen(1)
print("BENCH_SERVER_READY", flush=True)
while True:
    conn, _ = srv.accept()
    with conn:
        try:
            req = recv(conn)
            if req.get("cmd") == "shutdown":
                send(conn, {"ok": True})
                break
            res = HANDLERS[req["cmd"]](req)
        except Exception:
            res = {"ok": False, "stderr": traceback.format_exc()}
        try:
            send(conn, res)
        except Exception:
            pass
srv.close()
os.unlink(SOCK)
