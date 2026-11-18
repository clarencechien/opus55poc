#!/usr/bin/env python3
"""Operator-side setup for a bench stage (not exposed to the models).

    bench_admin.py init --run DIR --stage s1 --scenario easy [--budget 60] [--minutes 45] [--start FILE.blend]
    bench_admin.py stop
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import shutil
import signal
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=["init", "stop"])
    ap.add_argument("--run")
    ap.add_argument("--stage", default="s1")
    ap.add_argument("--scenario", default="easy")
    ap.add_argument("--budget", type=int, default=60)
    ap.add_argument("--minutes", type=int, default=45)
    ap.add_argument("--start")
    a = ap.parse_args()
    if a.action == "stop":
        run = pathlib.Path((pathlib.Path.home() / ".bench_current").read_text().strip())
        pid = run / ".bench" / "blender.pid"
        if pid.exists():
            try:
                os.killpg(int(pid.read_text()), signal.SIGKILL)
            except Exception:
                pass
        return
    run = pathlib.Path(a.run).resolve()
    if run.exists() and any(run.iterdir()):
        raise SystemExit(f"{run} is not empty")
    (run / ".bench").mkdir(parents=True)
    src = ROOT / "inputs" / a.scenario
    shutil.copytree(src, run / "inputs")
    if a.stage in ("s2", "s3", "s4") or True:
        ref = ROOT / "ref"
        if ref.exists() and a.stage == "s2":
            shutil.copytree(ref, run / "inputs" / "ref")
    if a.start:
        shutil.copy(a.start, run / ".bench" / "start.blend")
    now = time.time()
    st = {"stage": a.stage, "scenario": a.scenario, "budget": a.budget, "used": 0,
          "started": now, "deadline": now + a.minutes * 60}
    (run / ".bench" / "state.json").write_text(json.dumps(st, indent=1))
    (pathlib.Path.home() / ".bench_current").write_text(str(run))
    print(json.dumps({"run": str(run), **st}, indent=1))


if __name__ == "__main__":
    main()
