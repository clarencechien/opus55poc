// 68-ping apartment viewer: empty shell vs. Japanese wa-style fit-out.
// Every baked surface is MeshBasicMaterial(albedo map x Cycles lightmap): no real-time lighting, so phones keep 60 fps.
import * as THREE from "three";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";

const S = 0.0218, OX = 80, OY = 675;                 // plan pixels -> metres (same as interior/plan.json)
const P = (x, y, h) => new THREE.Vector3((x - OX) * S, h, -(OY - y) * S);
const EYE = 1.52;
const FLOORS = new Set(["oak_floor", "laminate", "tile_public", "marble", "stone", "bath_tile", "balcony", "gravel", "soil",
  "tatami_g", "tatami_a", "tatami_b"]);
const isFloor = (h) => {
  const m = Array.isArray(h.object.material) ? h.object.material[h.face?.materialIndex ?? 0] : h.object.material;
  const n = h.face ? h.face.normal.clone().transformDirection(h.object.matrixWorld) : null;
  return m && FLOORS.has(m.name) && n && n.y > 0.9 && h.point.y < 0.45;
};

const VIEWS = [
  { id: "entry", name: "玄關", pos: [692, 650], look: [692, 330] },
  { id: "living", name: "客廳", pos: [740, 478], look: [575, 160] },
  { id: "washitsu", name: "和室", pos: [528, 306], look: [405, 160] },
  { id: "garden", name: "窗景", pos: [470, 215], look: [466, 70], lookH: 1.05 },
  { id: "dining", name: "餐廳", pos: [650, 345], look: [470, 480], lookH: 0.9 },
  { id: "master", name: "主臥", pos: [965, 385], look: [800, 215], lookH: 0.9 },
  { id: "bath", name: "主浴", pos: [772, 505], look: [880, 520], lookH: 1.0 },
  { id: "br2", name: "臥室二", pos: [236, 300], look: [300, 110], lookH: 1.0 },
  { id: "br4", name: "臥室四", pos: [300, 392], look: [160, 470], lookH: 1.0 },
];

const canvas = document.getElementById("c");
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, powerPreference: "high-performance" });
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.75));
renderer.toneMapping = THREE.AgXToneMapping;
renderer.outputColorSpace = THREE.SRGBColorSpace;
const scene = new THREE.Scene();
scene.background = new THREE.Color(0x1c1a17);
const camera = new THREE.PerspectiveCamera(70, 1, 0.05, 200);
scene.add(new THREE.HemisphereLight(0xfff3e2, 0x6a5b4b, 1.6));          // only the imported props use real-time light
const sunish = new THREE.DirectionalLight(0xfff0dd, 1.2); sunish.position.set(3, 8, -6); scene.add(sunish);

const loader = new GLTFLoader();
const texLoader = new THREE.TextureLoader();
const maxAniso = renderer.capabilities.getMaxAnisotropy();
const variants = {};         // id -> { root, manifest, ready }
let current = "wa", mode = "walk";

// ---------------------------------------------------------------- loading
const fill = document.getElementById("fill"), statusEl = document.getElementById("status");
function progress(frac, msg) { fill.style.width = `${Math.round(frac * 100)}%`; if (msg) statusEl.textContent = msg; }

async function fetchJSON(url) { const r = await fetch(url); if (!r.ok) throw new Error(url); return r.json(); }
function loadTex(url, srgb = true, repeat = false) {
  return new Promise((res) => texLoader.load(url, (t) => {
    t.colorSpace = srgb ? THREE.SRGBColorSpace : THREE.NoColorSpace;
    if (repeat) { t.wrapS = t.wrapT = THREE.RepeatWrapping; t.anisotropy = Math.min(8, maxAniso); }
    res(t);
  }, undefined, () => res(null)));
}
function loadGLB(url, onProg) {
  return new Promise((res, rej) => loader.load(url, res, (e) => e.total && onProg && onProg(e.loaded / e.total), rej));
}

