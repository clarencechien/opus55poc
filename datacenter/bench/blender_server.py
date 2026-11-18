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


def scene_bounds():
    pts = []
    for o in bpy.context.scene.objects:
        if o.type in {"MESH", "CURVE", "FONT"} and o.visible_get():
            pts += [o.matrix_world @ mathutils.Vector(c) for c in o.bound_box]
    if not pts:
        return mathutils.Vector((-5, -5, 0)), mathutils.Vector((5, 5, 3))
    lo = mathutils.Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = mathutils.Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return lo, hi


def sync_viewport_colors():
    """Workbench shows material.diffuse_color; copy Principled base colour so node-built materials read right."""
    for m in bpy.data.materials:
        if m.use_nodes and m.node_tree:
            for n in m.node_tree.nodes:
                if n.type == "BSDF_PRINCIPLED":
                    c = n.inputs["Base Color"].default_value
                    m.diffuse_color = (c[0], c[1], c[2], 1.0)
                    break


def do_render(req):
    sc = bpy.context.scene
    view = req.get("view", "iso")
    w, h = (int(v) for v in req.get("res", "1024x768").split("x"))
    lo, hi = scene_bounds()
    ctr, size = (lo + hi) / 2, hi - lo
    cam_data = bpy.data.cameras.get("__bench_cam") or bpy.data.cameras.new("__bench_cam")
    cam = bpy.data.objects.get("__bench_cam") or bpy.data.objects.new("__bench_cam", cam_data)
    if cam.name not in sc.collection.objects:
        sc.collection.objects.link(cam)
    cam.hide_viewport = False
    cam_data.clip_start, cam_data.clip_end = 0.01, 1000
    aspect = w / h
    if view == "top":
        cam_data.type = "ORTHO"
        cam_data.ortho_scale = max(size.x, size.y * aspect) * 1.08 + 0.5
        cam.location = (ctr.x, ctr.y, hi.z + 20)
        cam.rotation_euler = (0, 0, 0)
    elif view in {"front", "back", "left", "right"}:
        cam_data.type = "ORTHO"
        horiz = size.x if view in {"front", "back"} else size.y
        cam_data.ortho_scale = max(horiz, size.z * aspect) * 1.08 + 0.5
        d = 50
        loc, rot = {
            "front": ((ctr.x, lo.y - d, ctr.z), (math.pi / 2, 0, 0)),
            "back": ((ctr.x, hi.y + d, ctr.z), (math.pi / 2, 0, math.pi)),
            "left": ((lo.x - d, ctr.y, ctr.z), (math.pi / 2, 0, -math.pi / 2)),
            "right": ((hi.x + d, ctr.y, ctr.z), (math.pi / 2, 0, math.pi / 2)),
        }[view]
        cam.location, cam.rotation_euler = loc, rot
    elif view.startswith("cam:"):
        a, b = view[4:].split(">")
        p = mathutils.Vector([float(v) for v in a.split(",")])
        t = mathutils.Vector([float(v) for v in b.split(",")])
        cam_data.type = "PERSP"
        cam_data.lens = float(req.get("lens", 24))
        cam.location = p
        cam.rotation_euler = (t - p).to_track_quat("-Z", "Y").to_euler()
    else:  # iso
        cam_data.type = "PERSP"
        cam_data.lens = 35
        r = max(size.length, 1.0)
        p = ctr + mathutils.Vector((-0.55, -0.75, 0.6)).normalized() * r * 1.25
        cam.location = p
        cam.rotation_euler = (ctr - p).to_track_quat("-Z", "Y").to_euler()
    sc.camera = cam
    sc.render.engine = "BLENDER_WORKBENCH"
    sh = sc.display.shading
    sh.light, sh.color_type = "STUDIO", "MATERIAL"
    sh.show_cavity, sh.show_object_outline = True, True
    sh.show_shadows = view not in {"top"}
    sync_viewport_colors()
    sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = w, h, 100
    sc.render.film_transparent = False
    sc.world = sc.world or bpy.data.worlds.new("World")
    idx = len([f for f in os.listdir(RENDERS) if f.endswith(".png")]) + 1
    safe = "".join(ch if ch.isalnum() else "_" for ch in view)[:40]
    path = os.path.join(RENDERS, f"{idx:03d}_{safe}.png")
    sc.render.filepath = path
    t = time.time()
    bpy.ops.render.render(write_still=True)
    cam.hide_viewport = True
    return {"ok": True, "path": path, "seconds": round(time.time() - t, 2),
            "bounds_m": {"min": [round(v, 3) for v in lo], "max": [round(v, 3) for v in hi]}}


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
