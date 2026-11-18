#!/usr/bin/env python3
"""bench — the only interface both models get to Blender.

    bench exec FILE.py                 run Python inside the persistent Blender scene (bpy available; 1 unit = 1 m)
    bench render VIEW [--res WxH]      preview render; VIEW = top | iso | front | back | left | right | cam:x,y,z>tx,ty,tz
    bench inspect [--filter TEXT]      JSON summary of scene objects (name, loc, rot, dims, custom props)
    bench view FILE.png                show an image (input plan, reference photo, or a render)
    bench save                         save the .blend for this stage
    bench submit STAGE                 hand in the stage (locks further calls)
    bench status                       remaining calls and time

exec / render / inspect / save count against the stage budget; view / status / submit do not.
The run directory comes from $BENCH_RUN or ~/.bench_current (written by bench_admin.py).
"""
from __future__ import annotations

import hashlib
import json
import os
import pathlib
import signal
import socket
import struct
import subprocess
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent
BLENDER = os.environ.get("BENCH_BLENDER", "/opt/blender/blender")
COUNTED = {"exec", "render", "inspect", "save"}
TIMEOUTS = {"exec": 180, "render": 180, "inspect": 60, "save": 120}


def run_dir() -> pathlib.Path:
    p = os.environ.get("BENCH_RUN") or (pathlib.Path.home() / ".bench_current").read_text().strip()
    return pathlib.Path(p).resolve()


RUN = run_dir()
META = RUN / ".bench"
STATE = META / "state.json"
SOCK = f"/tmp/bench-{hashlib.md5(str(RUN).encode()).hexdigest()[:12]}.sock"  # AF_UNIX paths max ~107 chars
LOG = RUN / "bench_log.jsonl"


def load_state() -> dict:
    return json.loads(STATE.read_text())


def save_state(st: dict) -> None:
    STATE.write_text(json.dumps(st, indent=1))