async function loadVariant(id, report) {
  const base = `assets/${id}/`;
  const man = await fetchJSON(base + "manifest.json");
  report(0.05, "讀取材質與光照…");
  const lms = {};
  for (const [obj, lm] of Object.entries(man.lightmaps)) {
    const t = await loadTex(base + lm.file, true);
    if (t) { t.channel = 1; t.flipY = false; }
    lms[obj] = { tex: t, intensity: lm.intensity };
  }
  const texCache = {};
  for (const [name, def] of Object.entries(man.materials)) {
    if (def.map && !texCache[def.map]) {
      const t = await loadTex(base + def.map, true, true);
      if (t) t.flipY = false;
      texCache[def.map] = t;
    }
  }
  report(0.35, "讀取模型…");
  const gltf = await loadGLB(base + "scene.glb", (f) => report(0.35 + f * 0.45));
  const root = new THREE.Group(); root.name = id;
  const matCache = {};
  const makeMat = (name, group) => {
    const key = `${name}|${group}`;
    if (matCache[key]) return matCache[key];
    const def = man.materials[name];
    let m;
    if (!def) m = new THREE.MeshBasicMaterial({ color: 0xbbbbbb });
    else if (def.type === "glass") m = new THREE.MeshBasicMaterial({ color: 0xe6f2f2, transparent: true, opacity: 0.1, depthWrite: false, side: THREE.DoubleSide });
    else if (def.type === "emit") {
      const c = new THREE.Color().setRGB(...def.color, THREE.LinearSRGBColorSpace).multiplyScalar(Math.min(def.strength / 5, 5));
      m = new THREE.MeshBasicMaterial({ color: c });
    } else {
      m = new THREE.MeshBasicMaterial();
      if (def.map && texCache[def.map]) m.map = texCache[def.map];
      else m.color.setRGB(...def.color, THREE.LinearSRGBColorSpace);
      const lm = lms[group];
      const vl = (man.vertexlit || {})[group];
      if (vl) { m.vertexColors = true; m.color.multiplyScalar(vl.intensity * (def.paper ? 1.7 : 1.0)); }
      else if (lm && lm.tex) { m.lightMap = lm.tex; m.lightMapIntensity = lm.intensity * (def.paper ? 1.7 : 1.0); }
      if (def.paper) m.side = THREE.DoubleSide;
    }
    m.name = name;
    return (matCache[key] = m);
  };
  gltf.scene.traverse((o) => {
    if (!o.isMesh) return;
    let g = o, group = "";
    while (g) { if (g.name && (g.name.startsWith("BAKE_") || g.name.startsWith("VC_") || g.name === "EMIT" || g.name === "GLASS")) { group = g.name; break; } g = g.parent; }
    const mats = Array.isArray(o.material) ? o.material : [o.material];
    const out = mats.map((mm) => makeMat(mm.name, group));
    o.material = out.length === 1 ? out[0] : out;
    if (group === "GLASS") o.renderOrder = 2;
  });
  root.add(gltf.scene);
  report(0.82, "讀取家具與植栽…");
  try {
    const props = await loadGLB(base + "props.glb", (f) => report(0.82 + f * 0.15));
    props.scene.traverse((o) => {
      if (o.isMesh && o.material) {
        const ms = Array.isArray(o.material) ? o.material : [o.material];
        ms.forEach((mm) => { if (mm.map) mm.map.anisotropy = 4; mm.envMapIntensity = 0.4; });
      }
    });
    root.add(props.scene);
  } catch (e) { console.warn("props", e); }
  if (man.sky && man.sky.file) {
    const sky = await loadTex(base + man.sky.file, true);
    if (sky) { sky.mapping = THREE.EquirectangularReflectionMapping; root.userData.sky = sky; }
  }
  root.userData.exposure = Math.pow(2, man.exposure || 0);
  report(1, "完成");
  variants[id] = { root, manifest: man };
  return variants[id];
}

