// 川端橋 3D 場景 —— Three.js
// 座標：x = 東（上游），y = 上，z = 南（永和）。單位：公尺。原點約在川端橋中點（新店溪河道中心）。
import * as THREE from 'three';
import { Sky } from 'three/addons/objects/Sky.js';
import { Water } from 'three/addons/objects/Water.js';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { UnrealBloomPass } from 'three/addons/postprocessing/UnrealBloomPass.js';
import { OutputPass } from 'three/addons/postprocessing/OutputPass.js';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { mergeGeometries } from 'three/addons/utils/BufferGeometryUtils.js';

const canvas = document.getElementById('gl');
const stage = canvas.parentElement;
const loading = document.getElementById('loading');
const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
const mobile = () => stage.clientWidth <= 760;

let renderer;
try {
  renderer = new THREE.WebGLRenderer({ canvas, antialias: true, powerPreference: 'high-performance' });
} catch (e) {
  document.body.classList.add('no-webgl');
  if (loading) loading.textContent = '此裝置不支援 WebGL，僅顯示文字內容。';
  throw e;
}
renderer.setPixelRatio(Math.min(devicePixelRatio, mobile() ? 1.5 : 1.75));
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 0.5;

const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(40, 1, 2, 60000);
camera.position.set(200, 30, 200);

// ---------- utilities ----------
let seed = 1937;
const rnd = () => { seed |= 0; seed = seed + 0x6D2B79F5 | 0; let t = Math.imul(seed ^ seed >>> 15, 1 | seed); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; };
const R = (a, b) => a + rnd() * (b - a);
const clamp = (v, a = 0, b = 1) => Math.min(b, Math.max(a, v));
const smooth = (a, b, v) => { const t = clamp((v - a) / (b - a)); return t * t * (3 - 2 * t); };
const lerp = (a, b, t) => a + (b - a) * t;
function hash2(x, z) { const s = Math.sin(x * 127.1 + z * 311.7) * 43758.5453; return s - Math.floor(s); }
function vnoise(x, z) {
  const xi = Math.floor(x), zi = Math.floor(z), xf = x - xi, zf = z - zi;
  const u = xf * xf * (3 - 2 * xf), v = zf * zf * (3 - 2 * zf);
  const a = hash2(xi, zi), b = hash2(xi + 1, zi), c = hash2(xi, zi + 1), d = hash2(xi + 1, zi + 1);
  return lerp(lerp(a, b, u), lerp(c, d, u), v);
}
const fbm = (x, z, o = 5) => { let s = 0, a = .5, f = 1; for (let i = 0; i < o; i++) { s += a * vnoise(x * f, z * f); f *= 2.03; a *= .5; } return s; };

function NI(g) { return g.index ? g.toNonIndexed() : g; }
function merge(list) { const m = mergeGeometries(list.map(NI), false); list.forEach(g => g.dispose()); return m; }
function box(w, h, d, x = 0, y = 0, z = 0, ry = 0, rx = 0, rz = 0) {
  const g = new THREE.BoxGeometry(w, h, d);
  if (rx) g.rotateX(rx); if (rz) g.rotateZ(rz); if (ry) g.rotateY(ry);
  g.translate(x, y, z); return g;
}
function cyl(r1, r2, h, x = 0, y = 0, z = 0, seg = 14) { const g = new THREE.CylinderGeometry(r1, r2, h, seg); g.translate(x, y + h / 2, z); return g; }
function rod(a, b, r, seg = 6) { // cylinder between two points
  const d = new THREE.Vector3().subVectors(b, a), L = d.length();
  const g = new THREE.CylinderGeometry(r, r, L, seg, 1, true);
  g.translate(0, L / 2, 0);
  const q = new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0, 1, 0), d.normalize());
  g.applyQuaternion(q); g.translate(a.x, a.y, a.z); return g;
}

const freshU = () => ({ uUp: { value: 0 }, uProj: { value: 0 }, uGlow: { value: 0 }, uGlowCol: { value: new THREE.Color(1, .75, .35) } });
// world-position based weathering (concrete stains / paint wear) + optional night glow terms
function weather(mat, opts = {}) {
  const { scale = 0.35, amount = 0.28, streak = 0.25 } = opts;
  mat.userData.u = freshU();
  mat.onBeforeCompile = function (sh) {
    Object.assign(sh.uniforms, this.userData.u);
    sh.vertexShader = sh.vertexShader
      .replace('#include <common>', '#include <common>\nvarying vec3 vWP;')
      .replace('#include <worldpos_vertex>', '#include <worldpos_vertex>\n{ vec4 wp4 = vec4(transformed,1.0);\n#ifdef USE_INSTANCING\n wp4 = instanceMatrix * wp4;\n#endif\n vWP = (modelMatrix * wp4).xyz; }');
    sh.fragmentShader = sh.fragmentShader
      .replace('#include <common>', `#include <common>
varying vec3 vWP; uniform float uUp; uniform float uProj; uniform float uGlow; uniform vec3 uGlowCol;
float h21(vec2 p){return fract(sin(dot(p,vec2(127.1,311.7)))*43758.5453);}
float vn(vec2 p){vec2 i=floor(p),f=fract(p);f=f*f*(3.-2.*f);return mix(mix(h21(i),h21(i+vec2(1,0)),f.x),mix(h21(i+vec2(0,1)),h21(i+vec2(1,1)),f.x),f.y);}
float fb(vec2 p){float s=0.,a=.5;for(int i=0;i<4;i++){s+=a*vn(p);p*=2.07;a*=.5;}return s;}`)
      .replace('#include <color_fragment>', `#include <color_fragment>
{ float n = fb(vWP.xz*${scale.toFixed(3)} + vWP.y*${(scale * 0.7).toFixed(3)});
  float st = fb(vec2(vWP.x*1.7+vWP.z*1.7, vWP.y*0.08))*smoothstep(0.5,1.0,fb(vec2(vWP.x+vWP.z,0.0)*0.9));
  diffuseColor.rgb *= 1.0 - ${amount.toFixed(3)}*(n-0.35) - ${streak.toFixed(3)}*st; }`)
      .replace('#include <emissivemap_fragment>', `#include <emissivemap_fragment>
totalEmissiveRadiance += uUp * vec3(1.0,0.66,0.32) * (0.25 + 1.6*smoothstep(8.0,-1.5,vWP.y));
{ float m = mod(vWP.z + 150.28, 21.4686); float dd = min(m, 21.4686-m);
  totalEmissiveRadiance += uProj * vec3(1.0,0.78,0.5) * (1.0 - smoothstep(1.0, 6.0, dd)) * smoothstep(20.0, 9.0, vWP.y) * smoothstep(-50.0, -18.0, vWP.x); }
totalEmissiveRadiance += uGlow * uGlowCol;`);
  };
  mat.customProgramCacheKey = () => 'w' + scale + amount + streak;
  return mat;
}

// ---------- materials ----------
const MAT = {};
MAT.concrete = weather(new THREE.MeshStandardMaterial({ color: 0xbdb6a8, roughness: .93 }), { amount: .32, streak: .35 });
MAT.concreteOld = weather(new THREE.MeshStandardMaterial({ color: 0xb3aa98, roughness: .95 }), { amount: .4, streak: .45 });
MAT.concreteNew = weather(new THREE.MeshStandardMaterial({ color: 0xd7d4cc, roughness: .85 }), { amount: .12, streak: .08 });
MAT.wideConc = weather(new THREE.MeshStandardMaterial({ color: 0xa9a8a2, roughness: .92 }), { amount: .35, streak: .4 });
MAT.stone = weather(new THREE.MeshStandardMaterial({ color: 0x9d9383, roughness: .97 }), { scale: 1.2, amount: .45, streak: .2 });
MAT.steel = weather(new THREE.MeshStandardMaterial({ color: 0x86b25a, roughness: .55, metalness: .35 }), { scale: .8, amount: .22, streak: .15 }); // 照片所見的淺綠色漆
MAT.mint = weather(new THREE.MeshStandardMaterial({ color: 0xc4e6df, roughness: .42, metalness: .3 }), { scale: .5, amount: .06, streak: .04 }); // 新中正橋的薄荷色鋼拱
MAT.cable = new THREE.MeshStandardMaterial({ color: 0xe8eef0, roughness: .3, metalness: .7 });
MAT.asphalt = new THREE.MeshStandardMaterial({ color: 0x3a3b3d, roughness: .95 });
MAT.rail = new THREE.MeshStandardMaterial({ color: 0x9aa3a8, roughness: .5, metalness: .6 });
MAT.railOld = weather(new THREE.MeshStandardMaterial({ color: 0xc7bfad, roughness: .9 }), { amount: .35, streak: .3 });
MAT.railNew = new THREE.MeshStandardMaterial({ color: 0xece5d6, roughness: .7 });
MAT.wood = weather(new THREE.MeshStandardMaterial({ color: 0x8a6240, roughness: .85 }), { scale: 2.5, amount: .35, streak: 0 });
MAT.led = new THREE.MeshBasicMaterial({ color: 0xffd9a0 }); MAT.led.toneMapped = false;
MAT.lampHead = new THREE.MeshStandardMaterial({ color: 0x333333, emissive: 0xffe2b0, emissiveIntensity: 0 }); MAT.lampHead.userData.isLamp = true;
MAT.lineWhite = new THREE.MeshStandardMaterial({ color: 0xe9e9e2, roughness: .8 });
MAT.green = new THREE.MeshStandardMaterial({ color: 0x2fbf9a, roughness: .6, metalness: .3 });
MAT.yellow = new THREE.MeshStandardMaterial({ color: 0xe8b21e, roughness: .55, metalness: .3 });
MAT.timber = weather(new THREE.MeshStandardMaterial({ color: 0x8b6a45, roughness: .95 }), { scale: 2, amount: .3, streak: 0 });

// ---------- geography (OpenStreetMap river centreline) ----------
const LON0 = 121.5161, LAT0 = 25.0206, ZOFF = 21;
const KX = 111320 * Math.cos(LAT0 * Math.PI / 180), KZ = 110574;
const geo = (lon, lat) => [(lon - LON0) * KX, -(lat - LAT0) * KZ + ZOFF];
const RIVER_LL = [
  [121.505, 25.090], [121.503, 25.070], [121.495, 25.055], [121.4886, 25.0443], [121.4843, 25.0397], [121.4832713, 25.034909],
  [121.4836186, 25.0331558], [121.488403, 25.0251971], [121.4890006, 25.0191122], [121.488651, 25.0175936], [121.488748, 25.0160775],
  [121.4893579, 25.0140543], [121.4916288, 25.011029], [121.4940415, 25.0097678], [121.4957471, 25.0096602], [121.4974625, 25.0103001],
  [121.4997913, 25.0117512], [121.5083368, 25.0210144], [121.5107134, 25.021774], [121.5144172, 25.0215331], [121.5199348, 25.0192485],
  [121.5217883, 25.0158432], [121.5253876, 25.0120714], [121.5307963, 25.0089055], [121.5320259, 25.0075238], [121.5326706, 25.0056724],
  [121.533628, 25.0041124], [121.5334391, 25.0031074], [121.5314904, 25.0015313], [121.530883, 24.9994749], [121.5308296, 24.99737],
  [121.531, 24.985], [121.534, 24.972], [121.540, 24.960]
];
const TRIB_LL = [[121.4832713, 25.034909], [121.475, 25.030], [121.462, 25.022], [121.447, 25.012], [121.430, 25.003]]; // 大漢溪
function densify(ll) {
  const p = ll.map(([a, b]) => new THREE.Vector3(geo(a, b)[0], 0, geo(a, b)[1]));
  const c = new THREE.CatmullRomCurve3(p, false, 'centripetal');
  return c.getSpacedPoints(Math.round(c.getLength() / 40)).map(v => [v.x, v.z]);
}
const RIV = densify(RIVER_LL), TRIB = densify(TRIB_LL);
const SEGS = [];
for (const L of [RIV, TRIB]) for (let i = 0; i < L.length - 1; i++) SEGS.push([L[i][0], L[i][1], L[i + 1][0], L[i + 1][1]]);
function riverDist(x, z) {
  let best = 1e12;
  for (const [ax, az, bx, bz] of SEGS) {
    const dx = bx - ax, dz = bz - az, t = clamp(((x - ax) * dx + (z - az) * dz) / (dx * dx + dz * dz));
    const ex = ax + dx * t - x, ez = az + dz * t - z, d = ex * ex + ez * ez;
    if (d < best) best = d;
  }
  return Math.sqrt(best);
}
// point on river: s = arc index along RIV (nearest to x), offset to the north(-)/south(+) bank
function riverFrame(x, z) {
  let bi = 0, bd = 1e12;
  for (let i = 0; i < RIV.length - 1; i++) { const d = (RIV[i][0] - x) ** 2 + (RIV[i][1] - z) ** 2; if (d < bd) { bd = d; bi = i; } }
  const a = RIV[bi], b = RIV[bi + 1];
  const t = new THREE.Vector2(b[0] - a[0], b[1] - a[1]).normalize();
  return { p: new THREE.Vector2(a[0], a[1]), t, n: new THREE.Vector2(-t.y, t.x) };
}
const W = 128; // half width of the channel
function hOld(d, x, z) {
  const n = (fbm(x * .004, z * .004) - .5) * 2.2;
  if (d < W - 12) return -4.2 + n * .3;
  if (d < W + 14) return lerp(-4.2, 3.2, smooth(W - 12, W + 14, d)) + n * .3;
  return 4 + n + smooth(W + 14, W + 200, d) * .6;
}
function hNew(d, x, z) {
  const n = (fbm(x * .006, z * .006) - .5);
  if (d < W - 12) return -4.2 + n * .3;
  if (d < W + 2) return lerp(-4.2, 1.0, smooth(W - 12, W + 2, d));
  if (d < W + 66) return 1.3 + n * .5;
  if (d < W + 76) return lerp(1.3, 9.2, smooth(W + 66, W + 76, d));
  if (d < W + 86) return 9.2;
  if (d < W + 94) return lerp(9.2, 7.2, smooth(W + 86, W + 94, d));
  return 7.2 + n * .4;
}
const PEAKS = [
  [-9140, -11910, 616, 2600], // 觀音山
  [590, -12650, 1090, 4200], [4030, -12300, 1120, 3600], // 大屯山、七星山
  [6550, -1000, 380, 1600], [8200, -2600, 420, 2200], // 象山・四獸山一帶
  [-3130, 2300, 300, 1400], [-1200, 4800, 420, 2600], [3000, 6200, 520, 3200], [9000, 4200, 600, 3800], // 南側丘陵
  [-12000, 3000, 500, 4000], [12500, -8000, 800, 5000]
];
function mountain(x, z) {
  let h = 0;
  for (const [px, pz, ph, pr] of PEAKS) { const d2 = ((x - px) ** 2 + (z - pz) ** 2) / (pr * pr); h += ph * Math.exp(-d2 * 1.6); }
  const r = Math.hypot(x * .8, z);
  h += smooth(8500, 15000, r) * 520 * fbm(x * .0004, z * .0004, 4);
  return h * (0.72 + 0.56 * fbm(x * .0012 + 7, z * .0012, 4));
}

