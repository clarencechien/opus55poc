// Image-based tour: a turntable image sequence for the model, 360° panoramas at two nodes and pre-rendered walk
// clips between them. The GPU only ever draws one textured sphere, and only while something changes; the walk clips
// play as plain <video> (hardware decoded) with the view locked to the walking direction, which is what keeps them
// sharp and keeps motion sickness down (translation only, no rotation while moving).
import * as THREE from "three";

const S = 0.0218, OX = 80, OY = 675;                 // plan pixels -> metres (same as interior/plan.json)
const P = (x, y, h) => new THREE.Vector3((x - OX) * S, h, -(OY - y) * S);
const NODES = {
  living: { name: "客廳", pos: [655, 195, 1.5], floor: 0.0, btn: "bLiving" },
  washitsu: { name: "和室", pos: [505, 200, 1.66], floor: 0.36, btn: "bWashitsu" },
};
const EDGES = { "living>washitsu": "walk_living_washitsu.mp4", "washitsu>living": "walk_washitsu_living.mp4" };
const CLIP_HFOV = 100, CLIP_ASPECT = 16 / 9;          // the walk clips: rectilinear 1920x1080, heading locked, pitch 0
const ASSET = "assets/";
const $ = (id) => document.getElementById(id);
const hint = $("hint"), pinsEl = $("pins");
let mode = "model", node = null, busy = false;

function setHint(t) { hint.textContent = t; }
function pressed(id) {
  for (const b of ["bModel", "bLiving", "bWashitsu"]) $(b).setAttribute("aria-pressed", String(b === id));
}
const loadImage = (src) => new Promise((res, rej) => { const i = new Image(); i.decoding = "async"; i.onload = () => res(i); i.onerror = rej; i.src = src; });

// ------------------------------------------------------------------ turntable (model)
const tcv = $("turn"), tctx = tcv.getContext("2d");
let meta = null, frames = [], fi = 0, target = 0, vel = 0, auto = true, tDirty = true, rect = { x: 0, y: 0, w: 1, h: 1 };
const turnPins = {};

function sizeTurn() {
  const dpr = Math.min(devicePixelRatio, 2);
  tcv.width = innerWidth * dpr; tcv.height = innerHeight * dpr;
  const iw = 1440, ih = 900, portrait = innerWidth < innerHeight;
  const sc = Math.min(innerWidth / iw, (innerHeight - 40) / ih) * (portrait ? 1.45 : 1.02);   // portrait: crop the empty sides
  rect = { w: iw * sc, h: ih * sc }; rect.x = (innerWidth - rect.w) / 2; rect.y = (innerHeight - rect.h) / 2 + 10;
  tDirty = true;
}

function drawTurn() {
  const n = meta.n, dpr = tcv.width / innerWidth;
  const f = ((fi % n) + n) % n, i0 = Math.floor(f), i1 = (i0 + 1) % n, raw = f - i0;
  // 5° between frames: hold each frame for most of the step and blend only around the switch (no doubled edges)
  const u = Math.min(1, Math.max(0, (raw - 0.3) / 0.4)), t = u * u * (3 - 2 * u);
  tctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  tctx.fillStyle = "#26231f"; tctx.fillRect(0, 0, innerWidth, innerHeight);
  const a = frames[i0], b = frames[i1];
  if (a) { tctx.globalAlpha = 1; tctx.drawImage(a, rect.x, rect.y, rect.w, rect.h); }
  if (b && t > 0.01) { tctx.globalAlpha = t; tctx.drawImage(b, rect.x, rect.y, rect.w, rect.h); }
  tctx.globalAlpha = 1;
  const p0 = meta.nodes[i0], p1 = meta.nodes[i1];
  for (const [id, el] of Object.entries(turnPins)) {
    const x = p0[id][0] * (1 - t) + p1[id][0] * t, y = p0[id][1] * (1 - t) + p1[id][1] * t;
    el.style.left = `${rect.x + x * rect.w}px`; el.style.top = `${rect.y + (1 - y) * rect.h}px`;
  }
}

function turnLoop() {
  if (mode === "model") {
    if (auto) target += 0.02;                                    // ~6°/s idle spin
    else if (Math.abs(vel) > 0.001) { target += vel; vel *= 0.9; }
    const d = target - fi;
    if (Math.abs(d) > 0.0005) { fi += d * 0.22; tDirty = true; }  // ease toward the finger so steps never jump
    if (tDirty) { drawTurn(); tDirty = false; }
  }
  requestAnimationFrame(turnLoop);
}