// ---------------------------------------------------------------- views and walking
const look = { yaw: 0, pitch: 0 };
function applyLook() {
  camera.rotation.set(0, 0, 0, "YXZ");
  camera.rotation.y = look.yaw; camera.rotation.x = look.pitch;
}
function floorHeightAt(x, z) {
  const v = variants[current]; if (!v) return 0;
  const rc = new THREE.Raycaster(new THREE.Vector3(x, 2.4, z), new THREE.Vector3(0, -1, 0), 0, 3);
  const hit = rc.intersectObject(v.root, true).find(isFloor);
  return hit ? hit.point.y : 0;
}
let tween = null;
function goTo(pos, yaw, pitch, dur = 700) {
  const from = camera.position.clone(), fy = look.yaw, fp = look.pitch;
  let dy = yaw === undefined ? 0 : ((yaw - fy + Math.PI) % (2 * Math.PI) + 2 * Math.PI) % (2 * Math.PI) - Math.PI;
  const t0 = performance.now();
  tween = (now) => {
    const t = Math.min(1, (now - t0) / dur), e = t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2;
    camera.position.lerpVectors(from, pos, e);
    if (yaw !== undefined) { look.yaw = fy + dy * e; look.pitch = fp + (pitch - fp) * e; }
    applyLook();
    if (t >= 1) tween = null;
  };
}
function jumpView(v, animate = true) {
  const pos = P(v.pos[0], v.pos[1], 0);
  pos.y = floorHeightAt(pos.x, pos.z) + EYE;
  const tgt = P(v.look[0], v.look[1], v.lookH ?? 1.2);
  const d = tgt.clone().sub(pos);
  const yaw = Math.atan2(-d.x, -d.z), pitch = Math.atan2(d.y, Math.hypot(d.x, d.z));
  if (mode !== "walk") setMode("walk");
  if (animate) goTo(pos, yaw, pitch, 900);
  else { camera.position.copy(pos); look.yaw = yaw; look.pitch = pitch; applyLook(); }
  document.querySelectorAll(".rooms button").forEach((b) => b.classList.toggle("on", b.dataset.id === v.id));
}

// pointer: drag to look, tap the floor to walk, pinch / wheel to zoom
const ptrs = new Map(); let downAt = null, pinch0 = null;
canvas.addEventListener("pointerdown", (e) => {
  canvas.setPointerCapture(e.pointerId); ptrs.set(e.pointerId, { x: e.clientX, y: e.clientY });
  if (ptrs.size === 1) downAt = { x: e.clientX, y: e.clientY, t: performance.now(), moved: 0 };
  if (ptrs.size === 2) { const [a, b] = [...ptrs.values()]; pinch0 = { d: Math.hypot(a.x - b.x, a.y - b.y), fov: camera.fov }; }
});
canvas.addEventListener("pointermove", (e) => {
  if (!ptrs.has(e.pointerId) || mode !== "walk") { if (ptrs.has(e.pointerId)) ptrs.set(e.pointerId, { x: e.clientX, y: e.clientY }); return; }
  const p = ptrs.get(e.pointerId); const dx = e.clientX - p.x, dy = e.clientY - p.y;
  ptrs.set(e.pointerId, { x: e.clientX, y: e.clientY });
  if (ptrs.size === 2 && pinch0) {
    const [a, b] = [...ptrs.values()];
    camera.fov = THREE.MathUtils.clamp(pinch0.fov * pinch0.d / Math.max(20, Math.hypot(a.x - b.x, a.y - b.y)), 30, 90);
    camera.updateProjectionMatrix(); return;
  }
  if (downAt) downAt.moved += Math.abs(dx) + Math.abs(dy);
  const k = (camera.fov / 70) * 0.0042;
  look.yaw += dx * k; look.pitch = THREE.MathUtils.clamp(look.pitch + dy * k, -1.35, 1.35);
  applyLook(); tween = null; hideHint();
});
const endPtr = (e) => {
  ptrs.delete(e.pointerId); if (ptrs.size < 2) pinch0 = null;
  if (mode === "walk" && downAt && ptrs.size === 0 && downAt.moved < 8 && performance.now() - downAt.t < 400) tapWalk(e.clientX, e.clientY);
  if (ptrs.size === 0) downAt = null;
};
canvas.addEventListener("pointerup", endPtr); canvas.addEventListener("pointercancel", endPtr);
canvas.addEventListener("wheel", (e) => {
  if (mode !== "walk") return;
  camera.fov = THREE.MathUtils.clamp(camera.fov + e.deltaY * 0.03, 30, 90); camera.updateProjectionMatrix();
}, { passive: true });