// ---------- terrain (morph: 0 = 1930s natural banks, 1 = post-1953 levees & floodplain park) ----------
function terrain(size, seg, far) {
  const g = new THREE.PlaneGeometry(size, size, seg, seg); g.rotateX(-Math.PI / 2);
  const P = g.attributes.position, n = P.count;
  const pN = new Float32Array(n * 3), cO = new Float32Array(n * 3), cN = new Float32Array(n * 3);
  const col = new THREE.Color();
  const inner = 800;
  for (let i = 0; i < n; i++) {
    const x = P.getX(i), z = P.getZ(i);
    let ho, hn, m = 0, d = 1e9;
    if (far && Math.abs(x) < inner - 1 && Math.abs(z) < inner - 1) { ho = hn = -9; }
    else {
      d = riverDist(x, z); ho = hOld(d, x, z); hn = hNew(d, x, z);
      if (far) { m = mountain(x, z); if (d > W + 20) { ho = Math.max(ho, m); hn = Math.max(hn, m); } }
    }
    P.setY(i, ho); pN[i * 3] = x; pN[i * 3 + 1] = hn; pN[i * 3 + 2] = z;
    const nn = fbm(x * .02, z * .02, 3);
    const mcol = () => col.setHSL(.26, .3, Math.max(.1, .2 + nn * .05 - Math.min(m, 900) * .00007));
    // 1930s: sandy banks, paddy fields
    if (d < W - 6) col.setRGB(.33, .3, .24);
    else if (d < W + 14) col.setRGB(.55, .5, .38).multiplyScalar(.85 + nn * .3);
    else { const plot = hash2(Math.floor(x / 38), Math.floor(z / 30)); col.setHSL(.2 + plot * .08, .35 + plot * .15, .27 + nn * .08 + plot * .05); }
    if (m > 30) mcol();
    cO[i * 3] = col.r; cO[i * 3 + 1] = col.g; cO[i * 3 + 2] = col.b;
    // modern: floodplain park, levee, city
    if (d < W - 6) col.setRGB(.33, .3, .24);
    else if (d < W + 3) col.setRGB(.45, .42, .34);
    else if (d < W + 66) col.setHSL(.25, .38, .26 + nn * .09);
    else if (d < W + 94) col.setRGB(.56, .56, .54);
    else { col.setRGB(.42, .41, .4).multiplyScalar(.85 + nn * .3); if (Math.abs(x) < 11 && Math.abs(z) > 230) col.setRGB(.2, .2, .21); }
    if (m > 30) mcol();
    cN[i * 3] = col.r; cN[i * 3 + 1] = col.g; cN[i * 3 + 2] = col.b;
  }
  g.setAttribute('color', new THREE.BufferAttribute(cO, 3));
  g.computeVertexNormals();
  const gN = g.clone(); gN.setAttribute('position', new THREE.BufferAttribute(pN, 3)); gN.computeVertexNormals();
  g.morphAttributes.position = [new THREE.BufferAttribute(pN, 3)];
  g.morphAttributes.normal = [gN.attributes.normal.clone()];
  g.morphAttributes.color = [new THREE.BufferAttribute(cN, 3)];
  gN.dispose();
  const mat = weather(new THREE.MeshStandardMaterial({ vertexColors: true, roughness: .97 }), { scale: .05, amount: .25, streak: 0 });
  const mesh = new THREE.Mesh(g, mat);
  mesh.morphTargetInfluences = [0];
  mesh.receiveShadow = !far;
  return mesh;
}
const terrNear = terrain(1600, 320, false);
const terrFar = terrain(32000, 400, true);
terrFar.position.y = -0.35;
scene.add(terrNear, terrFar);

// ---------- water ----------
const waterNormals = new THREE.TextureLoader().load('assets/waternormals.jpg', t => { t.wrapS = t.wrapT = THREE.RepeatWrapping; });
const water = new Water(new THREE.PlaneGeometry(40000, 40000), {
  textureWidth: mobile() ? 512 : 1024, textureHeight: mobile() ? 512 : 1024,
  waterNormals, sunDirection: new THREE.Vector3(0, 1, 0), sunColor: 0xffffff,
  waterColor: 0x1e3a33, distortionScale: 1.6, fog: true
});
water.rotation.x = -Math.PI / 2;
water.material.uniforms.size.value = 6.0;
scene.add(water);

// ---------- sky, sun, moon, stars ----------
const sky = new Sky(); sky.scale.setScalar(40000); scene.add(sky);
const SU = sky.material.uniforms;
const sun = new THREE.DirectionalLight(0xffffff, 3);
sun.castShadow = true;
sun.shadow.mapSize.set(mobile() ? 1024 : 2048, mobile() ? 1024 : 2048);
Object.assign(sun.shadow.camera, { left: -330, right: 330, top: 330, bottom: -330, near: 10, far: 2400 });
sun.shadow.bias = -0.0004; sun.shadow.normalBias = 0.6;
sun.target.position.set(-16, 0, 0);
scene.add(sun, sun.target);
const nightDome = new THREE.Mesh(new THREE.SphereGeometry(35000, 48, 24), new THREE.ShaderMaterial({
  side: THREE.BackSide, transparent: true, depthWrite: false, fog: false,
  uniforms: { uO: { value: 0 } },
  vertexShader: 'varying vec3 vD; void main(){ vD = normalize(position); gl_Position = projectionMatrix*modelViewMatrix*vec4(position,1.0); }',
  fragmentShader: 'uniform float uO; varying vec3 vD; void main(){ float h = max(vD.y, 0.0); vec3 zen = vec3(.012,.02,.055), hor = vec3(.075,.085,.13), glow = vec3(.16,.12,.11); vec3 c = mix(hor, zen, pow(h, .45)); c += glow * exp(-h * 18.0) * .9; gl_FragColor = vec4(c, uO); }'
}));
nightDome.renderOrder = -1; scene.add(nightDome);
const hemi = new THREE.HemisphereLight(0xcfe3ff, 0x4a4436, .6); scene.add(hemi);
scene.fog = new THREE.FogExp2(0xbfd1dc, 0.00011);

const stars = (() => {
  const n = 2600, p = new Float32Array(n * 3), c = new Float32Array(n * 3);
  for (let i = 0; i < n; i++) {
    const u = rnd(), v = rnd() * .95 + .03, th = u * Math.PI * 2, ph = Math.acos(v);
    p[i * 3] = Math.sin(ph) * Math.cos(th) * 30000; p[i * 3 + 1] = Math.cos(ph) * 30000; p[i * 3 + 2] = Math.sin(ph) * Math.sin(th) * 30000;
    const b = .5 + rnd() * .5; c[i * 3] = b; c[i * 3 + 1] = b; c[i * 3 + 2] = b * (0.9 + rnd() * .2);
  }
  const g = new THREE.BufferGeometry(); g.setAttribute('position', new THREE.BufferAttribute(p, 3)); g.setAttribute('color', new THREE.BufferAttribute(c, 3));
  const m = new THREE.PointsMaterial({ size: 1.6, sizeAttenuation: false, vertexColors: true, transparent: true, opacity: 0, depthWrite: false, fog: false });
  const pts = new THREE.Points(g, m); scene.add(pts); return pts;
})();
function glowTex(inner = 'rgba(255,248,225,1)', mid = 'rgba(255,240,200,.35)') {
  const c = document.createElement('canvas'); c.width = c.height = 256; const x = c.getContext('2d');
  const g = x.createRadialGradient(128, 128, 0, 128, 128, 128);
  g.addColorStop(0, inner); g.addColorStop(.12, inner); g.addColorStop(.16, mid); g.addColorStop(1, 'rgba(255,240,200,0)');
  x.fillStyle = g; x.fillRect(0, 0, 256, 256); const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; return t;
}
const moon = new THREE.Sprite(new THREE.SpriteMaterial({ map: glowTex(), transparent: true, depthWrite: false, fog: false, opacity: 0 }));
moon.material.toneMapped = false; moon.scale.setScalar(2200); scene.add(moon);
const moonDir = new THREE.Vector3().setFromSphericalCoords(1, THREE.MathUtils.degToRad(90 - 13), THREE.MathUtils.degToRad(-128));
moon.position.copy(moonDir).multiplyScalar(26000);

// ---------- helpers for scene objects ----------
const ALL = {}; // name -> {obj, v, target, apply}
function reg(name, obj, apply) {
  const mats = new Map();
  obj.traverse(o => {
    if (!o.material) return;
    const arr = Array.isArray(o.material) ? o.material : [o.material];
    const cl = arr.map(m => { if (!mats.has(m)) { const c = m.clone(); c.onBeforeCompile = m.onBeforeCompile; c.customProgramCacheKey = m.customProgramCacheKey; if (m.userData.u) c.userData.u = freshU(); if (m.userData.uNight) c.userData.uNight = { value: 0 }; if (m.uniforms) c.uniforms = THREE.UniformsUtils.clone(m.uniforms); mats.set(m, c); } return mats.get(m); });
    o.material = Array.isArray(o.material) ? cl : cl[0];
  });
  const S = { obj, v: 0, target: 0, mats: [...mats.values()], apply: apply || fadeApply };
  S.mats.forEach(m => { m.userData.baseOpacity = m.opacity; m.userData.baseTransparent = m.transparent; });
  ALL[name] = S; obj.visible = false; return S;
}
function fadeApply(S, v) {
  S.obj.visible = v > 0.003;
  const op = S.ghost !== undefined ? lerp(1, S.ghost, S.ghostV || 0) * v : v;
  for (const m of S.mats) {
    const t = op < 0.995;
    if (m.transparent !== (t || m.userData.baseTransparent)) { m.transparent = t || m.userData.baseTransparent; m.needsUpdate = true; }
    m.opacity = m.userData.baseOpacity * op;
    m.depthWrite = !t;
  }
}
function mesh(geo, mat, cast = true, recv = true) { const m = new THREE.Mesh(geo, mat); m.castShadow = cast; m.receiveShadow = recv; return m; }

// ---------- 川端橋 (1937) ----------
const L0 = 300.56, NS = 14, SPAN = L0 / NS, Z0 = -L0 / 2;
const pierZ = []; for (let i = 1; i < NS; i++) pierZ.push(Z0 + i * SPAN);
const Y_CAP = 7.4, Y_DECK = 9.3, RAISE = 1.5;

