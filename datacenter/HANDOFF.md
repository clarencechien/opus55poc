# 重現手冊：在地端的 Qwen3.8-Flash-Next 上跑同一套測試

對象：負責地端模型的團隊。目的：把第一階段的 6 個關卡接到你們自架的 Flash-Next 上各跑一次，確認「地端表現不會比雲端託管版好」這個推論。

第一階段的結論和雲端版的成績在 `report/phase1.html`。

## 1. 你需要準備的

| 項目 | 需求 |
|---|---|
| 模型服務 | 一個 OpenAI 相容的 `/v1/chat/completions` 端點，支援 tool calling 和圖片輸入（vLLM 或 SGLang） |
| 測試機 | Linux、4 核 CPU、16 GB 記憶體即可，不需要 GPU（Blender 只做無頭預覽） |
| 軟體 | Python 3.11 以上，`pip install requests pillow numpy scipy shapely`；Blender 4.2 LTS 由安裝腳本下載 |

vLLM 官方 recipe 建議的啟動參數（請依你們的版本確認）：

```bash
vllm serve Qwen/Qwen3.8-Flash-Next --enable-auto-tool-choice --tool-call-parser qwen3_coder --reasoning-parser qwen3
```

- 原生上下文是 262,144 token。要延伸到 1M，recipe 的做法是加 `--max-model-len 1000000`、對應的 `--hf-overrides`，並設環境變數 `VLLM_ALLOW_LONG_MAX_MODEL_LEN=1`。
- **請兩種設定都記錄**：原生 262K 和延伸後。照片關卡（S1P）在雲端版用到 274,507 token，原生設定預期會中途超出長度。
- 請記下你們實際用的精度（BF16、FP8 或哪一種量化）和 GPU 配置，這是比較時最重要的背景。

## 2. 安裝

```bash
git clone -b claude/eloquent-lovelace-4vrek4 https://github.com/clarencechien/opus55poc && cd opus55poc/datacenter
```

```bash
sudo bash bench/install.sh
```

安裝腳本會把 Blender 4.2 裝到 `/opt/blender`、補上無頭渲染需要的 EGL 函式庫，並建立 `bench` 指令。裝完用 `bench --help` 確認。

## 3. 跑一個關卡

每個關卡三步：建立執行目錄、讓模型跑、計分。以 S1 easy 為例：

```bash
python3 bench/bench_admin.py init --run runs/onprem/easy/s1-r1 --stage s1 --scenario easy --budget 60 --minutes 45
```

```bash
python3 harness/qwen_runner.py --run runs/onprem/easy/s1-r1 --stage s1 --model Qwen/Qwen3.8-Flash-Next --base-url http://localhost:8000/v1 --reasoning-effort high
```

- `--base-url` 指向你們的端點；有金鑰時用 `--api-key-env 變數名稱`。
- `--reasoning-effort high` 在地端會以 `reasoning_effort` 欄位送出。伺服器若需要別的欄位，用 `--extra-body '{"欄位": 值}'` 直接併入請求。
- 模型只能用三個工具：執行單一 `bench` 指令、寫檔、讀檔或看圖。圖片會縮到長邊 1568 px。這些限制由 `qwen_runner.py` 強制，請不要放寬，否則無法和雲端版比較。
- 伺服器回 400 類錯誤（例如超出上下文）時，執行會乾淨地結束並把原因記在 `run_summary.json` 的 `reason`，作品照當下的狀態交卷。

六個關卡的參數：

| 關卡 | init 的參數 | runner 的參數 |
|---|---|---|
| S1 easy | `--stage s1 --scenario easy` | `--stage s1` |
| S1 hard | `--stage s1 --scenario hard` | `--stage s1 --prompt s1-hard` |
| S2 | `--stage s2 --scenario easy` | `--stage s2` |
| S3 easy | `--stage s3 --scenario easy-s3 --start inputs/easy-s3/s3_start.blend` | `--stage s3` |
| S3 hard | `--stage s3 --scenario hard-s3 --start inputs/hard-s3/s3_start.blend` | `--stage s3 --prompt s3-hard` |
| S1P 照片 | `--stage s1p --scenario photo-hard --start inputs/photo-hard/start.blend --minutes 60` | `--stage s1p --prompt s1p --max-turns 200` |