const ring = document.getElementById("ring");
function tapWalk(cx, cy) {
  const v = variants[current]; if (!v) return;
  const ndc = new THREE.Vector2((cx / innerWidth) * 2 - 1, -(cy / innerHeight) * 2 + 1);
  const rc = new THREE.Raycaster(); rc.setFromCamera(ndc, camera);
  const hits = rc.intersectObject(v.root, true);
  const h = hits.find((x) => x.object.visible && !(x.object.material && x.object.material.transparent));
  if (!h) return;
  const n = h.face ? h.face.normal.clone().transformDirection(h.object.matrixWorld) : new THREE.Vector3(0, 1, 0);
  let target;
  if (isFloor(h)) target = h.point.clone();                                   // floor or tatami
  else {                                                                     // wall or furniture: stop 0.6 m short
    const d = h.point.clone().sub(camera.position); d.y = 0;
    const len = Math.max(0, d.length() - 0.6); if (len < 0.3) return;
    target = camera.position.clone().add(d.normalize().multiplyScalar(len)); target.y = 0;
    target.y = floorHeightAt(target.x, target.z);
  }
  ring.style.left = `${cx}px`; ring.style.top = `${cy}px`; ring.style.opacity = 1; setTimeout(() => (ring.style.opacity = 0), 350);
  const dest = new THREE.Vector3(target.x, target.y + EYE, target.z);
  goTo(dest, undefined, undefined, Math.min(1400, 350 + camera.position.distanceTo(dest) * 180));
  hideHint();
}

// keyboard for desktop (with a simple wall check)
const keys = new Set();
addEventListener("keydown", (e) => keys.add(e.key.toLowerCase()));
addEventListener("keyup", (e) => keys.delete(e.key.toLowerCase()));
function keyMove(dt) {
  if (mode !== "walk" || !keys.size) return;
  const f = (keys.has("w") || keys.has("arrowup") ? 1 : 0) - (keys.has("s") || keys.has("arrowdown") ? 1 : 0);
  const s = (keys.has("d") ? 1 : 0) - (keys.has("a") ? 1 : 0);
  const turn = (keys.has("arrowleft") ? 1 : 0) - (keys.has("arrowright") ? 1 : 0);
  look.yaw += turn * dt * 1.6; applyLook();
  if (!f && !s) return;
  const dir = new THREE.Vector3(-Math.sin(look.yaw) * f + Math.cos(look.yaw) * s, 0, -Math.cos(look.yaw) * f - Math.sin(look.yaw) * s).normalize();
  const rc = new THREE.Raycaster(camera.position.clone().setY(camera.position.y - 0.7), dir, 0, 0.45);
  if (rc.intersectObject(variants[current].root, true).length) return;
  camera.position.addScaledVector(dir, dt * 1.6);
  camera.position.y = floorHeightAt(camera.position.x, camera.position.z) + EYE;
}

// ---------------------------------------------------------------- dollhouse
const orbit = new OrbitControls(camera, canvas);
orbit.enabled = false; orbit.enableDamping = true; orbit.maxPolarAngle = 1.35; orbit.minDistance = 6; orbit.maxDistance = 45;
const CENTER = P(546, 370, 0);
const cutPlane = new THREE.Plane(new THREE.Vector3(0, -1, 0), 2.45);
const DOLL_BG = new THREE.Color(0x2a2724);
let walkState = null;
function setMode(m) {
  mode = m;
  document.getElementById("mWalk").setAttribute("aria-pressed", m === "walk");
  document.getElementById("mDoll").setAttribute("aria-pressed", m === "doll");
  if (m === "doll") {
    walkState = { pos: camera.position.clone(), yaw: look.yaw, pitch: look.pitch, fov: camera.fov };
    renderer.clippingPlanes = [cutPlane];
    scene.background = DOLL_BG; scene.backgroundIntensity = 1;
    camera.fov = 45; camera.updateProjectionMatrix();
    camera.position.copy(CENTER).add(innerWidth < innerHeight ? new THREE.Vector3(-9, 26, 15) : new THREE.Vector3(-9, 16, 12));
    orbit.target.copy(CENTER); orbit.enabled = true; orbit.update();
    setHint("單指旋轉・雙指縮放平移・點房間名稱進入");
  } else {
    renderer.clippingPlanes = [];
    orbit.enabled = false;
    const vv = variants[current];
    if (vv && vv.root.userData.sky) { scene.background = vv.root.userData.sky; scene.backgroundIntensity = 1.0 / vv.root.userData.exposure; }
    if (walkState) { camera.position.copy(walkState.pos); look.yaw = walkState.yaw; look.pitch = walkState.pitch; camera.fov = walkState.fov; camera.updateProjectionMatrix(); applyLook(); }
    setHint("拖曳環顧・點地板前往・雙指縮放");
  }
}
document.getElementById("mWalk").onclick = () => setMode("walk");
document.getElementById("mDoll").onclick = () => setMode("doll");