function makePin(label, floor, onClick) {
  const el = document.createElement("div");
  el.className = "pin" + (floor ? " floor" : "");
  el.innerHTML = `<span>${label}</span><i></i>`;
  el.addEventListener("pointerdown", (e) => e.stopPropagation());
  el.addEventListener("click", (e) => { e.stopPropagation(); onClick(); });
  pinsEl.appendChild(el);
  return el;
}

async function initTurn() {
  meta = await (await fetch(ASSET + "turn.json")).json();
  meta.nodes = Object.values(meta.nodes);
  frames = new Array(meta.n);
  frames[0] = await loadImage(ASSET + "turn_000.jpg");
  sizeTurn(); drawTurn();
  $("loading").style.opacity = 0; setTimeout(() => $("loading").remove(), 700);
  for (const [id, nd] of Object.entries(NODES)) turnPins[id] = makePin(nd.name, false, () => enter(id));
  // the rest of the ring: every 4th frame first so a coarse rotation works almost at once
  const order = [];
  for (const step of [6, 3, 1]) for (let i = 0; i < meta.n; i += step) if (!order.includes(i) && i) order.push(i);
  for (const i of order) loadImage(ASSET + `turn_${String(i).padStart(3, "0")}.jpg`).then((im) => { frames[i] = im; tDirty = true; });
  requestAnimationFrame(turnLoop);
}

{
  let last = null;
  const stage = $("stage");
  stage.addEventListener("pointerdown", (e) => { if (mode !== "model") return; last = e.clientX; auto = false; vel = 0; stage.setPointerCapture(e.pointerId); });
  stage.addEventListener("pointermove", (e) => {
    if (last === null) return;
    const d = (e.clientX - last) / 8; last = e.clientX;       // ~0.6° per pixel
    target -= d; vel = -d * 0.5;
  });
  const up = () => { last = null; };
  stage.addEventListener("pointerup", up); stage.addEventListener("pointercancel", up);
}

// ------------------------------------------------------------------ 360 panoramas and clips
const pcv = $("pano");
let renderer = null, scene, camera, sphere, yaw = 0, pitch = -0.08, fov = 68, pending = false, playing = null;
const panoTex = {}, clips = {};
const floorPins = {};

function initPano() {
  renderer = new THREE.WebGLRenderer({ canvas: pcv, antialias: false, powerPreference: "low-power" });
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  scene = new THREE.Scene();
  camera = new THREE.PerspectiveCamera(fov, 1, 0.1, 200);
  const g = new THREE.SphereGeometry(50, 64, 32); g.scale(-1, 1, 1);
  sphere = new THREE.Mesh(g, new THREE.MeshBasicMaterial({ color: 0xffffff }));
  sphere.rotation.y = -Math.PI / 2;            // equirect centre = plan north (-Z here), east to the right
  scene.add(sphere);
  for (const [k] of Object.entries(EDGES)) {
    const to = k.split(">")[1];
    floorPins[k] = makePin(`前往${NODES[to].name}`, true, () => move(to));
    floorPins[k].classList.add("hide");
  }
  sizePano();
  bindPanoInput();
}

function sizePano() {
  if (!renderer) return;
  renderer.setSize(innerWidth, innerHeight, false);
  camera.aspect = innerWidth / innerHeight; camera.updateProjectionMatrix(); req();
}

function texFor(id, size) {
  const key = `${id}_${size}`;
  if (!panoTex[key]) {
    panoTex[key] = new THREE.TextureLoader().loadAsync(ASSET + `pano_${id}${size === "1k" ? "_1k" : ""}.jpg`).then((t) => {
      t.colorSpace = THREE.SRGBColorSpace; t.generateMipmaps = size === "1k"; t.minFilter = size === "1k" ? THREE.LinearMipmapLinearFilter : THREE.LinearFilter;
      renderer.initTexture(t);
      return t;
    });
  }
  return panoTex[key];
}

function clipFor(from, to) {
  const k = `${from}>${to}`;
  if (!clips[k]) {
    const v = document.createElement("video");
    const mp4 = v.canPlayType('video/mp4; codecs="avc1.640028"');
    v.src = ASSET + (mp4 ? EDGES[k] : EDGES[k].replace(".mp4", ".webm"));
    v.muted = true; v.playsInline = true; v.preload = "auto"; v.setAttribute("playsinline", ""); v.setAttribute("muted", "");
    v.className = "clip"; document.body.insertBefore(v, pinsEl); v.load();
    clips[k] = v;
  }
  return clips[k];
}