function pierGeometry() {
  // local y: 0 (riverbed, world -4) … 11.4 (cap top, world 7.4)
  const parts = [];
  parts.push(box(8.6, 3.2, 3.6, 0, 1.6, 0));            // footing (below water)
  parts.push(box(7.0, .9, 2.8, 0, 3.55, 0));            // plinth at the waterline
  const cr = 1.0, cx = 2.15;
  parts.push(cyl(cr, cr * 1.04, 10.2, -cx, 0, 0, 20), cyl(cr, cr * 1.04, 10.2, cx, 0, 0, 20)); // twin columns
  const s = new THREE.Shape();
  s.moveTo(-cx, 6.0); s.lineTo(-1.15, 6.0); s.lineTo(-1.15, 8.0);
  s.absarc(0, 8.0, 1.15, Math.PI, 0, true);
  s.lineTo(1.15, 6.0); s.lineTo(cx, 6.0); s.lineTo(cx, 10.2); s.lineTo(-cx, 10.2); s.lineTo(-cx, 6.0);
  const wall = new THREE.ExtrudeGeometry(s, { depth: 1.5, bevelEnabled: true, bevelSize: .06, bevelThickness: .06, bevelSegments: 1, curveSegments: 16 });
  wall.translate(0, 0, -.75); parts.push(wall);
  parts.push(box(6.0, 1.2, 2.1, 0, 10.8, 0));           // cap
  parts.push(box(6.3, .18, 2.3, 0, 10.25, 0));          // cornice line
  return merge(parts);
}
const PIER_GEO = pierGeometry();
const kbPiers = new THREE.Group();
pierZ.forEach((z, i) => { const m = mesh(PIER_GEO, MAT.concreteOld); m.position.set(0, -4, z); m.userData.i = i; kbPiers.add(m); });
scene.add(kbPiers);
reg('kbPiers', kbPiers, (S, v) => {
  S.obj.visible = v > .003;
  S.obj.children.forEach((m, i) => { const k = smooth(0, 1, v * 1.8 - i * .06); m.scale.y = Math.max(.001, k); m.visible = k > .002; });
});

// abutments (masonry)
const kbAbut = new THREE.Group();
[-1, 1].forEach(sg => { kbAbut.add(mesh(merge([box(7.4, 11, 7, 0, 3.5, sg * (L0 / 2 + 3.2)), box(9.5, 1.1, 1.2, 0, 8.45, sg * (L0 / 2 + .4))]), MAT.stone)); });
scene.add(kbAbut); reg('kbAbut', kbAbut);

// girders: 14 spans of riveted deck plate girders (上承式鋼鈑梁)
function spanGeometry(L) {
  const p = [], gx = 1.9, H = 1.5, yb = Y_CAP;
  for (const x of [-gx, gx]) {
    p.push(box(.05, H, L - .3, x, yb + H / 2, L / 2));                  // web
    p.push(box(.46, .07, L - .3, x, yb + H - .035, L / 2), box(.46, .07, L - .3, x, yb + .035, L / 2)); // flanges
    for (let z = .6; z < L - .4; z += 1.3) p.push(box(.26, H - .14, .035, x, yb + H / 2, z)); // stiffeners
  }
  for (let z = .4; z <= L - .3; z += (L - .8) / 5) {                    // cross frames
    p.push(box(3.8, .16, .14, 0, yb + H - .2, z), box(3.8, .16, .14, 0, yb + .25, z));
    const a = Math.atan2(H - .5, 3.8);
    p.push(box(4.0, .1, .1, 0, yb + H / 2, z, 0, 0, a), box(4.0, .1, .1, 0, yb + H / 2, z, 0, 0, -a));
  }
  const bay = (L - .8) / 5;                                              // lateral bracing (bottom)
  for (let k = 0; k < 5; k++) { const z = .4 + bay * (k + .5), ang = Math.atan2(3.8, bay), len = Math.hypot(3.8, bay); p.push(box(.1, .08, len, 0, yb + .12, z, ang), box(.1, .08, len, 0, yb + .12, z, -ang)); }
  return merge(p);
}
const SPAN_GEO = spanGeometry(SPAN);
const kbTop = new THREE.Group(); scene.add(kbTop);
const kbGirders = new THREE.Group();
for (let i = 0; i < NS; i++) { const m = mesh(SPAN_GEO, MAT.steel); m.position.z = Z0 + i * SPAN; kbGirders.add(m); }
kbTop.add(kbGirders);
reg('kbGirders', kbGirders, (S, v) => {
  S.obj.visible = v > .003;
  S.obj.children.forEach((m, i) => { const k = smooth(0, 1, v * 1.9 - i * .065); m.position.y = (1 - k) * 28; m.visible = k > .01; });
});

// deck slab, name posts (親柱) and railings
function plaqueTex(txt) {
  const c = document.createElement('canvas'); c.width = 128; c.height = 384; const x = c.getContext('2d');
  x.fillStyle = '#d6cfbf'; x.fillRect(0, 0, 128, 384);
  x.strokeStyle = '#8c8474'; x.lineWidth = 6; x.strokeRect(10, 10, 108, 364);
  x.fillStyle = '#2b2721'; x.font = '900 86px "Noto Serif TC","Songti TC",serif'; x.textAlign = 'center'; x.textBaseline = 'middle';
  [...txt].forEach((ch, i) => x.fillText(ch, 64, 72 + i * 118));
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = 4; return t;
}
const PLQ = { kawabata: plaqueTex('川端橋'), zhongzheng: plaqueTex('中正橋') };
const plaqueMat = new THREE.MeshStandardMaterial({ map: PLQ.kawabata, roughness: .8 });
const kbDeck = new THREE.Group();
kbDeck.add(mesh(merge([box(6.0, .4, L0 + 1, 0, Y_DECK - .2, 0), box(6.3, .5, L0 + 1, 0, Y_DECK - .65, 0)]), MAT.concreteOld));
const postGeo = [];
[-1, 1].forEach(sz => [-1, 1].forEach(sx => postGeo.push(box(.9, 2.6, .9, sx * 3.35, Y_DECK + 1.3, sz * (L0 / 2 + .2)), box(1.1, .3, 1.1, sx * 3.35, Y_DECK + 2.75, sz * (L0 / 2 + .2)))));
kbDeck.add(mesh(merge(postGeo), MAT.concreteOld));
const plaques = [];
[-1, 1].forEach(sz => [-1, 1].forEach(sx => [-1, 1].forEach(face => {
  const m = new THREE.Mesh(new THREE.PlaneGeometry(.62, 1.86), plaqueMat);
  m.position.set(sx * 3.35, Y_DECK + 1.4, sz * (L0 / 2 + .2) + face * .46); m.rotation.y = face > 0 ? 0 : Math.PI; kbDeck.add(m); plaques.push(m);
})));
kbTop.add(kbDeck); reg('kbDeck', kbDeck);
const plaqueLive = plaques[0].material;
function railing(xs, y, len, step, postMat, withLed) {
  const g = [];
  for (const x of xs) {
    for (let z = -len / 2; z <= len / 2; z += step) g.push(box(.2, 1.0, .2, x, y + .5, z));
    g.push(box(.26, .16, len, x, y + 1.02, 0), box(.12, .1, len, x, y + .55, 0));
  }
  const grp = new THREE.Group(); grp.add(mesh(merge(g), postMat, true, true));
  if (withLed) { const l = []; for (const x of xs) l.push(box(.05, .05, len, x - Math.sign(x) * .16, y + .92, 0)); const lm = new THREE.Mesh(merge(l), MAT.led); lm.userData.led = true; grp.add(lm); }
  return grp;
}
const railOld = railing([-2.85, 2.85], Y_DECK, L0, 2.1, MAT.railOld, false); kbTop.add(railOld); reg('railOld', railOld);
const railNew = railing([-2.85, 2.85], Y_DECK + .08, L0, 2.1, MAT.railNew, true); kbTop.add(railNew); reg('railNew', railNew);
const wood = new THREE.Group(); wood.add(mesh(box(5.3, .1, L0, 0, Y_DECK + .05, 0), MAT.wood)); kbTop.add(wood); reg('wood', wood);
const pedestal = new THREE.Group(); pedestal.add(mesh(merge(pierZ.map(z => box(5.8, RAISE, 1.9, 0, Y_CAP + RAISE / 2, z))), MAT.concreteNew)); scene.add(pedestal); reg('pedestal', pedestal);

// flags for the 1937 opening
const flags = new THREE.Group();
{
  const poles = [], red = [], wht = [];
  for (let z = -L0 / 2 + 8; z < L0 / 2; z += 16) for (const x of [-2.9, 2.9]) {
    poles.push(cyl(.04, .04, 3.2, x, Y_DECK, z, 6));
    (Math.round(z / 16) % 2 ? red : wht).push(box(.02, .7, 1.1, x, Y_DECK + 2.8, z + .55));
  }
  flags.add(mesh(merge(poles), MAT.rail), mesh(merge(red), new THREE.MeshStandardMaterial({ color: 0xd8332b, roughness: .8, side: THREE.DoubleSide })), mesh(merge(wht), new THREE.MeshStandardMaterial({ color: 0xf2efe6, roughness: .8, side: THREE.DoubleSide })));
}
kbTop.add(flags); reg('flags', flags);

// scaffolding for 1935
const scaffold = new THREE.Group();
{
  const g = [];
  pierZ.forEach((z, i) => {
    if (i % 2) return;
    for (const x of [-4.4, 4.4]) for (const dz of [-2.2, 2.2]) g.push(box(.18, 13, .18, x, 2.5, z + dz));
    for (let y = -1; y < 9; y += 2.2) { g.push(box(9, .14, .14, 0, y, z - 2.2), box(9, .14, .14, 0, y, z + 2.2), box(.14, .14, 4.4, -4.4, y, z), box(.14, .14, 4.4, 4.4, y, z)); }
  });
  scaffold.add(mesh(merge(g), MAT.timber));
}
scene.add(scaffold); reg('scaffold', scaffold);

// uplights (2026) : fixtures + additive light cones
const uplights = new THREE.Group();
{
  const fx = [];
  pierZ.forEach(z => { for (const x of [-3.2, 3.2]) fx.push(box(.5, .3, .5, x, .6, z + 1.5), box(.5, .3, .5, x, .6, z - 1.5)); });
  const fm = new THREE.MeshBasicMaterial({ color: 0xffd08a }); fm.toneMapped = false;
  uplights.add(new THREE.Mesh(merge(fx), fm));
  const cone = new THREE.ConeGeometry(2.6, 9, 20, 1, true); cone.rotateX(Math.PI); cone.translate(0, 5.0, 0);
  const cm = new THREE.ShaderMaterial({
    transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, side: THREE.DoubleSide,
    uniforms: { uO: { value: 0 } },
    vertexShader: 'varying float vY; void main(){ vY = position.y; gl_Position = projectionMatrix*modelViewMatrix*vec4(position,1.0); }',
    fragmentShader: 'uniform float uO; varying float vY; void main(){ float a = (1.0 - smoothstep(0.5, 9.5, vY)) * 0.10 * uO; gl_FragColor = vec4(vec3(1.0,0.78,0.45)*a, a); }'
  });
  const cones = []; pierZ.forEach(z => { for (const x of [-3.2, 3.2]) for (const dz of [-1.5, 1.5]) { const c = cone.clone(); c.translate(x, .6, z + dz); cones.push(c); } });
  const cmesh = new THREE.Mesh(merge(cones), cm); cmesh.userData.cone = true; uplights.add(cmesh);
  cone.dispose();
}
scene.add(uplights);
reg('uplights', uplights, (S, v) => { S.obj.visible = v > .003; S.obj.children[1].material.uniforms.uO.value = v; });
const pierLights = [];
for (let i = 0; i < 4; i++) { const l = new THREE.PointLight(0xffc27a, 0, 70, 1.6); l.position.set(-6, 3, -100 + i * 66); scene.add(l); pierLights.push(l); }

