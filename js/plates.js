// 電影感 2.5D 播放器：每章一張烘焙好的畫面（plate）＋深度圖＋水面遮罩。
// 深度視差推鏡、水面波光、依深度溶接轉場、年代調色與底片顆粒。鏡頭固定，所以用「騙眼睛」的方式換取質感；
// 「自由探索 3D」時才載入即時 three.js 場景。
import * as THREE from 'three';

const stage = document.querySelector('.stage');
const loading = document.getElementById('loading');
const exploreBtn = document.getElementById('exploreBtn');
const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
const BASE = 'plates/web/';

let live = null; // lazily imported three.js scene
async function loadLive() {
  if (!live) { await import('./scene3d.js'); live = window.__kb3d; }
  return live;
}

let manifest = null;
try { manifest = await (await fetch(BASE + 'manifest.json', { cache: 'no-cache' })).json(); } catch (e) { manifest = null; }
const usable = manifest && (Object.values(manifest).some(m => m.ai) || new URLSearchParams(location.search).has('plates'));
if (!usable || new URLSearchParams(location.search).has('live')) {
  // no baked plates yet: fall back to the real-time scene
  document.body.classList.add('live-mode');
  await loadLive();
  exploreBtn?.addEventListener('click', () => live.setExplore(!document.body.classList.contains('exploring')));
} else {
  startPlates();
}