// vertical field of view at which the pano shows exactly what the clip shows (clip is object-fit: cover)
function clipFov() {
  const th = Math.tan((CLIP_HFOV * Math.PI) / 360), as = innerWidth / innerHeight;
  return (Math.atan(as >= CLIP_ASPECT ? th / as : th / CLIP_ASPECT) * 360) / Math.PI;
}

function showPano(id, tex) {
  sphere.material.map = tex; sphere.material.needsUpdate = true; node = id; req();
}

function prefetchAround(id) {
  for (const k of Object.keys(EDGES)) {
    const [from, to] = k.split(">");
    if (from === id) { clipFor(from, to); texFor(to, "1k"); texFor(to, "4k"); }
  }
}

function faceToward(from, to) {
  const tp = Array.isArray(to) ? to : NODES[to].pos;
  const d = P(tp[0], tp[1], 0).sub(P(...NODES[from].pos.slice(0, 2), 0));
  return Math.atan2(d.x, -d.z);
}
const shortest = (from, to) => from + ((to - from + Math.PI * 3) % (Math.PI * 2) - Math.PI);

async function enter(id) {
  if (busy) return;
  busy = true;
  if (!renderer) initPano();
  const other = Object.keys(NODES).find((k) => k !== id);
  yaw = faceToward(id, other); pitch = -0.1; fov = clipFov(); camera.fov = fov; camera.updateProjectionMatrix();
  setHint("讀取全景…");
  showPano(id, await texFor(id, "1k"));
  mode = "pano"; pressed(NODES[id].btn);
  pcv.classList.add("on"); $("panoStage").style.pointerEvents = "auto"; $("turn").classList.add("off");
  for (const el of Object.values(turnPins)) el.classList.add("hide");
  setHint("拖曳環顧・點地上的圓圈移動・雙指縮放");
  busy = false;
  texFor(id, "4k").then((t) => { if (node === id && !playing) showPano(id, t); });
  prefetchAround(id);
}

function backToModel() {
  if (busy) return;
  mode = "model"; node = null; pressed("bModel");
  pcv.classList.remove("on"); $("panoStage").style.pointerEvents = "none"; $("turn").classList.remove("off");
  for (const el of Object.values(turnPins)) el.classList.remove("hide");
  for (const el of Object.values(floorPins)) el.classList.add("hide");
  setHint("拖曳旋轉模型・點房間進入"); tDirty = true;
}

function tween(ms, fn) {
  return new Promise((res) => {
    const t0 = performance.now();
    const step = (now) => { const t = Math.min(1, (now - t0) / ms); fn(t * t * (3 - 2 * t)); req(); t < 1 ? requestAnimationFrame(step) : res(); };
    requestAnimationFrame(step);
  });
}

const waitFor = (v, ev, ms) => new Promise((res) => { const t = setTimeout(res, ms); v.addEventListener(ev, () => { clearTimeout(t); res(); }, { once: true }); });

async function move(to) {
  if (busy || mode !== "pano" || !node || node === to) return;
  const k = `${node}>${to}`;
  if (!EDGES[k]) return;
  busy = true;
  const v = clipFor(node, to), destTex = texFor(to, "4k");
  // 1. turn (only) to the walking direction, level the view and match the clip's field of view
  const y0 = yaw, y1 = shortest(y0, faceToward(node, to)), p0 = pitch, f0 = fov, f1 = clipFov();
  const turnMs = Math.max(350, Math.min(1100, (Math.abs(y1 - y0) / Math.PI) * 1100 + Math.abs(p0) * 600));
  await tween(turnMs, (t) => { yaw = y0 + (y1 - y0) * t; pitch = p0 * (1 - t); setFov(f0 + (f1 - f0) * t); });
  // 2. walk: the clip starts on exactly this view; translation only, heading locked
  try {
    if (v.readyState < 3) { setHint("讀取影片…"); await waitFor(v, "canplaythrough", 8000); }
    // show frame 0 (paused) over the identical pano view first, start playing only once it fully covers it,
    // so a slow first decode can never skip the start of the walk
    v.pause();
    if (v.currentTime > 0.001) { v.currentTime = 0; await waitFor(v, "seeked", 3000); }
    playing = v; v.classList.add("on"); setHint(`前往${NODES[to].name}…`); req();
    await new Promise((res) => setTimeout(res, 200));
    await v.play();
    const tex = await destTex;
    await waitFor(v, "ended", 15000);
    // 3. arrive: the destination pano at the same heading sits under the clip's last frame, then the clip fades out
    showPano(to, tex);
    frame();
  } catch (e) {
    console.warn("clip failed, cutting", e);
    showPano(to, await destTex);
  }
  v.classList.remove("on");
  await new Promise((res) => setTimeout(res, 220));
  playing = null; v.pause();
  pressed(NODES[to].btn);
  setHint("拖曳環顧・點地上的圓圈移動・雙指縮放");
  busy = false; req();
  prefetchAround(to);
}