// ---------- 1954–1972 拓寬與延伸 ----------
const WIDE = 24.5;
function hammerGeo() {
  const s = new THREE.Shape();
  s.moveTo(-WIDE / 2, 0); s.lineTo(WIDE / 2, 0); s.lineTo(WIDE / 2, -.8); s.lineTo(3.1, -2.2); s.lineTo(-3.1, -2.2); s.lineTo(-WIDE / 2, -.8); s.lineTo(-WIDE / 2, 0);
  const g = new THREE.ExtrudeGeometry(s, { depth: 2.2, bevelEnabled: false }); g.translate(0, Y_CAP, -1.1); return g;
}
const wide = new THREE.Group();
{
  const caps = pierZ.map(z => { const g = hammerGeo(); g.translate(0, 0, z); return g; });
  const girders = [];
  for (const x of [-11.2, -8.6, -6.0, -3.6, 3.6, 6.0, 8.6, 11.2]) girders.push(box(.5, 1.5, L0, x, Y_CAP + .75, 0), box(1.1, .25, L0, x, Y_CAP + 1.38, 0));
  const slab = [box(WIDE, .45, L0 + 1, 0, Y_DECK + .02, 0), box(.35, 1.0, L0 + 1, WIDE / 2 - .17, Y_DECK - .2, 0), box(.35, 1.0, L0 + 1, -WIDE / 2 + .17, Y_DECK - .2, 0)];
  wide.add(mesh(merge([...caps, ...girders]), MAT.wideConc), mesh(merge(slab), MAT.wideConc));
  wide.add(mesh(box(WIDE - 1, .04, L0 + 1, 0, Y_DECK + .26, 0), MAT.asphalt, false, true));
  const r = railing([-WIDE / 2 + .3, WIDE / 2 - .3], Y_DECK + .25, L0, 2.4, MAT.rail, false); wide.add(r);
  const lamps = [], heads = [];
  for (let z = -L0 / 2; z <= L0 / 2; z += 30) for (const x of [-WIDE / 2 + .5, WIDE / 2 - .5]) { lamps.push(cyl(.12, .16, 9, x, Y_DECK, z, 8), box(2.2, .14, .14, x - Math.sign(x) * 1.1, Y_DECK + 9, z)); heads.push(box(.9, .22, .45, x - Math.sign(x) * 2.1, Y_DECK + 8.9, z)); }
  wide.add(mesh(merge(lamps), MAT.rail, true, false)); const hm = new THREE.Mesh(merge(heads), MAT.lampHead); wide.add(hm);
}
scene.add(wide); reg('wide', wide);

const ext = new THREE.Group();
{
  const g = [], piers = [];
  for (const sg of [-1, 1]) {
    const a = L0 / 2, b = 252, mid = sg * (a + b) / 2, len = b - a;
    for (const x of [-11.2, -8.6, -6.0, -3.6, 0, 3.6, 6.0, 8.6, 11.2]) g.push(box(.5, 1.5, len, x, Y_CAP + .75, mid));
    g.push(box(WIDE, .45, len, 0, Y_DECK + .02, mid));
    for (const z of [183, 217]) { for (const x of [-7, 0, 7]) piers.push(cyl(.85, .9, 12, x, -3, sg * z, 14)); piers.push(box(WIDE - 2, 1.4, 2.0, 0, Y_CAP - .7, sg * z)); }
    piers.push(box(WIDE, 10, 3, 0, 2.5, sg * (b + 1.5)));
  }
  ext.add(mesh(merge(g), MAT.wideConc), mesh(merge(piers), MAT.wideConc));
  ext.add(mesh(merge([box(WIDE - 1, .04, 101.5, 0, Y_DECK + .26, 201), box(WIDE - 1, .04, 101.5, 0, Y_DECK + .26, -201)]), MAT.asphalt, false, true));
  ext.add(railing([-WIDE / 2 + .3, WIDE / 2 - .3], Y_DECK + .25, 100, 2.4, MAT.rail, false).translateZ(201));
  ext.add(railing([-WIDE / 2 + .3, WIDE / 2 - .3], Y_DECK + .25, 100, 2.4, MAT.rail, false).translateZ(-201));
}
scene.add(ext); reg('ext', ext);

// toll plaza (1973) at the Yonghe end
const toll = new THREE.Group();
{
  const booths = [], canopy = [];
  for (const x of [-9, -3, 3, 9]) booths.push(box(1.6, 2.6, 3.2, x, Y_DECK + 1.55, 236));
  canopy.push(box(WIDE, .5, 9, 0, Y_DECK + 6, 236));
  for (const x of [-11.5, -6, 0, 6, 11.5]) canopy.push(box(.5, 5.6, .5, x, Y_DECK + 3, 236));
  toll.add(mesh(merge(booths), new THREE.MeshStandardMaterial({ color: 0xf0ebe0, roughness: .6 })), mesh(merge(canopy), new THREE.MeshStandardMaterial({ color: 0xb4302a, roughness: .6 })));
}
scene.add(toll); reg('toll', toll);

// shear crack
const crack = new THREE.Group();
{
  const pts = []; let p = new THREE.Vector3(3.2, Y_CAP - .1, pierZ[6] + 1.12);
  for (let k = 0; k < 9; k++) { const q = p.clone().add(new THREE.Vector3(R(.3, .7), -R(.15, .35), 0)); pts.push(rod(p, q, .05, 4)); p = q; }
  const m = new THREE.MeshBasicMaterial({ color: 0xff3b2f }); m.toneMapped = false;
  crack.add(new THREE.Mesh(merge(pts), m));
  const ring = new THREE.Mesh(new THREE.RingGeometry(1.6, 1.9, 40), new THREE.MeshBasicMaterial({ color: 0xff5b4f, transparent: true, side: THREE.DoubleSide }));
  ring.position.set(5.2, Y_CAP - 1.1, pierZ[6] + 1.2); ring.userData.pulse = true; crack.add(ring);
}
scene.add(crack); reg('crack', crack);

// ---------- 新中正橋 (2019–2024) ----------
const X0 = -32, NB_Y = 12, NB_W = 24;
const nbDeck = new THREE.Group(), nbPiers = new THREE.Group();
{
  const len = 520;
  nbDeck.add(mesh(box(NB_W - 3, 2.4, len, X0, NB_Y - 1.4, 0), MAT.concreteNew));
  nbDeck.add(mesh(merge([box(.5, 1.5, len, X0 + NB_W / 2 - .25, NB_Y - .6, 0), box(.5, 1.5, len, X0 - NB_W / 2 + .25, NB_Y - .6, 0), box(NB_W, .35, len, X0, NB_Y - .18, 0)]), MAT.mint));
  nbDeck.add(mesh(box(NB_W - 1, .05, len, X0, NB_Y + .02, 0), MAT.asphalt, false, true));
  const lines = []; for (let z = -len / 2; z < len / 2; z += 12) for (const dx of [-7.5, -3.8, 3.8, 7.5]) lines.push(box(.15, .02, 5, X0 + dx, NB_Y + .06, z));
  lines.push(box(.7, .9, len, X0, NB_Y + .45, 0));
  nbDeck.add(mesh(merge(lines), MAT.lineWhite, false, true));
  nbDeck.add(railing([X0 - NB_W / 2 + .3, X0 + NB_W / 2 - .3], NB_Y, len, 2.5, MAT.rail, false));
  const lamps = [], heads = [];
  for (let z = -len / 2 + 10; z <= len / 2; z += 32) for (const x of [X0 - NB_W / 2 + .6, X0 + NB_W / 2 - .6]) { lamps.push(cyl(.12, .16, 10, x, NB_Y, z, 8), box(1.8, .12, .12, x - Math.sign(x - X0) * .9, NB_Y + 10, z)); heads.push(box(.8, .2, .4, x - Math.sign(x - X0) * 1.7, NB_Y + 9.9, z)); }
  nbDeck.add(mesh(merge(lamps), MAT.rail, true, false)); nbDeck.add(new THREE.Mesh(merge(heads), MAT.lampHead));
  const p = [];
  for (const z of [-230, -190, -150, 150, 190, 230]) { for (const x of [-6.5, 6.5]) p.push(cyl(1.3, 1.4, 14.4, X0 + x, -4, z, 22)); p.push(box(NB_W - 4, 1.6, 3.2, X0, NB_Y - 3.4, z)); }
  for (const z of [-107.5, 107.5]) p.push(box(NB_W + 6, 14, 10, X0, 2.3, z));
  nbPiers.add(mesh(merge(p), MAT.concreteNew));
}
scene.add(nbPiers, nbDeck); reg('nbPiers', nbPiers); reg('nbDeck', nbDeck);

// three-point open-web arch (透空拱肋): one foot at the Taipei end, two feet at the Yonghe end
const ARCH_SPAN = 215, RISE = 50, XU = X0 + NB_W / 2 + .5, XD = X0 - NB_W / 2 - .5, TB = .78;
const archMain = t => new THREE.Vector3(XU - 8.5 * Math.sin(Math.PI * t), NB_Y - 2.6 + RISE * 4 * t * (1 - t), -ARCH_SPAN / 2 + ARCH_SPAN * t);
const archBranch = s => { const p = archMain(TB + (1 - TB) * s); p.x = lerp(p.x, XD, smooth(0, 1, s)); return p; };
function chordPts(fn, a, b, off, n) {
  const out = [];
  for (let k = 0; k <= n; k++) {
    const t = a + (b - a) * k / n, p = fn(t), q = fn(Math.min(1, t + .002)), r = fn(Math.max(0, t - .002));
    const tan = new THREE.Vector3().subVectors(q, r).normalize();
    const nrm = new THREE.Vector3().crossVectors(tan, new THREE.Vector3(1, 0, 0)).normalize();
    if (nrm.y < 0) nrm.negate();
    out.push(p.clone().addScaledVector(nrm, off));
  }
  return out;
}
function ribGeo(fn, a, b) {
  const n = Math.max(6, Math.round((b - a) * 90));
  const up = chordPts(fn, a, b, 1.8, n), lo = chordPts(fn, a, b, -1.8, n), parts = [];
  for (const P of [up, lo]) parts.push(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(P), n * 2, .78, 8, false));
  for (let k = 0; k <= n; k += 1) parts.push(rod(lo[k], up[k], .32, 6));
  for (let k = 0; k < n; k += 2) parts.push(rod(lo[k], up[k + 1], .2, 5));
  return merge(parts);
}
const archSideA = new THREE.Group(), archSideB = new THREE.Group(), archMid = new THREE.Group(), hangers = new THREE.Group();
archSideA.add(mesh(ribGeo(archMain, 0, .25), MAT.mint));
archSideB.add(mesh(merge([ribGeo(archMain, .75, 1), ribGeo(archBranch, 0, 1)]), MAT.mint));
archMid.add(mesh(ribGeo(archMain, .25, .75), MAT.mint));
{
  const g = []; const lo = t => chordPts(archMain, t, t, -1.8, 1)[0];
  for (let k = 0; k < 14; k++) { const z = -78 + k * 12, t = (z + ARCH_SPAN / 2) / ARCH_SPAN, a = lo(t); g.push(rod(a, new THREE.Vector3(XU - 1.2, NB_Y + .3, z), .09, 6), rod(a, new THREE.Vector3(XD + 1.2, NB_Y + .3, z), .09, 6)); }
  hangers.add(mesh(merge(g), MAT.cable, true, false));
}
scene.add(archSideA, archSideB, archMid, hangers);
reg('archSideA_', archSideA); reg('archSideB_', archSideB);
reg('archSide', new THREE.Group(), (S, v) => { fadeApply(ALL.archSideA_, v); fadeApply(ALL.archSideB_, v); });
reg('archMid', archMid, (S, v) => { fadeApply(S, v); });
reg('hangers', hangers, (S, v) => { S.obj.visible = v > .01; S.obj.scale.y = 1; fadeApply(S, v); });
let liftK = 1; // 0 = lowered by 29 m, 1 = closed

// temporary lift towers & tower cranes (2021–2023)
const works = new THREE.Group();
{
  const g = [], gy = [];
  for (const z of [-44, -16, 16, 44]) for (const x of [XU - 4, XU - 12]) {
    const t = (z + ARCH_SPAN / 2) / ARCH_SPAN, top = archMain(t).y - 29 - 2.2;
    const h = top - NB_Y; if (h < 1) continue;
    g.push(box(2.6, h, 2.6, x, NB_Y + h / 2, z));
  }
  works.add(mesh(merge(g), new THREE.MeshStandardMaterial({ color: 0x2bb3a0, roughness: .6, metalness: .2, transparent: true, opacity: .92 })));
  for (const [x, z, rot] of [[X0 + 26, -60, .6], [X0 - 30, 70, 2.4]]) {
    gy.push(box(2.2, 78, 2.2, x, 39 - 4, z));
    const jib = box(70, 1.6, 1.6, 0, 0, 0); jib.translate(18, 74, 0); jib.rotateY(rot); jib.translate(x, 0, z); gy.push(jib);
    const cj = box(4, 3, 4, x, 75, z); gy.push(cj);
  }
  works.add(mesh(merge(gy), MAT.yellow));
}
scene.add(works); reg('works', works);

// ---------- other bridges up/downstream (present day, simplified) ----------
const others = new THREE.Group();
{
  const g = [];
  for (const [lon, lat, len] of [[121.5275, 25.0110, 420], [121.5305, 25.0077, 440], [121.4958, 25.0103, 520]]) {
    const [x, z] = geo(lon, lat), f = riverFrame(x, z), ang = Math.atan2(f.n.x, f.n.y);
    const parts = [box(20, 2.4, len, 0, 10.5, 0)]; for (let s = -len / 2 + 30; s < len / 2; s += 45) parts.push(cyl(1.5, 1.5, 14, 0, -4, s, 12));
    const m = merge(parts); m.rotateY(ang); m.translate(x, 0, z); g.push(m);
  }
  others.add(mesh(merge(g), MAT.concreteNew, false, true));
}
scene.add(others); reg('others', others);

