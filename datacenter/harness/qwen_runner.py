#!/usr/bin/env python3
"""Drive one bench stage with a model on OpenRouter, using the same three tools Claude Code gets
(a shell restricted to `bench ...`, write a file, read a file / image).

    python qwen_runner.py --run RUN_DIR --stage s1 [--model qwen/qwen3.8-flash] [--max-cost 1.5] [--max-turns 150]

Needs the OpenRouter key in $or_key (or $OPENROUTER_API_KEY). No nudging: when the model ends its turn
without a tool call, the run ends (a Claude Code session also ends there). Anything not submitted is
submitted by the harness.
"""
from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import os
import pathlib
import shlex
import subprocess
import sys
import time

import requests

HERE = pathlib.Path(__file__).resolve().parent
API = "https://openrouter.ai/api/v1/chat/completions"
TEXT_LIMIT = 20000
IMAGE_MAX = 1568

TOOLS = [
    {"type": "function", "function": {
        "name": "shell",
        "description": "Run a shell command in the run directory. Only `bench ...` commands are allowed. Returns stdout and stderr.",
        "parameters": {"type": "object", "properties": {"command": {"type": "string", "description": "e.g. `bench exec build.py`"}},
                       "required": ["command"]}}},
    {"type": "function", "function": {
        "name": "write_file",
        "description": "Create or overwrite a file in the run directory (path relative to it).",
        "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
                       "required": ["path", "content"]}}},
    {"type": "function", "function": {
        "name": "read_file",
        "description": "Read a file in the run directory. Text files return their content; PNG/JPEG images are shown to you as an image.",
        "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}},
]


class Runner:
    def __init__(self, a):
        self.a = a
        self.run = pathlib.Path(a.run).resolve()
        self.key = os.environ.get("or_key") or os.environ["OPENROUTER_API_KEY"]
        self.log = (self.run / "transcript.jsonl").open("a")
        self.cost = 0.0
        self.tokens = {"prompt": 0, "completion": 0, "cached": 0, "reasoning": 0}

    def rec(self, **kw):
        kw["t"] = round(time.time(), 2)
        self.log.write(json.dumps(kw, ensure_ascii=False) + "\n")
        self.log.flush()

    def inside(self, p: str) -> pathlib.Path:
        q = (self.run / p).resolve() if not os.path.isabs(p) else pathlib.Path(p).resolve()
        if q != self.run and self.run not in q.parents:
            raise ValueError("path must be inside the run directory")
        return q

    def bench_state(self):
        return json.loads((self.run / ".bench" / "state.json").read_text())

    # ---- tools ----
    def t_shell(self, command: str):
        try:
            argv = shlex.split(command)
        except ValueError as e:
            return f"error: {e}", None
        if not argv or argv[0] != "bench" or any(tok in command for tok in (";", "&&", "||", "|", "`", "$(", ">", "<")):
            return "error: only a single `bench ...` command is allowed (no pipes, redirects or chaining)", None
        env = dict(os.environ, BENCH_RUN=str(self.run))
        try:
            p = subprocess.run(["bench"] + argv[1:], cwd=self.run, capture_output=True, text=True, timeout=400, env=env)
            out = p.stdout + (("\n[stderr]\n" + p.stderr) if p.stderr.strip() else "")
        except subprocess.TimeoutExpired:
            out = "error: command timed out"
        return out[:TEXT_LIMIT], None

    def t_write_file(self, path: str, content: str):
        q = self.inside(path)
        q.parent.mkdir(parents=True, exist_ok=True)
        q.write_text(content)
        return f"wrote {len(content)} chars to {q.relative_to(self.run)}", None

    def t_read_file(self, path: str):
        q = self.inside(path)
        if not q.exists():
            return f"error: no such file {path}", None
        mt = mimetypes.guess_type(q.name)[0] or ""
        if mt.startswith("image/"):
            # downscale like Claude Code's image reading does (long edge <= 1568 px) so both sides see similar pixels
            from io import BytesIO
            from PIL import Image
            im = Image.open(q)
            im.load()
            scale = min(1.0, IMAGE_MAX / max(im.size))
            if scale < 1.0:
                im = im.resize((round(im.width * scale), round(im.height * scale)), Image.LANCZOS)
            buf = BytesIO()
            if mt == "image/png":
                im.save(buf, "PNG", optimize=True)
            else:
                im.convert("RGB").save(buf, "JPEG", quality=90)
                mt = "image/jpeg"
            data = base64.b64encode(buf.getvalue()).decode()
            return (f"image {q.relative_to(self.run)} ({im.width}x{im.height}) attached below",
                    {"type": "image_url", "image_url": {"url": f"data:{mt};base64,{data}"}})
        txt = q.read_text(errors="replace")
        return (txt if len(txt) <= TEXT_LIMIT else txt[:TEXT_LIMIT] + f"\n... [{len(txt) - TEXT_LIMIT} chars cut]"), None

    # ---- model ----
    def call(self, messages):
        body = {"model": self.a.model, "messages": messages, "tools": TOOLS, "tool_choice": "auto",
                "usage": {"include": True}, "max_tokens": 32000}
        if self.a.provider:
            body["provider"] = {"order": [self.a.provider], "allow_fallbacks": False}
        for attempt in range(6):
            try:
                r = requests.post(API, headers={"Authorization": f"Bearer {self.key}", "Content-Type": "application/json",
                                                "X-Title": "dc-bench"}, json=body, timeout=600)
                if r.status_code == 200:
                    d = r.json()
                    if "choices" in d:
                        return d
                    self.rec(kind="api_error", body=d)
                else:
                    self.rec(kind="http_error", status=r.status_code, body=r.text[:2000])
                    if r.status_code in (400, 401, 402, 403):
                        raise SystemExit(f"OpenRouter {r.status_code}: {r.text[:500]}")
            except requests.RequestException as e:
                self.rec(kind="net_error", error=str(e))
            time.sleep(min(60, 5 * 2 ** attempt))
        raise SystemExit("OpenRouter: too many failures")

    def go(self):
        sysmsg = (HERE / "prompts" / "system.md").read_text()
        task = (HERE / "prompts" / f"{self.a.stage}.md").read_text()
        messages = [{"role": "system", "content": sysmsg},
                    {"role": "user", "content": f"Your working directory (the run directory) is `{self.run}`.\n\n{task}"}]
        self.rec(kind="start", model=self.a.model, stage=self.a.stage)
        end_reason = "max_turns"
        t0 = time.time()
        for turn in range(self.a.max_turns):
            st = self.bench_state()
            if time.time() > st["deadline"] + 120:
                end_reason = "time"
                break
            if self.cost >= self.a.max_cost:
                end_reason = "cost"
                break
            d = self.call(messages)
            u = d.get("usage") or {}
            self.cost += float(u.get("cost") or 0)
            self.tokens["prompt"] += u.get("prompt_tokens", 0)
            self.tokens["completion"] += u.get("completion_tokens", 0)
            self.tokens["cached"] += (u.get("prompt_tokens_details") or {}).get("cached_tokens", 0) or 0
            self.tokens["reasoning"] += (u.get("completion_tokens_details") or {}).get("reasoning_tokens", 0) or 0
            msg = d["choices"][0]["message"]
            keep = {k: msg[k] for k in ("role", "content", "tool_calls", "reasoning_details") if msg.get(k) is not None}
            keep.setdefault("content", "")
            messages.append(keep)
            self.rec(kind="assistant", turn=turn, provider=d.get("provider"), usage=u, content=msg.get("content"),
                     reasoning=(msg.get("reasoning") or "")[:4000], tool_calls=msg.get("tool_calls"),
                     finish=d["choices"][0].get("finish_reason"))
            calls = msg.get("tool_calls") or []
            if not calls:
                end_reason = "model_stopped"
                break
            images = []
            for c in calls:
                name = c["function"]["name"]
                try:
                    args = json.loads(c["function"].get("arguments") or "{}")
                    fn = getattr(self, "t_" + name, None)
                    out, img = fn(**args) if fn else (f"error: unknown tool {name}", None)
                except Exception as e:
                    out, img = f"error: {type(e).__name__}: {e}", None
                messages.append({"role": "tool", "tool_call_id": c["id"], "content": out})
                self.rec(kind="tool", name=name, args=c["function"].get("arguments", "")[:TEXT_LIMIT], result=out[:4000],
                         image=bool(img))
                if img:
                    images.append((args.get("path"), img))
            if images:
                messages.append({"role": "user", "content": sum(
                    ([{"type": "text", "text": f"[read_file image: {p}]"}, im] for p, im in images), [])})
            if self.bench_state().get("submitted"):
                end_reason = "submitted"
                # let the model finish its turn naturally? A submitted stage refuses further calls; stop here.
                break
        st = self.bench_state()
        if not st.get("submitted"):
            for _ in range(2):
                subprocess.run(["bench", "submit", self.a.stage], cwd=self.run, capture_output=True,
                               env=dict(os.environ, BENCH_RUN=str(self.run)))
        summary = {"kind": "end", "reason": end_reason, "turns": turn + 1, "cost_usd": round(self.cost, 4),
                   "tokens": self.tokens, "seconds": round(time.time() - t0, 1),
                   "bench_calls": self.bench_state()["used"], "auto_submitted": not st.get("submitted")}
        self.rec(**summary)
        (self.run / "run_summary.json").write_text(json.dumps({"model": self.a.model, **summary}, indent=1))
        print(json.dumps(summary, indent=1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--stage", default="s1")
    ap.add_argument("--model", default="qwen/qwen3.8-flash")
    ap.add_argument("--provider", default="Alibaba")
    ap.add_argument("--max-cost", type=float, default=1.5)
    ap.add_argument("--max-turns", type=int, default=150)
    Runner(ap.parse_args()).go()


if __name__ == "__main__":
    sys.exit(main())
