# AI 機房 3D pipeline：Opus 5.5 vs Qwen 3.8 Flash 空間能力比較計畫

> 狀態：計畫稿（2026-11-18）。目錄 `datacenter/`，分支 `claude/eloquent-lovelace-4vrek4`。

## 1. 要回答的問題

給一張機房平面圖和幾張公開的機櫃照片，讓模型自己操作 Blender 完成這條 pipeline：

1. 平面圖 → 立體空間
2. 照片 → 機櫃模型
3. 把機櫃擺進空間
4. Web3D 呈現，點機櫃彈出浮動面板，顯示模擬資料

比較兩個模型在每一階段的**空間正確性**（位置、朝向、尺度）、**外觀還原度**、**成功率**和**成本／時間**。

| | Opus 5.5 | Qwen 3.8 Flash |
|---|---|---|
| 驅動方式 | 全新的 Claude Code session（不付 API 費，用 Claude 方案額度） | `harness/qwen_runner.py`，透過 OpenRouter 呼叫 `qwen/qwen3.8-flash` |
| 能力 | 吃圖片、能用工具 | 吃圖片、影片，能用工具 |
| 費用 | 方案額度 | $0.15 / $0.47 每百萬 token，快取讀取 $0.016 |
| 金鑰 | — | 環境變數 `or_key`（目前上限 $10，剩約 $5.05） |

選配對照組：`qwen/qwen3.8-max-0902`（$2 / $6）。如果 Flash 一面倒地輸，就加跑這一組，看差距是來自「模型等級」還是「模型家族」。

## 2. 公平性設計

比較的是模型，不是 harness，所以以下幾點兩邊都要一樣：

1. **同一套工具。** 兩邊都只能透過 `bench` CLI 操作 Blender（第 5 節）。
   - Qwen：`bench` 的每個子命令包成 OpenAI 格式的 tool。
   - Opus：runtime 目錄的 `.claude/settings.json` 只允許 `Bash(bench *)`，`Read`／`Write` 只能碰 `run/**`。這是用權限強制，不只是在 prompt 裡要求。
2. **同一份任務說明。** `harness/prompts/` 裡的 `system.md` 和 `s1.md`–`s4.md` 一字不差地給兩邊。prompt 只能在 pilot 階段修，而且只能修任務敘述不清的地方，不能針對任一模型調。
3. **同樣的上限。** 每階段 `bench` 呼叫最多 60 次、牆鐘時間 45 分鐘，由 `bench` 本身計數，超過就拒絕執行。圖片回饋一律 1024×768。
4. **不能看到答案。**
   - 正確答案（`layout.json`）和產生用的 seed 不進 git，存在 Modal Volume `dc-bench-gt`，只有計分時才讀。
   - Opus 必須在**全新的 session** 跑，不能用寫題目的這個 session（它看過答案）。
   - 那個 session 的工作目錄只放 runtime 檔案：`bench/`、`harness/prompts/`、`inputs/`、three.js。不放 `gen/`、`score/`、`oracle/`。
5. **每階段獨立計分。** 主要分數一律用「oracle 輸入」模式：每一階段都拿上一階段的正確答案當輸入，前一階段的錯不會一路傳下去。另外每個模型每個情境再跑一次「端到端」（用自己前一階段的產出），這次只拿來做展示和觀察錯誤怎麼累積。
6. **完整記錄。** 保留每次工具呼叫、模型輸出、token 數、花費、截圖，存在 `runs/<model>/<scenario>/<rep>/`。

## 3. 架構

```
            ┌───────────── 出題端（本 session）──────────────┐
            │ gen/layout_gen.py --seed S → layout.json (GT)  │
            │ gen/draw_plan.py           → plan.png (輸入)    │
            │ oracle/                    → 參考解（天花板）    │
            └──────────────┬─────────────────────────────────┘
                           │ inputs/（plan.png、ref/*.jpg、telemetry_schema.json）
        ┌──────────────────┴──────────────────┐
  Claude Code session（Opus）       qwen_runner.py → OpenRouter（Flash）
        │ Bash: bench …                       │ tool call: bench …
        └──────────────┬──────────────────────┘
                bench CLI ──socket──► blender_server.py（常駐 Blender 4.2 headless，保留場景狀態）
                       │
           run/<stage>/（.blend、layout_pred.json、rack.glb、scene.glb、web/）
                       │
       score/（S1–S3 幾何計分、S4 Playwright、視覺評審）──► report/index.html
                       │
       modal_dc.py（Modal L40S：每個 run 結束才渲染 8 張 Cycles 成品圖）
```

