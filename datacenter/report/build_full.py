#!/usr/bin/env python3
"""Full report (phase 1 + phase 2) as ONE self-contained HTML file (images embedded, no external requests).

    python report/build_full.py   ->  report/full_report.html (standalone document)
                                      report/full_report_artifact.html (same content without the document shell)

Everything numeric is read from the run directories (score_*.json, run_summary.json, bench_log.jsonl, transcript.jsonl).
Opus runs have no run_summary.json (they ran as Claude Code sessions); their wall-clock seconds are in OPUS_SEC.
"""
from __future__ import annotations

import base64
import html
import io
import json
import pathlib

from PIL import Image, ImageDraw, ImageFont

ROOT = pathlib.Path(__file__).resolve().parents[1]
RUNS = ROOT / "runs"
FONT_B = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
NATIVE_CTX = 262_144  # Qwen3.8-Flash-Next native context (model card)

OPUS_SEC = {"easy/s1-r1": 66, "hard/s1-r1": 95, "easy/s2-r1": 543, "easy/s3-r1": 102, "hard/s3-r1": 135,
            "photo-hard/s1p-r1": 954, "phase2/d1-r1": 567, "phase2/d2-r1": 699, "phase2/d3-r1": 468, "phase2/d5-r1": 154}
# (title, opus run, qwen run, score file, max, correctness weight, phase)
STAGES = [
    ("S1 圖面 → 3D 空間（easy，16 櫃）", "opus-5.5/easy/s1-r1", "qwen3.8-flash/easy/s1-r2-high", "score_s1.json", 100, 3, 1),
    ("S1 圖面 → 3D 空間（hard，58 櫃）", "opus-5.5/hard/s1-r1", "qwen3.8-flash/hard/s1-r1-high", "score_s1.json", 100, 5, 1),
    ("S2 照片 → 機櫃模型（只量幾何）", "opus-5.5/easy/s2-r1", "qwen3.8-flash/easy/s2-r2-high", "score_s2_auto.json", 40, 5, 1),
    ("S3 機櫃擺進空間（easy）", "opus-5.5/easy/s3-r1", "qwen3.8-flash/easy/s3-r2-high", "score_s3.json", 100, 2, 1),
    ("S3 機櫃擺進空間（hard）", "opus-5.5/hard/s3-r1", "qwen3.8-flash/hard/s3-r1-high", "score_s3.json", 100, 5, 1),
    ("S1P 現場照片 → 推回佈局", "opus-5.5/photo-hard/s1p-r1", "qwen3.8-flash/photo-hard/s1p-r1-high", "score_s1p.json", 100, 15, 1),
    ("D1 竣工比對：設計圖 vs 現場照片", "opus-5.5/phase2/d1-r1", "qwen3.8-flash/phase2/d1-r1-high", "score_d1.json", 100, 15, 2),
    ("D2 空機房佈局設計（規則檢查）", "opus-5.5/phase2/d2-r1", "qwen3.8-flash/phase2/d2-r1-high", "score_d2.json", 100, 10, 2),
    ("D3 冷卻水管 3D 繞行", "opus-5.5/phase2/d3-r1", "qwen3.8-flash/phase2/d3-r2-high", "score_d3.json", 100, 5, 2),
    ("D5 依三視圖復刻 CDU 設備", "opus-5.5/phase2/d5-r1", "qwen3.8-flash/phase2/d5-r1-high", "score_d5.json", 100, 5, 2),
]
PASS = 0.8


def b64(im: Image.Image, width: int, quality=80) -> str:
    im = im.convert("RGB")
    if im.width > width:
        im = im.resize((width, round(im.height * width / im.width)), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=quality, optimize=True)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def img(rel: str, width: int, quality=80, crop=None) -> str:
    im = Image.open(ROOT / rel)
    if crop:
        w, h = im.size
        im = im.crop((int(w * crop[0]), int(h * crop[1]), int(w * crop[2]), int(h * crop[3])))
    return b64(im, width, quality)


def sheet(run: str, marks: list[tuple[int, int]]) -> str:
    """5 close-up Cycles renders of one S2 submission side by side, with numbered defect markers."""
    names = ["RackA_front_open", "RackA_close", "RackA_back", "RackB_front", "RackB_close"]
    ims = []
    for n in names:
        im = Image.open(RUNS / run / "review_cycles" / f"cyc_{n}.jpg")
        w, h = im.size
        im = im.crop((int(w * 0.2), int(h * 0.08), int(w * 0.8), int(h * 0.92)))
        ims.append(im.resize((420, int(420 * im.height / im.width))))
    out = Image.new("RGB", (2100, ims[0].height + 34), "white")
    d = ImageDraw.Draw(out)
    f = ImageFont.truetype(FONT_B, 17)
    for i, (im, cap) in enumerate(zip(ims, ["Rack A front, doors hidden", "Rack A 3/4 view", "Rack A rear", "Rack B front", "Rack B 3/4 view"])):
        out.paste(im, (i * 420, 34))
        d.text((i * 420 + 10, 8), cap, fill=(60, 60, 60), font=f)
    fn = ImageFont.truetype(FONT_B, 22)
    for k, (x, y) in enumerate(marks, 1):
        x, y = int(x * 1.05), int(y * 1.05) + 34
        d.ellipse([x - 19, y - 19, x + 19, y + 19], fill=(214, 40, 40), outline="white", width=3)
        d.text((x, y), str(k), fill="white", font=fn, anchor="mm")
    return b64(out, 2100, 82)