// ---------- city ----------
function buildingMaterial(color) {
  const m = new THREE.MeshStandardMaterial({ color, roughness: .8, metalness: .05 });
  m.userData.uNight = { value: 0 };
  m.onBeforeCompile = function (sh) {
    sh.uniforms.uNight = this.userData.uNight;
    sh.vertexShader = sh.vertexShader.replace('#include <common>', '#include <common>\nvarying vec3 vWP2; varying vec3 vWN2;')
      .replace('#include <worldpos_vertex>', '#include <worldpos_vertex>\n{ vec4 w=vec4(transformed,1.0);\n#ifdef USE_INSTANCING\n w=instanceMatrix*w;\n#endif\n vWP2=(modelMatrix*w).xyz; vec3 nn2 = objectNormal;\n#ifdef USE_INSTANCING\n nn2 = mat3(instanceMatrix)*nn2;\n#endif\n vWN2 = normalize(mat3(modelMatrix)*nn2); }');
    sh.fragmentShader = sh.fragmentShader.replace('#include <common>', '#include <common>\nvarying vec3 vWP2; varying vec3 vWN2; uniform float uNight;\nfloat hh(vec2 p){return fract(sin(dot(p,vec2(12.9898,78.233)))*43758.5453);}')
      .replace('#include <color_fragment>', `#include <color_fragment>
float wall = 1.0 - step(0.6, abs(vWN2.y));
vec2 cc = vec2((abs(vWN2.x) > 0.5 ? vWP2.z : vWP2.x) / 3.4, (vWP2.y - 1.0) / 3.2);
vec2 ff = fract(cc), id = floor(cc);
float win = wall * step(.16, ff.x) * step(ff.x, .84) * step(.28, ff.y) * step(ff.y, .82) * step(3.2, vWP2.y);
diffuseColor.rgb = mix(diffuseColor.rgb, vec3(.16,.19,.23), win * .65);
float litW = win * step(.55, hh(id + floor(vWP2.xz / 23.0) * 7.1));`)
      .replace('#include <emissivemap_fragment>', '#include <emissivemap_fragment>\ntotalEmissiveRadiance += litW * uNight * mix(vec3(1.0,.8,.5), vec3(.75,.88,1.0), hh(id.yx)) * 1.7;');
  };
  m.customProgramCacheKey = () => 'bld';
  return m;
}
function cityLots(kind) {
  const lots = [];
  const step = kind === 'old' ? 22 : 30, Rm = kind === 'old' ? 1800 : 2900;
  for (let x = -Rm; x <= Rm; x += step) for (let z = -Rm; z <= Rm; z += step) {
    const jx = x + R(-4, 4), jz = z + R(-4, 4), r = Math.hypot(jx, jz);
    if (r > Rm) continue;
    const d = riverDist(jx, jz);
    if (kind === 'old') {
      if (d < W + 30) continue;
      const north = riverFrameSide(jx, jz) < 0;
      const dens = north ? (0.55 * smooth(1800, 400, r) + 0.08) : 0.05;
      if (rnd() > dens) continue;
      lots.push({ x: jx, z: jz, w: R(7, 13), d: R(7, 12), h: R(3.4, 5.2), ry: R(-.05, .05) });
    } else {
      if (d < W + 104) continue;
      if (Math.abs(jx) < 16 && Math.abs(jz) < 700) continue;
      const dens = kind === 'mid' ? .8 : .9;
      if (rnd() > dens * smooth(3200, 1200, r) + .05) continue;
      const w = R(12, 24), dd = R(12, 24);
      let h = kind === 'mid' ? R(9, 19) : (rnd() < .07 ? R(70, 140) : R(14, 58));
      if (kind === 'new' && d < W + 160) h = Math.min(h, 45);
      lots.push({ x: jx, z: jz, w, d: dd, h, ry: 0 });
    }
  }
  return lots;
}
function riverFrameSide(x, z) { // <0 = north (Taipei) side of the channel, >0 = south (Yonghe)
  let bi = 0, bd = 1e12;
  for (let i = 0; i < RIV.length - 1; i++) { const d = (RIV[i][0] - x) ** 2 + (RIV[i][1] - z) ** 2; if (d < bd) { bd = d; bi = i; } }
  const a = RIV[bi], b = RIV[bi + 1];
  return (b[0] - a[0]) * (z - a[1]) - (b[1] - a[1]) * (x - a[0]) < 0 ? -1 : 1;
}
const cityGroups = {};
function buildCity(kind) {
  const lots = cityLots(kind);
  const grp = new THREE.Group();
  const bg = new THREE.BoxGeometry(1, 1, 1); bg.translate(0, .5, 0);
  const pal = kind === 'old' ? [0xcfc3ad, 0xb8a58a, 0x9c8a74, 0xd8d0c0] : kind === 'mid' ? [0xc9c6bd, 0xb7b3a8, 0xd9d3c3, 0xa9aba6, 0xc4b8a2] : [0xc8ccd0, 0xaab2ba, 0xd6d3cc, 0x9aa3ab, 0xbfb9ad, 0x8e98a2, 0xe0ddd5];
  const im = new THREE.InstancedMesh(bg, buildingMaterial(0xffffff), lots.length);
  const M = new THREE.Matrix4(), q = new THREE.Quaternion(), c = new THREE.Color();
  lots.forEach((l, i) => {
    const y = kind === 'old' ? hOld(W + 300, l.x, l.z) - .5 : 7.0;
    M.compose(new THREE.Vector3(l.x, y, l.z), q.setFromEuler(new THREE.Euler(0, l.ry, 0)), new THREE.Vector3(l.w, l.h, l.d));
    im.setMatrixAt(i, M); im.setColorAt(i, c.set(pal[i % pal.length]).multiplyScalar(.85 + rnd() * .25));
  });
  im.castShadow = false; im.receiveShadow = true; grp.add(im);
  if (kind === 'old') { // hip roofs (黑瓦)
    const rg = new THREE.ConeGeometry(.75, 1, 4, 1); rg.rotateY(Math.PI / 4); rg.translate(0, .5, 0);
    const rm = new THREE.InstancedMesh(rg, new THREE.MeshStandardMaterial({ color: 0x3b3a3c, roughness: .85 }), lots.length);
    lots.forEach((l, i) => { M.compose(new THREE.Vector3(l.x, hOld(W + 300, l.x, l.z) - .5 + l.h, l.z), q.setFromEuler(new THREE.Euler(0, l.ry, 0)), new THREE.Vector3(l.w * 1.05, l.h * .55, l.d * 1.05)); rm.setMatrixAt(i, M); });
    grp.add(rm);
  }
  scene.add(grp);
  cityGroups[kind] = grp;
  reg('city_' + kind, grp, (S, v) => { S.obj.visible = v > .003; S.obj.scale.y = Math.max(.001, smooth(0, 1, v)); S.obj.position.y = kind === 'old' ? 0 : 0; });
}
buildCity('old'); buildCity('mid'); buildCity('new');

// Taipei 101 (4.9 km ENE)
const t101 = new THREE.Group();
{
  const [x, z] = geo(121.5645, 25.0340), g = [];
  g.push(box(64, 40, 64, 0, 20, 0));
  g.push(cyl(24, 30, 190, 0, 40, 0, 4));
  for (let k = 0; k < 8; k++) g.push(cyl(27, 21, 32, 0, 230 + k * 32, 0, 4));
  g.push(cyl(14, 18, 30, 0, 486, 0, 4), cyl(2.5, 1, 60, 0, 516, 0, 6));
  const m = merge(g); m.rotateY(Math.PI / 4);
  const mat = buildingMaterial(0x6f8f88); mat.metalness = .5; mat.roughness = .35;
  const tm = new THREE.Mesh(m, mat); tm.position.set(x, 7, z); t101.add(tm);
}
scene.add(t101); reg('t101', t101);

// trees: floodplain parks (modern) and bamboo / field trees (1930s)
function trees(kind) {
  const pos = [];
  for (let i = 0; i < (kind === 'old' ? 2600 : 1600); i++) {
    const x = R(-1500, 1500), z = R(-1500, 1500), d = riverDist(x, z);
    if (Math.abs(x) < 45 && Math.abs(z) < 420) continue;
    if (kind === 'old') { if (d < W + 18 || rnd() > .7) continue; pos.push([x, hOld(d, x, z), z, R(1.8, 3.6)]); }
    else { if (d < W + 8 || d > W + 60) continue; pos.push([x, hNew(d, x, z), z, R(2, 3.8)]); }
  }
  const g = new THREE.IcosahedronGeometry(1, 1); g.translate(0, 1.1, 0);
  const im = new THREE.InstancedMesh(g, new THREE.MeshStandardMaterial({ color: 0xffffff, roughness: .95 }), pos.length);
  const M = new THREE.Matrix4(), c = new THREE.Color();
  pos.forEach(([x, y, z, s], i) => { M.compose(new THREE.Vector3(x, y - .3, z), new THREE.Quaternion(), new THREE.Vector3(s * R(.8, 1.2), s * R(1.1, 1.8), s * R(.8, 1.2))); im.setMatrixAt(i, M); im.setColorAt(i, c.setHSL(R(.22, .3), R(.3, .45), R(.09, .16))); });
  im.receiveShadow = true;
  const grp = new THREE.Group(); grp.add(im); scene.add(grp); return grp;
}
reg('trees_old', trees('old')); reg('trees_new', trees('new'));

// ---------- 1930s: 網溪別墅、菊花、紀州庵、渡船、屋形船、螢火 ----------
const [VX, VZ] = geo(121.51691, 25.01605);
const villa = new THREE.Group();
{
  const y0 = hOld(W + 300, VX, VZ) - .3;
  const wall = new THREE.MeshStandardMaterial({ color: 0xe6dcc6, roughness: .85 }), roof = new THREE.MeshStandardMaterial({ color: 0x5b3f33, roughness: .8 });
  villa.add(mesh(merge([box(18, 7.2, 10, 0, y0 + 3.6, 0), box(12, 3.4, 8, 0, y0 + 8.9, 0)]), wall));
  const rf = new THREE.ConeGeometry(9.5, 4.2, 4); rf.rotateY(Math.PI / 4); rf.scale(1.05, 1, .62); rf.translate(0, y0 + 12.7, 0);
  villa.add(mesh(rf, roof));
  const cols = []; for (let x = -8; x <= 8; x += 2.7) cols.push(box(.4, 3.2, .4, x, y0 + 1.6, -5.4));
  cols.push(box(18.6, .35, 1.6, 0, y0 + 3.4, -5.4));
  villa.add(mesh(merge(cols), wall));
  villa.position.set(VX, 0, VZ);
  const fl = [], sg = new THREE.SphereGeometry(.28, 6, 4);
  const fm = new THREE.InstancedMesh(sg, new THREE.MeshStandardMaterial({ color: 0xffffff, roughness: .7 }), 2200);
  const M = new THREE.Matrix4(), c = new THREE.Color();
  for (let i = 0; i < 2200; i++) { const x = R(-60, 60), z = R(-70, -12); M.makeTranslation(x, y0 + .35 + R(0, .3), z); fm.setMatrixAt(i, M); fm.setColorAt(i, rnd() < .72 ? c.set(0xf2c230) : c.set(0xf7f2e4)); void fl; }
  villa.add(fm);
}
scene.add(villa); reg('villa', villa);

const [KSX, KSZ] = geo(121.52062, 25.02153);
const ryotei = new THREE.Group();
{
  const y0 = hOld(W + 300, KSX, KSZ) - .4;
  const wall = new THREE.MeshStandardMaterial({ color: 0x7a5e48, roughness: .9 }), roof = new THREE.MeshStandardMaterial({ color: 0x2f2e31, roughness: .8 });
  const lit = new THREE.MeshBasicMaterial({ color: 0xffcf85 }); lit.toneMapped = false;
  [[0, 0, 26, 12], [-30, 18, 18, 10], [24, 22, 16, 10]].forEach(([dx, dz, w, d]) => {
    ryotei.add(mesh(box(w, 4.6, d, KSX + dx, y0 + 2.3, KSZ + dz), wall));
    const r = new THREE.ConeGeometry(.75, 1, 4); r.rotateY(Math.PI / 4); r.scale(w * 1.12, 3.2, d * 1.2); r.translate(KSX + dx, y0 + 6.2, KSZ + dz); ryotei.add(mesh(r, roof));
    ryotei.add(new THREE.Mesh(box(w * .8, 1.1, .1, KSX + dx, y0 + 2.4, KSZ + dz + d / 2 + .06), lit));
  });
}
scene.add(ryotei); reg('ryotei', ryotei);