每個關卡都加 `--budget 60`；除了 S1P，時間上限都是 `--minutes 45`。

## 4. 計分

答案卷不在 repo 裡，要用種子重建。**重建出來的檔案請放在 repo 外面**，不要讓受測模型讀得到：

```bash
python3 gen/layout_gen.py --scenario easy --seed 338793 --out /tmp/keys/easy
```

```bash
python3 gen/layout_gen.py --scenario hard --seed 806569 --out /tmp/keys/hard
```

```bash
python3 gen/layout_gen.py --scenario hard --seed 69495 --out /tmp/keys/photo
```

| 關卡 | 計分指令（`RUN` 換成執行目錄） | 滿分 |
|---|---|---|
| S1 easy | `python3 score/s1_layout.py --run RUN --gt /tmp/keys/easy` | 100 |
| S1 hard | `python3 score/s1_layout.py --run RUN --gt /tmp/keys/hard` | 100 |
| S2 | `python3 score/s2_rack.py --run RUN`（只量幾何，不評外觀） | 40 |
| S3 easy | `python3 score/s3_place.py --run RUN --layout inputs/easy-s3/layout.json` | 100 |
| S3 hard | `python3 score/s3_place.py --run RUN --layout inputs/hard-s3/layout.json` | 100 |
| S1P 照片 | `python3 score/s1p_photo.py --run RUN --gt /tmp/keys/photo/layout.json` | 100 |

S2 的 3D 元件缺失檢查（懸空零件、門的透空率、設備重疊）：

```bash
/opt/blender/blender -b RUN/s2.blend --python score/audit_s2.py -- RUN/audit_s2.json
```

## 5. 要記錄並回報的數字

每個關卡的 `run_summary.json` 已經有大部分欄位：

| 欄位 | 意義 | 雲端版對照 |
|---|---|---|
| 分數 | 上表計分程式的 `total` | 見下表 |
| `reason` | 結束原因：`submitted` 是正常交卷；`api_stop…` 是 API 錯誤（含超出上下文）；`time`、`max_turns` 是超出上限 | 全部 `submitted` |
| `seconds` | 用時 | 見下表 |
| `bench_calls` | 計次的 Blender 操作次數 | 見下表 |
| `peak_prompt_tokens` | 單次請求的最大上下文 | S1P 為 274,507 |
| `turns` | 模型回合數 | 14–134 |

另外請記錄：模型精度與量化方式、GPU 配置、推論框架與版本、上下文設定、平均每秒輸出 token 數。

雲端託管版（OpenRouter `qwen/qwen3.8-flash`，推理強度 high）和 Opus 5.5 的成績：

| 關卡 | Opus 分數 | Qwen 雲端版分數 | Opus 用時 | Qwen 雲端版用時 |
|---|---|---|---|---|
| S1 easy | 97.1 | 97.1 | 66 秒 | 561 秒 |
| S1 hard | 100 | 100 | 95 秒 | 1,397 秒 |
| S2（幾何，滿分 40） | 40 | 40 | 543 秒 | 1,002 秒 |
| S3 easy | 100 | 100 | 102 秒 | 733 秒 |
| S3 hard | 100 | 100 | 135 秒 | 478 秒 |
| S1P 照片 | 96.1 | 52.6 | 954 秒 | 3,452 秒 |

報告用的判定規則：每一關都要達到滿分的 80%，而且加權總分要達到 80（配分見報告第 2 節）。

## 6. 已知狀況

- 每個關卡在雲端版只跑過 1 次，分數會有波動。建議地端每關至少跑 2 次。
- S2 的參考照片只有 4 張（另外 2 張候選照片當時下載失敗）。
- 預覽渲染用 Blender Workbench 的軟體渲染，每張約 1 秒；沒有裝 EGL 函式庫時 `bench render` 會失敗，重跑 `bench/install.sh` 即可。
- `bench` 會從目前所在的執行目錄判斷要操作哪一次執行，所以可以同時跑多個關卡，各自用不同的執行目錄。
- 第二階段的 4 個新關卡（竣工比對、限制式佈局設計、3D 管線繞行、依三視圖復刻設備）還在製作，完成後會補進這份手冊。
- 想看每一步的細節：`RUN/transcript.jsonl` 是模型的完整對話紀錄，`RUN/bench_log.jsonl` 是每一次 Blender 操作和執行的腳本。