def run_stats(rel: str) -> dict:
    run = RUNS / rel
    log = [json.loads(l) for l in (run / "bench_log.jsonl").read_text().splitlines() if l.strip()]
    ex = [e for e in log if e.get("cmd") == "exec"]
    fail = [e for e in ex if not e.get("ok")]
    errs = []
    for e in fail:
        lines = [l for l in (e.get("stderr") or "").strip().splitlines() if l.strip()]
        if lines:
            errs.append(lines[-1][:110])
    st = {"exec": len(ex), "failed": len(fail), "errors": errs[:3],
          "calls": sum(1 for e in log if e.get("cmd") in ("exec", "render", "inspect", "save") and not e.get("refused"))}
    s = run / "run_summary.json"
    if s.exists():
        j = json.loads(s.read_text())
        st.update(sec=j["seconds"], cost=j.get("cost_usd"), turns=j["turns"])
        peak = bad = 0
        for l in (run / "transcript.jsonl").read_text().splitlines():
            d = json.loads(l)
            if d["kind"] == "assistant":
                peak = max(peak, (d.get("usage") or {}).get("prompt_tokens", 0))
            if d["kind"] == "tool" and d["result"].startswith("error"):
                bad += 1
        st.update(peak_ctx=max(peak, j.get("peak_prompt_tokens") or 0), tool_errors=bad)
    else:
        st.update(sec=OPUS_SEC["/".join(rel.split("/")[1:])], cost=None)
    return st


def score(rel: str, f: str):
    d = json.loads((RUNS / rel / f).read_text())
    return d.get("total", d.get("auto_total_40")), d


def fmt_t(s):
    return f"{round(s)} 秒" if s < 120 else f"{s / 60:.0f} 分鐘"


E = html.escape
data = []
for title, o, q, f, mx, w, ph in STAGES:
    so, do = score(o, f)
    sq, dq = score(q, f)
    data.append(dict(title=title, so=so, sq=sq, mx=mx, w=w, ph=ph, to=run_stats(o), tq=run_stats(q), do=do, dq=dq, o=o, q=q))

rows = []
for ph, label in ((1, "第一階段：照圖面建模、照照片建模、擺放"), (2, "第二階段：沒有標準答案可抄的工程任務")):
    rows.append(f'<tr class="grp"><td colspan="5">{label}</td></tr>')
    for t in (t for t in data if t["ph"] == ph):
        so, sq, mx, to, tq = t["so"], t["sq"], t["mx"], t["to"], t["tq"]
        gap = abs(so - sq) / mx >= 0.1
        rows.append(f"""<tr class="{'gap' if gap else ''}"><td>{E(t['title'])}</td>
      <td class="num"><div class="bar"><i class="o" style="width:{so / mx * 100:.0f}%"></i></div><b>{so:g}</b><span>/{mx}</span></td>
      <td class="num"><div class="bar"><i class="q" style="width:{sq / mx * 100:.0f}%"></i></div><b>{sq:g}</b><span>/{mx}</span></td>
      <td class="num">{fmt_t(to['sec'])}<br><span>{to['calls']} 次操作</span></td>
      <td class="num">{fmt_t(tq['sec'])}<br><span>{tq['calls']} 次操作 · 慢 {tq['sec'] / to['sec']:.1f} 倍</span></td></tr>""")

code_rows = []
for t in data:
    def cell(s):
        e = "".join(f"<li><code>{E(x)}</code></li>" for x in s["errors"])
        return (f"<b>{s['exec']}</b> 支腳本，<b class=\"{'bad' if s['failed'] else ''}\">{s['failed']}</b> 支執行失敗"
                + (f"；另有 {s['tool_errors']} 次工具用法錯誤" if s.get("tool_errors") else "")
                + (f"<ul class=\"err\">{e}</ul>" if e else ""))
    code_rows.append(f"<tr><td>{E(t['title'])}</td><td>{cell(t['to'])}</td><td>{cell(t['tq'])}</td></tr>")

qcost = sum(t["tq"]["cost"] or 0 for t in data)
peaks = [(t["title"], t["tq"]["peak_ctx"]) for t in data]
peak_max = max(p for _, p in peaks)
ctx_rows = "".join(
    f"""<tr class="{'gap' if p >= 0.85 * NATIVE_CTX else ''}"><td>{E(n)}</td><td class="num"><b>{p:,}</b></td>
    <td class="num"><div class="bar"><i class="q" style="width:{min(p / NATIVE_CTX, 1) * 100:.0f}%"></i></div>{p / NATIVE_CTX * 100:.0f}%</td></tr>"""
    for n, p in peaks)
near = [n for n, p in peaks if p >= 0.85 * NATIVE_CTX]


# ---- scoring model (weights set AFTER seeing the results; the report says so and shows other weightings) ----
def model(weights, eff_pts=30, idx=None):
    idx = list(range(len(data))) if idx is None else idx
    sw = sum(weights[i] for i in idx)
    corr_pts = 100 - eff_pts
    out = {}
    for k in ("o", "q"):
        c = sum(weights[i] * data[i]["s" + k] / data[i]["mx"] for i in idx) / sw * corr_pts
        e = sum(min(data[i]["to"]["sec"], data[i]["tq"]["sec"]) / data[i]["t" + k]["sec"] for i in idx) / len(idx) * eff_pts
        gate = all(data[i]["s" + k] / data[i]["mx"] >= PASS for i in idx)
        out[k] = (c, e, c + e, gate)
    return out


W = [t["w"] for t in data]
main = model(W)
corr = {"o": main["o"][0], "q": main["q"][0]}
eff_o, eff_q = main["o"][1], main["q"][1]
tot_o, tot_q = main["o"][2], main["q"][2]
gate_rows = []
for t in data:
    po, pq = t["so"] / t["mx"] >= PASS, t["sq"] / t["mx"] >= PASS
    gate_rows.append(f"""<tr><td>{E(t['title'])}</td><td class="num">{t['w']}</td>
      <td class="num"><b>{t['w'] * t['so'] / t['mx']:.1f}</b> <span class="pf {'p' if po else 'f'}">{'通過' if po else '不通過'}</span></td>
      <td class="num"><b>{t['w'] * t['sq'] / t['mx']:.1f}</b> <span class="pf {'p' if pq else 'f'}">{'通過' if pq else '不通過'}</span></td></tr>""")