function sampan(scale = 1, lantern = true) {
  const g = new THREE.Group(), wood2 = new THREE.MeshStandardMaterial({ color: 0x3f3025, roughness: .9 });
  const hull = new THREE.Shape(); hull.moveTo(-5.5, 0); hull.quadraticCurveTo(0, -1.4, 5.5, 0); hull.lineTo(5, .7); hull.lineTo(-5, .7); hull.lineTo(-5.5, 0);
  const hg = new THREE.ExtrudeGeometry(hull, { depth: 1.9, bevelEnabled: false }); hg.translate(0, 0, -.95); hg.rotateY(Math.PI / 2);
  g.add(mesh(hg, wood2));
  g.add(mesh(merge([box(1.5, .9, 2.4, 0, 1.1, -.6)]), new THREE.MeshStandardMaterial({ color: 0x4f3e2e, roughness: .9 })));
  const ppl = []; for (const [x, z] of [[.3, 1.4], [-.4, 1.9], [.1, 2.6]]) ppl.push(cyl(.22, .26, 1.0, x, .7, z, 8), new THREE.SphereGeometry(.2, 8, 6).translate(x, 1.9, z));
  ppl.push(cyl(.2, .24, 1.2, 0, .7, -3.6, 8), new THREE.SphereGeometry(.2, 8, 6).translate(0, 2.1, -3.6), rod(new THREE.Vector3(0, 2.0, -3.6), new THREE.Vector3(.5, -2.5, -5.8), .04, 4));
  g.add(mesh(merge(ppl), new THREE.MeshStandardMaterial({ color: 0x2a2622, roughness: .9 })));
  if (lantern) { const lm = new THREE.MeshBasicMaterial({ color: 0xffc46a }); lm.toneMapped = false; g.add(new THREE.Mesh(new THREE.SphereGeometry(.28, 10, 8).translate(0, 2.3, 4.2), lm)); }
  g.scale.setScalar(scale); return g;
}
const ferry = new THREE.Group(), ferryBoats = [];
{
  const f = riverFrame(-150, -70);
  for (let i = 0; i < 3; i++) { const b = sampan(1); ferry.add(b); ferryBoats.push({ b, ph: i * 2.1, off: -40 + i * 38, f }); }
}
scene.add(ferry); reg('ferry', ferry);

const yakata = new THREE.Group(), yakataBoats = [];
{
  const f = riverFrame(260, 120);
  for (let i = 0; i < 2; i++) {
    const g = new THREE.Group(), hullM = new THREE.MeshStandardMaterial({ color: 0x3b2b22, roughness: .9 });
    g.add(mesh(box(4.4, 1.0, 17, 0, .3, 0), hullM));
    g.add(mesh(box(3.9, 2.2, 12, 0, 1.9, 0), new THREE.MeshStandardMaterial({ color: 0x6b4d3a, roughness: .9 })));
    const rf = new THREE.ConeGeometry(.75, 1, 4); rf.rotateY(Math.PI / 4); rf.scale(5.6, 1.2, 16); rf.translate(0, 3.6, 0); g.add(mesh(rf, new THREE.MeshStandardMaterial({ color: 0x2b2729, roughness: .8 })));
    const lm = new THREE.MeshBasicMaterial({ color: 0xffd08a }); lm.toneMapped = false;
    g.add(new THREE.Mesh(merge([box(.06, 1.0, 10.5, 1.97, 1.9, 0), box(.06, 1.0, 10.5, -1.97, 1.9, 0)]), lm));
    const rl = new THREE.MeshBasicMaterial({ color: 0xff5a3a }); rl.toneMapped = false;
    const l = []; for (let z = -5; z <= 5; z += 2.5) for (const x of [-2.2, 2.2]) l.push(new THREE.SphereGeometry(.28, 8, 6).translate(x, 3.0, z));
    g.add(new THREE.Mesh(merge(l), rl));
    yakata.add(g); yakataBoats.push({ g, f, s: -60 + i * 90 });
  }
}
scene.add(yakata); reg('yakata', yakata);

const fireflies = (() => {
  const n = 260, p = new Float32Array(n * 3), base = [];
  const f = riverFrame(200, 100);
  for (let i = 0; i < n; i++) { const s = R(-200, 250), o = -(W + R(-5, 40)); const x = f.p.x + f.t.x * s + f.n.x * o, z = f.p.y + f.t.y * s + f.n.y * o; base.push([x, R(4.5, 9), z, R(0, 6.28)]); }
  const g = new THREE.BufferGeometry(); g.setAttribute('position', new THREE.BufferAttribute(p, 3));
  const m = new THREE.PointsMaterial({ color: 0xd9ff8a, size: 5, sizeAttenuation: false, transparent: true, opacity: 0, depthWrite: false, blending: THREE.AdditiveBlending, map: glowTex('rgba(240,255,200,1)', 'rgba(200,255,120,.5)') });
  m.toneMapped = false;
  const pts = new THREE.Points(g, m); pts.userData.base = base; scene.add(pts); return pts;
})();

// ---------- traffic ----------
function carGeo() { return merge([box(1.8, .75, 4.4, 0, .6, 0), box(1.62, .62, 2.3, 0, 1.28, -.2)]); }
function busGeo() { return merge([box(2.5, 2.9, 11, 0, 1.8, 0)]); }
function scooterGeo() { return merge([box(.6, .7, 1.8, 0, .55, 0), cyl(.24, .26, .75, 0, .95, -.2, 6), new THREE.SphereGeometry(.2, 8, 6).translate(0, 1.95, -.2)]); }
function car37Geo() { return merge([box(1.65, .8, 3.9, 0, .75, 0), box(1.5, .9, 1.9, 0, 1.55, -.3), box(1.9, .1, 3.2, 0, .45, 0)]); }
function personGeo() { return merge([new THREE.CapsuleGeometry(.22, .95, 3, 8).translate(0, .8, 0), new THREE.SphereGeometry(.17, 8, 6).translate(0, 1.62, 0)]); }
function bikeGeo() { return merge([box(.12, .9, 1.7, 0, .45, 0), new THREE.CapsuleGeometry(.2, .7, 3, 8).translate(0, 1.35, -.1), new THREE.SphereGeometry(.16, 8, 6).translate(0, 1.95, -.1)]); }
class Traffic {
  constructor(parent, geo, colors, lanes, n, speed, headlights = false) {
    this.im = new THREE.InstancedMesh(geo, new THREE.MeshStandardMaterial({ color: 0xffffff, roughness: .45, metalness: .3 }), n);
    this.im.castShadow = true; this.im.frustumCulled = false;
    this.items = []; const c = new THREE.Color();
    for (let i = 0; i < n; i++) { const ln = lanes[i % lanes.length]; this.items.push({ ln, s: R(ln.z0, ln.z1), v: speed * R(.75, 1.2) }); this.im.setColorAt(i, c.set(colors[i % colors.length])); }
    parent.add(this.im);
    if (headlights) {
      const hg = merge([box(.3, .18, .05, -.6, .7, 2.22), box(.3, .18, .05, .6, .7, 2.22)]), tg = merge([box(.3, .18, .05, -.6, .75, -2.22), box(.3, .18, .05, .6, .75, -2.22)]);
      const hm = new THREE.MeshBasicMaterial({ color: 0xfff1cf }), tm = new THREE.MeshBasicMaterial({ color: 0xff2a1a }); hm.toneMapped = tm.toneMapped = false;
      this.hl = new THREE.InstancedMesh(hg, hm, n); this.tl = new THREE.InstancedMesh(tg, tm, n); this.hl.frustumCulled = this.tl.frustumCulled = false;
      parent.add(this.hl, this.tl);
    }
    this.M = new THREE.Matrix4(); this.q0 = new THREE.Quaternion(); this.q1 = new THREE.Quaternion().setFromEuler(new THREE.Euler(0, Math.PI, 0)); this.sc = new THREE.Vector3(1, 1, 1); this.p = new THREE.Vector3();
    this.update(0);
  }
  update(dt, night = 0) {
    this.items.forEach((it, i) => {
      const L = it.ln; it.s += it.v * dt * L.dir;
      if (it.s > L.z1) it.s = L.z0; if (it.s < L.z0) it.s = L.z1;
      this.p.set(L.x, L.y, it.s); this.M.compose(this.p, L.dir > 0 ? this.q0 : this.q1, this.sc);
      this.im.setMatrixAt(i, this.M); if (this.hl) { this.hl.setMatrixAt(i, this.M); this.tl.setMatrixAt(i, this.M); }
    });
    this.im.instanceMatrix.needsUpdate = true;
    if (this.hl) { this.hl.instanceMatrix.needsUpdate = this.tl.instanceMatrix.needsUpdate = true; this.hl.visible = this.tl.visible = night > .3; }
  }
}
const TR = {};
const carCols = [0xe9e9e9, 0x1c1c1f, 0xb5b8bb, 0x8a1d1d, 0x21477a, 0xd9c541, 0x4d5a4f];
{
  const g37 = new THREE.Group(); kbTop.add(g37);
  TR.t37 = [
    new Traffic(g37, car37Geo(), [0x222222, 0x2e3a2c, 0x3b2a24], [{ x: 1.3, y: Y_DECK, dir: 1, z0: -150, z1: 150 }, { x: -1.3, y: Y_DECK, dir: -1, z0: -150, z1: 150 }], 5, 6),
    new Traffic(g37, bikeGeo(), [0x2a2622, 0x3a3027], [{ x: 2.2, y: Y_DECK, dir: 1, z0: -150, z1: 150 }, { x: -2.2, y: Y_DECK, dir: -1, z0: -150, z1: 150 }], 14, 2.8),
    new Traffic(g37, personGeo(), [0x4a4138, 0x2b2c33, 0xd8d2c4], [{ x: 2.45, y: Y_DECK, dir: 1, z0: -150, z1: 150 }, { x: -2.45, y: Y_DECK, dir: -1, z0: -150, z1: 150 }], 22, 1.2)
  ];
  reg('traffic37', g37);
  const g70 = new THREE.Group(); scene.add(g70);
  const lanes70 = []; for (const [x, dir] of [[-10.2, -1], [-6.8, -1], [-3.4, -1], [3.4, 1], [6.8, 1], [10.2, 1]]) lanes70.push({ x, y: Y_DECK + .27, dir, z0: -250, z1: 252 });
  TR.t70 = [
    new Traffic(g70, carGeo(), carCols, lanes70.slice(1, 5), 60, 11, true),
    new Traffic(g70, busGeo(), [0x2f5f9a, 0xd8d2c4, 0x3f8a4a], [lanes70[2], lanes70[3]], 6, 9, true),
    new Traffic(g70, scooterGeo(), [0xc0392b, 0x2471a3, 0xf1c40f, 0xecf0f1, 0x27ae60], [lanes70[0], lanes70[5], { ...lanes70[0], x: -11.4 }, { ...lanes70[5], x: 11.4 }], 220, 10)
  ];
  reg('traffic70', g70);
  const gN = new THREE.Group(); scene.add(gN);
  const lanesN = []; for (const [dx, dir] of [[-9.6, -1], [-5.7, -1], [-1.9, -1], [1.9, 1], [5.7, 1], [9.6, 1]]) lanesN.push({ x: X0 + dx, y: NB_Y + .05, dir, z0: -260, z1: 260 });
  TR.tn = [
    new Traffic(gN, carGeo(), carCols, lanesN.slice(1, 5), 56, 13, true),
    new Traffic(gN, busGeo(), [0x2f5f9a, 0xe6e2d6], [lanesN[2], lanesN[3]], 4, 11, true),
    new Traffic(gN, scooterGeo(), [0xc0392b, 0x2471a3, 0xf1c40f, 0xecf0f1, 0x27ae60, 0x222222], [lanesN[0], lanesN[5]], 90, 11)
  ];
  reg('trafficNew', gN);
  const gP = new THREE.Group(); kbTop.add(gP);
  TR.people = [
    new Traffic(gP, personGeo(), [0x2b2c33, 0x6b2f2f, 0xd8d2c4, 0x2f4f6b, 0x4a4138], [{ x: -1.6, y: Y_DECK + .1, dir: 1, z0: -150, z1: 150 }, { x: -.4, y: Y_DECK + .1, dir: -1, z0: -150, z1: 150 }, { x: 1.0, y: Y_DECK + .1, dir: 1, z0: -150, z1: 150 }], 70, 1.15),
    new Traffic(gP, bikeGeo(), [0x2a2622, 0x6b2f2f, 0x2f4f6b], [{ x: 1.9, y: Y_DECK + .1, dir: -1, z0: -150, z1: 150 }], 8, 3.6)
  ];
  reg('people', gP);
}