function startPlates() {
  document.body.classList.add('plate-mode');
  const hv = document.getElementById('hudView'); if (hv) hv.textContent = '3D 構圖・AI 輔助寫實渲染';
  const canvas = document.createElement('canvas'); canvas.id = 'plate'; canvas.setAttribute('aria-hidden', 'true');
  stage.insertBefore(canvas, stage.firstChild);
  const labelsEl = document.createElement('div'); labelsEl.id = 'plabels'; labelsEl.setAttribute('aria-hidden', 'true');
  stage.insertBefore(labelsEl, canvas.nextSibling);

  const renderer = new THREE.WebGLRenderer({ canvas, antialias: false, alpha: false, powerPreference: 'high-performance' });
  renderer.setPixelRatio(Math.min(devicePixelRatio, 1.5));
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  const scene = new THREE.Scene(), cam = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1);
  const ERA = { old: 0, mid: 1, new: 2 }, TOD = { day: 0, dusk: .5, night: 1 };
  const blank = new THREE.DataTexture(new Uint8Array([0, 0, 0, 255]), 1, 1); blank.needsUpdate = true;
  const U = {
    tA: { value: blank }, dA: { value: blank }, wA: { value: blank },
    tB: { value: blank }, dB: { value: blank }, wB: { value: blank },
    uMix: { value: 0 }, uTime: { value: 0 }, uRes: { value: new THREE.Vector2(1, 1) }, uImg: { value: 16 / 9 },
    uFocusX: { value: .62 }, uPar: { value: new THREE.Vector2() }, uDollyA: { value: 0 }, uDollyB: { value: 0 },
    uEraA: { value: 2 }, uEraB: { value: 2 }, uNightA: { value: 1 }, uNightB: { value: 1 }, uShiftX: { value: 0 }
  };
  const mat = new THREE.ShaderMaterial({
    uniforms: U,
    vertexShader: 'varying vec2 vUv; void main(){ vUv = uv; gl_Position = vec4(position.xy, 0.0, 1.0); }',
    fragmentShader: /* glsl */`
precision highp float;
varying vec2 vUv;
uniform sampler2D tA, dA, wA, tB, dB, wB;
uniform float uMix, uTime, uImg, uFocusX, uDollyA, uDollyB, uEraA, uEraB, uNightA, uNightB, uShiftX;
uniform vec2 uRes, uPar;
float h21(vec2 p){ return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
float vn(vec2 p){ vec2 i = floor(p), f = fract(p); f = f*f*(3.-2.*f); return mix(mix(h21(i), h21(i+vec2(1,0)), f.x), mix(h21(i+vec2(0,1)), h21(i+vec2(1,1)), f.x), f.y); }
vec2 cover(vec2 uv){
  float sa = uRes.x / uRes.y;
  vec2 s = sa > uImg ? vec2(1.0, uImg / sa) : vec2(sa / uImg, 1.0);
  return uv * s + (1.0 - s) * vec2(uFocusX, 0.5) + vec2(uShiftX, 0.0);
}
// depth-aware parallax + dolly: near pixels (depth≈1) move and grow more
vec2 warp(sampler2D D, vec2 uv, float dolly, vec2 par){
  vec2 p = uv;
  for (int i = 0; i < 4; i++) {
    float d = texture2D(D, p).r;
    float z = 1.0 + dolly * (0.35 + 0.65 * d);
    p = 0.5 + (uv - 0.5) / z - par * (d - 0.35);
  }
  return p;
}
vec3 water(sampler2D T, sampler2D W, sampler2D D, vec2 p, float night){
  float w = texture2D(W, p).r;
  float d = texture2D(D, p).r;
  vec2 q = p;
  if (w > 0.01) {
    float t = uTime;
    vec2 wob = vec2(sin(p.y * 260.0 + t * 1.6 + vn(p * 40.0 + t * .2) * 6.0) * 0.0009,
                    sin(p.x * 80.0 - t * 1.2) * 0.0011 + (vn(vec2(p.x * 30.0, p.y * 220.0 - t * .8)) - .5) * 0.004);
    q += wob * w * (0.4 + d);
  }
  vec3 c = texture2D(T, q).rgb;
  if (w > 0.01) {
    float lum = dot(c, vec3(.3, .59, .11));
    float glint = pow(vn(vec2(q.x * 900.0, q.y * 2600.0) + uTime * vec2(.6, 1.3)), 14.0);
    c += w * glint * (0.12 + 0.6 * smoothstep(.45, .95, lum)) * mix(vec3(1.0, .95, .85), vec3(1.0, .82, .55), night);
  }
  return c;
}
vec3 grade(vec3 c, float era, vec2 uv){
  float l = dot(c, vec3(.299, .587, .114));
  if (era < 0.5) {            // 1920s–1940s: hand-tinted print, warm toning, gate weave dust
    vec3 sepia = vec3(l) * vec3(1.08, .96, .78);
    c = mix(sepia, c, .42);
    c = c * .92 + .045;
    float dust = step(.9975, h21(floor(uv * vec2(900.0, 500.0)) + floor(uTime * 12.0)));
    float scratch = step(.9985, h21(vec2(floor(uv.x * 700.0), floor(uTime * 8.0)))) * .25;
    c = mix(c, vec3(.95, .9, .8), dust * .5) + scratch;
    c *= 0.97 + 0.03 * sin(uTime * 23.0);
  } else if (era < 1.5) {     // 1970s: faded Kodachrome
    c = mix(vec3(l), c, .82);
    c = c * vec3(1.04, .99, .9) * .93 + vec3(.03, .04, .045);
    c = mix(c, c * vec3(.9, 1.02, 1.05), 1.0 - smoothstep(.0, .5, l));
  } else {                    // today: gentle filmic contrast, teal shadows / warm highlights
    c = mix(c, c * vec3(.94, 1.0, 1.04), 1.0 - smoothstep(.1, .5, l));
    c = mix(c, c * vec3(1.04, 1.0, .95), smoothstep(.5, 1.0, l));
    c = (c - .5) * 1.05 + .5;
  }
  return c;
}
void main(){
  vec2 uv = cover(vUv);
  float t = uTime;
  vec2 par = uPar;
  vec2 weave = vec2(0.0);
  if (uEraA < .5 || uEraB < .5) weave = (vec2(h21(vec2(floor(t * 12.0), 1.0)), h21(vec2(floor(t * 12.0), 2.0))) - .5) * .0012;
  vec2 pA = warp(dA, uv + weave * step(uEraA, .5), uDollyA, par);
  vec2 pB = warp(dB, uv + weave * step(uEraB, .5), uDollyB, par);
  vec3 a = grade(water(tA, wA, dA, pA, uNightA), uEraA, vUv);
  vec3 col = a;
  if (uMix > 0.001) {
    vec3 b = grade(water(tB, wB, dB, pB, uNightB), uEraB, vUv);
    // depth dissolve: the far distance of the next shot appears first, the foreground last
    float d = texture2D(dB, pB).r;
    float n = vn(vUv * vec2(9.0, 5.0) + t * .3) * .25;
    float e = uMix * 1.5 - .25;
    float m = smoothstep(e + .12, e - .12, d + n);
    col = mix(a, b, m);
  }
  // vignette + grain
  vec2 v = vUv - .5; col *= 1.0 - dot(v, v) * .55;
  float g = h21(vUv * uRes + fract(t * 61.0) * 100.0) - .5;
  float oldness = 1.0 - smoothstep(.5, 1.5, mix(uEraA, uEraB, uMix));
  col += g * mix(.022, .06, oldness);
  gl_FragColor = vec4(clamp(col, 0.0, 1.0), 1.0);
}`
  });
  scene.add(new THREE.Mesh(new THREE.PlaneGeometry(2, 2), mat));

  // ---------- assets ----------
  const loader = new THREE.TextureLoader();
  const cache = new Map();
  function tex(url, color) {
    return new Promise((res, rej) => loader.load(url, t => { t.colorSpace = THREE.NoColorSpace; void color; t.minFilter = THREE.LinearFilter; t.generateMipmaps = false; res(t); }, undefined, rej));
  }
  function plate(scene) {
    const m = manifest[scene]; if (!m) return Promise.reject(new Error('no plate ' + scene));
    if (!cache.has(scene)) cache.set(scene, Promise.all([tex(BASE + m.id + '.jpg', true), tex(BASE + m.id + '_d.png'), tex(BASE + m.id + '_w.png')]).then(([t, d, w]) => ({ t, d, w, m })));
    return cache.get(scene);
  }
  const order = [...document.querySelectorAll('.step')].map(s => s.dataset.scene);
  function prefetch(scene) { const i = order.indexOf(scene); [order[i + 1], order[i - 1], order[i + 2]].forEach(s => s && manifest[s] && plate(s).catch(() => {})); }

  // ---------- labels (projected positions baked with the plates) ----------
  function coverMap(x, yTop) { // baked image coords (x from left, y from top) -> screen px, following the shader's dolly
    const W = stage.clientWidth, H = stage.clientHeight, sa = W / H, ia = U.uImg.value;
    const z = 1 + U.uDollyA.value * .6;
    const u = .5 + (x - .5) * z, v = .5 + ((1 - yTop) - .5) * z;
    const s = sa > ia ? [1, ia / sa] : [sa / ia, 1];
    const off = [(1 - s[0]) * U.uFocusX.value + U.uShiftX.value, (1 - s[1]) * .5];
    return [(u - off[0]) / s[0] * W, (1 - (v - off[1]) / s[1]) * H];
  }
  let labelData = [];
  function showLabels(list) {
    labelsEl.innerHTML = '';
    labelData = (list || []).map(l => { const e = document.createElement('div'); e.className = 'lbl' + (l.warn ? ' warn' : ''); e.innerHTML = `<b>${l.t}</b>${l.s ? `<span>${l.s}</span>` : ''}`; labelsEl.appendChild(e); return { l, e }; });
    placeLabels();
  }
  function placeLabels() {
    for (const { l, e } of labelData) { const [x, y] = coverMap(l.x, l.y); e.style.transform = `translate(${x.toFixed(1)}px,${y.toFixed(1)}px)`; }
  }

  // ---------- scene switching ----------
  let cur = null, want = null, busy = false, mixT = 0;
  const dolly = { A: 0, B: 0 };
  async function go(scene) {
    want = scene; if (busy || scene === cur || !manifest[scene]) return;
    busy = true;
    let P; try { P = await plate(scene); } catch (e) { busy = false; return; }
    if (cur === null) {
      Object.assign(U.tA, { value: P.t }); U.dA.value = P.d; U.wA.value = P.w; U.uEraA.value = ERA[P.m.era]; U.uNightA.value = TOD[P.m.time];
      cur = scene; busy = false; loading?.classList.add('done'); showLabels(P.m.labels); prefetch(scene); return;
    }
    U.tB.value = P.t; U.dB.value = P.d; U.wB.value = P.w; U.uEraB.value = ERA[P.m.era]; U.uNightB.value = TOD[P.m.time];
    labelsEl.style.opacity = 0;
    const dur = reduce ? 1 : 1700, t0 = performance.now();
    await new Promise(r => { const step = now => { mixT = Math.min(1, (now - t0) / dur); U.uMix.value = mixT * mixT * (3 - 2 * mixT); if (mixT < 1) requestAnimationFrame(step); else r(); }; requestAnimationFrame(step); });
    U.tA.value = P.t; U.dA.value = P.d; U.wA.value = P.w; U.uEraA.value = U.uEraB.value; U.uNightA.value = U.uNightB.value; U.uMix.value = 0;
    dolly.A = dolly.B;
    cur = scene; busy = false; showLabels(P.m.labels); labelsEl.style.opacity = 1; prefetch(scene);
    if (want !== cur) go(want);
  }
  window.addEventListener('kb-scene', e => go(e.detail));

  // ---------- explore mode: hand over to the live three.js scene ----------
  exploreBtn?.addEventListener('click', async () => {
    const on = !document.body.classList.contains('exploring');
    if (on) { exploreBtn.textContent = '載入 3D…'; await loadLive(); live.setScene(cur || 'reopen', true); }
    live.setExplore(on);
  });

  // ---------- loop ----------
  const pointer = new THREE.Vector2(), parNow = new THREE.Vector2();
  addEventListener('pointermove', e => { if (e.pointerType === 'mouse') pointer.set(e.clientX / innerWidth - .5, e.clientY / innerHeight - .5); }, { passive: true });
  let visible = true;
  new IntersectionObserver(es => { visible = es[0].isIntersecting; }).observe(document.getElementById('story'));
  function resize() {
    const W = stage.clientWidth, H = stage.clientHeight; renderer.setSize(W, H, false); U.uRes.value.set(W * renderer.getPixelRatio(), H * renderer.getPixelRatio());
    // plates are composed for a desktop layout with the text column on the left; on narrow screens focus on the subject
    U.uFocusX.value = W > 760 ? .5 : .66; U.uShiftX.value = 0;
    placeLabels();
  }
  addEventListener('resize', resize); resize();
  const steps = [...document.querySelectorAll('.step')];
  let t0 = performance.now();
  function frame(now) {
    requestAnimationFrame(frame);
    if (!visible || document.body.classList.contains('exploring')) return;
    U.uTime.value = (now - t0) / 1000;
    // scroll progress through the active chapter drives a slow dolly-in
    const act = steps.find(s => s.classList.contains('is-active'));
    if (act && !reduce) { const r = act.getBoundingClientRect(); const p = Math.min(1, Math.max(0, (innerHeight * .5 - r.top) / r.height)); dolly.B = .015 + p * .07; }
    U.uDollyA.value += ((busy ? dolly.A : dolly.B) - U.uDollyA.value) * .06; U.uDollyB.value = dolly.B;
    const sway = reduce ? 0 : 1;
    parNow.lerp(new THREE.Vector2(pointer.x * .014 + Math.sin(now * .00013) * .004 * sway, pointer.y * .008 + Math.cos(now * .00011) * .003 * sway), .05);
    U.uPar.value.copy(parNow);
    renderer.render(scene, cam);
    if (!busy) placeLabels();
  }
  requestAnimationFrame(frame);
  go(window.__scene || 'reopen');
}