ALT = [
    ("本報告採用：照片／竣工比對加重，正確性 70 + 效率 30", model(W)),
    ("10 關同分，正確性 70 + 效率 30", model([1] * 10)),
    ("只看正確性（不計速度），本報告配分", model(W, eff_pts=0)),
    ("只看正確性，10 關同分", model([1] * 10, eff_pts=0)),
    ("只看第一階段 6 關（第一階段報告的算法）", model([5, 10, 10, 5, 10, 30, 0, 0, 0, 0], idx=list(range(6)))),
    ("只看第二階段 4 關，同分，正確性 70 + 效率 30", model([1] * 10, idx=[6, 7, 8, 9])),
]


def verdict(r):
    c, e, tot, gate = r
    ok = gate and tot >= 80
    return f'<b>{tot:.1f}</b> <span class="pf {"p" if ok else "f"}">{"通過" if ok else "不通過"}</span>'


alt_rows = "".join(f"<tr><td>{E(n)}</td><td class='num'>{verdict(r['o'])}</td><td class='num'>{verdict(r['q'])}</td></tr>" for n, r in ALT)
print(f"weighted: opus {tot_o:.1f} (corr {corr['o']:.1f} + eff {eff_o:.1f}); qwen {tot_q:.1f} (corr {corr['q']:.1f} + eff {eff_q:.1f})")
for n, r in ALT:
    print(" ", n, [round(x, 1) if isinstance(x, float) else x for x in r["o"]], [round(x, 1) if isinstance(x, float) else x for x in r["q"]])

S = {t["title"][:3].strip(): t for t in data}
s1p_o, s1p_q = S["S1P"]["do"]["detail"], S["S1P"]["dq"]["detail"]
d1_o, d1_q = S["D1"]["do"]["detail"], S["D1"]["dq"]["detail"]
d2_o, d2_q = S["D2"]["do"]["detail"], S["D2"]["dq"]["detail"]
d3_o, d3_q = S["D3"]["do"]["detail"]["routes"], S["D3"]["dq"]["detail"]["routes"]
d5_o, d5_q = S["D5"]["do"]["detail"], S["D5"]["dq"]["detail"]
slow_lo = min(t["tq"]["sec"] / t["to"]["sec"] for t in data)
slow_hi = max(t["tq"]["sec"] / t["to"]["sec"] for t in data)
d3_detour = [k for k in d3_q if d3_q[k]["length"] > d3_q[k]["L_ref"] + 1e-6]

P2 = "runs/opus-5.5/phase2"
Q2 = "runs/qwen3.8-flash/phase2"
IMG = {
    "s2_opus": sheet("opus-5.5/easy/s2-r1", [(440, 330), (960, 200), (1680, 250), (1390, 130)]),
    "s2_qh": sheet("qwen3.8-flash/easy/s2-r2-high", [(130, 240), (540, 20), (928, 28), (1000, 320), (1390, 250), (1390, 50)]),
    "photo": img("inputs/photo-hard/photo_2.jpg", 900),
    "ov_o": img("runs/" + STAGES[5][1] + "/review/overlay_plan.png", 1300, 85),
    "ov_q": img("runs/" + STAGES[5][2] + "/review/overlay_plan.png", 1300, 85),
    "d1_photo": img("inputs/d1/photo_1.jpg", 900),
    "d1_o": img(f"{P2}/d1-r1/review/d1_overlay.png", 1200, 85),
    "d1_q": img(f"{Q2}/d1-r1-high/review/d1_overlay.png", 1200, 85),
    "d2_o": img(f"{P2}/d2-r1/review/d2_overlay.png", 1200, 85),
    "d2_q": img(f"{Q2}/d2-r1-high/review/d2_overlay.png", 1200, 85),
    "d3_o": img(f"{P2}/d3-r1/review/d3_iso.png", 900, 82, crop=(0.08, 0.25, 0.92, 0.95)),
    "d3_q": img(f"{Q2}/d3-r2-high/review/d3_iso.png", 900, 82, crop=(0.08, 0.25, 0.92, 0.95)),
    "d5_views": img(f"{Q2}/d5-r1-high/review/compare_views.png", 1400, 82),
    "d5_diff": img(f"{Q2}/d5-r1-high/review/compare_diff.png", 1300, 85),
}

DEFECTS = {
    "s2_opus": ("Opus 5.5", [
        ("量測", "櫃體本身只有 570 mm 寬，比規格 600 mm 窄 30 mm；整體外框靠其他零件撐到 600，所以幾何分沒有扣到。"),
        ("目視", "前後門的孔洞畫得太大、太疏，和照片裡細密的網孔不像。"),
        ("目視", "Rack B 的藍色線束走在機櫃外側，像硬管一樣懸空轉彎，不像實際的線束。"),
        ("目視", "Rack B 上方的 4U 光纖箱正面像一片螢幕，看不出是什麼設備。"),
    ], "做對的：1U／2U／4U 伺服器混搭、6 片盲板、腳輪加調整腳、後門對開、頂板有走線開孔（射線檢查透空率 2.6%）、沒有懸空或重疊的零件。"),
    "s2_qh": ("Qwen 3.8 Flash（high）", [
        ("量測", "Rack A 沒有任何盲板，空的槽位直接空著（任務明確要求盲板）。"),
        ("目視", "Rack A 頂板比櫃體大一圈，前緣突出。"),
        ("目視", "門的角落有缺口（白色 L 形破面）。"),
        ("目視", "後門只有一片開孔板，沒有門把、鉸鏈或線材等細節。"),
        ("量測", "Rack B 沒有配線架（patch panel 物件 0 個）；線材是幾條直線直接穿過理線器，沒有接到任何設備。"),
        ("目視", "Rack B 頂部有一塊用途不明的深色楔形件；設備只是素面方塊。"),
    ], "做對的：伺服器寬 483 mm（19 吋）、導軌高度剛好 42U、LED 會發光、頂板有走線開孔、沒有懸空或重疊的零件。"),
}