// ---------- labels ----------
const labelsEl = document.getElementById('labels');
const LABELS = [
  { t: '臺北', s: '川端町・古亭', p: [30, 26, -300], sc: ['ferry', 'kawabata', 'piers', 'girders', 'open', 'rename'] },
  { t: '溪洲', s: '中和庄（今永和）', p: [30, 22, 330], sc: ['ferry', 'kawabata', 'piers', 'girders', 'open', 'rename'] },
  { t: '臺北市 中正區', s: '', p: [40, 40, -380], sc: ['widen', 'toll', 'danger', 'heritage', 'newbuild', 'newopen', 'restore', 'reopen'] },
  { t: '新北市 永和區', s: '', p: [40, 40, 400], sc: ['widen', 'toll', 'danger', 'heritage', 'newbuild', 'newopen', 'restore', 'reopen'] },
  { t: '網溪渡', s: '渡船頭（約略位置）', p: [-150, 8, 20], sc: ['ferry', 'petition'] },
  { t: '新店溪', s: '往下游・淡水河 →', p: [-480, 6, -40], sc: ['ferry', 'kawabata', 'open', 'widen', 'newopen'] },
  { t: '紀州庵', s: '1917 川端町支店', p: [KSX, 16, KSZ], sc: ['kawabata'] },
  { t: '網溪別墅', s: '1919 楊仲佐宅', p: [VX, 22, VZ], sc: ['petition'] },
  { t: '觀音山', s: '', p: [-9140, 700, -11910], sc: ['ferry', 'kawabata', 'rename', 'danger', 'restore'] },
  { t: '臺北101', s: '', p: [...(() => { const [x, z] = geo(121.5645, 25.0340); return [x, 540, z]; })()], sc: ['heritage', 'newopen', 'reopen', 'newbuild'] },
  { t: '川端橋', s: '1937 原橋', p: [0, 16, -60], sc: ['open', 'girders', 'rename', 'restore', 'reopen', 'heritage'] },
  { t: '新中正橋', s: '三點式鋼拱', p: [X0, 66, 0], sc: ['newopen', 'restore', 'newbuild'] },
  { t: '剪力裂縫', s: '230 cm', p: [6, 4, pierZ[6]], sc: ['danger'], warn: true },
  { t: '收費站', s: '1973', p: [0, 20, 236], sc: ['toll'] },
  { t: '中段拱肋', s: '1,800噸・頂升約29 m', p: [X0 + 6, 36, 0], sc: ['newbuild'] },
];
LABELS.forEach(L => { const e = document.createElement('div'); e.className = 'lbl' + (L.warn ? ' warn' : ''); e.innerHTML = `<b>${L.t}</b>${L.s ? `<span>${L.s}</span>` : ''}`; labelsEl.appendChild(e); L.el = e; L.v = new THREE.Vector3(...L.p); });

// ---------- scenes ----------
const T = {
  day: { el: 42, az: -35, turb: 4, ray: 1.2, mie: .004, mg: .8, exp: .36, bloom: .1, bth: .92, sunI: 2.6, hemi: .55, night: 0, fog: 0xb9cad6, fogD: .000065, water: 0x2a4a40, env: .65 },
  dusk: { el: 1.6, az: -101, turb: 9, ray: 2.6, mie: .012, mg: .96, exp: .4, bloom: .32, bth: .8, sunI: 1.5, hemi: .3, night: .35, fog: 0xc59a82, fogD: .00012, water: 0x26343a, env: .7 },
  night: { el: -9, az: -101, turb: 1.5, ray: .35, mie: .004, mg: .8, exp: .42, bloom: .55, bth: .6, sunI: .0, hemi: .1, night: 1, fog: 0x0c1322, fogD: .00015, water: 0x0b151d, env: .2 }
};
const KB = ['kbAbut', 'kbPiers', 'kbGirders', 'kbDeck'];
const NB = ['nbPiers', 'nbDeck', 'archSide', 'archMid', 'hangers'];
const SC = {
  reopen: { t: 'night', era: 1, city: 'new', on: [...KB, 'pedestal', 'railNew', 'wood', ...NB, 'trafficNew', 'uplights', 'people', 't101', 'trees_new', 'others'], raise: 1, plaque: 'kawabata', cam: [[150, 30, 170], [-16, 18, -10]], camM: [[170, 34, 190], [-16, 18, -10]] },
  ferry: { t: 'night', era: 0, city: 'old', on: ['ferry', 'trees_old'], cam: [[-40, 7, 95], [-190, 3, -40]] },
  kawabata: { t: 'dusk', era: 0, city: 'old', on: ['yakata', 'ryotei', 'trees_old', 'fireflies'], cam: [[330, 14, 160], [180, 5, -170]] },
  petition: { t: 'day', era: 0, city: 'old', on: ['villa', 'ferry', 'trees_old'], cam: [[VX + 130, 38, VZ + 90], [VX - 20, 4, VZ - 60]] },
  piers: { t: 'day', era: 0, city: 'old', on: ['kbAbut', 'kbPiers', 'scaffold', 'trees_old'], cam: [[70, 12, 95], [-10, 2, -30]] },
  girders: { t: 'day', era: 0, city: 'old', on: ['kbAbut', 'kbPiers', 'kbGirders', 'scaffold', 'trees_old'], cam: [[26, 22, 70], [0, 7, -20]] },
  open: { t: 'day', era: 0, city: 'old', on: [...KB, 'railOld', 'flags', 'traffic37', 'trees_old'], plaque: 'kawabata', cam: [[150, 16, 95], [-10, 6, -40]] },
  rename: { t: 'dusk', era: 0, city: 'old', on: [...KB, 'railOld', 'traffic37', 'trees_old'], plaque: 'zhongzheng', cam: [[1.2, 11.3, -129], [0, 10.9, -152]], camM: [[1.2, 11.3, -129], [0, 10.9, -152]] },
  widen: { t: 'day', era: 1, city: 'mid', on: [...KB, 'wide', 'ext', 'traffic70', 'trees_new'], plaque: 'zhongzheng', cam: [[170, 42, 170], [0, 6, 20]] },
  toll: { t: 'day', era: 1, city: 'mid', on: [...KB, 'wide', 'ext', 'traffic70', 'toll', 'trees_new'], cam: [[-7, 15.5, 176], [2, 10.5, 246]] },
  danger: { t: 'dusk', era: 1, city: 'mid', on: [...KB, 'wide', 'ext', 'crack', 'trees_new'], cam: [[34, 3, pierZ[6] + 26], [3, 5.2, pierZ[6]]] },
  heritage: { t: 'night', era: 1, city: 'new', on: [...KB, 'railOld', 'wide', 'ext', 'trees_new', 't101', 'others'], ghost: .1, glow: 1, cam: [[64, 6, 64], [0, 6, -10]] },
  newbuild: { t: 'day', era: 1, city: 'new', on: [...KB, 'wide', 'ext', 'traffic70', 'nbPiers', 'nbDeck', 'archSide', 'archMid', 'works', 'trees_new', 't101', 'others'], lift: 1, cam: [[190, 70, 230], [X0, 26, 0]] },
  newopen: { t: 'day', era: 1, city: 'new', on: [...KB, 'wide', 'ext', ...NB, 'trafficNew', 'trees_new', 't101', 'others'], cam: [[-235, 26, -30], [X0, 26, 10]] },
  restore: { t: 'dusk', era: 1, city: 'new', on: [...KB, 'pedestal', 'railNew', 'wood', ...NB, 'trafficNew', 'trees_new', 't101', 'others'], raise: 1, plaque: 'kawabata', cam: [[120, 18, 150], [-14, 12, 0]] },
};
SC.finale = { ...SC.reopen, cam: [[9, 16.5, 150], [-8, 13, 40]], camM: [[9, 17, 160], [-8, 14, 40]] };
let cur = null, tState = { ...T.night };
const camGoal = { p: new THREE.Vector3(150, 30, 170), t: new THREE.Vector3(-16, 18, -10) };
const camNow = { p: camGoal.p.clone(), t: camGoal.t.clone() };
let eraGoal = 1, eraNow = 1, raiseGoal = 0, raiseNow = 0, ghostGoal = 0, glowGoal = 0, glowNow = 0, liftStart = 0;
function setScene(name, snap = false) {
  const S = SC[name]; if (!S || (name === cur && !snap)) return; const prev = snap ? null : cur; cur = name;
  for (const k in ALL) if (!k.endsWith('_')) ALL[k].target = 0;
  S.on.forEach(k => { if (ALL[k]) ALL[k].target = 1; });
  ALL['city_' + S.city].target = 1;
  eraGoal = S.era; raiseGoal = S.raise || 0; ghostGoal = S.ghost ? 1 : 0; glowGoal = S.glow || 0;
  ['wide', 'ext'].forEach(k => { ALL[k].ghost = S.ghost ?? 1; });
  tGoal = T[S.t];
  const [p, t] = mobile() && S.camM ? S.camM : S.cam;
  camGoal.p.set(...p); camGoal.t.set(...t);
  if (S.lift) { liftK = 0; liftStart = performance.now() + 1400; } else liftK = 1;
  if (S.plaque) setTimeout(() => { plaqueLive.map = PLQ[S.plaque]; plaqueLive.needsUpdate = true; }, name === 'rename' ? 1600 : 0);
  if (reduce || prev === null) { camNow.p.copy(camGoal.p); camNow.t.copy(camGoal.t); for (const k in ALL) ALL[k].v = ALL[k].target; eraNow = eraGoal; raiseNow = raiseGoal; tState = { ...tGoal }; glowNow = glowGoal; for (const k of ['wide', 'ext']) ALL[k].ghostV = ghostGoal; if (S.lift && snap) liftK = 1; envRT && updateEnv(); }
  LABELS.forEach(L => L.on = L.sc.includes(name === 'finale' ? 'reopen' : name));
}
let tGoal = T.night;
window.addEventListener('kb-scene', e => setScene(e.detail));

// ---------- post-processing ----------
const composer = new EffectComposer(renderer);
composer.addPass(new RenderPass(scene, camera));
const bloom = new UnrealBloomPass(new THREE.Vector2(512, 512), .3, .55, .85);
composer.addPass(bloom);
composer.addPass(new OutputPass());

// environment map from the sky
const pmrem = new THREE.PMREMGenerator(renderer);
const skyScene = new THREE.Scene(); const skyForEnv = new Sky(); skyForEnv.scale.setScalar(1000); skyScene.add(skyForEnv);
let envRT = null, envTimer = 0;
function updateEnv() {
  for (const k of ['turbidity', 'rayleigh', 'mieCoefficient', 'mieDirectionalG']) skyForEnv.material.uniforms[k].value = SU[k].value;
  // a sun below the horizon makes the sky shader return invalid values that blacken the whole PMREM; keep it just above
  const sp = SU.sunPosition.value.clone().normalize(); const minY = Math.sin(THREE.MathUtils.degToRad(2));
  if (sp.y < minY) { const h = Math.hypot(sp.x, sp.z) || 1; sp.set(sp.x / h * Math.cos(Math.asin(minY)), minY, sp.z / h * Math.cos(Math.asin(minY))); }
  skyForEnv.material.uniforms.sunPosition.value.copy(sp);
  if (envRT) envRT.dispose();
  envRT = pmrem.fromScene(skyScene, 0, 1, 2000);
  scene.environment = envRT.texture;
}

// ---------- resize & framing ----------
function resize() {
  const w = stage.clientWidth, h = stage.clientHeight;
  renderer.setSize(w, h, false); composer.setSize(w, h);
  camera.aspect = w / h;
  if (document.body.classList.contains('exploring')) { camera.clearViewOffset(); camera.fov = 45; }
  else if (w > 760) { const cardR = Math.min(w * .42, 58 + 430); const shift = cardR * .5; camera.setViewOffset(w, h, -shift, 0, w, h); camera.fov = 40; }
  else { camera.setViewOffset(w, h, 0, h * .2, w, h); camera.fov = 62; }
  camera.updateProjectionMatrix();
}
addEventListener('resize', resize); resize();

// ---------- explore mode ----------
const controls = new OrbitControls(camera, canvas);
canvas.style.touchAction = 'pan-y'; // OrbitControls sets 'none', which would block page scrolling on phones
controls.enabled = false; controls.enableDamping = true; controls.maxPolarAngle = Math.PI * .495; controls.minDistance = 8; controls.maxDistance = 3000;
const exploreBtn = document.getElementById('exploreBtn');
function setExplore(on) {
  document.body.classList.toggle('exploring', on);
  if (exploreBtn) { exploreBtn.textContent = on ? '結束自由探索' : '自由探索 3D'; exploreBtn.setAttribute('aria-pressed', String(on)); }
  controls.enabled = on; canvas.style.touchAction = on ? 'none' : 'pan-y';
  if (on) { controls.target.copy(camNow.t); camera.clearViewOffset(); camera.updateProjectionMatrix(); }
  requestAnimationFrame(resize);
}

