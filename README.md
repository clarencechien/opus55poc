# 川端橋 1937–2026

以捲動驅動的 **3D 動畫**介紹新店溪上的川端橋（戰後改名中正橋）：從渡船時代、1937 年開通、戰後三次拓寬、危橋與 2015 年文資保存、新中正橋鋼拱施工，到 **2026 年 9 月 21 日川端橋修復啟用**。

- `index.html` — 內容、樣式、章節卡片、地圖與年表
- `js/scene3d.js` — three.js 場景：依史料尺寸建模的川端橋（13 座雙柱式拱型橋墩、14 孔上承式鋼鈑梁、300.56 m × 5.2 m）、1972 年拓寬段、新中正橋三點式透空拱肋鋼拱（拱跨 215 m、拱高 50 m、28 條鋼纜）、依 OpenStreetMap 新店溪中心線生成的河道與地形、各年代城市、天空／水面反射／夜間光雕
- `js/page.js` — 捲動章節、年份 HUD、互動地圖、年表、數字動畫
- `js/plates.js` — 電影感 2.5D 播放器：每章一張烘焙畫面＋深度圖＋水面遮罩，做深度視差推鏡、水面波光、依深度溶接轉場、年代調色與底片顆粒；有 AI 畫面時預設使用，否則退回即時 3D（`?live` 強制即時 3D，`?plates` 用 3D 渲染圖預覽播放器）
- 畫面品質流程：`index.html?live&hq` 以高精度模型烘焙（人有四肢、車有車窗車輪、分團樹冠與竹叢、永和側紅磚三合院、公寓陽台鐵窗與屋頂水塔；僅供烘焙，網頁即時 3D 仍用輕量模型），並輸出類別 ID 圖；`modal run plates/modal_plates.py --detail` 依 ID 圖把人、車、樹、房屋、船逐一裁切放大到 1024 px、依年代提示詞局部重繪後貼回
- `plates/selection.json` — 每章採用的 AI 版本；`python plates/tools.py web` 依此產出 `plates/web/`
- `plates/` — 畫面烘焙流程：`passes/`（three.js 輸出的成品圖、深度、水面遮罩）、`prompts.json`（各章提示詞）、`modal_plates.py`（Modal GPU：RealVisXL＋SDXL depth ControlNet img2img）、`tools.py`（前後處理）、`web/`（網頁用素材與 manifest）
- `.github/workflows/plates.yml` — （選用，手動觸發）在 GitHub Actions 上呼叫 Modal 生成畫面；需 repo secrets `MODAL_TOKEN_ID`、`MODAL_TOKEN_SECRET`。本機或雲端沙箱直接執行即可：`pip install 'modal[api-proxy-support]'` 後 `modal run plates/modal_plates.py`（有 HTTP proxy 的環境必須裝 `api-proxy-support`）
- `render/` — Blender Cycles 路徑追蹤流程（做法參考 pirrer/meiji-bridge-3d，MIT）：`kawabata_scene.py` 以 Poly Haven CC0 PBR 材質、HDRI 天空、真實光源重建場景，`modal_render.py` 在 Modal L40S 上以無頭 Blender 4.2 LTS 渲染
  - 靜態樣張：`modal run render/modal_render.py --shots open,reopen` → `render/out/`；`render/samples/` 為成品
  - 紀錄片試片（1935–1937 建橋，25 秒、30 fps）：`modal run render/modal_render.py::anim --clip build` 將 750 格分 10 段平行渲染到 Modal Volume，再加中文字幕、淡入淡出並以 H.264 編碼成 `render/out/pilot_build.mp4`；`--probe 60,300,700 --res 960x540 --samples 48` 只渲染幾格快速檢查
- `assets/waternormals.jpg` — 水面法線貼圖（three.js 範例素材，MIT）

## 和風宅：空屋 ⇄ 日式和風（`interior/`）

一張 68 坪豪宅家具配置圖 → 空屋平面 → 空屋 3D → 日式和風裝潢渲染 → 手機可跑的 3D 導覽。

- `interior/plan.json` — 由原圖描出的牆、柱、門窗、樑、房間（像素座標＋比例），所有後續步驟共用這一份資料；`tools/plan_tools.py` 可疊圖檢查、算面積、輸出空屋平面 SVG 與公尺座標
- `interior/blender/interior_scene.py` — Blender 程序化建模：`--variant empty` 交屋空屋、`--variant wa` 和風裝潢（和室＋雪見障子、坪庭、秋田杉電視牆、竿緣天井、間接照明、檜木浴缸…），Poly Haven CC0 材質／HDRI／植栽茶具
- `interior/blender/bake_export.py` — 把 Cycles 光照烘焙成光照圖（大面）與逐角頂點色（細小構件、軟墊），輸出 GLB＋manifest 給手機導覽
- `interior/modal_interior.py` — 在 Modal L40S 上執行：`::plan`（平面圖轉 PNG）、`::render --variant empty,wa --shots living,washitsu…`、`::bake --variant empty,wa`
- `interior/index.html` — 空屋／和風逐空間拖曳對照頁；`interior/viewer/` — three.js 手機 3D 導覽（漫遊／俯瞰、空屋／和風即時切換，材質為貼圖×烘焙光照，不做即時光照）
- `interior/renders/` — 渲染成品

## 部署（GitHub Pages）

純靜態網站，無需建置。在 repo 的 **Settings → Pages** 選擇要發布的分支與根目錄 `/`，即可於 `https://<帳號>.github.io/<repo>/` 瀏覽。three.js 由 jsDelivr CDN 載入。

本機預覽：`python3 -m http.server` 後開啟 `http://localhost:8000/`（ES module 無法以 `file://` 直接開啟）。

資料來源列於頁面底部；3D 場景為依史料與照片重建的示意，非工程圖。