- **建模迴圈在本容器裡跑**（4 核、15 GB、無 GPU）。預覽渲染先試 Workbench 搭 Mesa llvmpipe（快）。不行的話改用 Cycles CPU：16 samples、1024×768，每張大約 5–15 秒。
- **Modal 只用在成品渲染**，每個 run 一次，不讓 GPU 在 LLM 思考時空等。沿用 `interior/modal_interior.py` 的 Blender 4.2 映像檔做法。

## 4. 任務與計分

先產生兩個情境：

| 情境 | 內容 |
|---|---|
| `easy` | 單一機房，約 14 m × 10 m；2 列，每列 10 櫃，全是 600×1200 標準櫃；1 條冷通道；4 根柱子；2 台 CRAH；1 扇門 |
| `hard` | 約 24 m × 16 m，柱距 8 m 的柱網；4 列，含冷通道封閉；有一列是 800 寬的 GPU 櫃；一列被柱子打斷；另有 UPS 室；有 CRAH、PDU、線槽 |

平面圖用建築圖的畫法：粗牆線、柱網編號（A–F / 1–8）、尺寸線（mm）、比例尺、機櫃編號（A01…）。機櫃前方用一條前緣線加三角形標示，這是業界常見畫法。**圖上不直接標冷熱通道**，要模型自己從機櫃朝向推斷。

### S1 平面圖 → 立體空間（25%）

| 項目 | 內容 |
|---|---|
| 輸入 | `plan.png` |
| 產出 | `layout_pred.json`（與 GT 同一個 schema），以及 Blender 裡的房間殼體：牆、柱、門、架高地板、天花板高度 |

| 指標 | 算法 |
|---|---|
| 機櫃偵測 F1 | 中心點用 Hungarian 演算法配對，誤差 ≤ 300 mm 才算對到 |
| 位置誤差 | 配對到的機櫃，中心點 RMSE（mm） |
| 朝向正確率 | 前門方向是否正確（0/90/180/270） |
| 編號正確率 | 機櫃 ID 對不對 |
| 房間與柱子 | 房間外框尺寸誤差（%）、柱子數量與位置 |
| 通道寬度 | 冷通道寬度誤差 |
| 殼體一致性 | 從 Blender 匯出牆的 bbox，比對 layout_pred 是否吻合 |

### S2 照片 → 機櫃模型（20%）

| 項目 | 內容 |
|---|---|
| 輸入 | `ref/` 照片，加規格文字：「42U、600 W × 1200 D × 2000 H mm、前後開孔門」 |
| 子題 | 2A 封閉式黑色開孔門機櫃（NERSC、WMF 照片）；2B 開放式框架機櫃（架高地板照片） |
| 產出 | `rack_A.glb`、`rack_B.glb`，以及 4 個固定視角的渲染 |

| 指標 | 算法 |
|---|---|
| 尺寸誤差 | W/D/H 與規格比對，誤差 ≤ 1% 給滿分 |
| U 數與導軌 | 42U 是否正確、19 吋導軌位置 |
| 元件清單 | 開孔前門、後門、側板、頂部走線孔、調平腳或腳輪、伺服器面板、盲板、LED、門把或鎖，共 10 項，由評審判定 |
| 外觀相似度 | 人工盲測兩兩比較（主要）＋第三方 VLM 評審（次要）。評審用 Anthropic 和 Qwen 以外的模型家族，經 OpenRouter 呼叫，約 $1–3 |
| 效能 | 面數 ≤ 50k，用於 web |

### S3 擺進空間（30%，空間能力的核心）

| 項目 | 內容 |
|---|---|
| 輸入 | GT `layout.json`、參考機櫃 GLB、S1 的參考房間殼體 |
| 產出 | `scene.blend`、`scene.glb`，每個機櫃物件的 `rackId` 寫在 custom property |
| 附加要求 | 冷通道封閉、600 mm 地磚格線、線槽 |

| 指標 | 算法 |
|---|---|
| 位置誤差 | 每個機櫃的中心點誤差（mm） |
| 旋轉誤差 | 角度誤差（°） |
| 前門朝冷通道 | 正確比例（%） |
| 碰撞 | 機櫃之間、機櫃與牆或柱子的碰撞數，用 bbox 加 BVH 檢查 |
| 出界 | 超出房間的物件數 |
| 封閉 | 冷通道封閉是否蓋住正確的通道 |
| 地磚 | 地磚是否對齊 600 mm 格線 |
| 擺放方式 | 使用 instancing 還是複製實體（記錄，不計分） |

### S4 Web3D 與浮動面板（25%）

| 項目 | 內容 |
|---|---|
| 輸入 | GT `scene.glb`、`telemetry_schema.json` |
| 產出 | `web/index.html` 加 JS，使用 vendored three.js，不連 CDN，方便離線測試 |

**資料模擬。** 模型依 schema 自己寫產生器，每個機櫃每秒更新一次，數值用固定 seed 的 random walk。欄位：