// ---------- loop ----------
let last = performance.now(), running = true, visible = true;
new IntersectionObserver(es => { visible = es[0].isIntersecting; }, { threshold: 0 }).observe(document.getElementById('story'));
const sunV = new THREE.Vector3(), tmpV = new THREE.Vector3();
function lerpT(a, b, k) { for (const key in b) { if (typeof b[key] === 'number' && key !== 'fog' && key !== 'water') a[key] = lerp(a[key], b[key], k); } a._fog = (a._fog || new THREE.Color(b.fog)).lerp(new THREE.Color(b.fog), k); a._water = (a._water || new THREE.Color(b.water)).lerp(new THREE.Color(b.water), k); }
let slowFrames = 0, degraded = false;
function frame(now) {
  requestAnimationFrame(frame);
  const rawDt = (now - last) / 1000;
  const dt = Math.min(.05, rawDt); last = now;
  if (!degraded && visible) { slowFrames = rawDt > .045 ? slowFrames + 1 : Math.max(0, slowFrames - 1); if (slowFrames > 90) { degraded = true; renderer.setPixelRatio(1); renderer.shadowMap.enabled = false; resize(); } }
  const exploring = document.body.classList.contains('exploring');
  if ((!visible || document.body.classList.contains('plate-mode')) && !exploring) return;
  const k = reduce ? 1 : 1 - Math.exp(-dt * 1.7), kf = reduce ? 1 : 1 - Math.exp(-dt * 2.6);
  // time of day
  const prevEl = tState.el; lerpT(tState, tGoal, k);
  const phi = THREE.MathUtils.degToRad(90 - tState.el), th = THREE.MathUtils.degToRad(tState.az);
  sunV.setFromSphericalCoords(1, phi, th);
  SU.sunPosition.value.copy(sunV); SU.turbidity.value = tState.turb; SU.rayleigh.value = tState.ray; SU.mieCoefficient.value = tState.mie; SU.mieDirectionalG.value = tState.mg;
  const night = tState.night;
  if (night > .6) { sun.position.copy(moonDir).multiplyScalar(900).add(sun.target.position); sun.color.set(0x9fb5ff); sun.intensity = .35 * night; }
  else { sun.position.copy(sunV).multiplyScalar(900).add(sun.target.position); sun.color.setHSL(.09, .6 * clamp(1 - tState.el / 30), .6 + clamp(tState.el / 40) * .35); sun.intensity = tState.sunI; }
  hemi.intensity = tState.hemi;
  renderer.toneMappingExposure = tState.exp;
  bloom.strength = tState.bloom; bloom.threshold = tState.bth;
  scene.fog.color.copy(tState._fog); scene.fog.density = tState.fogD;
  water.material.uniforms.sunDirection.value.copy(night > .6 ? moonDir : sunV);
  water.material.uniforms.sunColor.value.set(night > .6 ? 0x6a7a9a : 0xffffff).multiplyScalar(night > .6 ? .6 : 1);
  water.material.uniforms.waterColor.value.copy(tState._water);
  water.material.uniforms.time.value += dt * .45;
  stars.material.opacity = clamp((night - .5) * 2); nightDome.material.uniforms.uO.value = clamp((night - .3) * 1.45); moon.material.opacity = clamp((night - .2) * 1.25);
  scene.environmentIntensity = tState.env;
  envTimer += dt; if (Math.abs(prevEl - tState.el) > .05 && envTimer > .35) { envTimer = 0; updateEnv(); } else if (!envRT) updateEnv();
  // era
  eraNow = lerp(eraNow, eraGoal, k); terrNear.morphTargetInfluences[0] = terrFar.morphTargetInfluences[0] = eraNow;
  raiseNow = lerp(raiseNow, raiseGoal, reduce ? 1 : 1 - Math.exp(-dt * .9)); kbTop.position.y = raiseNow * RAISE;
  // groups
  for (const key in ALL) { const S = ALL[key]; if (key.endsWith('_')) continue; S.v = lerp(S.v, S.target, kf); if (Math.abs(S.v - S.target) < .002) S.v = S.target; if (S.ghost !== undefined) S.ghostV = lerp(S.ghostV || 0, ghostGoal, kf); S.apply(S, S.v); }
  // heritage glow on the 1937 structure
  glowNow = lerp(glowNow, glowGoal, kf);
  const pulse = glowNow * (.55 + .45 * Math.sin(now * .002));
  for (const S of [ALL.kbPiers, ALL.kbGirders]) S.mats.forEach(m => { if (m.userData.u) { m.userData.u.uGlow.value = pulse * .95; } });
  // night lighting
  const upOn = ALL.uplights.v * night;
  ALL.kbPiers.mats.forEach(m => { if (m.userData.u) m.userData.u.uUp.value = upOn * 1.1; });
  ALL.nbDeck.mats.concat(ALL.nbPiers.mats).forEach(m => { if (m.userData.u) m.userData.u.uProj.value = upOn * 1.3; });
  [ALL.archSideA_, ALL.archSideB_, ALL.archMid].forEach(S => S.mats.forEach(m => { if (m.userData.u) { const hue = (now * .00004) % 1; m.userData.u.uGlowCol.value.setHSL(.55 + .1 * Math.sin(hue * 6.28), .45, .6); m.userData.u.uGlow.value = upOn * .55; } }));
  pierLights.forEach((l, i) => { l.intensity = upOn * 900; });
  [ALL.wide, ALL.nbDeck].forEach(S => S.mats.forEach(m => { if (m.userData.isLamp) m.emissiveIntensity = night * 9; }));
  for (const kind of ['old', 'mid', 'new']) ALL['city_' + kind].mats.forEach(m => { if (m.userData.uNight) m.userData.uNight.value = night * (kind === 'old' ? .22 : kind === 'mid' ? .6 : .8); });
  ALL.t101.mats.forEach(m => { if (m.userData.uNight) m.userData.uNight.value = night; });
  railNew.children[1] && (railNew.children[1].visible = night > .3);
  // arch lifting
  if (ALL.archMid.target === 1 && liftK < 1 && now > liftStart) liftK = Math.min(1, liftK + dt / (reduce ? .01 : 5.5));
  archMid.position.y = -29 * (1 - smooth(0, 1, liftK));
  hangers.visible = hangers.visible && liftK > .98;
  // animated things
  const t = now / 1000;
  if (ALL.ferry.obj.visible) ferryBoats.forEach(({ b, ph, off, f }) => {
    const u = Math.sin(t * .09 + ph), o = u * (W - 18);
    const s = off; b.position.set(f.p.x + f.t.x * s + f.n.x * o, .25 + Math.sin(t * 1.3 + ph) * .08, f.p.y + f.t.y * s + f.n.y * o);
    const dir = Math.cos(t * .09 + ph) >= 0 ? 1 : -1; b.rotation.y = Math.atan2(f.n.x * dir, f.n.y * dir); b.rotation.z = Math.sin(t * 1.1 + ph) * .02;
  });
  if (ALL.yakata.obj.visible) yakataBoats.forEach(y => { y.s += dt * .8; if (y.s > 220) y.s = -120; const o = -(W - 40); y.g.position.set(y.f.p.x + y.f.t.x * y.s + y.f.n.x * o, .3 + Math.sin(t + y.s) * .06, y.f.p.y + y.f.t.y * y.s + y.f.n.y * o); y.g.rotation.y = Math.atan2(y.f.t.x, y.f.t.y); });
  const ffOn = ALL.fireflies ? 0 : 0; void ffOn;
  fireflies.material.opacity = (SC[cur]?.on.includes('fireflies') ? 1 : 0) * clamp(night * 2.5) * (reduce ? 1 : 1);
  if (fireflies.material.opacity > 0) { const a = fireflies.geometry.attributes.position; fireflies.userData.base.forEach(([x, y, z, p], i) => a.setXYZ(i, x + Math.sin(t * .6 + p) * 3, y + Math.sin(t * .9 + p * 2) * 1.2, z + Math.cos(t * .5 + p) * 3)); a.needsUpdate = true; }
  crack.children[1].scale.setScalar(1 + ((t * .8) % 1) * 1.4); crack.children[1].material.opacity = (1 - ((t * .8) % 1)) * ALL.crack.v;
  if (!reduce) {
    if (ALL.traffic37.obj.visible) TR.t37.forEach(tr => tr.update(dt));
    if (ALL.traffic70.obj.visible) TR.t70.forEach(tr => tr.update(dt, night));
    if (ALL.trafficNew.obj.visible) TR.tn.forEach(tr => tr.update(dt, night));
    if (ALL.people.obj.visible) TR.people.forEach(tr => tr.update(dt));
  }
  // camera
  if (!controls.enabled) {
    camNow.p.lerp(camGoal.p, k * .9); camNow.t.lerp(camGoal.t, k * .9);
    const sway = reduce ? 0 : Math.sin(t * .07) * .018;
    tmpV.subVectors(camNow.p, camNow.t).applyAxisAngle(new THREE.Vector3(0, 1, 0), sway);
    camera.position.copy(camNow.t).add(tmpV); camera.lookAt(camNow.t);
  } else controls.update();
  // labels
  const w = stage.clientWidth, h = stage.clientHeight;
  camera.updateMatrixWorld();
  LABELS.forEach(L => {
    tmpV.copy(L.v).project(camera);
    const vis = L.on && tmpV.z < 1 && Math.abs(tmpV.x) < 1.05 && Math.abs(tmpV.y) < 1.05;
    L.el.style.opacity = vis ? 1 : 0;
    if (vis) L.el.style.transform = `translate(${((tmpV.x + 1) / 2 * w).toFixed(1)}px,${((1 - tmpV.y) / 2 * h).toFixed(1)}px)`;
  });
  composer.render();
}
setScene(window.__scene || 'reopen');
updateEnv();
requestAnimationFrame(t => { last = t; frame(t); });
setTimeout(() => loading?.classList.add('done'), 300);
// ---------- offline passes (used to bake the cinematic plates; not used by the live page) ----------
const depthMat = new THREE.ShaderMaterial({
  vertexShader: `#include <common>
#include <morphtarget_pars_vertex>
varying float vD;
void main(){
  #include <begin_vertex>
  #include <morphtarget_vertex>
  vec4 mv = vec4(transformed, 1.0);
  #ifdef USE_INSTANCING
  mv = instanceMatrix * mv;
  #endif
  mv = modelViewMatrix * mv; vD = -mv.z; gl_Position = projectionMatrix * mv; }`,
  fragmentShader: `varying float vD; void main(){ float v = 1.0 - log(max(vD,3.0)/3.0)/log(8000.0/3.0); gl_FragColor = vec4(vec3(clamp(v,0.0,1.0)),1.0); }`
});
const waterMaskMat = new THREE.ShaderMaterial({
  vertexShader: depthMat.vertexShader.replace('varying float vD;', 'varying float vD; varying float vY;').replace('mv = modelViewMatrix * mv;', 'vY = (modelMatrix * mv).y; mv = modelViewMatrix * mv;'),
  fragmentShader: 'varying float vY; void main(){ gl_FragColor = vec4(vec3(abs(vY) < 0.05 ? 1.0 : 0.0), 1.0); }'
});
function renderPasses(W = 1920, H = 1080) {
  const prevSize = new THREE.Vector2(); renderer.getSize(prevSize); const prevPR = renderer.getPixelRatio();
  renderer.setPixelRatio(1); renderer.setSize(W, H, false); composer.setSize(W, H);
  camera.aspect = W / H; camera.fov = 40; camera.setViewOffset(W, H, -W * .17, 0, W, H); camera.updateProjectionMatrix();
  camera.position.copy(camNow.p); camera.lookAt(camNow.t); camera.updateMatrixWorld();
  const out = {};
  composer.render(); out.beauty = canvas.toDataURL('image/png');
  const hide = [stars, moon, nightDome, sky, fireflies]; const vis = hide.map(o => o.visible); hide.forEach(o => o.visible = false);
  const bg = scene.background, fog = scene.fog; scene.background = new THREE.Color(0); scene.fog = null;
  renderer.toneMapping = THREE.NoToneMapping;
  const wob = water.onBeforeRender; water.onBeforeRender = () => {};
  scene.overrideMaterial = depthMat; renderer.render(scene, camera); out.depth = canvas.toDataURL('image/png');
  scene.overrideMaterial = null;
  scene.overrideMaterial = waterMaskMat; renderer.render(scene, camera); out.water = canvas.toDataURL('image/png'); scene.overrideMaterial = null;
  water.onBeforeRender = wob;
  renderer.toneMapping = THREE.ACESFilmicToneMapping; scene.background = bg; scene.fog = fog; hide.forEach((o, i) => o.visible = vis[i]);
  out.labels = LABELS.filter(L => L.on).map(L => { const v = L.v.clone().project(camera); return { t: L.t, s: L.s, warn: !!L.warn, x: +((v.x + 1) / 2).toFixed(4), y: +((1 - v.y) / 2).toFixed(4), z: v.z }; }).filter(l => l.z < 1 && l.x > -0.05 && l.x < 1.05 && l.y > -0.05 && l.y < 1.05);
  renderer.setPixelRatio(prevPR); renderer.setSize(prevSize.x, prevSize.y, false); resize();
  return out;
}
window.__kb3d = { scene, camera, ALL, setScene, renderer, renderPasses, setExplore };
