# 川端橋 1937–2026

以捲動驅動的 **3D 動畫**介紹新店溪上的川端橋（戰後改名中正橋）：從渡船時代、1937 年開通、戰後三次拓寬、危橋與 2015 年文資保存、新中正橋鋼拱施工，到 **2026 年 9 月 21 日川端橋修復啟用**。

- `index.html` — 內容、樣式、章節卡片、地圖與年表
- `js/scene3d.js` — three.js 場景：依史料尺寸建模的川端橋（13 座雙柱式拱型橋墩、14 孔上承式鋼鈑梁、300.56 m × 5.2 m）、1972 年拓寬段、新中正橋三點式透空拱肋鋼拱（拱跨 215 m、拱高 50 m、28 條鋼纜）、依 OpenStreetMap 新店溪中心線生成的河道與地形、各年代城市、天空／水面反射／夜間光雕
- `js/page.js` — 捲動章節、年份 HUD、互動地圖、年表、數字動畫
- `js/plates.js` — 電影感 2.5D 播放器：每章一張烘焙畫面＋深度圖＋水面遮罩，做深度視差推鏡、水面波光、依深度溶接轉場、年代調色與底片顆粒；有 AI 畫面時預設使用，否則退回即時 3D（`?live` 強制即時 3D，`?plates` 用 3D 渲染圖預覽播放器）
- `plates/selection.json` — 每章採用的 AI 版本；`python plates/tools.py web` 依此產出 `plates/web/`
- `plates/` — 畫面烘焙流程：`passes/`（three.js 輸出的成品圖、深度、水面遮罩）、`prompts.json`（各章提示詞）、`modal_plates.py`（Modal GPU：RealVisXL＋SDXL depth ControlNet img2img）、`tools.py`（前後處理）、`web/`（網頁用素材與 manifest）
- `.github/workflows/plates.yml` — （選用，手動觸發）在 GitHub Actions 上呼叫 Modal 生成畫面；需 repo secrets `MODAL_TOKEN_ID`、`MODAL_TOKEN_SECRET`。本機或雲端沙箱直接執行即可：`pip install 'modal[api-proxy-support]'` 後 `modal run plates/modal_plates.py`（有 HTTP proxy 的環境必須裝 `api-proxy-support`）
- `assets/waternormals.jpg` — 水面法線貼圖（three.js 範例素材，MIT）

## 部署（GitHub Pages）

純靜態網站，無需建置。在 repo 的 **Settings → Pages** 選擇要發布的分支與根目錄 `/`，即可於 `https://<帳號>.github.io/<repo>/` 瀏覽。three.js 由 jsDelivr CDN 載入。

本機預覽：`python3 -m http.server` 後開啟 `http://localhost:8000/`（ES module 無法以 `file://` 直接開啟）。

資料來源列於頁面底部；3D 場景為依史料與照片重建的示意，非工程圖。