def defect_block(key):
    name, items, good = DEFECTS[key]
    lis = "".join(f'<li><span class="n">{i}</span><span class="src {"m" if s == "量測" else "v"}">{s}</span>{E(t)}</li>'
                  for i, (s, t) in enumerate(items, 1))
    return f"""<div class="card"><h3>{E(name)}</h3><div class="scroll"><img src="{IMG[key]}" alt="{E(name)} 的機櫃模型，紅色編號為缺失位置"></div>
      <ol class="defects">{lis}</ol><p class="good">{E(good)}</p></div>"""


CSS = open(pathlib.Path(__file__).with_name("report.css")).read()

BODY = f"""
<main>
<header style="display:flex;flex-direction:column;gap:12px">
  <span class="eyebrow">AI 機房 3D pipeline 驗證 · 完整報告（第一＋第二階段） · 2026-11-18</span>
  <h1>這條機房建模流程不能用地端的 Qwen 3.8 Flash-Next，應使用 Opus</h1>
  <p class="lead">我們讓 Opus 5.5 和 Qwen 3.8 Flash 各自操作 Blender，完成同一條機房建模流程的 10 個關卡：第一階段 6 關是照圖面和照片建模，第二階段 4 關是沒有答案可抄的工程任務。兩邊用同一套工具、同樣的時間和次數上限、同樣的推理強度（high），全部用程式自動計分。</p>
</header>

<section>
  <div class="verdict">
    <span class="eyebrow">結論與建議</span>
    <div class="big">Qwen 3.8 Flash 即使是條件最好的雲端託管版，也有 2 個關卡不及格：「看現場照片推回佈局」53 分、「設計圖對現場照片找差異」60 分（Opus 96 與 100）。10 關加權總分 {tot_q:.0f} 對 {tot_o:.0f}。地端的 Flash-Next 條件只會更差，這條流程應使用 Opus。</div>
    <p>兩個不及格的關卡都是「從現場照片判斷空間」，正好是機房驗收實際要做的事。這次實測的是雲端託管版；「地端只會更差」是依據第 7 節的事實推論，重現用的 repo 已經準備好，可以在地端實測確認。</p>
  </div>
  <div class="three">
    <div class="card"><span class="tag no">2 個關鍵關卡不及格</span><h3>看現場照片：53 分與 60 分</h3>
      <p>照片推回佈局時，Qwen 放錯 2 整列機櫃；竣工比對時，16 處現場和設計不同的地方只找到 6 處，還報了 2 處不存在的差異。Opus 兩關幾乎全對。</p></div>
    <div class="card"><span class="tag no">速度</span><h3>每一關都比 Opus 慢 {slow_lo:.1f}–{slow_hi:.0f} 倍</h3>
      <p>照圖面建模、擺放機櫃、管線繞行和照三視圖建模，Qwen 分數接近 Opus，但用時多很多。竣工比對用了 61 分鐘（上限 60），照片推佈局用了 58 分鐘。</p></div>
    <div class="card"><span class="tag no">地端條件更差</span><h3>3 個關卡的對話長度已經碰到地端原生上限</h3>
      <p>Qwen 最長用到 {peak_max:,} token，Flash-Next 地端原生上限是 262,144。竣工比對和三視圖建模也用到上限的 9 成左右。地端再加上量化和硬體限制，表現預期低於這次的數字。</p></div>
  </div>
</section>

<section>
  <span class="eyebrow">1 · 成績總覽</span>
  <h2>10 個關卡：簡單的建模兩邊都會，差距出現在「看照片」和「速度」</h2>
  <div class="key"><span><i style="background:var(--o)"></i>Opus 5.5（Claude Code，推理強度 high）</span><span><i style="background:var(--q)"></i>Qwen 3.8 Flash（OpenRouter 託管版，推理強度 high）</span></div>
  <div class="tbl"><table><thead><tr><th>關卡</th><th>Opus 分數</th><th>Qwen 分數</th><th>Opus 用時</th><th>Qwen 用時</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div>
  <ul>
    <li>黃底是兩邊差 10% 以上的關卡。差距大的 3 關都要從圖片自己判斷空間或做設計：照片推佈局、竣工比對、空機房佈局設計。</li>
    <li>題目給了清楚數字的關卡（照圖面建模、擺放、管線繞行、三視圖建模），Qwen 也能做到 99 分以上，差別只在速度。</li>
    <li>S2 的 40 分只檢查外框尺寸、擺放位置、命名和面數，<b>不評外觀</b>。外觀的缺失見第 5 節。</li>
    <li>Qwen 10 個關卡的 API 費用合計約 ${qcost:.2f}；Opus 用的是 Claude 方案額度。</li>
  </ul>
</section>

<section>
  <span class="eyebrow">2 · 配分與判定方式</span>
  <h2>判定規則：每一關都要過 80%，再看加權總分；Qwen 兩項都沒過</h2>
  <p>流程是串接的，前一關錯了，後面的 3D 場景就跟著錯，所以先用「每關都要通過」把關，再用加權總分比較。配分是看到結果之後才訂的，所以下面另外列出 6 種不同配分的結果：<b>不管怎麼配，Qwen 都不通過</b>。</p>
  <div class="tbl"><table><thead><tr><th>關卡</th><th>配分</th><th>Opus 得分</th><th>Qwen 得分</th></tr></thead><tbody>
    {''.join(gate_rows)}
    <tr><td>正確性小計</td><td class="num">70</td><td class="num"><b>{corr['o']:.1f}</b></td><td class="num"><b>{corr['q']:.1f}</b></td></tr>
    <tr><td>效率（各關「最快用時 ÷ 自己用時」的平均 × 30）</td><td class="num">30</td><td class="num"><b>{eff_o:.1f}</b></td><td class="num"><b>{eff_q:.1f}</b></td></tr>
    <tr class="gap"><td><b>加權總分</b>（及格 80）</td><td class="num">100</td><td class="num">{verdict(main['o'])}</td><td class="num">{verdict(main['q'])}</td></tr>
  </tbody></table></div>
  <h3>配分理由</h3>
  <ul>
    <li><b>照片推佈局、竣工比對各配 15 分，是最重的兩關</b>：答案不在輸入資料裡，要靠模型自己判斷空間；而且實際驗收機房時，輸入就是現場照片。</li>
    <li><b>空機房佈局設計配 10 分</b>：沒有答案可以對，只能靠規則檢查，最接近實際的規劃工作。</li>
    <li><b>困難版配分比簡單版高</b>：58 櫃、L 形機房比較接近真實機房的規模。</li>
    <li><b>效率配 30 分</b>：流程要反覆執行，速度直接決定能不能實際使用。地端的速度還要再受硬體限制。</li>
  </ul>
  <h3>換一種配分會怎樣</h3>
  <div class="tbl"><table><thead><tr><th>配分方式</th><th>Opus</th><th>Qwen</th></tr></thead><tbody>{alt_rows}</tbody></table></div>
  <p class="note">「通過」要同時滿足兩個條件：所列關卡每一關都 ≥ 80%，而且總分 ≥ 80。只看第二階段時，Qwen 的總分接近及格，但竣工比對只有 60 分，仍然不通過。只看正確性而且 10 關同分時，Qwen 總分 {ALT[3][1]["q"][2]:.1f} 超過 80，但照片推佈局和竣工比對兩關不及格，所以仍不通過。</p>
</section>

<section>
  <span class="eyebrow">3 · 拉開差距的關卡（一）</span>
  <h2>看現場照片推回機房佈局：Opus 幾乎全對，Qwen 放錯兩整列</h2>
  <p>模型只拿到 5 張現場照片、相機位置和一張空房間平面圖，要推出 61 個機櫃和 3 台空調各在哪裡、朝哪個方向。圖上沒有尺寸可以抄。</p>
  <div class="two">
    <figure><img src="{IMG['photo']}" alt="輸入的現場照片之一"><figcaption>輸入的 5 張現場照片之一（用 Blender 渲染的模擬照片）</figcaption></figure>
    <div class="card"><h3>結果</h3>
      <div class="tbl"><table><thead><tr><th></th><th>Opus</th><th>Qwen</th></tr></thead><tbody>
      <tr><td>位置對到的機櫃（共 {s1p_o['racks_gt']}）</td><td class="num"><b>{s1p_o['racks_matched']}</b></td><td class="num"><b>{s1p_q['racks_matched']}</b></td></tr>
      <tr><td>朝向正確率</td><td class="num">{s1p_o['facing_acc'] * 100:.0f}%</td><td class="num">{s1p_q['facing_acc'] * 100:.0f}%</td></tr>
      <tr><td>機櫃寬度正確率</td><td class="num">{s1p_o['width_acc'] * 100:.0f}%</td><td class="num">{s1p_q['width_acc'] * 100:.0f}%</td></tr>
      <tr><td>空調對到（共 3）</td><td class="num">{s1p_o['crah']['matched']}</td><td class="num">{s1p_q['crah']['matched']}</td></tr>
      </tbody></table></div></div>
  </div>
  <div class="two">
    <figure><img src="{IMG['ov_o']}" alt="Opus 的佈局對照圖"><figcaption><b>Opus</b>：唯一的錯是把 C 列東半段的 8 個 600 mm 櫃看成 6 個 800 mm 的 GPU 櫃，少 2 櫃。</figcaption></figure>
    <figure><img src="{IMG['ov_q']}" alt="Qwen 的佈局對照圖"><figcaption><b>Qwen</b>：A、C 兩列整排偏移超過 600 mm，多放 4 櫃；空調放了 4 台、全在西牆，只有 1 台位置對，東牆那台漏掉。</figcaption></figure>
  </div>
  <p class="note">圖例：灰框是真實位置；綠色是位置和朝向都對，紅色是 600 mm 內對不到真實機櫃。</p>
</section>

<section>
  <span class="eyebrow">3 · 拉開差距的關卡（二）</span>
  <h2>竣工比對：Opus 找出全部 16 處差異，Qwen 只找到 6 處</h2>
  <p>模型拿到機房的設計圖（62 台設備的位置）和 7 張竣工後的現場照片，要找出現場和設計不同的地方，交出實際的設備配置。差異的數量不告訴模型；設備可能少了、多了、換位置、轉向或換寬度。</p>
  <div class="two">
    <figure><img src="{IMG['d1_photo']}" alt="竣工比對的現場照片之一"><figcaption>輸入的 7 張現場照片之一。機櫃正面有白色標籤條和藍色 LED，背面沒有，用來判斷朝向。</figcaption></figure>
    <div class="card"><h3>結果</h3>
      <div class="tbl"><table><thead><tr><th></th><th>Opus</th><th>Qwen</th></tr></thead><tbody>
      <tr><td>找到的真實差異（共 {d1_o['true_changes']} 筆）</td><td class="num"><b>{d1_o['matched_changes']}</b></td><td class="num"><b>{d1_q['matched_changes']}</b></td></tr>
      <tr><td>報了但其實沒變（誤報）</td><td class="num">{d1_o['predicted_changes'] - d1_o['matched_changes']}</td><td class="num">{d1_q['predicted_changes'] - d1_q['matched_changes']}</td></tr>
      <tr><td>交出的設備配置裡，和現場相符（共 {d1_o['items_as_built']} 台）</td><td class="num">{d1_o['items_matched']}</td><td class="num">{d1_q['items_matched']}</td></tr>
      <tr><td>現場其實沒有的設備</td><td class="num">{d1_o['items_surplus']}</td><td class="num">{d1_q['items_surplus']}</td></tr>
      </tbody></table></div>
      <p class="note">16 筆差異來自 9 個現場事件：A03–A05 三櫃整排轉向、B03 和 C01–C02 沒裝、E01 移到 E05 的位置、F05 從 600 換成 800 mm、多裝一台 D14、一台空調往南移 1.8 m。Qwen 只找到「三櫃轉向」這一件。</p></div>
  </div>
  <div class="two">
    <figure><img src="{IMG['d1_o']}" alt="Opus 的竣工比對結果"><figcaption><b>Opus</b>：16 處差異全部找到，沒有誤報，交出的 60 台設備全部和現場相符。</figcaption></figure>
    <figure><img src="{IMG['d1_q']}" alt="Qwen 的竣工比對結果"><figcaption><b>Qwen</b>：紅色斜線是漏掉的差異（沒裝的櫃子還留著、移位和換寬度沒發現、空調位置沒改）；橘色是誤報（把一台沒變動的機櫃報成有變動）。</figcaption></figure>
  </div>
  <p class="note">圖例：藍框是真實的差異位置；綠色是交出的設備且正確；紅色斜線是漏掉的差異；橘色是誤報。這一關 Qwen 用了 61 分鐘、31 次操作，最長對話 {S['D1']['tq']['peak_ctx']:,} token；Opus 用了 {fmt_t(S['D1']['to']['sec'])}、{S['D1']['to']['calls']} 次操作。</p>
</section>

<section>
  <span class="eyebrow">3 · 拉開差距的關卡（三）</span>
  <h2>空機房佈局設計：兩邊都沒違規，但 Opus 多放 {d2_o['n_valid'] - d2_q['n_valid']} 櫃</h2>
  <p>給一間空的 L 形機房（柱子、門、固定的空調），要在 9 條規則下（不出牆、不重疊、前後維修空間、冷熱通道、門口動線等）放進最多機櫃，其中剛好 8 台 GPU 櫃。沒有答案可抄，用規則檢查程式計分，以我們用最佳化求解器找到的 250 櫃為滿分基準。</p>
  <div class="two">
    <figure><img src="{IMG['d2_o']}" alt="Opus 的佈局設計"><figcaption><b>Opus</b>：{d2_o['n_valid']} 櫃，0 違規（基準的 {d2_o['raw_ratio'] * 100:.1f}%）。機櫃排成南北向的列，L 形的兩翼都用滿。</figcaption></figure>
    <figure><img src="{IMG['d2_q']}" alt="Qwen 的佈局設計"><figcaption><b>Qwen</b>：{d2_q['n_valid']} 櫃，0 違規（基準的 {d2_q['raw_ratio'] * 100:.1f}%）。機櫃排成東西向的列，北側整條空著沒用到。</figcaption></figure>
  </div>
  <p class="note">兩邊都通過全部 9 條規則，8 台 GPU 櫃都正確。差距在空間利用率：機櫃佔地 Opus {d2_o['it_footprint_m2_valid']:.0f} m²、Qwen {d2_q['it_footprint_m2_valid']:.0f} m²。Qwen 用時 {fmt_t(S['D2']['tq']['sec'])}，Opus {fmt_t(S['D2']['to']['sec'])}。</p>
</section>

<section>
  <span class="eyebrow">4 · 第二階段其他關卡</span>
  <h2>管線繞行和三視圖建模：兩邊都接近滿分，Qwen 慢 2–15 倍</h2>
  <div class="two">
    <div class="card"><h3>D3 冷卻水管 3D 繞行</h3>
      <p>機房天花板下有樑、風管和線槽，要為 6 條冷卻水管從牆上的分歧管各找一條路線接到機櫃頂端，和所有障礙物、其他管線都保持距離。</p>
      <ul>
        <li>兩邊 6 條管線全部合規，沒有碰撞。</li>
        <li>Opus 6 條都是最短路線（和我們的參考解一樣長）。Qwen 有 {len(d3_detour)} 條（{', '.join(d3_detour)}）多繞約 0.36 m、多 1–2 個彎頭，所以 {S['D3']['sq']:g} 分。</li>
        <li>Opus 自己寫了一個 3D 格點尋路程式，{S['D3']['to']['calls']} 次操作完成；Qwen 用 {S['D3']['tq']['calls']} 次操作。</li>
      </ul></div>
    <figure><img src="{IMG['d3_q']}" alt="Qwen 的管線路線"><figcaption>Qwen 的 6 條管線（綠色）。Opus 的路線看起來幾乎相同，差在少幾個彎。</figcaption></figure>
  </div>
  <div class="card"><h3>D5 依三視圖復刻冷卻水分配器（CDU）</h3>
    <p>只給 5 張正投影視圖（每像素 2 mm）和 2 張透視圖，沒有寫尺寸，要量圖把設備建出來，再用 1 cm³ 的體素和真實模型做 3D 比對。</p>
    <ul>
      <li>兩邊外框尺寸都是 0 mm 誤差，體素重合率 Opus {d5_o['iou'] * 100:.2f}%、Qwen {d5_q['iou'] * 100:.2f}%。</li>
      <li>Qwen 的小零件有偏差：4 個腳做得太大（精確度 {d5_q['features']['feet']['score'] * 100:.0f}%）、背面水管位置偏移（{d5_q['features']['rear_manifold']['score'] * 100:.0f}%）、門把偏移（{d5_q['features']['handle']['score'] * 100:.0f}%）。Opus 只有背面水管差一點（{d5_o['features']['rear_manifold']['score'] * 100:.0f}%）。</li>
      <li>Opus {fmt_t(S['D5']['to']['sec'])}、{S['D5']['to']['calls']} 次操作；Qwen {fmt_t(S['D5']['tq']['sec'])}、{S['D5']['tq']['calls']} 次操作，最長對話 {S['D5']['tq']['peak_ctx']:,} token，已到地端原生上限的 {S['D5']['tq']['peak_ctx'] / NATIVE_CTX * 100:.0f}%。</li>
      <li>顏色和材質不計分（題目有說明），兩邊都沒有上色。</li>
    </ul>
    <div class="scroll"><img src="{IMG['d5_views']}" alt="CDU 真實模型（上）和 Qwen 的作品（下）"></div>
    <p class="note">上排是真實的 CDU，下排是 Qwen 建的模型。外形幾乎一樣；差別要看下面的差異圖才看得出來。</p>
    <div class="scroll"><img src="{IMG['d5_diff']}" alt="Qwen 作品和真實模型的體素差異圖"></div>
    <p class="note">差異圖：灰色是兩邊都有；紅色是 Qwen 少做的；藍色是 Qwen 多做的。紅藍並排的線條是位置偏移的零件（背面水管、頂部管口）。</p>
  </div>
</section>

<section>
  <span class="eyebrow">5 · 建出的 3D 元件缺失</span>
  <h2>元件缺失：Qwen 在機櫃模型和竣工配置都有實質缺漏</h2>
  <p>S2 的任務是照 4 張參考照片做一座封閉式機櫃（Rack A）和一座開放式機架（Rack B）。紅色編號對應下方清單。「量測」是用程式直接檢查場景檔得到的；「目視」是看渲染圖判斷的，比較主觀。</p>
  {defect_block('s2_opus')}
  {defect_block('s2_qh')}
  <p class="note">Qwen 預設推理強度（非 high）那次的機櫃另有 6 項缺失（伺服器寬度錯、頂板沒開孔、LED 不發光、盲板懸空、線束和設備穿插），詳見第一階段報告。第二位評審 Gemini 4 Argon 的外觀分數分不出高下（93–94），外觀建議以人工盲測為準。</p>
  <h3>各關卡的元件缺失</h3>
  <div class="tbl"><table><thead><tr><th>關卡</th><th>Opus</th><th>Qwen</th></tr></thead><tbody>
    <tr><td>S1 房間殼體</td><td>easy 版的門洞從地板切到頂，沒有做門楣（任務只要求門洞，不扣分）。北側熱通道只畫到柱線。</td><td>沒有發現缺失；同樣把北側熱通道只畫到柱線。</td></tr>
    <tr><td>S3 擺放</td><td>沒有發現缺失。機櫃用連結複製，場景較輕（hard：6.1 萬個三角面）。</td><td>位置全對，但每個機櫃都合併成一個獨立網格再複製，場景較重（hard：10.6 萬個三角面）。</td></tr>
    <tr><td>S1P 照片推佈局</td><td>C 列東半段的 8 個 600 mm 櫃看成 6 個 GPU 櫃，少 2 櫃。</td><td>2 整列位置錯、多 4 櫃、空調 3 台只對 1 台。</td></tr>
    <tr><td>D1 竣工比對</td><td>沒有缺失：60 台設備全部和現場相符。</td><td>交出 62 台，其中 {d1_q['items_surplus']} 台現場其實沒有（沒裝的 B03、C01、C02 等仍留著）；現場有的 D14、換寬度的 F05、移位的 E05 和空調沒有建出來。</td></tr>
    <tr><td>D2 佈局設計</td><td>0 違規。</td><td>0 違規，但北側整條空間沒用，少放 {d2_o['n_valid'] - d2_q['n_valid']} 櫃。</td></tr>
    <tr><td>D3 管線繞行</td><td>沒有發現缺失；6 條都是最短路線。</td><td>{len(d3_detour)} 條管線多繞路、多 1–2 個彎頭（合規，但多用管材和接頭）。</td></tr>
    <tr><td>D5 三視圖建模</td><td>背面水管有 1 處小偏差。</td><td>4 個腳太大、背面水管和門把位置偏移、頂部管口有 2 處偏移。</td></tr>
  </tbody></table></div>
</section>

<section>
  <span class="eyebrow">6 · 程式問題</span>
  <h2>兩邊寫的 Blender 腳本：Qwen 的失敗和修補次數明顯較多</h2>
  <p>所有 Blender 腳本都是受測模型自己寫的。下表直接從執行紀錄統計：寫了幾支腳本、幾支執行時報錯。</p>
  <div class="tbl"><table><thead><tr><th>關卡</th><th>Opus</th><th>Qwen（high）</th></tr></thead><tbody>{''.join(code_rows)}</tbody></table></div>
  <h3>程式碼審查（Gemini 4 Carbon，匿名審查 S3 hard）</h3>
  <div class="tbl"><table><thead><tr><th></th><th>Opus</th><th>Qwen</th></tr></thead><tbody>
    <tr><td>評分（1–5）</td><td>符合規格 5、從輸入推導 5、自我檢查 5、程式品質 4、效率 5</td><td>符合規格 4、從輸入推導 5、自我檢查 3、程式品質 3、效率 3</td></tr>
    <tr><td>指出的問題</td><td><ul><li>留下沒用到的函式和沒用到的計算結果（小問題）。</li><li>「把 GPU 櫃的寬度縮放蓋掉」：<b>經量測不成立</b>，3 個 GPU 櫃寬度都是 0.8 m。</li></ul></td>
        <td><ul><li>做有孔地磚時，用來挖孔的輔助物件留在場景裡沒有清掉。</li><li>挖孔的圓柱建在世界原點，和地磚不在同一位置，孔可能沒挖到。</li><li>方塊的高度計算有誤，靠後續腳本修補。</li></ul><span class="note">這三項是審查者的判斷，沒有逐項用場景檔查證；最後成品的位置檢查是通過的。</span></td></tr>
    <tr><td>兩兩比較</td><td colspan="2">判 Opus 較好（信心高）：3 支腳本完成，結構清楚，有自我檢查。</td></tr>
  </tbody></table></div>
  <ul>
    <li><b>第二階段的作法差異</b>：Opus 在管線繞行寫了完整的 3D 尋路程式、在竣工比對寫了相機投影程式把設計投到照片上逐台比對；Qwen 多半是反覆試錯，三視圖建模寫了 14 支逐步修補的腳本（s1.py…s14.py）。</li>
    <li>Qwen 的「工具用法錯誤」多半是想用管線或重導向等被禁止的指令。</li>
    <li>程式碼審查只完成 S3 hard 一個關卡；其餘關卡因為 Gemini 費用偏高先停掉了。</li>
  </ul>
</section>

<section>
  <span class="eyebrow">7 · 地端 Flash-Next 的限制</span>
  <h2>地端用 Flash-Next 只會比這次更差</h2>
  <p>這次測的雲端託管版是這個模型家族條件最好的版本：原廠全精度部署、1M 上下文、內建工具。地端的每一項條件都比它差或相同，沒有一項更好。</p>
  <div class="three">
    <div class="card"><span class="big-num">{peak_max:,}</span><h3>上下文不夠跑完照片關卡</h3>
      <p>Qwen 在照片推佈局用到 {peak_max:,} token，超過 Flash-Next 地端原生上限 262,144，原生設定下會中途中斷。竣工比對和三視圖建模也用到上限的 9 成左右。模型卡說可以用 YaRN 延伸到 1M，但延伸後的品質沒有公開數據。</p></div>
    <div class="card"><span class="big-num">約 360 GB</span><h3>全精度權重要多張高階 GPU</h3>
      <p>模型卡列出約 180B 參數、BF16 精度，換算約 360 GB。硬體不夠就要用量化版，能力會再下降，降多少沒有公開數據。</p></div>
    <div class="card"><span class="big-num">{slow_lo:.1f}–{slow_hi:.0f} 倍</span><h3>雲端版已經比 Opus 慢這麼多</h3>
      <p>地端的速度取決於自己的 GPU 數量，一般不會比原廠雲端快。竣工比對雲端版用了 61 分鐘（上限 60），照片推佈局 58 分鐘（上限 60），地端再慢一點就會逾時。</p></div>
  </div>
  <h3>每一關 Qwen 用到的最長對話（地端原生上限 262,144 token）</h3>
  <div class="tbl"><table><thead><tr><th>關卡</th><th>最長一次請求的 token</th><th>佔地端原生上限</th></tr></thead><tbody>{ctx_rows}</tbody></table></div>
  <ul>
    <li>黃底是用到上限 85% 以上的關卡：{'、'.join(near)}。<b>這幾關正好也是最難、最需要看圖的關卡</b>；對話越長，代表模型看越多圖、試越多次。</li>
    <li>工具呼叫要靠地端推論框架的解析器，穩定度可能和雲端版不同。這次雲端版仍有多次工具用法錯誤（見第 6 節）。</li>
    <li>官方只說雲端版「以 Flash-Next 為基礎」，沒有說兩者權重相同，也沒有兩者對比的公開實測。授權是 qwen-community-1.0，商用前要確認條款。</li>
    <li><b>以上是依據事實的推論，不是地端實測結果。</b>重現用的 repo（<code>clarencechien/qwenpoc</code>）可以把同一套 10 關接到地端的 Flash-Next 上跑一次確認。</li>
  </ul>
</section>

<section>
  <span class="eyebrow">8 · 這份結果的限制</span>
  <h2>需要注意的地方</h2>
  <ul>
    <li>每個關卡、每個模型在同一設定下只跑 1 次，結果可能有運氣成分。兩個不及格的關卡差距很大（53 對 96、60 對 100），不太可能只是運氣。</li>
    <li>Opus 是在同一台機器上用全新對話執行，工具限制靠指令要求，事後逐筆檢查對話紀錄：第二階段 4 關都沒有讀取執行目錄以外的檔案。Qwen 的限制由程式強制。</li>
    <li>Opus 跑照片推佈局時，Qwen 的答案曾誤留在磁碟上約 2 分鐘，從結果看沒有被使用（兩邊錯的地方完全不同）。</li>
    <li>Qwen 的管線繞行第一次執行，因為一次回覆超過 32,000 token 的輸出上限被截斷而中止（0 分）。這是測試程式的設定問題，修正後重跑一次，報告採用重跑的成績。</li>
    <li>題目和計分程式由主控的 Claude 撰寫，Opus 是受測者之一；計分全部用程式對答案卷，沒有人為給分。答案卷不放在 repo 裡，用固定的亂數種子重建。</li>
    <li>空機房佈局設計的滿分基準（250 櫃）是我們的求解器找到的最好結果，不保證是理論最佳；兩邊都用同一個基準。</li>
    <li>這次沒有實測地端的 Flash-Next；「地端只會更差」是推論。</li>
  </ul>
</section>
</main>
"""

TITLE = "機房 3D pipeline 完整報告"
frag = f"<title>{TITLE}</title>\n<meta name=\"claude:viewport-fit-sides\" content=\"cover\">\n<style>{CSS}</style>\n{BODY}"
full = ("<!doctype html>\n<html lang=\"zh-Hant\"><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
        f"<title>{TITLE}</title><style>{CSS}</style></head><body>{BODY}</body></html>\n")
(ROOT / "report" / "full_report_artifact.html").write_text(frag)
(ROOT / "report" / "full_report.html").write_text(full)
print(f"full_report.html {len(full) / 1e6:.2f} MB")
for t in data:
    print(t["title"], t["so"], t["sq"], t["to"]["sec"], t["tq"]["sec"], "exec", t["to"]["exec"], t["to"]["failed"], "|",
          t["tq"]["exec"], t["tq"]["failed"], t["tq"].get("tool_errors"), "peak", t["tq"].get("peak_ctx"))
