#!/usr/bin/env python3
"""Phase-1 summary report as ONE self-contained HTML file (images embedded, no external requests).

    python report/build_phase1.py   ->  report/phase1.html (standalone document)
                                        report/phase1_artifact.html (same content without the document shell)
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

OPUS_SEC = {"easy/s1-r1": 66, "hard/s1-r1": 95, "easy/s2-r1": 543, "easy/s3-r1": 102, "hard/s3-r1": 135, "photo-hard/s1p-r1": 954}
STAGES = [
    ("S1 圖面 → 3D 空間（easy，16 櫃）", "opus-5.5/easy/s1-r1", "qwen3.8-flash/easy/s1-r2-high", "score_s1.json", 100),
    ("S1 圖面 → 3D 空間（hard，58 櫃）", "opus-5.5/hard/s1-r1", "qwen3.8-flash/hard/s1-r1-high", "score_s1.json", 100),
    ("S2 照片 → 機櫃模型（只量幾何）", "opus-5.5/easy/s2-r1", "qwen3.8-flash/easy/s2-r2-high", "score_s2_auto.json", 40),
    ("S3 機櫃擺進空間（easy）", "opus-5.5/easy/s3-r1", "qwen3.8-flash/easy/s3-r2-high", "score_s3.json", 100),
    ("S3 機櫃擺進空間（hard）", "opus-5.5/hard/s3-r1", "qwen3.8-flash/hard/s3-r1-high", "score_s3.json", 100),
    ("S1P 現場照片 → 推回佈局", "opus-5.5/photo-hard/s1p-r1", "qwen3.8-flash/photo-hard/s1p-r1-high", "score_s1p.json", 100),
]


def b64(im: Image.Image, width: int, quality=80) -> str:
    im = im.convert("RGB")
    if im.width > width:
        im = im.resize((width, round(im.height * width / im.width)), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=quality, optimize=True)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


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
        st.update(sec=j["seconds"], cost=j["cost_usd"], turns=j["turns"])
        tr = run / "transcript.jsonl"
        peak = bad = 0
        for l in tr.read_text().splitlines():
            d = json.loads(l)
            if d["kind"] == "assistant":
                peak = max(peak, (d.get("usage") or {}).get("prompt_tokens", 0))
            if d["kind"] == "tool" and d["result"].startswith("error"):
                bad += 1
        st.update(peak_ctx=peak, tool_errors=bad)
    else:
        st.update(sec=OPUS_SEC["/".join(rel.split("/")[1:])], cost=None)
    return st


def score(rel: str, f: str):
    d = json.loads((RUNS / rel / f).read_text())
    return d.get("total", d.get("auto_total_40")), d


def fmt_t(s):
    return f"{round(s)} 秒" if s < 120 else f"{s / 60:.0f} 分鐘"


E = html.escape
rows, data = [], []
for title, o, q, f, mx in STAGES:
    so, _ = score(o, f)
    sq, _ = score(q, f)
    to, tq = run_stats(o), run_stats(q)
    data.append((title, so, sq, mx, to, tq))
    gap = abs(so - sq) / mx >= 0.1
    rows.append(f"""<tr class="{'gap' if gap else ''}"><td>{E(title)}</td>
      <td class="num"><div class="bar"><i class="o" style="width:{so / mx * 100:.0f}%"></i></div><b>{so:g}</b><span>/{mx}</span></td>
      <td class="num"><div class="bar"><i class="q" style="width:{sq / mx * 100:.0f}%"></i></div><b>{sq:g}</b><span>/{mx}</span></td>
      <td class="num">{fmt_t(to['sec'])}<br><span>{to['calls']} 次操作</span></td>
      <td class="num">{fmt_t(tq['sec'])}<br><span>{tq['calls']} 次操作 · 慢 {tq['sec'] / to['sec']:.0f} 倍</span></td></tr>""")

code_rows = []
for title, o, q, f, mx in STAGES:
    to, tq = run_stats(o), run_stats(q)
    def cell(t):
        e = "".join(f"<li><code>{E(x)}</code></li>" for x in t["errors"])
        return (f"<b>{t['exec']}</b> 支腳本，<b class=\"{'bad' if t['failed'] else ''}\">{t['failed']}</b> 支執行失敗"
                + (f"；另有 {t['tool_errors']} 次工具用法錯誤" if t.get("tool_errors") else "")
                + (f"<ul class=\"err\">{e}</ul>" if e else ""))
    code_rows.append(f"<tr><td>{E(title)}</td><td>{cell(to)}</td><td>{cell(tq)}</td></tr>")

peak = max(t[5].get("peak_ctx", 0) for t in data)
qcost = sum(t[5]["cost"] or 0 for t in data)
s1p_o = json.loads((RUNS / STAGES[5][1] / "score_s1p.json").read_text())["detail"]
s1p_q = json.loads((RUNS / STAGES[5][2] / "score_s1p.json").read_text())["detail"]

# ---- scoring model for the recommendation (weights were set AFTER seeing the results; stated in the report) ----
WEIGHTS = [5, 10, 10, 5, 10, 30]          # correctness points per stage, sum 70
PASS = 0.8                                # a stage passes at >= 80% of its maximum
corr = {"o": 0.0, "q": 0.0}
eff = {"o": [], "q": []}
gate_rows = []
for (title, so, sq, mx, to, tq), w in zip(data, WEIGHTS):
    corr["o"] += w * so / mx
    corr["q"] += w * sq / mx
    fastest = min(to["sec"], tq["sec"])
    eff["o"].append(fastest / to["sec"])
    eff["q"].append(fastest / tq["sec"])
    po, pq = so / mx >= PASS, sq / mx >= PASS
    gate_rows.append(f"""<tr><td>{E(title)}</td><td class="num">{w}</td>
      <td class="num"><b>{w * so / mx:.1f}</b> <span class="pf {'p' if po else 'f'}">{'通過' if po else '不通過'}</span></td>
      <td class="num"><b>{w * sq / mx:.1f}</b> <span class="pf {'p' if pq else 'f'}">{'通過' if pq else '不通過'}</span></td></tr>""")
eff_o, eff_q = 30 * sum(eff["o"]) / 6, 30 * sum(eff["q"]) / 6
tot_o, tot_q = corr["o"] + eff_o, corr["q"] + eff_q
print(f"weighted: opus {tot_o:.1f} (corr {corr['o']:.1f} + eff {eff_o:.1f}); qwen {tot_q:.1f} (corr {corr['q']:.1f} + eff {eff_q:.1f})")

IMG = {
    "s2_opus": sheet("opus-5.5/easy/s2-r1", [(440, 330), (960, 200), (1680, 250), (1390, 130)]),
    "s2_qh": sheet("qwen3.8-flash/easy/s2-r2-high", [(130, 240), (540, 20), (928, 28), (1000, 320), (1390, 250), (1390, 50)]),
    "s2_qd": sheet("qwen3.8-flash/easy/s2-r1", [(200, 150), (560, 12), (262, 90), (1400, 283), (1400, 72), (1730, 75)]),
    "photo": b64(Image.open(ROOT / "inputs/photo-hard/photo_2.jpg"), 900),
    "ov_o": b64(Image.open(RUNS / STAGES[5][1] / "review/overlay_plan.png"), 1300, 85),
    "ov_q": b64(Image.open(RUNS / STAGES[5][2] / "review/overlay_plan.png"), 1300, 85),
    "plan": b64(Image.open(ROOT / "inputs/hard/plan.png"), 1100, 80),
    "s3_o": b64(Image.open(RUNS / "opus-5.5/hard/s3-r1/review/review_iso.png"), 900),
    "s3_q": b64(Image.open(RUNS / "qwen3.8-flash/hard/s3-r1-high/review/review_iso.png"), 900),
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
    "s2_qd": ("Qwen 3.8 Flash（預設強度）", [
        ("量測", "伺服器只有 455 mm 寬，不是 19 吋機架設備的 483 mm。"),
        ("量測", "頂板沒有真正的走線開孔（射線檢查透空率 0%）。"),
        ("量測", "做了 95 顆 LED，但材質都不發光。"),
        ("量測", "Rack B 有 3 片盲板懸空，沒有接觸立柱或任何零件（圖上標出其中一片）。"),
        ("量測", "Rack B 頂部的線束和一台設備互相穿插約 45 mm。"),
        ("目視", "Rack B 頂部的線纜像一根硬管。"),
    ], "做對的：有盲板、有配線架和跳線。但一座機櫃拆成 271 個物件，場景很重。"),
}


def defect_block(key):
    name, items, good = DEFECTS[key]
    lis = "".join(f'<li><span class="n">{i}</span><span class="src {"m" if s == "量測" else "v"}">{s}</span>{E(t)}</li>'
                  for i, (s, t) in enumerate(items, 1))
    return f"""<div class="card"><h3>{E(name)}</h3><div class="scroll"><img src="{IMG[key]}" alt="{E(name)} 的機櫃模型，紅色編號為缺失位置"></div>
      <ol class="defects">{lis}</ol><p class="good">{E(good)}</p></div>"""


CSS = """
:root{--bg:#f4f6f7;--card:#fff;--ink:#16212b;--mut:#5c6975;--line:#d6dde2;--o:#5847c9;--q:#0b7d61;--bad:#c22f2f;--warn:#a15c00;--ok:#1d7a46;--soft:#eaeef1}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#0f1417;--card:#171e22;--ink:#e4eaed;--mut:#97a5ae;--line:#2c373e;--o:#9c8ff5;--q:#49c39f;--bad:#f08a80;--warn:#e0a24b;--ok:#5cc48a;--soft:#1e272c;color-scheme:dark}}
:root[data-theme="dark"]{--bg:#0f1417;--card:#171e22;--ink:#e4eaed;--mut:#97a5ae;--line:#2c373e;--o:#9c8ff5;--q:#49c39f;--bad:#f08a80;--warn:#e0a24b;--ok:#5cc48a;--soft:#1e272c;color-scheme:dark}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.7 "Noto Sans TC","PingFang TC","Microsoft JhengHei",system-ui,sans-serif}
main{max-width:1180px;margin:0 auto;padding-block:36px 90px;padding-left:max(16px,env(safe-area-inset-left,0px));padding-right:max(16px,env(safe-area-inset-right,0px));display:flex;flex-direction:column;gap:52px}
h1{font-size:34px;line-height:1.25;margin:0;text-wrap:balance}
h2{font-size:24px;line-height:1.35;margin:0;text-wrap:balance}
h3{font-size:17px;margin:0}
p{margin:0;max-width:74ch}
.eyebrow{font:600 12px/1 ui-monospace,Menlo,monospace;letter-spacing:.08em;color:var(--mut);text-transform:uppercase}
section{display:flex;flex-direction:column;gap:16px}
.lead{font-size:18px}
.verdict{background:var(--card);border:1px solid var(--line);border-left:6px solid var(--warn);border-radius:10px;padding:20px 22px;display:flex;flex-direction:column;gap:10px}
.verdict .big{font-size:22px;font-weight:700;line-height:1.4}
.three{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:14px}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:16px 18px;display:flex;flex-direction:column;gap:10px;min-width:0}
.tag{display:inline-block;font-size:12px;font-weight:700;border-radius:999px;padding:2px 10px;align-self:flex-start}
.tag.yes{background:var(--ok);color:var(--card)}.tag.no{background:var(--bad);color:var(--card)}.tag.unk{background:var(--mut);color:var(--card)}
ul{margin:0;padding-left:20px;display:flex;flex-direction:column;gap:6px}
.tbl{overflow-x:auto;background:var(--card);border:1px solid var(--line);border-radius:10px}
table{border-collapse:collapse;width:100%;font-size:14.5px}
th,td{padding:10px 14px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}
th{font-size:12.5px;color:var(--mut);font-weight:600;background:var(--soft);white-space:nowrap}
tr:last-child td{border-bottom:0}
td.num{font-variant-numeric:tabular-nums;white-space:nowrap}
td.num span{color:var(--mut);font-size:12.5px}
td.num b{font-size:18px}
tr.gap td{background:color-mix(in srgb,var(--warn) 9%,transparent)}
.bar{height:7px;background:var(--soft);border-radius:4px;overflow:hidden;width:120px;margin-bottom:4px}
.bar i{display:block;height:100%}.bar i.o{background:var(--o)}.bar i.q{background:var(--q)}
.key{display:flex;gap:18px;font-size:13px;color:var(--mut);flex-wrap:wrap}
.key i{display:inline-block;width:11px;height:11px;border-radius:3px;margin-right:6px;vertical-align:-1px}
img{max-width:100%;height:auto;display:block;border-radius:6px;border:1px solid var(--line)}
.scroll{overflow-x:auto}.scroll img{min-width:900px}
.two{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:14px}
figure{margin:0;display:flex;flex-direction:column;gap:6px;min-width:0}figcaption{font-size:13px;color:var(--mut)}
ol.defects{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:7px;font-size:14.5px}
ol.defects li{display:flex;gap:8px;align-items:baseline}
.n{flex:0 0 auto;width:22px;height:22px;border-radius:50%;background:var(--bad);color:var(--card);font:700 12px/22px ui-monospace,monospace;text-align:center}
.src{flex:0 0 auto;font-size:11.5px;border:1px solid var(--line);border-radius:4px;padding:0 6px;color:var(--mut)}
.src.m{border-color:var(--ok);color:var(--ok)}
.good{font-size:14px;color:var(--mut)}
code{font:12.5px ui-monospace,Menlo,monospace;word-break:break-all}
ul.err{font-size:12.5px;color:var(--mut);margin-top:4px}
b.bad{color:var(--bad)}
.note{font-size:13.5px;color:var(--mut)}
.big-num{font:700 30px/1.1 ui-monospace,Menlo,monospace}
.pf{font-size:12px;font-weight:700;border-radius:999px;padding:1px 9px;color:var(--card)}.pf.p{background:var(--ok)}.pf.f{background:var(--bad)}
"""

BODY = f"""
<main>
<header style="display:flex;flex-direction:column;gap:12px">
  <span class="eyebrow">AI 機房 3D pipeline 驗證 · 第一階段報告 · 2026-11-18</span>
  <h1>這條機房建模流程不建議用地端的 Qwen 3.8 Flash-Next，應使用 Opus</h1>
  <p class="lead">我們讓 Opus 5.5 和 Qwen 3.8 Flash 各自操作 Blender，完成同一條機房建模流程的 6 個關卡，用同一套工具、同樣的時間和次數上限，再用程式自動計分。</p>
</header>

<section>
  <div class="verdict">
    <span class="eyebrow">結論與建議</span>
    <div class="big">Qwen 3.8 Flash 在條件最好的雲端託管版就已經過不了「看照片推回佈局」這一關（53 分，Opus 96 分），整條流程的加權總分是 {tot_q:.0f} 對 {tot_o:.0f}。地端的 Flash-Next 條件只會更差，因此建議這條流程使用 Opus。</div>
    <p>這次實測的是雲端託管版，不是地端版本。「地端只會更差」是依據下方第 6 節的三項事實所做的推論，建議用附帶的重現手冊在地端實測一次確認。</p>
  </div>
  <div class="three">
    <div class="card"><span class="tag no">關鍵關卡不通過</span><h3>看照片推回佈局：Qwen 53 分，Opus 96 分</h3>
      <p>Qwen 把 6 列機櫃中的 2 列整排放錯位置，4 台空調只有 1 台位置對。流程是一關接一關的，這一關錯了，後面的 3D 場景就跟著錯。</p></div>
    <div class="card"><span class="tag no">速度</span><h3>每一關都比 Opus 慢 2–15 倍</h3>
      <p>照圖面建模和擺放機櫃，Qwen 分數和 Opus 相同，但用時和操作次數都多很多。照片關卡用了 58 分鐘，上限是 60 分鐘。</p></div>
    <div class="card"><span class="tag no">地端條件更差</span><h3>照片關卡的對話長度已超過地端原生上限</h3>
      <p>Qwen 在這一關用到 {peak:,} token，Flash-Next 地端原生上限是 262,144。再加上量化和硬體限制，地端表現預期低於這次的數字。</p></div>
  </div>
</section>

<section>
  <span class="eyebrow">1 · 成績總覽</span>
  <h2>6 個關卡裡，5 個分數相同；差距出現在「看照片」和「速度」</h2>
  <div class="key"><span><i style="background:var(--o)"></i>Opus 5.5（Claude Code，推理強度 high）</span><span><i style="background:var(--q)"></i>Qwen 3.8 Flash（OpenRouter 託管版，推理強度 high）</span></div>
  <div class="tbl"><table><thead><tr><th>關卡</th><th>Opus 分數</th><th>Qwen 分數</th><th>Opus 用時</th><th>Qwen 用時</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div>
  <ul>
    <li>Qwen 每個關卡都比 Opus 慢 2–15 倍，操作 Blender 的次數也多 1.5–8 倍。時間幾乎都花在等模型回應。</li>
    <li>S2 的 40 分只檢查外框尺寸、擺放位置、命名和面數，<b>不評外觀</b>。外觀的缺失見第 4 節。</li>
    <li>Qwen 6 個關卡的 API 費用合計約 ${qcost:.2f}；Opus 用的是 Claude 方案額度。</li>
  </ul>
</section>

<section>
  <span class="eyebrow">2 · 配分與判定方式</span>
  <h2>判定規則：每一關都要過 80%，再看加權總分；Qwen 兩項都沒過</h2>
  <p>流程是串接的，前一關的錯會帶到後面，所以先用「每關都要通過」把關，再用加權總分比較。配分是看到結果之後才訂的，理由寫在表格下方，可以依實際需求調整。</p>
  <div class="tbl"><table><thead><tr><th>關卡</th><th>配分</th><th>Opus 得分</th><th>Qwen 得分</th></tr></thead><tbody>
    {''.join(gate_rows)}
    <tr><td>正確性小計</td><td class="num">70</td><td class="num"><b>{corr['o']:.1f}</b></td><td class="num"><b>{corr['q']:.1f}</b></td></tr>
    <tr><td>效率（各關「最快用時 ÷ 自己用時」的平均 × 30）</td><td class="num">30</td><td class="num"><b>{eff_o:.1f}</b></td><td class="num"><b>{eff_q:.1f}</b></td></tr>
    <tr class="gap"><td><b>加權總分</b>（及格 80）</td><td class="num">100</td><td class="num"><b>{tot_o:.1f}</b> <span class="pf p">通過</span></td><td class="num"><b>{tot_q:.1f}</b> <span class="pf f">不通過</span></td></tr>
  </tbody></table></div>
  <ul>
    <li><b>照片推回佈局配 30 分，是最重的一關</b>：只有這一關的答案不在輸入資料裡，要靠模型自己判斷空間；而且實際驗收機房時，輸入就是現場照片。</li>
    <li><b>困難版配分是簡單版的 2 倍</b>：58 櫃、L 形機房比較接近真實機房的規模。</li>
    <li><b>效率配 30 分</b>：流程要反覆執行，速度直接決定能不能實際使用。地端的速度還要再受硬體限制。</li>
    <li>如果完全不計效率、只看正確性（滿分 70），是 Opus {corr['o']:.1f} 對 Qwen {corr['q']:.1f}，換算成百分比是 {corr['o'] / 0.7:.0f}% 對 {corr['q'] / 0.7:.0f}%。這時 Qwen 只比及格線低一點，結論主要靠「照片關卡不通過」這一條。</li>
  </ul>
</section>

<section>
  <span class="eyebrow">3 · 拉開差距的關卡</span>
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
  <span class="eyebrow">4 · 建出的 3D 元件缺失</span>
  <h2>機櫃模型：尺寸都對，但細看三份作品都有缺失</h2>
  <p>任務是照 4 張參考照片做一座封閉式機櫃（Rack A）和一座開放式機架（Rack B）。紅色編號對應下方清單。「量測」是用程式直接檢查場景檔得到的；「目視」是看渲染圖判斷的，比較主觀。</p>
  {defect_block('s2_opus')}
  {defect_block('s2_qh')}
  {defect_block('s2_qd')}
  <ul>
    <li><b>整體來看</b>：Opus 的細節最完整（盲板、配線、理線器都有），主要問題在比例和線材的真實感；Qwen（high）缺的是任務明確要求的零件；Qwen（預設）零件多但尺寸和接合有錯。</li>
    <li>第二位評審 Gemini 4 Argon 的外觀分數很接近：Qwen（high）94、Opus 93、Qwen（預設）89，分不出高下。外觀這一關建議以人工盲測為準。</li>
  </ul>
  <h3>其他關卡的元件缺失</h3>
  <div class="tbl"><table><thead><tr><th>關卡</th><th>Opus</th><th>Qwen</th></tr></thead><tbody>
    <tr><td>S1 房間殼體</td><td>easy 版的門洞從地板切到頂，沒有做門楣（任務只要求門洞，不扣分）。北側熱通道只畫到柱線。</td><td>沒有發現缺失；high 版同樣把北側熱通道只畫到柱線。</td></tr>
    <tr><td>S3 擺放</td><td>沒有發現缺失。機櫃用連結複製，場景較輕（hard：6.1 萬個三角面）。</td><td>位置全對，但每個機櫃都合併成一個獨立網格再複製，場景較重（hard：10.6 萬個三角面）。</td></tr>
    <tr><td>S1P 照片推佈局</td><td>C 列東半段的 8 個 600 mm 櫃看成 6 個 GPU 櫃，少 2 櫃。</td><td>2 整列位置錯、多 4 櫃、空調 3 台只對 1 台。</td></tr>
  </tbody></table></div>
  <figure><img src="{IMG['plan']}" alt="hard 情境的平面圖"><figcaption>S1 hard 的輸入圖面：L 形機房、UPS 室、被柱子打斷的機櫃列、GPU 櫃、東西向的列。兩個模型都完全讀對。</figcaption></figure>
</section>

<section>
  <span class="eyebrow">5 · 程式問題</span>
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
  <p class="note">程式碼審查只完成 S3 hard 一個關卡；其餘關卡因為 Gemini 費用偏高先停掉了。Qwen 的「工具用法錯誤」多半是想用管線或重導向等被禁止的指令。</p>
</section>

<section>
  <span class="eyebrow">6 · 地端 Flash-Next 的限制</span>
  <h2>地端用 Flash-Next 只會比這次更差：三項事實</h2>
  <p>這次測的雲端託管版是這個模型家族條件最好的版本：原廠全精度部署、1M 上下文、內建工具。地端的每一項條件都比它差或相同，沒有一項更好。</p>
  <div class="three">
    <div class="card"><span class="big-num">{peak:,}</span><h3>上下文不夠跑完照片關卡</h3>
      <p>Qwen 在這一關最長的一次對話用到 {peak:,} token，超過 Flash-Next 地端原生上限 262,144。在原生設定下，這一關會在中途因為超出長度而中斷。模型卡提到可以用 YaRN 延伸到 1M，但延伸後的品質沒有公開數據。</p></div>
    <div class="card"><span class="big-num">約 360 GB</span><h3>全精度權重要多張高階 GPU</h3>
      <p>模型卡列出約 180B 參數、BF16 精度，換算約 360 GB。硬體不夠就要用量化版，能力會再下降，降多少沒有公開數據。</p></div>
    <div class="card"><span class="big-num">2–15 倍</span><h3>雲端版已經比 Opus 慢這麼多</h3>
      <p>地端的速度取決於自己的 GPU 數量，一般不會比原廠雲端快。照片關卡雲端版用了 58 分鐘，上限是 60 分鐘，地端再慢一點就會逾時。</p></div>
  </div>
  <ul>
    <li>其他關卡的上下文用量在 5–13 萬 token 之間，地端原生上限放得下；超出的是照片關卡。</li>
    <li>工具呼叫要靠地端推論框架的解析器，穩定度可能和雲端版不同。這次雲端版每個關卡仍有 2–8 次工具用法錯誤。</li>
    <li>官方只說雲端版「以 Flash-Next 為基礎」，沒有說兩者權重相同，也沒有兩者對比的公開實測。授權是 qwen-community-1.0，商用前要確認條款。</li>
    <li><b>以上是依據事實的推論，不是地端實測結果。</b>repo 裡附有重現手冊（<code>datacenter/HANDOFF.md</code>），地端團隊可以把同一套測試接到自己的 Flash-Next 上跑一次來確認。</li>
  </ul>
</section>

<section>
  <span class="eyebrow">7 · 這份結果的限制與下一步</span>
  <h2>第一階段還不足以下最後結論</h2>
  <ul>
    <li>每個關卡、每個模型在同一設定下只跑 1 次，結果可能有運氣成分。</li>
    <li>Opus 是在同一台機器上用全新對話執行，工具限制靠指令要求；Qwen 的限制由程式強制。Opus 跑照片關卡時，Qwen 的答案曾誤留在磁碟上約 2 分鐘，從結果看沒有被使用（兩邊錯的地方完全不同）。</li>
    <li>題目和計分程式由主控的 Claude 撰寫，Opus 是受測者之一；計分全部用程式對答案卷，沒有人為給分。</li>
    <li><b>第二階段</b>正在製作 4 個沒有標準答案可抄的關卡：竣工比對（設計圖對現場照片找差異）、限制式佈局設計、3D 管線繞行、依三視圖復刻設備。</li>
    <li>這次沒有實測地端的 Flash-Next；「地端只會更差」是推論。重現手冊在 <code>datacenter/HANDOFF.md</code>。</li>
  </ul>
</section>
</main>
"""

frag = f"<title>機房 3D pipeline 第一階段報告</title>\n<meta name=\"claude:viewport-fit-sides\" content=\"cover\">\n<style>{CSS}</style>\n{BODY}"
full = ("<!doctype html>\n<html lang=\"zh-Hant\"><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
        f"<title>機房 3D pipeline 第一階段報告</title><style>{CSS}</style></head><body>{BODY}</body></html>\n")
(ROOT / "report" / "phase1_artifact.html").write_text(frag)
(ROOT / "report" / "phase1.html").write_text(full)
print(f"phase1.html {len(full) / 1e6:.2f} MB")
for t in data:
    print(t[0], t[1], t[2], t[4]["sec"], t[5]["sec"], "exec", t[4]["exec"], t[4]["failed"], "|", t[5]["exec"], t[5]["failed"], t[5].get("tool_errors"))