function req() { if (!pending && renderer) { pending = true; requestAnimationFrame(frame); } }
let drawn = 0;
function frame() {
  pending = false;
  if (mode !== "pano") return;
  const cp = Math.cos(pitch);
  camera.position.set(0, 0, 0);
  camera.lookAt(Math.sin(yaw) * cp, Math.sin(pitch), -Math.cos(yaw) * cp);
  renderer.render(scene, camera); drawn++;
  // floor targets toward neighbouring nodes
  const fwd = new THREE.Vector3(); camera.getWorldDirection(fwd);
  for (const [k, el] of Object.entries(floorPins)) {
    const [from, to] = k.split(">");
    if (from !== node || playing) { el.classList.add("hide"); continue; }
    const a = NODES[from], b = NODES[to];
    const w = P(b.pos[0], b.pos[1], b.floor).sub(P(a.pos[0], a.pos[1], a.pos[2]));
    if (w.dot(fwd) <= 0.2) { el.classList.add("hide"); continue; }
    const s = w.clone().project(camera);
    el.classList.remove("hide");
    el.style.left = `${(s.x + 1) / 2 * innerWidth}px`; el.style.top = `${(1 - s.y) / 2 * innerHeight}px`;
  }
}

function bindPanoInput() {
  const st = $("panoStage"), pts = new Map();
  let pinch = 0;
  st.addEventListener("pointerdown", (e) => { pts.set(e.pointerId, [e.clientX, e.clientY]); st.setPointerCapture(e.pointerId); });
  st.addEventListener("pointermove", (e) => {
    if (!pts.has(e.pointerId) || busy) return;
    const [px, py] = pts.get(e.pointerId); pts.set(e.pointerId, [e.clientX, e.clientY]);
    if (pts.size === 2) {
      const [a, b] = [...pts.values()], d = Math.hypot(a[0] - b[0], a[1] - b[1]);
      if (pinch) setFov(fov * pinch / d);
      pinch = d; return;
    }
    const k = (fov / 75) * 0.0042;
    yaw -= (e.clientX - px) * k; pitch = Math.max(-1.35, Math.min(1.35, pitch + (e.clientY - py) * k)); req();
  });
  const up = (e) => { pts.delete(e.pointerId); if (pts.size < 2) pinch = 0; };
  st.addEventListener("pointerup", up); st.addEventListener("pointercancel", up);
  st.addEventListener("wheel", (e) => { e.preventDefault(); setFov(fov * Math.exp(e.deltaY * 0.001)); }, { passive: false });
}
function setFov(f) { fov = Math.max(35, Math.min(95, f)); camera.fov = fov; camera.updateProjectionMatrix(); req(); }

// ------------------------------------------------------------------ chrome
$("bModel").onclick = backToModel;
for (const [id, nd] of Object.entries(NODES)) {
  $(nd.btn).onclick = () => (mode === "pano" && node && node !== id ? move(id) : mode === "model" ? enter(id) : null);
}
addEventListener("resize", () => { sizeTurn(); sizePano(); });
// the walk clips are linked from a pano; start buffering the first one as soon as the model is up
setTimeout(() => { if (!Object.keys(clips).length) clipFor("living", "washitsu"); }, 2500);

function stats() {
  let bytes = 0;
  for (const r of performance.getEntriesByType("resource")) bytes += r.transferSize || r.encodedBodySize || 0;
  $("stats").textContent = `已下載 ${(bytes / 1048576).toFixed(1)} MB・GPU 只畫一顆貼圖球（${mode === "model" ? "模型是圖片序列" : `已繪製 ${drawn} 格`}）`;
}
setInterval(stats, 1000);

window.__tour = { enter, move, backToModel, look(y, p) { yaw = y; pitch = p; req(); }, get state() { return { mode, node, yaw, pitch, drawn, fi }; }, NODES };
initTurn().catch((e) => { $("lstat").textContent = "載入失敗：" + e.message; });
