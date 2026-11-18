#!/usr/bin/env python3
"""Build the inspection page: datacenter/report/index.html + img/ (run from anywhere).

Collects every pilot run (scores, timing, the model's own exec'd code and output, its renders, fixed review
renders, layout predictions) and the Gemini judge results into one embedded JSON blob.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import re

from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "report"
IMG = OUT / "img"
IMG.mkdir(parents=True, exist_ok=True)

MODELS = {
    "opus": {"label": "Opus 5.5", "note": "Claude Code 子代理，effort high"},
    "qwen-high": {"label": "Qwen 3.8 Flash · high", "note": "OpenRouter，reasoning effort high"},
    "qwen-default": {"label": "Qwen 3.8 Flash · 預設", "note": "OpenRouter，供應商預設推理強度"},
}
# Opus token counts come from the sub-agent completion reports (Claude Code does not write them to the run folder)
OPUS_TOKENS = {"easy/s1-r1": 77931, "easy/s2-r1": 151057, "easy/s3-r1": 91693, "hard/s1-r1": 82881, "hard/s3-r1": 103424}

SECTIONS = [
    {"id": "s1-easy", "stage": "s1", "scenario": "easy", "title": "S1 平面圖 → 3D 空間 · easy",
     "runs": [("opus", "opus-5.5/easy/s1-r1"), ("qwen-high", "qwen3.8-flash/easy/s1-r2-high"), ("qwen-default", "qwen3.8-flash/easy/s1-r1")],
     "inputs": [("inputs/easy/plan.png", "輸入：平面圖（easy）")]},
    {"id": "s1-hard", "stage": "s1", "scenario": "hard", "title": "S1 平面圖 → 3D 空間 · hard",
     "runs": [("opus", "opus-5.5/hard/s1-r1"), ("qwen-high", "qwen3.8-flash/hard/s1-r1-high")],
     "inputs": [("inputs/hard/plan.png", "輸入：平面圖（hard：L 形機房、UPS 室、柱子打斷的列、GPU 櫃、東西向的列）")]},
    {"id": "s2", "stage": "s2", "scenario": "easy", "title": "S2 照片 → 機櫃模型",
     "runs": [("opus", "opus-5.5/easy/s2-r1"), ("qwen-high", "qwen3.8-flash/easy/s2-r2-high"), ("qwen-default", "qwen3.8-flash/easy/s2-r1")],
     "inputs": [("ref/rack_row_front_nersc.jpg", "參考：NERSC 封閉式機櫃正面（CC0）"),
                ("ref/rack_rear_cray_nersc.jpg", "參考：機櫃背面（CC0）"),
                ("ref/rack_open_frame_raised_floor.jpg", "參考：開放式框架機櫃＋架高地板（CC BY 2.0, Carl Lender）"),
                ("ref/hall_overview_cern.jpg", "參考：CERN 機房俯瞰（CC BY-SA 3.0, Hugovanmeijeren）")]},
    {"id": "s3-easy", "stage": "s3", "scenario": "easy", "title": "S3 機櫃擺進空間 · easy",
     "runs": [("opus", "opus-5.5/easy/s3-r1"), ("qwen-high", "qwen3.8-flash/easy/s3-r2-high"), ("qwen-default", "qwen3.8-flash/easy/s3-r1")],
     "inputs": [("judge/assets/easy-s3_layout_plan.png", "輸入的 layout.json（重畫成平面圖，模型拿到的是 JSON）")]},
    {"id": "s3-hard", "stage": "s3", "scenario": "hard", "title": "S3 機櫃擺進空間 · hard",
     "runs": [("opus", "opus-5.5/hard/s3-r1"), ("qwen-high", "qwen3.8-flash/hard/s3-r1-high")],
     "inputs": [("judge/assets/hard-s3_layout_plan.png", "輸入的 layout.json（重畫成平面圖，模型拿到的是 JSON）")]},
    {"id": "s1p", "stage": "s1p", "scenario": "photo-hard", "title": "S1P 現場照片 → 推回佈局",
     "runs": [("opus", "opus-5.5/photo-hard/s1p-r1"), ("qwen-high", "qwen3.8-flash/photo-hard/s1p-r1-high")],
     "inputs": [(f"inputs/photo-hard/photo_{i}.jpg", f"輸入：現場照片 {i}（相機參數在 cameras.json）") for i in range(1, 6)]
               + [("inputs/photo-hard/plan_empty.png", "輸入：空房間平面圖（沒有設備）")]},
]

REVIEW = {
    "s1": [("redrawn_plan.png", "用它的 layout_pred.json 重畫的平面圖"), ("review_top.png", "殼體俯視"), ("review_iso.png", "殼體等角")],
    "s2": [(f"review_Rack{r}_{v}.png", f"Rack {r} · {n}") for r in "AB" for v, n in
           (("front", "正面"), ("close", "近景"), ("iso", "等角"), ("back", "背面"), ("right", "側面"))],
    "s1p": [("overlay_plan.png", "佈局對照：灰框＝真實位置；綠＝對到且朝向對，橘＝對到但朝向錯，紅＝600 mm 內對不到；白線＝前方")],
    "s2cyc": [(f"../review_cycles/cyc_Rack{r}_{v}.jpg", f"Rack {r} · {n}（Cycles）") for r in "AB" for v, n in
              (("front", "正面"), ("front_open", "拿掉門看內部"), ("close", "近景"), ("back", "背面"), ("side", "側面"))],
    "s3": [("review_top.png", "俯視"), ("review_iso.png", "等角"), ("review_overview0.png", "總覽 1"),
           ("review_coldaisle0.png", "冷通道 1 內部"), ("review_overview1.png", "總覽 2"), ("review_coldaisle1.png", "冷通道 2 內部"),
           ("review_overview2.png", "總覽 3"), ("review_coldaisle2.png", "冷通道 3 內部")],
}


def put_image(src: pathlib.Path, max_w: int, keep_png=False) -> str | None:
    if not src.exists():
        return None
    key = hashlib.md5(str(src.resolve().relative_to(ROOT)).encode()).hexdigest()[:12]
    im = Image.open(src)
    if im.width > max_w:
        im = im.resize((max_w, round(im.height * max_w / im.width)), Image.LANCZOS)
    if keep_png:
        name = f"{key}.png"
        im.save(IMG / name, "PNG", optimize=True)
    else:
        name = f"{key}.jpg"
        im.convert("RGB").save(IMG / name, "JPEG", quality=82, optimize=True)
    return f"img/{name}"


def clip(s: str, n: int) -> str:
    s = s or ""
    return s if len(s) <= n else s[:n] + f"\n… [截斷 {len(s) - n} 字]"


def run_info(model_key: str, rel: str, stage: str) -> dict:
    run = ROOT / "runs" / rel
    info = {"model": model_key, "path": f"datacenter/runs/{rel}", "exists": run.exists()}
    if not run.exists():
        return info
    log = [json.loads(l) for l in (run / "bench_log.jsonl").read_text().splitlines() if l.strip()]
    ts = [e["t"] for e in log if "t" in e]
    summ = run / "run_summary.json"
    if summ.exists():
        s = json.loads(summ.read_text())
        info.update(seconds=s["seconds"], turns=s["turns"], bench_calls=s["bench_calls"], cost=s["cost_usd"],
                    tokens=s["tokens"], effort=s.get("reasoning_effort", "provider default"))
    else:
        st = run / ".bench" / "state.json"
        if st.exists():
            d = json.loads(st.read_text())
            info.update(seconds=round(d.get("submitted_at", ts[-1]) - d["started"], 1), bench_calls=d["used"])
        else:
            info.update(seconds=round(ts[-1] - ts[0], 1) if ts else None,
                        bench_calls=sum(1 for e in log if e.get("cmd") in ("exec", "render", "inspect", "save")))
        key = "/".join(rel.split("/")[1:])
        info.update(cost=None, tokens={"total": OPUS_TOKENS.get(key)}, effort="high")
    # scores
    for f, k in (("score_s1.json", "score"), ("score_s3.json", "score"), ("score_s2_auto.json", "score"), ("score_s1p.json", "score")):
        if (run / f).exists():
            info[k] = json.loads((run / f).read_text())
    # the model's own work, in order
    steps = []
    for e in log:
        if e.get("cmd") == "exec":
            steps.append({"kind": "exec", "file": (e.get("args") or ["?"])[0], "ok": e.get("ok"), "sec": e.get("sec"),
                          "code": clip(e.get("code", ""), 12000), "out": clip(e.get("stdout", ""), 3000),
                          "err": clip(e.get("stderr", ""), 3000)})
        elif e.get("cmd") in ("render", "inspect", "save", "submit", "view"):
            steps.append({"kind": e["cmd"], "args": " ".join(e.get("args") or []) if isinstance(e.get("args"), list) else "",
                          "ok": e.get("ok"), "refused": e.get("refused")})
    info["steps"] = steps
    # model's own renders (process), at most 12 evenly spread
    rend = sorted((run / "renders").glob("*.png")) if (run / "renders").exists() else []
    if len(rend) > 12:
        idx = [round(i * (len(rend) - 1) / 11) for i in range(12)]
        rend = [rend[i] for i in sorted(set(idx))]
    info["own_renders"] = [{"src": put_image(p, 640), "name": p.name} for p in rend]
    info["own_render_total"] = len(list((run / "renders").glob("*.png"))) if (run / "renders").exists() else 0
    # fixed review renders
    info["review"] = []
    review_set = "s2cyc" if stage == "s2" and (run / "review_cycles").exists() else stage
    for fname, cap in REVIEW[review_set]:
        wide = fname in ("redrawn_plan.png", "overlay_plan.png")
        src = put_image((run / "review" / fname).resolve(), 1800 if wide else 1024, keep_png=wide)
        if src:
            info["review"].append({"src": src, "cap": cap})
    if (run / "review_cycles" / "structure.json").exists():
        info["structure"] = (run / "review_cycles" / "structure.json").read_text()
    if (run / "layout_pred.json").exists():
        info["layout_pred"] = clip((run / "layout_pred.json").read_text(), 60000)
    files = sorted(p.name for p in run.iterdir() if p.is_file() and p.suffix in (".py", ".json") and not p.name.startswith(("score", "run_summary")))
    info["files"] = files
    return info


def judge_info() -> list:
    out = []
    jd = ROOT / "judge"
    label_of = {}
    for _, sec in enumerate(SECTIONS):
        for mk, rel in sec["runs"]:
            label_of[str((ROOT / "runs" / rel).resolve())] = MODELS[mk]["label"]
    specs = [
        ("s2-easy-argon", "judge.json", "mapping.json", "S2（Cycles 評審圖）", "Gemini 4 Argon（Gemini API 直連）"),
        ("s2-easy-carbon", "judge.json", "mapping.json", "S2（Cycles 評審圖）", "Gemini 4 Carbon（Gemini API 直連）"),
        ("s1-easy", "judge.json", "mapping.json", "S1 easy", "Gemini 3.8 Flash（Gemini API 直連）"),
        ("s1-easy", "judge_openrouter_gemini-4-argon.json", "mapping_openrouter_gemini-4-argon.json", "S1 easy", "Gemini 4 Argon（經 OpenRouter，早期試跑）"),
        ("s2-easy-qwen-default", "judge.json", "mapping.json", "S2", "Gemini 3.8 Flash"),
        ("s2-easy-qwen-high", "judge.json", "mapping.json", "S2", "Gemini 3.8 Flash"),
        ("s3-easy", "judge.json", "mapping.json", "S3 easy", "Gemini 3.8 Flash"),
    ]
    for d, jf, mf, stage, model in specs:
        j, m = jd / d / jf, jd / d / mf
        if not j.exists():
            continue
        J, M = json.loads(j.read_text()), json.loads(m.read_text())
        names = {k: label_of.get(str(pathlib.Path(v).resolve()), v.split("/runs/")[-1]) for k, v in M.items()}
        absolute = {}
        for L, grades in J["absolute"].items():
            rows = []
            for g in grades:
                der = g.get("derived") or {}
                pct = der.get("pct", der.get("total"))
                rows.append({"pct": pct, "raw": g.get("total"), "summary": g.get("summary", ""),
                             "flags": [f"{c.get('category') or c.get('rack', '')} · {c['item']}：{c['verdict']} — {c['note']}"
                                       for c in g.get("checks", []) if c["verdict"] not in ("correct", "present")]})
            absolute[names[L]] = rows
        pairs = []
        for p_ in J.get("pairs") or []:
            nx, ny = names[p_["X_is"]], names[p_["Y_is"]]
            nm = lambda v: nx if v == "X" else ny if v == "Y" else "平手"
            pairs.append(f"{nx} 對 {ny}：整體 {nm(p_['better_overall'])}（{p_['confidence']}）；Rack A {nm(p_['better_rack_A'])}、Rack B {nm(p_['better_rack_B'])}")
        pw = J.get("pairwise") or {}
        out.append({"stage": stage, "judge": model, "dir": f"datacenter/judge/{d}/{jf}", "cost": round(J.get("cost_usd", 0), 3), "pairs": pairs,
                    "absolute": absolute,
                    "pairwise": {k: (names.get(v, v) if v in ("X", "Y") else v) for k, v in pw.items() if k not in ("reason",)},
                    "reason": (re.sub(r"\b(Submission|Model) ([XY])\b", lambda mm: names[mm.group(2)], pw.get("reason", ""))
                               .replace(" X ", f" {names['X']} ").replace(" Y ", f" {names['Y']} ")) if pw else ""})
    return out


def code_info() -> list:
    out = []
    label_of = {}
    for sec in SECTIONS:
        for mk, rel in sec["runs"]:
            label_of[str((ROOT / "runs" / rel).resolve())] = MODELS[mk]["label"]
    for d, stage in (("code-s1-hard", "S1 hard"), ("code-s2-easy", "S2"), ("code-s3-hard", "S3 hard"), ("code-s1p-photo", "S1P 照片")):
        f = ROOT / "judge" / d / "review.json"
        if not f.exists():
            continue
        R, M = json.loads(f.read_text()), json.loads((ROOT / "judge" / d / "mapping.json").read_text())
        names = {k: label_of.get(str(pathlib.Path(v).resolve()), v) for k, v in M.items()}
        reviews = [{"name": names[k], "scores": v["scores"], "bugs": v["bugs"], "strengths": v["strengths"], "summary": v["summary"]}
                   for k, v in sorted(R["reviews"].items(), key=lambda kv: names[kv[0]])]
        pairs = [f"{names[p['X_is']]} 對 {names[p['Y_is']]}：{names[p['X_is']] if p['better'] == 'X' else names[p['Y_is']] if p['better'] == 'Y' else '平手'}"
                 f"（{p['confidence']}）— {p['reason']}" for p in R.get("pairs", [])]
        out.append({"stage": stage, "model": R["model"], "dir": f"datacenter/judge/{d}/review.json", "cost": round(R.get("cost_usd", 0), 3),
                    "reviews": reviews, "pairs": pairs})
    return out


VERIFY = [
    {"stage": "S2", "claim": "Opus 的 Rack A 伺服器高度一致、沒有盲板",
     "check": "讀 s2.blend：Opus Rack A 有 6 個盲板物件，伺服器高度 1U×11、2U×5、4U×3。判斷錯誤，可能因為前門深色開孔、預覽圖無材質看不清。"},
    {"stage": "S3 easy", "claim": "Qwen 的機櫃轉反 180°，背板朝冷通道",
     "check": "Qwen Rack_A01 旋轉 −180°、B01 0°，與 Opus、參考解相同；頂點質心 A 列偏北、B 列偏南（朝冷通道）。判斷錯誤。"},
    {"stage": "S3 easy", "claim": "Opus 完全沒做有孔地磚",
     "check": "Opus 場景有 16 個 PerfTile_*，0.6×0.6 m、頂面 z = 0.6，計分程式逐格確認。判斷錯誤。"},
    {"stage": "S3 hard（程式碼審查）", "claim": "Gemini 4 Carbon：Opus 把 RackG 複本的 root scale 設成 1，蓋掉 1.333 的寬度",
     "check": "計分程式量到 Opus 的 B01–B03 寬度都是 0.8 m（size_ok），GPU 櫃寬度正確；這個 bug 不成立或沒有影響結果。"},
    {"stage": "S2（Gemini 4 Argon）", "claim": "改用 Cycles 評審圖後的判斷",
     "check": "沒有再出現與場景檔矛盾的指控；兩次評分完全一致（Qwen high 94.2、Opus 93.3、Qwen 預設 89.2），但兩兩比較的排序與單獨評分相反。"},
    {"stage": "S1 easy", "claim": "（Gemini 3.8 Flash 自己給的總分約 70）",
     "check": "同一次評分裡所有項目都判「正確」，總分卻打七折；之後改用逐項判定換算分數。"},
]


def main():
    data = {"models": MODELS, "sections": [], "judges": judge_info(), "verify": VERIFY, "code": code_info()}
    for sec in SECTIONS:
        s = {k: sec[k] for k in ("id", "stage", "scenario", "title")}
        s["inputs"] = [{"src": put_image(ROOT / p, 2400 if p.endswith("plan.png") else 1600, keep_png=p.endswith(".png")), "cap": c}
                       for p, c in sec["inputs"]]
        s["runs"] = [run_info(mk, rel, sec["stage"]) for mk, rel in sec["runs"]]
        data["sections"].append(s)
    tpl = (OUT / "template.html").read_text()
    html = tpl.replace("/*__DATA__*/null", json.dumps(data, ensure_ascii=False).replace("</", "<\\/"))
    (OUT / "index.html").write_text(html)
    size = sum(p.stat().st_size for p in IMG.iterdir())
    print(f"index.html {len(html) / 1e6:.2f} MB, images {len(list(IMG.iterdir()))} files {size / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
