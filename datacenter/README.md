# datacenter：已移到 qwenpoc

這裡原本是「Opus 5.5 vs Qwen 3.8 Flash 操作 Blender 建 AI 機房 3D 模型」的評測工作區。整套評測已經分到獨立的 repo：

**https://github.com/clarencechien/qwenpoc**

那邊有：
- 10 個關卡的評測程式
- 答案卷重建與雜湊驗證
- 計分彙整
- 20 筆參考執行紀錄
- 完整報告與簡報
- 給接手 agent 的 `AGENTS.md`、`docs/AGENT_HANDOFF.md`

## 結論

雲端託管版 Qwen 3.8 Flash（推理強度 high）有 2 關不及格，10 關加權總分 62.7 對 99.1（及格 80）：
- 照片推回佈局：52.6 分（Opus 96.1）
- 竣工比對：60 分（Opus 100）

報告的立場是地端 Qwen3.8-Flash-Next 不能用、應使用 Opus。這是推論，地端版待實測。

## 原始工作區

qwenpoc 是精簡過的版本。原始工作區保留在分支 `claude/eloquent-lovelace-4vrek4` 的 commit `b32b206`，有些東西只在那裡：
- 含 `.blend`、Cycles 渲染圖、檢視圖的完整執行目錄
- 報告產生器 `report/build_full.py`
- Gemini 評審結果 `judge/`
- 計畫書 `PLAN.md`

取回方式：

```bash
git fetch origin claude/eloquent-lovelace-4vrek4
git checkout b32b206 -- datacenter
```