def log(entry: dict) -> None:
    entry["t"] = round(time.time(), 2)
    with LOG.open("a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def out(obj: dict, code: int = 0):
    print(json.dumps(obj, ensure_ascii=False, indent=1))
    sys.exit(code)


def rpc(req: dict, timeout: float):
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.settimeout(timeout)
    s.connect(SOCK)
    data = json.dumps(req).encode()
    s.sendall(struct.pack(">Q", len(data)) + data)
    n = struct.unpack(">Q", s.recv(8, socket.MSG_WAITALL))[0]
    buf = b""
    while len(buf) < n:
        chunk = s.recv(n - len(buf))
        if not chunk:
            break
        buf += chunk
    s.close()
    return json.loads(buf.decode())


def server_alive() -> bool:
    try:
        return rpc({"cmd": "ping"}, 5).get("ok", False)
    except Exception:
        return False


def kill_server() -> None:
    pidf = META / "blender.pid"
    if pidf.exists():
        try:
            os.killpg(int(pidf.read_text()), signal.SIGKILL)
        except Exception:
            pass
        pidf.unlink(missing_ok=True)


def start_server() -> None:
    kill_server()
    autosave = META / "autosave.blend"
    start = META / "start.blend"
    load = autosave if autosave.exists() else (start if start.exists() else None)
    cmd = [BLENDER, "-b", "--factory-startup", "--python", str(HERE / "blender_server.py"), "--",
           "--sock", SOCK, "--run", str(RUN)]
    if load:
        cmd += ["--load", str(load)]
    logf = open(META / "blender.log", "a")
    p = subprocess.Popen(cmd, stdout=logf, stderr=subprocess.STDOUT, start_new_session=True)
    (META / "blender.pid").write_text(str(p.pid))
    for _ in range(120):
        if server_alive():
            return
        if p.poll() is not None:
            break
        time.sleep(0.5)
    raise RuntimeError("Blender server failed to start; see .bench/blender.log")


def ensure_server() -> None:
    if not server_alive():
        start_server()


def main(argv: list[str]) -> None:
    if not argv or argv[0] in {"-h", "--help", "help"}:
        print(__doc__)
        return
    cmd, args = argv[0], argv[1:]
    st = load_state()
    now = time.time()
    remaining_s = int(st["deadline"] - now)
    if cmd == "status":
        out({"stage": st["stage"], "calls_used": st["used"], "calls_left": st["budget"] - st["used"],
             "seconds_left": max(remaining_s, 0), "submitted": st.get("submitted", False)})
    if st.get("submitted"):
        out({"ok": False, "error": f"stage {st['stage']} already submitted"}, 1)
    if cmd in COUNTED:
        if st["used"] >= st["budget"]:
            log({"cmd": cmd, "args": args, "refused": "budget"})
            out({"ok": False, "error": "call budget exhausted; submit now with: bench submit " + st["stage"]}, 1)
        if remaining_s <= 0:
            log({"cmd": cmd, "args": args, "refused": "time"})
            out({"ok": False, "error": "time limit reached; submit now with: bench submit " + st["stage"]}, 1)
        st["used"] += 1
        save_state(st)

    if cmd == "view":
        if not args:
            out({"ok": False, "error": "usage: bench view FILE.png"}, 1)
        p = pathlib.Path(args[0])
        p = p if p.is_absolute() else (pathlib.Path.cwd() / p)
        if not p.exists():
            out({"ok": False, "error": f"no such file: {p}"}, 1)
        try:
            from PIL import Image
            size = Image.open(p).size
        except Exception:
            size = None
        log({"cmd": "view", "args": [str(p)]})
        out({"ok": True, "image": str(p.resolve()), "size": size})

    if cmd == "submit":
        if not args or args[0] != st["stage"]:
            out({"ok": False, "error": f"usage: bench submit {st['stage']}"}, 1)
        sys.path.insert(0, str(HERE))
        from stages import check_submission  # noqa: E402
        try:
            ensure_server()
            scene = rpc({"cmd": "inspect", "limit": 100000}, 60).get("objects", [])
        except Exception:
            scene = None
        problems = check_submission(st["stage"], RUN, scene)
        if problems and not st.get("submit_warned"):
            st["submit_warned"] = True
            save_state(st)
            log({"cmd": "submit", "warning": problems})
            out({"ok": False, "error": "submission incomplete (run submit again to hand in anyway)",
                 "problems": problems}, 1)
        try:
            ensure_server()
            req = {"cmd": "save", "path": str(RUN / f"{st['stage']}.blend")}
            if st["stage"] != "s1":
                req["glb"] = str(RUN / f"{st['stage']}.glb")
            rpc(req, 300)
        except Exception as e:
            problems = (problems or []) + [f"could not save blend: {e}"]
        st["submitted"] = True
        st["submitted_at"] = now
        save_state(st)
        log({"cmd": "submit", "problems": problems})
        try:
            rpc({"cmd": "shutdown"}, 10)
        except Exception:
            kill_server()
        out({"ok": True, "submitted": st["stage"], "problems": problems})

    if cmd not in COUNTED:
        out({"ok": False, "error": f"unknown command {cmd}; see bench --help"}, 1)

    if cmd == "exec":
        if not args:
            out({"ok": False, "error": "usage: bench exec FILE.py"}, 1)
        p = pathlib.Path(args[0])
        if not p.exists():
            out({"ok": False, "error": f"no such file: {p}"}, 1)
        req = {"cmd": "exec", "code": p.read_text(), "filename": str(p)}
    elif cmd == "render":
        if not args:
            out({"ok": False, "error": "usage: bench render VIEW [--res WxH]"}, 1)
        req = {"cmd": "render", "view": args[0]}
        if "--res" in args:
            req["res"] = args[args.index("--res") + 1]
        if "--lens" in args:
            req["lens"] = args[args.index("--lens") + 1]
    elif cmd == "inspect":
        req = {"cmd": "inspect"}
        if "--filter" in args:
            req["filter"] = args[args.index("--filter") + 1]
    else:  # save
        req = {"cmd": "save", "path": str(RUN / f"{st['stage']}.blend")}

    t0 = time.time()
    try:
        ensure_server()
        res = rpc(req, TIMEOUTS[cmd])
    except socket.timeout:
        kill_server()
        res = {"ok": False, "error": f"{cmd} timed out after {TIMEOUTS[cmd]} s; Blender was restarted "
                                     "from the state after the last successful exec"}
    except Exception as e:
        kill_server()
        st["used"] -= 1  # infrastructure failure: do not charge the model
        save_state(st)
        res = {"ok": False, "error": f"bench infrastructure error (not counted): {e}"}
    res["calls_left"] = st["budget"] - st["used"]
    res["seconds_left"] = max(int(st["deadline"] - time.time()), 0)
    entry = {"cmd": cmd, "args": args, "ok": res.get("ok"), "sec": round(time.time() - t0, 2)}
    if cmd == "exec":
        entry["code"] = req["code"]
        entry["stdout"], entry["stderr"] = res.get("stdout", ""), res.get("stderr", "")
    elif cmd == "render":
        entry["path"] = res.get("path")
    log(entry)
    if cmd == "inspect" and res.get("ok"):  # one object per line keeps large scenes readable
        objs = res.pop("objects", [])
        print(json.dumps(res, ensure_ascii=False))
        for o in objs:
            print(json.dumps(o, ensure_ascii=False, separators=(",", ":")))
        sys.exit(0)
    out(res, 0 if res.get("ok") else 1)


if __name__ == "__main__":
    main(sys.argv[1:])