- 識別：`rack_id`、`row`、`model`（例如 "GPU rack, NVL72-class"）
- 電力：`power_kw`（目前／上限）、`pdu_a_pct`、`pdu_b_pct`
- 溫濕度：`inlet_c`、`outlet_c`、`humidity_pct`
- 容量與運算：`u_used/u_total`、`gpu_count`、`gpu_util_pct`
- 網路：`uplinks`
- 狀態：`status`（ok / warn / crit）、`alarms[]`、`updated_at`

**頁面 API 合約。** 頁面必須提供 `window.__bench = { scene, camera, selectRack(id), getPanelState() }`，這是規格的一部分，寫在任務說明裡。

**Playwright 測試**（`score/s4_web.py`，用 Chromium headless）：

1. GLB 載入完成，場景裡的機櫃數和 ID 與 GT 一致
2. 把 GT 機櫃中心投影到螢幕座標後點擊，面板要顯示**那一個**機櫃。這同時測 raycast 和擺放是否正確
3. 移動相機之後，面板仍錨定在該機櫃附近（螢幕距離 ≤ 80 px），被遮住時要有合理處理
4. 5 秒內面板數值有更新，`status` 顏色正確
5. 沒有 console error；GLB 加 JS 總大小 ≤ 20 MB
6. 記錄 FPS，只作參考（headless 下不準）

### 效率指標（不計入總分，另外列）

- `bench` 呼叫次數、牆鐘時間、自我修正次數（工具報錯後成功修好的次數）
- 花費：Qwen 用實際 token 費用；Opus 記錄 session 時間和額度用量
- 失敗類型：工具格式錯、Blender Python 錯、放棄、超出上限

## 5. `bench` CLI（兩個模型共用的唯一操作介面）

| 子命令 | 作用 | 回傳 |
|---|---|---|
| `bench exec <file.py>` | 在常駐的 Blender 裡執行 Python，場景狀態會保留 | stdout/stderr，截斷到 8k 字元 |
| `bench render <view> [--res 1024x768]` | 渲染預覽；`view` 可以是 `top`、`front`、`iso`、`cam:x,y,z>tx,ty,tz` | PNG 路徑 |
| `bench inspect [--filter]` | 場景摘要：物件、尺寸、位置、旋轉、custom props | JSON |
| `bench view <png>` | 看圖。Qwen harness 把圖附進下一則訊息；Opus 用 `Read` | — |
| `bench save` | 存 `.blend`，並依階段匯出 json/glb | 檔案路徑 |
| `bench submit <stage>` | 交卷，鎖定這個階段 | — |
| `bench status` | 剩餘呼叫次數與時間 | — |

Qwen harness 另外提供 `write_file` 和 `read_file`，只能操作 `run/`，對應 Claude Code 的 Write／Read。

## 6. 素材（公開授權）

全部來自 Wikimedia Commons，作者與授權記在 `ref/LICENSES.md`：

| 用途 | 檔案 | 授權 |
|---|---|---|
| 2A 整列封閉式機櫃正面 | Front_of_server_racks_at_NERSC.jpg | CC0 |
| 2A 單一機櫃，門打開 | Rack_in_wmf_sf_office.jpg | CC BY-SA 3.0 |
| 2A 伺服器面板細節 | Datacenter_Rack.jpg | CC BY-SA 3.0 |
| 2B 開放式框架加架高地板 | Datacenter_Server_Racks_(22370909788).jpg | CC BY 2.0 |
| 背面／熱通道 | Rear_of_Hopper_Cray_XE6_racks.jpg | CC0 |
| S3 機房俯瞰 | Cern_datacenter.jpg | CC BY-SA 3.0 |

材質沿用 repo 既有做法，用 Poly Haven CC0。平面圖由 `gen/draw_plan.py` 自己畫，沒有授權問題。

## 7. 執行矩陣與預算

每個 rep 包含 S1–S4 四個階段，全部用 oracle 輸入。

| | 情境 | 獨立計分 rep | 端到端 | 合計 |
|---|---|---|---|---|
| Qwen 3.8 Flash | easy、hard | 3 | 1 | 8 個 rep |
| Opus 5.5 | easy、hard | 2 | 1 | 6 個 rep（受方案額度限制） |
| （選配）Qwen 3.8 Max 0902 | easy、hard | 2 | 1 | 6 個 rep |

| 項目 | 估算 |
|---|---|
| Flash，每個 rep 約 4×40 回合 | $0.4–2 / rep → **$3–16** |
| 第三方 VLM 評審 | **$1–3** |
| Modal 成品渲染（約 20 個 run × 8 張 Cycles，含冷啟動） | 每 run $0.1–0.2 → **$3–5**（含建映像檔） |
| Opus | $0 API 費用；每個 rep 約 2–3 小時 session |
| **合計現金** | **約 $10–25**；加選配 Max 再加約 $30 |