// ---------------------------------------------------------------- variants
const badge = document.getElementById("badge");
function showVariant(id) {
  const v = variants[id]; if (!v) return;
  current = id;
  for (const [k, vv] of Object.entries(variants)) vv.root.visible = k === id;
  if (mode === "doll") scene.background = DOLL_BG;
  else if (v.root.userData.sky) { scene.background = v.root.userData.sky; scene.backgroundIntensity = 1.0 / v.root.userData.exposure; }
  renderer.toneMappingExposure = v.root.userData.exposure;
  document.getElementById("vEmpty").setAttribute("aria-pressed", id === "empty");
  document.getElementById("vWa").setAttribute("aria-pressed", id === "wa");
  if (mode === "walk") camera.position.y = floorHeightAt(camera.position.x, camera.position.z) + EYE;
  badge.textContent = id === "wa" ? "和風" : "空屋"; badge.style.opacity = 1; setTimeout(() => (badge.style.opacity = 0), 900);
}
async function ensure(id, btn) {
  if (variants[id]) return showVariant(id);
  btn.disabled = true; const label = btn.textContent; btn.textContent = "載入…";
  const v = await loadVariant(id, () => {});
  scene.add(v.root); v.root.visible = false;
  btn.disabled = false; btn.textContent = label;
  showVariant(id);
}
document.getElementById("vEmpty").onclick = (e) => ensure("empty", e.currentTarget);
document.getElementById("vWa").onclick = (e) => ensure("wa", e.currentTarget);

// ---------------------------------------------------------------- ui
const hintEl = document.getElementById("hint"); let hintTimer = null;
function setHint(t) { hintEl.textContent = t; hintEl.style.opacity = 1; clearTimeout(hintTimer); hintTimer = setTimeout(hideHint, 6000); }
function hideHint() { hintEl.style.opacity = 0; }
const roomsEl = document.getElementById("rooms");
for (const v of VIEWS) {
  const b = document.createElement("button"); b.textContent = v.name; b.dataset.id = v.id;
  b.onclick = () => jumpView(v); roomsEl.appendChild(b);
}
function resize() {
  const w = innerWidth, h = innerHeight;
  renderer.setSize(w, h, false); camera.aspect = w / h;
  camera.fov = mode === "walk" ? (w < h ? 78 : 66) : camera.fov; camera.updateProjectionMatrix();
}
addEventListener("resize", resize);

// ---------------------------------------------------------------- start
(async () => {
  resize();
  const params = new URLSearchParams(location.search);
  const first = params.get("v") === "empty" ? "empty" : "wa";
  try {
    const v = await loadVariant(first, progress);
    scene.add(v.root);
    showVariant(first);
    jumpView(VIEWS.find((x) => x.id === (params.get("room") || "living")) || VIEWS[1], false);
    if (params.get("mode") === "doll") setMode("doll");
    const ld = document.getElementById("loading"); ld.style.opacity = 0; setTimeout(() => ld.remove(), 700);
    setHint("拖曳環顧・點地板前往・雙指縮放");
    // preload the other variant quietly so the toggle is instant
    const other = first === "wa" ? "empty" : "wa";
    loadVariant(other, () => {}).then((o) => { scene.add(o.root); o.root.visible = false; }).catch(() => {});
  } catch (e) {
    console.error(e); statusEl.textContent = "載入失敗，請重新整理";
  }
})();

let last = performance.now();
renderer.setAnimationLoop((now) => {
  const dt = Math.min(0.05, (now - last) / 1000); last = now;
  if (tween) tween(now);
  keyMove(dt);
  if (mode === "doll") orbit.update();
  renderer.render(scene, camera);
});
window.__viewer = { camera, scene, variants, jumpView, setMode, showVariant, VIEWS };