目前 OpenRouter key 剩 $5.05，夠跑 pilot，正式比較前要把上限調到 $20 以上。harness 每個 rep 會設花費上限，達到就中止並記錄。

## 8. 目錄結構

```
datacenter/
  PLAN.md
  ref/                    公開照片 + LICENSES.md
  gen/                    layout_gen.py、draw_plan.py、schema/layout.schema.json   （出題端）
  oracle/                 參考解：s1–s4 腳本、參考 GLB                            （出題端）
  bench/                  bench_cli.py、blender_server.py、tools.json             （runtime）
  harness/                qwen_runner.py、prompts/system.md、s1–s4.md             （runtime）
  inputs/<scenario>/      plan.png、telemetry_schema.json                         （runtime）
  vendor/three/           three.js（固定版本）                                    （runtime）
  score/                  s1_layout.py、s2_rack.py、s3_place.py、s4_web.py、judge.py、aggregate.py
  modal_dc.py             成品渲染
  runs/<model>/<scenario>/<rep>/   logs、截圖、產出（.blend 不進 git，GLB 進 git）
  report/index.html       比較頁：分數表、並排渲染、Web3D 連結、花費／時間
```

正確答案 `layout.json` 和 seed 存在 Modal Volume `dc-bench-gt`，不進 git。

## 9. 工作順序

| 里程碑 | 內容 | 完成條件 |
|---|---|---|
| M0 環境 | 容器裝 Blender 4.2 LTS；確認 Workbench + llvmpipe 能否 headless 渲染，否則用 Cycles CPU；寫 `blender_server.py` 和 `bench` | `bench exec`、`render`、`inspect` 都能跑；一張預覽 ≤ 15 秒 |
| M1 出題 | layout 產生器、平面圖繪製、兩個情境、telemetry schema、下載照片 | 平面圖人工看得懂；GT 通過 schema 驗證 |
| M2 參考解 | 我用 oracle 腳本把 S1–S4 做完一遍 | 每題都做得出來；oracle 分數 ≈ 滿分，也藉此驗證計分程式 |
| M3 計分 | s1–s4 計分程式、Playwright、評審 prompt、`aggregate.py` | 對 oracle 解和故意做錯的解，分數合理 |
| M4 Qwen harness + pilot | `qwen_runner.py`（OpenRouter tool calling、圖片附件、花費計算、上限）；在 easy 上跑 Flash 的 S1 | 跑得完；花費 < $0.5；只修 prompt 裡敘述不清的地方 |
| M5 Opus pilot | 開全新的 Claude Code session，用 runtime 目錄和權限設定，跑 easy 的 S1 | 權限限制有效；log 格式和 Qwen 一致 |
| M6 正式比較 | 依第 7 節的矩陣執行 | 全部 rep 完成或記錄失敗原因 |
| M7 報告 | `report/index.html`、Modal 成品圖、端到端 Web3D 展示 | 可分享的比較頁 |

## 10. 風險與對策

| 風險 | 對策 |
|---|---|
| 容器沒有 GPU，headless Workbench 可能不能跑 | 改用 Cycles CPU 低 sample；再不行就讓 `bench render` 轉呼叫 Modal（會多 $，兩邊一樣） |
| Flash 的工具呼叫格式不穩 | 格式錯算一次呼叫，記為失敗類型；固定 OpenRouter provider，降低變異 |
| Claude Code 會自動壓縮上下文，Qwen harness 不會 | Qwen harness 在 80% 上下文時摘要舊回合，並記錄觸發次數；每階段都開新對話，降低影響 |
| 兩家的圖片 token 算法不同 | 圖片解析度固定，只比結果，不比 token |
| Opus 額度用完 | Opus 的 rep 數設成 2；必要時分天跑 |
| 評審有偏好 | 人工盲測為主；VLM 評審用第三方模型家族；畫面隨機左右排列 |
| CC BY-SA 照片 | 只當參考，不重新散布修改版；`LICENSES.md` 完整標示作者 |

## 11. 待決事項

1. **Opus 的 runtime 環境。** 建議另開分支 `bench/runtime`，只放 runtime 檔案，Opus session 從這個分支開。建這個分支需要你同意，目前只能推到本分支。替代方案：同一分支，但正確答案只放 Modal Volume，並用權限擋掉讀取 `gen/`、`oracle/`、`score/`。
2. **OpenRouter key 上限**：正式比較前從 $10 調到約 $20（要加選配 Max 的話調到 $50）。
3. **人工盲測**：S2 外觀和端到端成品各約 20 組兩兩比較，由你評分，每組約 10 秒。
4. **要不要加選配 `qwen3.8-max-0902`**，建議等 pilot 結果再決定。
