"""68-ping apartment, empty shell vs. Japanese wa-style fit-out, for Blender 4.2 Cycles (headless).

    blender -b --python interior_scene.py -- --variant empty|wa --shot living --plan plan.json --assets DIR \
        --out out/wa_living.png --res 1600x1000 --samples 512
    blender -b --python interior_scene.py -- --variant wa --bake OUTDIR --plan plan.json --assets DIR   (lightmaps + GLB)

Plan coordinates come from interior/plan.json (pixels of the source drawing); metres here: x east, y north, z up,
finished floor at z = 0. Every mesh gets a UV map in metres divided by its material's texture size, so the same
materials work in Cycles and in the glTF export for the phone viewer. Object name prefixes drive the bake:
A_ architecture (baked), F_ furniture (baked), G_ glass, E_ emitters, P_ imported plants/props, X_ helpers.
"""
import argparse
import glob
import json
import math
import os
import sys
import time

import bpy
from mathutils import Matrix, Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
ap = argparse.ArgumentParser()
ap.add_argument("--variant", default="empty")
ap.add_argument("--shot", default="axo")
ap.add_argument("--plan", default="plan.json")
ap.add_argument("--assets", default="assets")
ap.add_argument("--out", default="out/render.png")
ap.add_argument("--res", default="1600x1000")
ap.add_argument("--samples", type=int, default=256)
ap.add_argument("--cam", default="", help="x,y,z,tx,ty,tz,lens in plan px (z in m)")
ap.add_argument("--bake", default="", help="output dir: bake lightmaps and export GLB instead of rendering")
ap.add_argument("--texel", type=float, default=48.0, help="lightmap texels per metre")
ap.add_argument("--night", action="store_true")
ap.add_argument("--hq", action="store_true", help="bake: high-quality set (denser lightmaps, PBR maps)")
ap.add_argument("--walk", default="", help="walkthrough: first:last[:step] frames of the camera path (12 fps)")
ap.add_argument("--outdir", default="", help="walkthrough / tour: output directory")
ap.add_argument("--tour", default="", help="JSON list of image-based tour jobs (pano / path / turn), see run_tour()")
A = ap.parse_args(argv)
WA = A.variant == "wa"
T0 = time.time()


def tick(msg):
    print(f"[t {time.time() - T0:6.1f}s] {msg}", flush=True)


PLAN = json.load(open(A.plan, encoding="utf-8"))
S = PLAN["scale"]; OX, OY = PLAN["origin_px"]
HT = PLAN["heights"]
H = HT["clear"]                       # structural ceiling (slab soffit)
CH = 2.75 if WA else H                # finished ceiling in the wa fit-out


def PX(x):
    return (x - OX) * S


def PY(y):
    return (OY - y) * S


def R(r):
    """plan rect (px) -> (x0, y0, x1, y1) metres, y north"""
    return PX(r[0]), PY(r[3]), PX(r[2]), PY(r[1])


def P(x, y):
    return PX(x), PY(y)


# ============================================================== scene reset
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
COLL = sc.collection
world = bpy.data.worlds.new("world"); sc.world = world

# ============================================================== materials
TEXDIR = os.path.join(A.assets, "textures")
MATS = {}


def tex_file(tid, kind):
    f = glob.glob(os.path.join(TEXDIR, tid, f"{tid}_{kind}_*.jpg"))
    return f[0] if f else None


def img(path, noncolor=False):
    im = bpy.data.images.load(path, check_existing=True)
    if noncolor:
        im.colorspace_settings.name = "Non-Color"
    return im


def new_mat(name, size=1.0):
    m = bpy.data.materials.new(name); m.use_nodes = True
    m["size"] = size
    MATS[name] = m
    return m


def pbr(name, tid, size, tint=(1, 1, 1), rough=None, rough_mul=1.0, bump=0.6, sat=1.0, bright=1.0, spec=0.5, coat=0.0):
    m = new_mat(name, size)
    nt = m.node_tree; N = nt.nodes.new; L = nt.links.new
    b = nt.nodes["Principled BSDF"]
    b.inputs["Specular IOR Level"].default_value = spec
    if coat:
        b.inputs["Coat Weight"].default_value = coat; b.inputs["Coat Roughness"].default_value = 0.15
    f = tex_file(tid, "Diffuse")
    if f:
        t = N("ShaderNodeTexImage"); t.image = img(f)
        hs = N("ShaderNodeHueSaturation"); hs.inputs["Saturation"].default_value = sat; hs.inputs["Value"].default_value = bright
        mx = N("ShaderNodeMix"); mx.data_type = "RGBA"; mx.blend_type = "MULTIPLY"; mx.inputs["Factor"].default_value = 1.0
        mx.inputs["B"].default_value = (*tint, 1)
        L(t.outputs["Color"], hs.inputs["Color"]); L(hs.outputs["Color"], mx.inputs["A"]); L(mx.outputs["Result"], b.inputs["Base Color"])
        m["albedo"] = os.path.basename(f); m["albedo_path"] = f; m["sat"] = sat
    else:
        b.inputs["Base Color"].default_value = (*tint, 1)
    m["tint"] = list(tint); m["bright"] = bright
    fr = tex_file(tid, "Rough")
    m["rough_mul"] = rough_mul; m["coat"] = coat; m["bump"] = bump
    if fr and rough is None:
        m["rough_path"] = fr
    if rough is not None:
        b.inputs["Roughness"].default_value = rough
    elif fr:
        t = N("ShaderNodeTexImage"); t.image = img(fr, True)
        mm = N("ShaderNodeMath"); mm.operation = "MULTIPLY"; mm.use_clamp = True; mm.inputs[1].default_value = rough_mul
        L(t.outputs["Color"], mm.inputs[0]); L(mm.outputs[0], b.inputs["Roughness"])
    fn = tex_file(tid, "nor_gl")
    if fn and bump > 0:
        m["normal_path"] = fn
    if fn and bump > 0:
        t = N("ShaderNodeTexImage"); t.image = img(fn, True)
        nm = N("ShaderNodeNormalMap"); nm.inputs["Strength"].default_value = bump
        L(t.outputs["Color"], nm.inputs["Color"]); L(nm.outputs["Normal"], b.inputs["Normal"])
    m["rough"] = rough if rough is not None else 0.5 * rough_mul
    return m


def flat(name, color, rough=0.5, metal=0.0, spec=0.5, coat=0.0):
    m = new_mat(name)
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*color, 1); b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal; b.inputs["Specular IOR Level"].default_value = spec
    if coat:
        b.inputs["Coat Weight"].default_value = coat
    m["color"] = list(color); m["rough"] = rough; m["metal"] = metal
    return m


def emit(name, color, strength):
    m = new_mat(name)
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*color, 1)
    b.inputs["Emission Color"].default_value = (*color, 1); b.inputs["Emission Strength"].default_value = strength
    m["emit"] = list(color); m["strength"] = strength
    return m


def glass(name, tint=(1, 1, 1)):
    """window glass that lets sunlight through (shadow rays see it as transparent)"""
    m = new_mat(name)
    nt = m.node_tree; N = nt.nodes.new; L = nt.links.new
    b = nt.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*tint, 1); b.inputs["Roughness"].default_value = 0.0
    b.inputs["Transmission Weight"].default_value = 1.0; b.inputs["IOR"].default_value = 1.45
    lp = N("ShaderNodeLightPath"); tr = N("ShaderNodeBsdfTransparent"); mx = N("ShaderNodeMixShader")
    out = nt.nodes["Material Output"]
    L(lp.outputs["Is Shadow Ray"], mx.inputs[0]); L(b.outputs[0], mx.inputs[1]); L(tr.outputs[0], mx.inputs[2])
    L(mx.outputs[0], out.inputs["Surface"])
    m["glass"] = True
    return m


def glass_thin(name, tint=(0.96, 1.0, 0.98)):
    """thin glass sheet (shower screens): transparent + fresnel gloss, no refraction, so grazing views never go black"""
    m = new_mat(name)
    nt = m.node_tree; N = nt.nodes.new; L = nt.links.new
    tr = N("ShaderNodeBsdfTransparent"); tr.inputs["Color"].default_value = (*tint, 1)
    gl = N("ShaderNodeBsdfGlossy"); gl.inputs["Roughness"].default_value = 0.02
    lw = N("ShaderNodeLayerWeight"); lw.inputs["Blend"].default_value = 0.12
    mx = N("ShaderNodeMixShader"); L(lw.outputs["Fresnel"], mx.inputs[0]); L(tr.outputs[0], mx.inputs[1]); L(gl.outputs[0], mx.inputs[2])
    lp = N("ShaderNodeLightPath"); tr2 = N("ShaderNodeBsdfTransparent"); mx2 = N("ShaderNodeMixShader")
    L(lp.outputs["Is Shadow Ray"], mx2.inputs[0]); L(mx.outputs[0], mx2.inputs[1]); L(tr2.outputs[0], mx2.inputs[2])
    L(mx2.outputs[0], nt.nodes["Material Output"].inputs["Surface"])
    m["glass"] = True
    return m


def paper(name, color=(0.93, 0.91, 0.85)):
    """washi for shoji: diffuse + translucent so daylight glows through"""
    m = new_mat(name)
    nt = m.node_tree; N = nt.nodes.new; L = nt.links.new
    b = nt.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*color, 1); b.inputs["Roughness"].default_value = 0.85
    tl = N("ShaderNodeBsdfTranslucent"); tl.inputs["Color"].default_value = (*color, 1)
    mx = N("ShaderNodeMixShader"); mx.inputs[0].default_value = 0.55
    L(b.outputs[0], mx.inputs[1]); L(tl.outputs[0], mx.inputs[2])
    L(mx.outputs[0], nt.nodes["Material Output"].inputs["Surface"])
    m["color"] = list(color); m["paper"] = True
    return m


def make_materials():
    flat("paint", (0.80, 0.80, 0.78), 0.9, spec=0.3)
    flat("ceiling", (0.82, 0.82, 0.80), 0.95, spec=0.2)
    flat("alu", (0.05, 0.05, 0.055), 0.35, 0.8)
    flat("steel", (0.55, 0.56, 0.58), 0.3, 1.0)
    flat("door_white", (0.78, 0.77, 0.74), 0.45, spec=0.4)
    flat("black", (0.02, 0.02, 0.02), 0.4)
    flat("porcelain", (0.9, 0.9, 0.88), 0.08, spec=0.6)
    flat("mirror", (0.9, 0.9, 0.9), 0.02, 1.0)
    flat("soil", (0.08, 0.06, 0.045), 0.95)
    glass("glass"); glass("glass_rail", (0.9, 0.97, 0.95))
    pbr("tile_public", "marble_01", 0.8, tint=(1.0, 0.97, 0.9), rough=0.06, bump=0.05, bright=1.1, sat=0.4, spec=0.6)
    pbr("laminate", "laminate_floor_03", 2.0, tint=(1.0, 0.95, 0.88), bump=0.3, rough_mul=0.9)
    pbr("bath_tile", "marble_01", 0.6, tint=(0.92, 0.92, 0.92), rough=0.1, bump=0.05, sat=0.2, bright=1.1)
    pbr("balcony", "concrete_floor_02", 1.2, tint=(0.7, 0.69, 0.67), bump=0.4, sat=0.3)
    if WA:
        pbr("oak_floor", "laminate_floor_02", 2.2, tint=(1.0, 0.94, 0.84), bump=0.35, rough_mul=0.85, bright=1.08, sat=0.75)
        pbr("tatami_a", "tatami_mat", 0.9, tint=(0.62, 0.64, 0.56), bump=0.8, sat=0.55)
        pbr("tatami_b", "tatami_mat", 0.9, tint=(0.40, 0.42, 0.38), bump=0.8, sat=0.45)
        pbr("tatami_g", "tatami_mat", 0.9, tint=(0.92, 0.9, 0.72), bump=0.8, sat=0.7)
        pbr("ash", "ash_veneer", 1.4, tint=(1.0, 0.93, 0.82), bump=0.25, rough_mul=0.9, bright=1.05)
        pbr("cedar", "oak_veneer_01", 1.2, tint=(1.0, 0.86, 0.7), bump=0.25, bright=1.0)
        pbr("walnut", "american_walnut_veneer", 1.2, tint=(0.95, 0.85, 0.78), bump=0.25, coat=0.3)
        pbr("plaster", "clay_plaster", 2.2, tint=(1.0, 0.96, 0.9), bump=0.2, sat=0.25, bright=2.1)
        pbr("cement_tile", "concrete_floor_02", 1.0, tint=(0.78, 0.76, 0.72), bump=0.4, sat=0.4)
        pbr("fabric_grey", "rough_linen", 0.45, tint=(0.36, 0.36, 0.35), bump=0.6, sat=0.1, bright=0.9)
        pbr("linen", "rough_linen", 0.5, tint=(0.95, 0.93, 0.88), bump=0.4, sat=0.4)
        pbr("marble", "marble_01", 1.4, tint=(0.95, 0.9, 0.82), rough=0.1, bump=0.1, sat=0.6)
        pbr("stone", "concrete_floor_02", 1.2, tint=(0.52, 0.5, 0.47), bump=0.4, sat=0.3)
        pbr("gravel", "gravel_floor", 1.0, tint=(1.1, 1.08, 1.02), bump=0.9, sat=0.3, bright=1.2)
        pbr("bamboo", "bamboo_wall", 1.5, tint=(0.95, 0.85, 0.65), bump=0.6)
        pbr("hinoki", "ash_veneer", 1.0, tint=(1.0, 0.9, 0.7), bump=0.2, bright=1.12, sat=0.8)
        paper("washi")
        flat("fusuma", (0.84, 0.8, 0.72), 0.8)
        flat("dark_wood", (0.12, 0.08, 0.05), 0.4)
        flat("cushion", (0.2, 0.22, 0.24), 0.9)
        flat("indigo", (0.12, 0.17, 0.28), 0.85)
        flat("bedding", (0.88, 0.86, 0.82), 0.9)
        pbr("olive", "rough_linen", 0.45, tint=(0.45, 0.46, 0.26), bump=0.5, sat=0.2)
        pbr("sofa_fabric", "jogging_melange", 0.35, tint=(0.52, 0.5, 0.48), bump=0.7, sat=0.2, bright=0.85)
        pbr("chair_fabric", "jogging_melange", 0.35, tint=(0.78, 0.74, 0.68), bump=0.7, sat=0.3)
        pbr("zabuton", "rough_linen", 0.3, tint=(0.25, 0.3, 0.42), bump=0.6, sat=0.6)
        pbr("lacquer", "american_walnut_veneer", 0.8, tint=(0.62, 0.3, 0.2), bump=0.15, coat=0.6, sat=1.1)
        flat("water", (0.1, 0.16, 0.15), 0.03, spec=0.5)
        flat("ceramic", (0.75, 0.72, 0.66), 0.25, spec=0.6)
        flat("scroll", (0.86, 0.83, 0.74), 0.8)
        flat("chrome", (0.86, 0.86, 0.86), 0.1, 1.0)
        flat("appliance", (0.86, 0.86, 0.84), 0.35, spec=0.5)
        flat("induction", (0.012, 0.012, 0.014), 0.04, spec=0.8)
        flat("graphite", (0.09, 0.09, 0.095), 0.35)
        glass_thin("glass_thin")
        pbr("towel", "rough_linen", 0.12, tint=(0.97, 0.95, 0.9), bump=1.3, sat=0.15, bright=1.1)
        pbr("towel_indigo", "rough_linen", 0.12, tint=(0.28, 0.36, 0.5), bump=1.3, sat=0.4)
        pbr("rug", "rough_linen", 0.18, tint=(0.7, 0.64, 0.54), bump=1.2, sat=0.35)
        pbr("deck", "oak_veneer_01", 1.0, tint=(0.66, 0.54, 0.44), bump=0.5, sat=0.6, rough_mul=1.2)
        emit("led_warm", (1.0, 0.8, 0.58), 30.0)
        emit("lamp_paper", (1.0, 0.86, 0.68), 6.0)
        emit("downlight", (1.0, 0.9, 0.78), 25.0)


# ============================================================== mesh builder (UVs in metres / material size)
class MB:
    def __init__(self, T=None):
        self.v, self.f, self.m, self.rot = [], [], [], []
        self.T = T or Matrix.Identity(4)

    def _v(self, p):
        self.v.append(tuple(self.T @ Vector(p))); return len(self.v) - 1

    def face(self, pts, m=0, rot=False):
        self.f.append([self._v(p) for p in pts]); self.m.append(m); self.rot.append(rot)

    def box(self, x0, y0, z0, x1, y1, z1, m=0, rot=False, skip=()):
        if x0 > x1: x0, x1 = x1, x0
        if y0 > y1: y0, y1 = y1, y0
        if z0 > z1: z0, z1 = z1, z0
        c = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0), (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
        faces = {"bottom": (0, 3, 2, 1), "top": (4, 5, 6, 7), "s": (0, 1, 5, 4), "e": (1, 2, 6, 5), "n": (2, 3, 7, 6), "w": (3, 0, 4, 7)}
        for k, idx in faces.items():
            if k not in skip:
                self.face([c[i] for i in idx], m, rot)

    def obox(self, p0, p1, t, z0, z1, m=0, rot=False, skip=()):
        """box whose plan centreline runs p0 -> p1 with thickness t"""
        d = Vector((p1[0] - p0[0], p1[1] - p0[1], 0)); L = d.length
        if L < 1e-6:
            return
        u = d / L; n = Vector((-u.y, u.x, 0)) * (t / 2)
        a, b = Vector((p0[0], p0[1], 0)), Vector((p1[0], p1[1], 0))
        q = [a - n, b - n, b + n, a + n]
        c = [(p.x, p.y, z0) for p in q] + [(p.x, p.y, z1) for p in q]
        for k, idx in {"bottom": (0, 3, 2, 1), "top": (4, 5, 6, 7), "s": (0, 1, 5, 4), "e": (1, 2, 6, 5), "n": (2, 3, 7, 6), "w": (3, 0, 4, 7)}.items():
            if k not in skip:
                self.face([c[i] for i in idx], m, rot)

    def prism(self, pts, z0, z1, m=0, rot=False, sides=True, bottom=True):
        area = sum(pts[i][0] * pts[(i + 1) % len(pts)][1] - pts[(i + 1) % len(pts)][0] * pts[i][1] for i in range(len(pts)))
        if area < 0:
            pts = pts[::-1]
        self.face([(x, y, z1) for x, y in pts], m, rot)
        if bottom:
            self.face([(x, y, z0) for x, y in pts[::-1]], m, rot)
        if sides:
            for i in range(len(pts)):
                (ax, ay), (bx, by) = pts[i], pts[(i + 1) % len(pts)]
                self.face([(ax, ay, z0), (bx, by, z0), (bx, by, z1), (ax, ay, z1)], m, rot)

    def cyl(self, cx, cy, z0, z1, r, seg=24, m=0, ry=None, caps=True):
        ry = ry or r
        ring = [(cx + r * math.cos(2 * math.pi * i / seg), cy + ry * math.sin(2 * math.pi * i / seg)) for i in range(seg)]
        for i in range(seg):
            (ax, ay), (bx, by) = ring[i], ring[(i + 1) % seg]
            self.face([(ax, ay, z0), (bx, by, z0), (bx, by, z1), (ax, ay, z1)], m)
        if caps:
            self.face([(x, y, z1) for x, y in ring], m); self.face([(x, y, z0) for x, y in ring[::-1]], m)

    def sq(self, cx, cy, cz, a, b, c, e1=0.25, e2=0.25, nu=28, nv=16, m=0):
        """superquadric (half-sizes a, b, c): e ~0.2 = soft box (cushions), 1 = ellipsoid"""
        def f(w, e):
            return math.copysign(abs(w) ** e, w)
        rows = []
        for j in range(nv + 1):
            eta = -math.pi / 2 + math.pi * j / nv
            row = []
            for i in range(nu):
                om = -math.pi + 2 * math.pi * i / nu
                row.append((cx + a * f(math.cos(eta), e1) * f(math.cos(om), e2), cy + b * f(math.cos(eta), e1) * f(math.sin(om), e2),
                            cz + c * f(math.sin(eta), e1)))
            rows.append(row)
        for j in range(nv):
            for i in range(nu):
                q = [rows[j][i], rows[j][(i + 1) % nu], rows[j + 1][(i + 1) % nu], rows[j + 1][i]]
                if j == 0:
                    self.face([q[0], q[2], q[3]], m)
                elif j == nv - 1:
                    self.face([q[0], q[1], q[2]], m)
                else:
                    self.face(q, m)

    def cylt(self, p0, p1, r0, r1, seg=12, m=0):
        """tapered round member from p0 to p1 (3D)"""
        a, b = Vector(p0), Vector(p1)
        d = (b - a).normalized()
        u = d.orthogonal().normalized(); v = d.cross(u)
        ra = [a + (u * math.cos(2 * math.pi * i / seg) + v * math.sin(2 * math.pi * i / seg)) * r0 for i in range(seg)]
        rb = [b + (u * math.cos(2 * math.pi * i / seg) + v * math.sin(2 * math.pi * i / seg)) * r1 for i in range(seg)]
        for i in range(seg):
            self.face([tuple(ra[i]), tuple(ra[(i + 1) % seg]), tuple(rb[(i + 1) % seg]), tuple(rb[i])], m)
        self.face([tuple(p) for p in rb], m); self.face([tuple(p) for p in ra[::-1]], m)

    def sphere(self, c, r, seg=16, rings=10, m=0, sz=1.0):
        pts = [[(c[0] + r * math.sin(math.pi * j / rings) * math.cos(2 * math.pi * i / seg),
                 c[1] + r * math.sin(math.pi * j / rings) * math.sin(2 * math.pi * i / seg),
                 c[2] + sz * r * math.cos(math.pi * j / rings)) for i in range(seg)] for j in range(rings + 1)]
        for j in range(rings):
            for i in range(seg):
                self.face([pts[j][i], pts[j + 1][i], pts[j + 1][(i + 1) % seg], pts[j][(i + 1) % seg]], m)

    def lathe(self, cx, cy, z, prof, seg=32, m=0):
        """surface of revolution about a vertical axis; prof = [(r, dz), ...] (outer surface upward, inner surface downward)"""
        rings = [[(cx + max(r, 1e-3) * math.cos(2 * math.pi * i / seg), cy + max(r, 1e-3) * math.sin(2 * math.pi * i / seg), z + h)
                  for i in range(seg)] for r, h in prof]
        for j in range(len(prof) - 1):
            a, b = rings[j], rings[j + 1]
            for i in range(seg):
                i2 = (i + 1) % seg
                self.face([a[i], a[i2], b[i2], b[i]], m)

    def well(self, x0, y0, x1, y1, z0, z1, m=0):
        """open-top basin seen from inside (floor + four walls facing inward)"""
        self.face([(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0)], m)
        self.face([(x0, y0, z0), (x0, y0, z1), (x1, y0, z1), (x1, y0, z0)], m)
        self.face([(x1, y1, z0), (x1, y1, z1), (x0, y1, z1), (x0, y1, z0)], m)
        self.face([(x0, y1, z0), (x0, y1, z1), (x0, y0, z1), (x0, y0, z0)], m)
        self.face([(x1, y0, z0), (x1, y0, z1), (x1, y1, z1), (x1, y1, z0)], m)

    def path(self, pts, r, seg=10, m=0):
        """round tube through a 3D polyline (faucets, rails)"""
        for a, b in zip(pts, pts[1:]):
            self.cylt(a, b, r, r, seg, m)
        for p in pts[1:-1]:
            self.sphere(p, r, seg, 6, m)

    def build(self, name, mats, bevel=0.0, smooth=False):
        me = bpy.data.meshes.new(name)
        me.from_pydata(self.v, [], self.f)
        me.validate(clean_customdata=False)
        mats = mats if isinstance(mats, (list, tuple)) else [mats]
        for mt in mats:
            me.materials.append(MATS[mt] if isinstance(mt, str) else mt)
        for i, p in enumerate(me.polygons):
            p.material_index = min(self.m[i], len(mats) - 1) if i < len(self.m) else 0
        # UVs: planar per face on its dominant axis, metres / texture size
        uv = me.uv_layers.new(name="UVMap")
        for p in me.polygons:
            n = p.normal; ax = max(range(3), key=lambda k: abs(n[k]))
            size = me.materials[p.material_index].get("size", 1.0) if me.materials else 1.0
            rot = self.rot[p.index] if p.index < len(self.rot) else False
            for li in p.loop_indices:
                co = me.vertices[me.loops[li].vertex_index].co
                if ax == 2:
                    u, v = co.x, co.y
                elif ax == 0:
                    u, v = co.y, co.z
                else:
                    u, v = co.x, co.z
                if rot:
                    u, v = v, u
                uv.data[li].uv = (u / size, v / size)
        me.update()
        o = bpy.data.objects.new(name, me); COLL.objects.link(o)
        if smooth:
            for p in me.polygons:
                p.use_smooth = True
        if bevel:
            md = o.modifiers.new("bevel", "BEVEL"); md.width = bevel; md.segments = 2; md.limit_method = "ANGLE"
            md.harden_normals = False
        return o


# ============================================================== architecture
REMOVED_WA = [[533, 133, 538, 316]]           # BR3 east partition -> shoji screens (washitsu opens to the living room)


def room(rid):
    return next(r for r in PLAN["rooms"] if r["id"] == rid)


def floor_mat(rm):
    f = rm["floor"]
    if rm.get("outdoor"):
        return "cement_tile" if WA else "balcony"     # wa: balconies get a cedar deck on top
    if WA:
        return {"stone": "marble"}.get(f, "oak_floor")
    return {"public": "tile_public", "tile": "tile_public", "wood": "laminate", "stone": "bath_tile"}.get(f, "tile_public")


def build_shell():
    wallmat = "plaster" if WA else "paint"
    walls = [w for w in PLAN["walls"] if not (WA and w["r"] in REMOVED_WA)]
    mb = MB()
    for w in walls:
        x0, y0, x1, y1 = R(w["r"])
        mb.box(x0, y0, 0, x1, y1, H, 0, skip=("top", "bottom"))
    for c in PLAN["columns"]:
        x0, y0, x1, y1 = R(c)
        mb.box(x0, y0, 0, x1, y1, H, 0, skip=("top", "bottom"))
    # beams under the slab (wood-clad in the wa fit-out)
    bm = MB()
    for b in PLAN["beams"]:
        x0, y0, x1, y1 = R(b["r"])
        bm.box(x0, y0, H - b["d"], x1, y1, H, 0, rot=(x1 - x0) < (y1 - y0), skip=("top",))
    # sills and heads around openings
    for op in PLAN["openings"]:
        x0, y0, x1, y1 = R(op["r"]); k = op["kind"]
        if k in ("window", "window_high"):
            sill = HT["bath_sill"] if k == "window_high" else HT["window_sill"]
            mb.box(x0, y0, 0, x1, y1, sill, 0); mb.box(x0, y0, HT["window_head"], x1, y1, H, 0)
        elif k == "slider":
            mb.box(x0, y0, HT["slider"], x1, y1, H, 0)
        elif k == "railing":
            mb.box(x0, y0, 0, x1, y1, HT["parapet"], 0); mb.box(x0, y0, HT["window_head"], x1, y1, H, 0)
        elif k in ("door", "entry"):
            if WA and op["id"] == "D_B":
                pass
            mb.box(x0, y0, HT["door"] + (0.05 if k == "entry" else 0), x1, y1, H, 0)
    mb.build("A_walls", [wallmat])
    bm.build("A_beams", ["ash" if WA else wallmat])
    # parapets: low wall + glass balustrade + rail
    pm, gm = MB(), MB()
    for p in PLAN["parapets"]:
        x0, y0, x1, y1 = R(p)
        pm.box(x0, y0, -0.1, x1, y1, 0.3, 0); pm.box(x0, y0, 1.08, x1, y1, 1.12, 1)
        cx0, cy0, cx1, cy1 = x0, (y0 + y1) / 2 - 0.006, x1, (y0 + y1) / 2 + 0.006
        if (x1 - x0) < (y1 - y0):
            cx0, cx1, cy0, cy1 = (x0 + x1) / 2 - 0.006, (x0 + x1) / 2 + 0.006, y0, y1
        gm.box(cx0, cy0, 0.3, cx1, cy1, 1.08, 0)
    pm.build("A_parapets", [wallmat, "alu"])
    gm.build("G_balustrade", ["glass_rail"])
    # floors
    fl = MB(); mats = []
    for rm in PLAN["rooms"]:
        if "poly" not in rm:
            continue
        mt = floor_mat(rm)
        if rm["id"] == "PLT":
            mt = "gravel" if WA else "soil"
        if mt not in mats:
            mats.append(mt)
        z = -0.06 if rm.get("outdoor") else 0.0
        fl.prism([P(x, y) for x, y in rm["poly"]], z - 0.02, z, mats.index(mt), sides=False, bottom=False)
    fl.build("A_floors", mats)
    # structural slabs above and below (hidden from inside except through the cove gaps)
    xs = [PX(c[0]) for c in PLAN["columns"]] + [PX(c[2]) for c in PLAN["columns"]]
    ys = [PY(c[1]) for c in PLAN["columns"]] + [PY(c[3]) for c in PLAN["columns"]]
    sl = MB()
    sl.box(min(xs) - 0.2, min(ys) - 0.3, H, max(xs) + 0.2, max(ys) + 0.3, H + 0.25, 0, skip=("top",))
    sl.box(min(xs) - 0.2, min(ys) - 0.3, -0.35, max(xs) + 0.2, max(ys) + 0.3, -0.08, 1, skip=("top", "bottom"))
    sl.build("A_slab", ["ceiling", "paint"])


def build_openings():
    """window frames and glass; interior door leaves (open) and the entry door (closed)"""
    fr, gl, dr = MB(), MB(), MB()
    for op in PLAN["openings"]:
        x0, y0, x1, y1 = R(op["r"]); k = op["kind"]
        horiz = (x1 - x0) >= (y1 - y0)
        L = (x1 - x0) if horiz else (y1 - y0)
        mid = ((y0 + y1) / 2) if horiz else ((x0 + x1) / 2)

        def seg(a, b, z0, z1, t, m, mb):
            if horiz:
                mb.box(x0 + a, mid - t / 2, z0, x0 + b, mid + t / 2, z1, m)
            else:
                mb.box(mid - t / 2, y0 + a, z0, mid + t / 2, y0 + b, z1, m)
        if k in ("window", "window_high", "slider"):
            z0 = {"window": HT["window_sill"], "window_high": HT["bath_sill"], "slider": 0.0}[k]
            z1 = HT["slider"] if k == "slider" else HT["window_head"]
            f = 0.05
            seg(0, L, z0, z0 + f, 0.1, 0, fr); seg(0, L, z1 - f, z1, 0.1, 0, fr)
            seg(0, f, z0, z1, 0.1, 0, fr); seg(L - f, L, z0, z1, 0.1, 0, fr)
            n = max(1, round(L / 1.4)) if k != "slider" else max(2, round(L / 1.6))
            for i in range(1, n):
                a = L * i / n
                seg(a - 0.03, a + 0.03, z0, z1, 0.09, 0, fr)
            if k == "slider":   # two glass planes on offset tracks
                for i in range(n):
                    off = 0.022 if i % 2 else -0.022
                    a, b = L * i / n, L * (i + 1) / n
                    if horiz:
                        gl.box(x0 + a, mid + off - 0.004, z0 + f, x0 + b, mid + off + 0.004, z1 - f, 0)
                    else:
                        gl.box(mid + off - 0.004, y0 + a, z0 + f, mid + off + 0.004, y0 + b, z1 - f, 0)
            else:
                seg(f, L - f, z0 + f, z1 - f, 0.01, 0, gl)
        elif k in ("door", "entry"):
            dh = HT["door"]
            # jambs / head casing
            t = 0.02 if horiz else 0.02
            if k == "entry":
                seg(0, L * 0.64, 0, dh + 0.05, 0.06, 1, dr)     # main leaf (closed), side panel fixed
                seg(L * 0.64, L, 0, dh + 0.05, 0.06, 1, dr)
                continue
            if WA and op["id"] == "D_B":
                continue                                        # sliding fusuma drawn with the washitsu
            h = (x0, y0) if op.get("hinge") == "start" else ((x1, y0) if horiz else (x0, y1))
            if horiz:
                h = (x0 if op.get("hinge") == "start" else x1, mid)
                u = Vector((1 if op.get("hinge") == "start" else -1, 0, 0))
                nrm = Vector((0, -op.get("side", 1), 0))        # plan +y (down) is -y in metres
            else:
                h = (mid, y1 if op.get("hinge") == "start" else y0)   # plan start = top = larger y
                u = Vector((0, -1 if op.get("hinge") == "start" else 1, 0))
                nrm = Vector((1 if (WA and op["id"] == "D_SVC") else op.get("side", 1), 0, 0))   # wa: opens into the kitchen
            a = math.radians(84)
            d = u * math.cos(a) + nrm * math.sin(a)
            w = L - 0.06
            p0 = Vector((h[0], h[1], 0)) + u * 0.03 + nrm * 0.03
            if not (WA and op["id"] == "D_K"):                  # kitchen gets a sliding door in the wa fit-out
                dr.obox((p0.x, p0.y), (p0.x + d.x * w, p0.y + d.y * w), 0.04, 0.0, dh - 0.01, 0)
                dr.obox((p0.x + d.x * (w - 0.08), p0.y + d.y * (w - 0.08)), (p0.x + d.x * (w - 0.06), p0.y + d.y * (w - 0.06)), 0.1, 1.0, 1.03, 2)
            # frame casing around the opening, flush with both wall faces
            wt = abs((y1 - y0) if horiz else (x1 - x0))
            seg(0, 0.04, 0, dh, wt + 0.02, 1, dr); seg(L - 0.04, L, 0, dh, wt + 0.02, 1, dr)
            seg(0, L, dh - 0.04, dh, wt + 0.02, 1, dr)
    fr.build("A_frames", ["alu"])
    gl.build("G_glass", ["glass"])
    leaf = "ash" if WA else "door_white"
    dr.build("A_doors", [leaf, "dark_wood" if WA else "door_white", "steel"], bevel=0.004)


# ============================================================== imported CC0 props (Poly Haven .blend, LOD appended)
def load_gltf(aid):
    """fallback for Poly Haven .blend files saved by a newer Blender than the render image's"""
    f = glob.glob(os.path.join(A.assets, "models", aid, f"{aid}_1k.gltf"))
    if not f:
        print("[model] missing", aid); return None
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=f[0])
    new = [o for o in bpy.data.objects if o not in before]
    objs = [o for o in new if o.type == "MESH"]
    for o in objs:
        mw = o.matrix_world.copy(); o.parent = None; o.matrix_world = mw
    for o in new:
        for c in list(o.users_collection):
            c.objects.unlink(o)
        if o.type != "MESH":
            bpy.data.objects.remove(o)
    return objs or None


def load_model(aid):
    f = glob.glob(os.path.join(A.assets, "models", aid, f"{aid}_1k.blend"))
    if not f:
        return load_gltf(aid)
    try:
        with bpy.data.libraries.load(f[0], link=False) as (src, dst):
            dst.objects = list(src.objects)
    except OSError as e:
        print("[model] blend unreadable, using glTF:", aid, e)
        return load_gltf(aid)
    objs = [o for o in dst.objects if o is not None and o.type == "MESH"]
    for im in bpy.data.images:
        if im.filepath.startswith("//"):
            im.filepath = os.path.join(os.path.dirname(f[0]), im.filepath[2:])
    if not objs:
        return None
    # keep the highest-detail LOD only
    lods = [o for o in objs if "LOD" in o.name]
    if lods:
        objs = [o for o in objs if "LOD0" in o.name or "LOD" not in o.name] or objs[:1]
    for o in objs:
        o.parent = None
    return objs


def place_model(aid, x, y, z=0.0, rot=0.0, scale=1.0, name=None, height=None):
    objs = load_model(aid)
    if not objs:
        return None
    root = bpy.data.objects.new(f"P_{name or aid}", None); COLL.objects.link(root)
    for o in objs:
        COLL.objects.link(o); o.parent = root
        o.name = f"P_{name or aid}_{o.name}"
    if height:
        zmax = max((o.matrix_world @ Vector(c)).z for o in objs for c in o.bound_box)
        zmin = min((o.matrix_world @ Vector(c)).z for o in objs for c in o.bound_box)
        scale = height / max(zmax - zmin, 1e-3)
    root.location = (x, y, z); root.rotation_euler = (0, 0, rot); root.scale = (scale,) * 3
    bpy.context.view_layer.update()
    pts = [o.matrix_world @ Vector(c) for o in objs for c in o.bound_box]
    print(f"[prop] {name or aid}: " + " ".join(f"{max(p[k] for p in pts) - min(p[k] for p in pts):.2f}" for k in range(3))
          + f" z0={min(p.z for p in pts):.2f}")
    return root


# ============================================================== empty unit extras
def build_empty_extras():
    # a bare builder bulb socket per room, planter soil with a few builder shrubs
    mb = MB()
    for rm in PLAN["rooms"]:
        if "label" in rm and not rm.get("outdoor") and not rm.get("hidden"):
            x, y = P(*rm["label"])
            mb.cyl(x, y, H - 0.04, H, 0.06, 16, 0)
    mb.build("F_sockets", ["porcelain"])


# ============================================================== wa fit-out helpers
LIGHTS = []   # (kind, loc, energy, color, extra) collected; created after geometry


def pxr(r):
    return R(r)


def inset_ortho(pts, d):
    """offset an orthogonal polygon inward by d (vertex moves along the sum of the adjacent inward normals)"""
    n = len(pts)
    area = sum(pts[i][0] * pts[(i + 1) % n][1] - pts[(i + 1) % n][0] * pts[i][1] for i in range(n))
    sgn = 1 if area > 0 else -1
    out = []
    for i in range(n):
        p0, p1, p2 = Vector((*pts[i - 1], 0)), Vector((*pts[i], 0)), Vector((*pts[(i + 1) % n], 0))
        e1 = (p1 - p0).normalized(); e2 = (p2 - p1).normalized()
        n1 = Vector((-e1.y, e1.x, 0)) * sgn; n2 = Vector((-e2.y, e2.x, 0)) * sgn
        out.append(((p1 + (n1 + n2) * d).x, (p1 + (n1 + n2) * d).y))
    return out


def shoji(mb, p0, p1, z0, z1, m_frame, m_paper, grid=(3, 6), glass_low=0.0, gmb=None, t=0.03, vertical=False):
    """one shoji panel in the plane p0->p1: frame, kumiko grid, washi (optionally a 雪見 glass lower part)"""
    d = Vector((p1[0] - p0[0], p1[1] - p0[1], 0)); L = d.length; u = d / L
    def at(s):
        return (p0[0] + u.x * s, p0[1] + u.y * s)
    f = 0.03
    mb.obox(at(0), at(f), t, z0, z1, m_frame); mb.obox(at(L - f), at(L), t, z0, z1, m_frame)
    mb.obox(at(0), at(L), t, z0, z0 + 0.06, m_frame); mb.obox(at(0), at(L), t, z1 - f, z1, m_frame)
    zp = z0 + 0.06
    if glass_low:
        zg = z0 + glass_low
        mb.obox(at(0), at(L), t, zg - 0.015, zg + 0.015, m_frame)
        if gmb is not None:
            gmb.obox(at(f), at(L - f), 0.006, zp, zg - 0.015, 0)
        zp = zg + 0.015
    nx, ny = grid
    for i in range(1, nx):
        s = f + (L - 2 * f) * i / nx
        mb.obox(at(s - 0.006), at(s + 0.006), t * 0.7, zp, z1 - f, m_frame)
    for j in range(1, ny):
        z = zp + (z1 - f - zp) * j / ny
        mb.obox(at(f), at(L - f), t * 0.7, z - 0.006, z + 0.006, m_frame)
    mb.obox(at(f), at(L - f), 0.004, zp, z1 - f, m_paper)


def lattice(mb, p0, p1, z0, z1, m, pitch=0.045, slat=0.018, depth=0.03, frame=True):
    """千本格子: fine vertical slats"""
    d = Vector((p1[0] - p0[0], p1[1] - p0[1], 0)); L = d.length; u = d / L
    at = lambda s: (p0[0] + u.x * s, p0[1] + u.y * s)
    n = int(L / pitch)
    for i in range(n + 1):
        s = min(L - slat, i * L / n)
        mb.obox(at(s), at(s + slat), depth, z0, z1, m)
    if frame:
        mb.obox(at(0), at(L), depth + 0.01, z0, z0 + 0.03, m); mb.obox(at(0), at(L), depth + 0.01, z1 - 0.03, z1, m)


def light(kind, loc, energy, color=(1.0, 0.8, 0.6), size=0.05, spot=None, rot=(0, 0, 0), name=None):
    LIGHTS.append((kind, loc, energy, color, size, spot, rot, name))


def downlight_grid(mb, x, y, n=2, pitch=0.18, energy=35, z=None):
    """the square 4-light recessed fixtures of the reference (with real spots below)"""
    z = z or CH
    for i in range(n):
        for j in range(n):
            cx, cy = x + (i - (n - 1) / 2) * pitch, y + (j - (n - 1) / 2) * pitch
            mb.box(cx - 0.055, cy - 0.055, z - 0.004, cx + 0.055, cy + 0.055, z, 0)
            light("SPOT", (cx, cy, z - 0.02), energy, (1.0, 0.88, 0.74), size=0.04, spot=(math.radians(75), 0.6))


def sofa(mb, T, w=2.3, d=0.95):
    """low wood-frame sofa (reference: 入字 legs, tweed cushions, round bolsters). local: seat along x, front = +y.
    returns (wood MB, fabric MB)"""
    wd, fb = MB(T), MB(T)
    wd.box(-w / 2, -d / 2, 0.1, w / 2, d / 2, 0.16, 0)                          # platform
    for sx in (-1, 1):                                                           # 入字 legs, splayed
        for sy in (-1, 1):
            wd.cylt((sx * (w / 2 - 0.18), sy * (d / 2 - 0.14), 0.1), (sx * (w / 2 - 0.12), sy * (d / 2 - 0.06), 0.0), 0.022, 0.018, 8, 0)
    wd.box(-w / 2, -d / 2, 0.16, w / 2, -d / 2 + 0.07, 0.34, 0)                  # low back rail
    for k in range(9):                                                           # visible slats under the cushions
        x = -w / 2 + 0.1 + (w - 0.2) * k / 8
        wd.box(x - 0.03, -d / 2 + 0.07, 0.16, x + 0.03, d / 2, 0.175, 0)
    half = (w - 0.06) / 4
    for sx in (-1, 1):
        cx = sx * (half + 0.01)
        fb.sq(cx, 0.06, 0.26, half, d / 2 - 0.06, 0.095, e1=0.3, e2=0.18, m=0)  # seat cushions
        # reclined back cushions (12 deg)
        Tb = Matrix.Translation((cx, -d / 2 + 0.2, 0.55)) @ Matrix.Rotation(math.radians(-12), 4, "X")
        bm_ = MB(T @ Tb); bm_.sq(0, 0, 0, half, 0.12, 0.24, e1=0.35, e2=0.35, m=0)
        fb.v += []; base = len(fb.v)
        fb.v += bm_.v; fb.f += [[i + base for i in f_] for f_ in bm_.f]; fb.m += bm_.m; fb.rot += bm_.rot
    for sx in (-1, 1):                                                           # round bolsters at the ends
        Tb = Matrix.Translation((sx * (w / 2 - 0.2), 0.1, 0.46)) @ Matrix.Rotation(math.pi / 2, 4, "X")
        bm_ = MB(T @ Tb); bm_.sq(0, 0, 0, 0.13, 0.13, 0.26, e1=0.5, e2=1.0, m=0)
        base = len(fb.v); fb.v += bm_.v; fb.f += [[i + base for i in f_] for f_ in bm_.f]; fb.m += bm_.m; fb.rot += bm_.rot
    return wd, fb


def oval_table(mb, x, y, rx, ry, h, m_top, rot=0.0):
    T = Matrix.Translation((x, y, 0)) @ Matrix.Rotation(rot, 4, "Z")
    t = MB(T)
    t.sq(0, 0, h - 0.018, rx, ry, 0.018, e1=0.25, e2=1.0, nu=48, nv=6, m=0)
    for sx in (-1, 1):                          # four square legs, splayed like the reference table
        for sy in (-1, 1):
            t.cylt((sx * rx * 0.5, sy * ry * 0.5, h - 0.035), (sx * rx * 0.58, sy * ry * 0.62, 0.0), 0.028, 0.022, 4, 0)
    return t


def zaisu(T):
    """鳥居椅: natural-edge lacquered base, torii back (two posts, 笠木 with raised ends, 貫), round zabuton.
    local front = +y (the sitter faces +y). returns (wood MB, cushion MB)"""
    wd, cu = MB(T), MB(T)
    wd.sq(0, 0.0, 0.03, 0.26, 0.27, 0.03, e1=0.3, e2=0.7, nu=24, nv=8, m=0)       # organic base slab
    lean = math.radians(10)
    top = 0.5
    for sx in (-0.15, 0.15):
        p0 = (sx, -0.2, 0.05); p1 = (sx, -0.2 - top * math.sin(lean), 0.05 + top * math.cos(lean))
        wd.cylt(p0, p1, 0.018, 0.015, 8, 0)
    zt = 0.05 + top * math.cos(lean); yt = -0.2 - top * math.sin(lean)
    # 笠木: centre bar plus two up-swept ends
    wd.box(-0.2, yt - 0.02, zt - 0.005, 0.2, yt + 0.02, zt + 0.03, 0)
    for sx in (-1, 1):
        wd.cylt((sx * 0.19, yt, zt + 0.012), (sx * 0.29, yt, zt + 0.045), 0.018, 0.012, 8, 0)
    zn = 0.05 + 0.33 * math.cos(lean); yn = -0.2 - 0.33 * math.sin(lean)
    wd.box(-0.21, yn - 0.012, zn - 0.015, 0.21, yn + 0.012, zn + 0.015, 0)           # 貫
    cu.sq(0, 0.02, 0.1, 0.22, 0.22, 0.045, e1=0.35, e2=1.0, nu=28, nv=10, m=0)      # round zabuton
    return wd, cu


def dining_chair(T):
    """Japanese dining chair (web refs): round tapered legs, curved 笠木, upholstered seat and back pad. front = +y"""
    wd, fb = MB(T), MB(T)
    for sx in (-0.2, 0.2):
        wd.cylt((sx * 1.02, 0.19, 0.0), (sx, 0.17, 0.42), 0.017, 0.021, 10, 0)         # front legs
        wd.cylt((sx * 1.05, -0.22, 0.0), (sx, -0.19, 0.42), 0.017, 0.021, 10, 0)       # rear legs
        wd.cylt((sx, -0.19, 0.42), (sx * 0.98, -0.25, 0.8), 0.021, 0.017, 10, 0)       # back posts, raked
    wd.box(-0.21, -0.2, 0.38, 0.21, 0.19, 0.42, 0)                                    # seat frame
    for k in range(8):                                                               # curved 笠木
        t0, t1 = k / 8, (k + 1) / 8
        x0, x1 = -0.25 + 0.5 * t0, -0.25 + 0.5 * t1
        y0 = -0.26 - 0.035 * (1 - (2 * t0 - 1) ** 2); y1 = -0.26 - 0.035 * (1 - (2 * t1 - 1) ** 2)
        wd.obox((x0, y0), (x1, y1), 0.035, 0.78, 0.83, 0)
    fb.sq(0, 0.0, 0.455, 0.205, 0.2, 0.04, e1=0.35, e2=0.2, m=0)                      # seat pad
    Tb = Matrix.Translation((0, -0.235, 0.64)) @ Matrix.Rotation(math.radians(-10), 4, "X")
    bm_ = MB(T @ Tb); bm_.sq(0, 0, 0, 0.18, 0.022, 0.1, e1=0.35, e2=0.35, m=0)        # back pad
    base = len(fb.v); fb.v += bm_.v; fb.f += [[i + base for i in f_] for f_ in bm_.f]; fb.m += bm_.m; fb.rot += bm_.rot
    return wd, fb


def lounge_chair(T):
    """low lounge chair (天童木工 低座イス type): bent-ply sides, upholstered seat and back. front = +y"""
    wd, fb = MB(T), MB(T)
    for sx in (-0.29, 0.29):
        wd.box(sx - 0.012, -0.25, 0.0, sx + 0.012, 0.28, 0.05, 0)
        wd.box(sx - 0.012, 0.2, 0.0, sx + 0.012, 0.26, 0.22, 0)
        wd.box(sx - 0.012, -0.3, 0.0, sx + 0.012, -0.18, 0.45, 0)
    wd.box(-0.3, -0.2, 0.18, 0.3, 0.24, 0.2, 0)
    fb.sq(0, 0.02, 0.25, 0.3, 0.25, 0.06, e1=0.35, e2=0.35, m=0)
    Tb = Matrix.Translation((0, -0.24, 0.5)) @ Matrix.Rotation(math.radians(-16), 4, "X")
    bm_ = MB(T @ Tb); bm_.sq(0, 0, 0, 0.3, 0.05, 0.2, e1=0.5, e2=0.5, m=0)
    base = len(fb.v); fb.v += bm_.v; fb.f += [[i + base for i in f_] for f_ in bm_.f]; fb.m += bm_.m; fb.rot += bm_.rot
    return wd, fb


def andon(x, y, z=0.0, h=0.55, w=0.24):
    fm = MB(Matrix.Translation((x, y, z)))
    for sx in (-1, 1):
        for sy in (-1, 1):
            fm.box(sx * w / 2 - 0.012, sy * w / 2 - 0.012, 0, sx * w / 2 + 0.012, sy * w / 2 + 0.012, h, 0)
    fm.box(-w / 2, -w / 2, h - 0.02, w / 2, w / 2, h, 0); fm.box(-w / 2, -w / 2, 0.08, w / 2, w / 2, 0.1, 0)
    pm = MB(Matrix.Translation((x, y, z)))
    pm.box(-w / 2 + 0.008, -w / 2 + 0.008, 0.1, w / 2 - 0.008, w / 2 - 0.008, h - 0.02, 0)
    light("POINT", (x, y, z + 0.1 + (h - 0.12) / 2), 12, (1.0, 0.72, 0.45), size=0.06)
    return fm, pm


def woven_pendant(x, y, z, r=0.28):
    """bamboo-weave globe (組子/編み) with a bulb inside"""
    m = MB()
    seg, rings = 18, 9
    for i in range(seg):
        a = 2 * math.pi * i / seg
        pts = [(x + r * math.sin(math.pi * j / rings) * math.cos(a), y + r * math.sin(math.pi * j / rings) * math.sin(a),
                z + 0.8 * r * math.cos(math.pi * j / rings)) for j in range(rings + 1)]
        for j in range(1, rings - 1):
            p, q = pts[j], pts[j + 1]
            m.obox((p[0], p[1]), (q[0] + 1e-4, q[1] + 1e-4), 0.008, min(p[2], q[2]) - 0.004, max(p[2], q[2]) + 0.004, 0)
    for j in range(2, rings - 1):
        rr = r * math.sin(math.pi * j / rings); zz = z + 0.8 * r * math.cos(math.pi * j / rings)
        m.cyl(x, y, zz - 0.004, zz + 0.004, rr, seg * 2, 0, caps=False)
    m.box(x - 0.004, y - 0.004, z + 0.8 * r, x + 0.004, y + 0.004, CH, 0)
    light("POINT", (x, y, z), 45, (1.0, 0.74, 0.48), size=0.05)
    return m


def cone_pendant(x, y, z):
    m = MB()
    seg = 24
    for i in range(seg):
        a0, a1 = 2 * math.pi * i / seg, 2 * math.pi * (i + 1) / seg
        m.face([(x + 0.05 * math.cos(a0), y + 0.05 * math.sin(a0), z + 0.2), (x + 0.2 * math.cos(a0), y + 0.2 * math.sin(a0), z),
                (x + 0.2 * math.cos(a1), y + 0.2 * math.sin(a1), z), (x + 0.05 * math.cos(a1), y + 0.05 * math.sin(a1), z + 0.2)], 0)
    m.box(x - 0.003, y - 0.003, z + 0.2, x + 0.003, y + 0.003, CH, 1)
    light("POINT", (x, y, z + 0.08), 40, (1.0, 0.76, 0.5), size=0.04)
    return m


def bed(T, w=1.9, l=2.1, base="ash", head_h=0.95, head_w=None):
    """low platform bed; returns (frame MB [ash, black, cedar], soft MB [linen, bedding])"""
    m, sf = MB(T), MB(T)
    head_w = head_w or w + 1.1
    m.box(-0.1, -w / 2 - 0.12, 0.04, l + 0.12, w / 2 + 0.12, 0.22, 0)                  # platform
    m.box(0.0, -w / 2 - 0.1, 0.0, l, w / 2 + 0.1, 0.04, 1)                             # shadow gap
    m.box(-0.12, -head_w / 2, 0.04, -0.02, head_w / 2, head_h, 2)                      # headboard panel
    m.box(-0.14, -head_w / 2, head_h, 0.06, head_w / 2, head_h + 0.03, 2)              # shelf
    sf.sq(l / 2, 0, 0.32, l / 2, w / 2, 0.1, e1=0.2, e2=0.12, m=0)                     # mattress
    sf.sq(l / 2 + 0.18, 0, 0.44, l / 2 - 0.16, w / 2 + 0.03, 0.05, e1=0.45, e2=0.15, m=1)   # duvet
    for sy in (-1, 1):
        sf.sq(0.22, sy * w / 4, 0.49, 0.15, 0.32, 0.07, e1=0.5, e2=0.35, m=0)           # pillows
    return m, sf


def wardrobe(mb, p0, p1, depth, z0, z1, m=0, groove=2, pitch=0.6):
    d = Vector((p1[0] - p0[0], p1[1] - p0[1], 0)); L = d.length; u = d / L; nn = Vector((-u.y, u.x, 0))
    c0 = (p0[0] + nn.x * depth / 2, p0[1] + nn.y * depth / 2); c1 = (p1[0] + nn.x * depth / 2, p1[1] + nn.y * depth / 2)
    mb.obox(c0, c1, depth, z0, z1, m)
    n = max(1, round(L / pitch))
    for i in range(1, n):
        s = L * i / n
        a = (p0[0] + u.x * s + nn.x * (depth + 0.002), p0[1] + u.y * s + nn.y * (depth + 0.002))
        mb.obox((a[0] - u.x * 0.004, a[1] - u.y * 0.004), (a[0] + u.x * 0.004, a[1] + u.y * 0.004), 0.006, z0 + 0.01, z1 - 0.01, groove)


def clad_room(mb, rect_px, z0, z1, m, t=0.012, only="nsew"):
    """line the inner faces of a rectangular room, leaving doors/windows open (windows keep the part below the sill)"""
    rx0, ry0, rx1, ry1 = rect_px
    sides = {"w": ("x", rx0, ry0, ry1), "e": ("x", rx1, ry0, ry1), "n": ("y", ry0, rx0, rx1), "s": ("y", ry1, rx0, rx1)}
    sides = {k: v for k, v in sides.items() if k in only}
    face_of = {"w": "e", "e": "w", "n": "s", "s": "n"}       # panel faces into the room
    for side, (ax, c, a, b) in sides.items():
        cuts = []
        for op in PLAN["openings"]:
            o = op["r"]
            if ax == "x" and o[0] - 3 <= c <= o[2] + 3 and o[3] > a and o[1] < b and (o[3] - o[1]) > (o[2] - o[0]):
                cuts.append((max(a, o[1]), min(b, o[3]), op))
            if ax == "y" and o[1] - 3 <= c <= o[3] + 3 and o[2] > a and o[0] < b and (o[2] - o[0]) >= (o[3] - o[1]):
                cuts.append((max(a, o[0]), min(b, o[2]), op))
        cuts.sort(key=lambda t_: t_[0])
        spans, cur = [], a
        for c0, c1, op in cuts:
            if c0 > cur:
                spans.append((cur, c0, z1))
            if op["kind"].startswith("window"):
                sill = HT["bath_sill"] if op["kind"] == "window_high" else HT["window_sill"]
                spans.append((c0, c1, min(z1, sill)))
            cur = max(cur, c1)
        if cur < b:
            spans.append((cur, b, z1))
        for s0, s1, zt in spans:
            if ax == "x":
                x0_, y0_, x1_, y1_ = R([c, s0, c, s1])
            else:
                x0_, y0_, x1_, y1_ = R([s0, c, s1, c])
            clad(mb, x0_, y0_, x1_, y1_, z0, zt, face_of[side], t, m)


def clad(mb, x0, y0, x1, y1, z0, z1, face, t=0.015, m=0):
    """cladding panel on a wall face: face in n/s/e/w (direction the panel faces)"""
    if face == "e":
        mb.box(x0, y0, z0, x0 + t, y1, z1, m)
    elif face == "w":
        mb.box(x1 - t, y0, z0, x1, y1, z1, m)
    elif face == "n":
        mb.box(x0, y0, z0, x1, y0 + t, z1, m)
    else:
        mb.box(x0, y1 - t, z0, x1, y1, z1, m)



# ---------------------------------------------------------------- fixtures (bath, kitchen, bedroom)
def toilet(T):
    """one-piece toilet with washlet and low tank (TOTO type). local: tank against the wall at y=-0.34, front = +y"""
    m = MB(T)
    m.sq(0, 0.03, 0.17, 0.15, 0.21, 0.17, e1=0.4, e2=0.75, m=0)          # trapway body
    m.sq(0, 0.07, 0.33, 0.19, 0.27, 0.075, e1=0.45, e2=0.85, m=0)        # bowl
    m.sq(0, 0.06, 0.42, 0.185, 0.255, 0.022, e1=0.3, e2=0.85, m=0)       # seat + closed lid
    m.sq(0, -0.19, 0.45, 0.17, 0.09, 0.045, e1=0.3, e2=0.3, m=0)         # washlet unit
    m.sq(0, -0.255, 0.66, 0.205, 0.085, 0.2, e1=0.2, e2=0.22, m=0)       # tank
    return m


def vessel(mb, x, y, z, r=0.2, h=0.14, oval=1.0):
    """round vessel basin sitting on a counter (outer wall, rolled rim, inner bowl)"""
    prof = [(0.0, 0.0), (0.3, 0.0), (0.36, 0.03), (0.75, 0.3), (0.95, 0.72), (1.0, 1.0), (0.94, 1.03), (0.86, 0.66),
            (0.6, 0.3), (0.25, 0.17), (0.0, 0.16)]
    mb.lathe(x, y, z, [(r * a, h * b) for a, b in prof], seg=40, m=0)


def wall_spout(mb, x, y, z, dx, dy, L=0.17, m=0):
    """wall-mounted basin spout + lever, projecting along (dx, dy)"""
    mb.cylt((x, y, z), (x + dx * 0.012, y + dy * 0.012, z), 0.032, 0.032, 20, m)
    mb.cylt((x, y, z), (x + dx * L, y + dy * L, z), 0.011, 0.01, 12, m)
    mb.cylt((x + dx * 0.012, y + dy * 0.012, z + 0.09), (x + dx * 0.06, y + dy * 0.06, z + 0.09), 0.008, 0.008, 10, m)
    mb.cylt((x, y, z + 0.09), (x + dx * 0.012, y + dy * 0.012, z + 0.09), 0.022, 0.022, 16, m)


def gooseneck(mb, x, y, z, dx, dy, h=0.36, reach=0.22, m=0):
    """kitchen gooseneck faucet on the counter, spout pointing along (dx, dy)"""
    pts = [(x, y, z), (x, y, z + h)]
    for k in range(1, 7):
        a = math.pi * k / 6
        rr = reach / 2
        pts.append((x + dx * rr * (1 - math.cos(a)), y + dy * rr * (1 - math.cos(a)), z + h + rr * math.sin(a) * 0.8))
    pts.append((x + dx * reach, y + dy * reach, z + h - 0.08))
    mb.cyl(x, y, z, z + 0.04, 0.03, 16, m)
    mb.path(pts, 0.012, 10, m)
    mb.cylt((x - dy * 0.03, y + dx * 0.03, z + 0.12), (x - dy * 0.1, y + dx * 0.1, z + 0.14), 0.007, 0.006, 8, m)


def towel_bar(x, y, z, L, dx, dy, mats=("chrome", "towel"), folds=1):
    """bar parallel to a wall at (x, y) running along (dx, dy); towel(s) draped over it. returns (metal MB, towel MB)"""
    nx, ny = dy, -dx                                  # wall normal (into the room)
    bar, tw = MB(), MB()
    a = (x - dx * L / 2 + nx * 0.07, y - dy * L / 2 + ny * 0.07, z); b = (x + dx * L / 2 + nx * 0.07, y + dy * L / 2 + ny * 0.07, z)
    bar.cylt(a, b, 0.009, 0.009, 10, 0)
    for p in ((x - dx * L / 2, y - dy * L / 2), (x + dx * L / 2, y + dy * L / 2)):
        bar.cylt((p[0], p[1], z), (p[0] + nx * 0.075, p[1] + ny * 0.075, z), 0.008, 0.008, 8, 0)
        bar.cylt((p[0], p[1], z), (p[0] + nx * 0.01, p[1] + ny * 0.01, z), 0.022, 0.022, 14, 0)
    for k in range(folds):
        w = L * 0.78 / folds
        cx, cy = x + dx * (k - (folds - 1) / 2) * (L / folds) + nx * 0.07, y + dy * (k - (folds - 1) / 2) * (L / folds) + ny * 0.07
        T = Matrix.Translation((cx, cy, z - 0.24)) @ Matrix.Rotation(math.atan2(dy, dx), 4, "Z")
        t = MB(T); t.sq(0, 0, 0, w / 2, 0.024, 0.26, e1=0.18, e2=0.25, nu=20, nv=10, m=0)
        base = len(tw.v); tw.v += t.v; tw.f += [[i + base for i in f_] for f_ in t.f]; tw.m += t.m; tw.rot += t.rot
    return bar, tw


def towel_stack(x, y, z, w=0.32, d=0.24, n=3, rot=0.0):
    t = MB(Matrix.Translation((x, y, z)) @ Matrix.Rotation(rot, 4, "Z"))
    for k in range(n):
        t.sq(0, 0, 0.03 + k * 0.055, w / 2, d / 2, 0.028, e1=0.35, e2=0.25, nu=20, nv=8, m=0)
    return t


def rain_shower(mb, x, y, zc, wall=None, m=0):
    """ceiling-mounted rain head; optional wall mixer + hand shower on a slide rail at wall=(wx, wy, nx, ny)"""
    mb.cylt((x, y, zc), (x, y, zc - 0.25), 0.012, 0.012, 10, m)
    mb.cyl(x, y, zc - 0.27, zc - 0.25, 0.15, 32, m)
    if wall:
        wx, wy, nx, ny = wall
        mb.cylt((wx, wy, 1.05), (wx + nx * 0.06, wy + ny * 0.06, 1.05), 0.035, 0.03, 16, m)       # mixer
        mb.cylt((wx + nx * 0.06, wy + ny * 0.06, 1.05), (wx + nx * 0.07, wy + ny * 0.07, 1.05), 0.03, 0.03, 16, m)
        mb.cylt((wx + nx * 0.03, wy + ny * 0.03, 1.15), (wx + nx * 0.03, wy + ny * 0.03, 1.95), 0.011, 0.011, 10, m)  # rail
        mb.cylt((wx + nx * 0.06, wy + ny * 0.06, 1.62), (wx + nx * 0.07, wy + ny * 0.07, 1.82), 0.015, 0.03, 12, m)   # hand shower
        mb.cyl(wx + nx * 0.07, wy + ny * 0.07, 1.82, 1.84, 0.045, 20, m)


def nightstand(fx, I, x, y, w=0.46, d=0.4, h=0.46, rot=0.0):
    """floating-look ash night table with one drawer (groove + finger pull); front = local +y"""
    T = Matrix.Translation((x, y, 0)) @ Matrix.Rotation(rot, 4, "Z")
    m = MB(T)
    m.box(-w / 2, -d / 2, 0.06, w / 2, d / 2, h, 0)
    m.box(-w / 2 + 0.04, -d / 2 + 0.04, 0.0, w / 2 - 0.04, d / 2 - 0.04, 0.06, 1)
    m.box(-w / 2 + 0.01, d / 2, h - 0.15, w / 2 - 0.01, d / 2 + 0.002, h - 0.144, 1)
    m.box(-0.06, d / 2, h - 0.06, 0.06, d / 2 + 0.003, h - 0.05, 1)
    return m


def table_lamp(x, y, z, h=0.44, r=0.15):
    """ceramic base + linen drum shade (emissive) with a real bulb"""
    b = MB(); b.lathe(x, y, z, [(0.0, 0.0), (0.06, 0.0), (0.085, 0.05), (0.09, 0.12), (0.06, 0.2), (0.02, 0.24), (0.0, 0.245)], seg=24)
    b.cylt((x, y, z + 0.24), (x, y, z + h - 0.06), 0.006, 0.006, 8, 0)
    s = MB(); s.cyl(x, y, z + h - 0.2, z + h, r, 32, 0, caps=False)
    light("POINT", (x, y, z + h - 0.11), 14, (1.0, 0.76, 0.5), size=0.04)
    return b, s


def pane(mb, p0, p1, z0, z1, m=0):
    """single-sheet vertical glass (no thickness)"""
    mb.face([(p0[0], p0[1], z0), (p1[0], p1[1], z0), (p1[0], p1[1], z1), (p0[0], p0[1], z1)], m)


def rug(x0, y0, x1, y1, z=0.0):
    m = MB(); m.sq((x0 + x1) / 2, (y0 + y1) / 2, z + 0.006, abs(x1 - x0) / 2, abs(y1 - y0) / 2, 0.006, e1=0.5, e2=0.06, nu=48, nv=4)
    return m


def washer(fx, I, x, y, z, front, stacked=True):
    """drum washer (+ dryer on top) against a wall; front = axis-aligned unit vector the doors face"""
    fxv, fyv = front
    w, d, h = 0.6, 0.62, 0.85
    hx, hy = (w / 2, d / 2) if fyv else (d / 2, w / 2)
    px, py = abs(fyv), abs(fxv)                           # along the front face
    for k in range(2 if stacked else 1):
        z0 = z + k * (h + 0.02)
        fx.box(x - hx, y - hy, z0, x + hx, y + hy, z0 + h, I["appliance"])
        cx, cy = x + fxv * hx, y + fyv * hy               # centre of the front face
        fx.cylt((cx, cy, z0 + 0.42), (cx + fxv * 0.02, cy + fyv * 0.02, z0 + 0.42), 0.2, 0.19, 32, I["chrome"])
        fx.cylt((cx + fxv * 0.02, cy + fyv * 0.02, z0 + 0.42), (cx + fxv * 0.026, cy + fyv * 0.026, z0 + 0.42), 0.15, 0.15, 32, I["induction"])
        fx.box(min(cx, cx + fxv * 0.004) - 0.25 * px, min(cy, cy + fyv * 0.004) - 0.25 * py, z0 + h - 0.12,
               max(cx, cx + fxv * 0.004) + 0.25 * px, max(cy, cy + fyv * 0.004) + 0.25 * py, z0 + h - 0.04, I["graphite"])


# ============================================================== wa fit-out
def build_wa():
    fx = MB()      # fitted millwork & furniture (materials by index below)
    FX = ["ash", "cedar", "walnut", "black", "fabric_grey", "linen", "cement_tile", "washi", "fusuma", "tatami_a", "tatami_b",
          "tatami_g", "cushion", "indigo", "bedding", "dark_wood", "marble", "porcelain", "stone", "hinoki", "bamboo", "ceramic",
          "scroll", "mirror", "steel", "plaster", "water", "chrome", "appliance", "induction", "graphite", "deck"]
    I = {k: i for i, k in enumerate(FX)}
    glm = MB()      # glass in shoji (雪見)
    gsh = MB()      # thin shower screens
    lamp = MB()     # emissive paper / LEDs
    LM = ["lamp_paper", "led_warm", "downlight"]
    J = {k: i for i, k in enumerate(LM)}
    sub = []        # sub-builders with their own transforms -> merged by material lists

    # ---------- ceilings: floating panels with perimeter coves (indirect light), cedar board ceiling in the washitsu
    cm, cove = MB(), MB()
    for rid in ("PUB", "MBR", "BR2", "BR4", "BR5", "HALL"):
        if rid == "HALL":
            continue
        rm = room(rid)
        pts = [P(x, y) for x, y in rm["poly"]]
        inner = inset_ortho(pts, 0.18)
        cm.prism(inner, CH, CH + 0.03, 0, sides=True, bottom=True)
        # LED strip lying on the panel edge, lighting the slab and the upper walls
        for i in range(len(inner)):
            a, b = inner[i], inner[(i + 1) % len(inner)]
            cove.obox(a, b, 0.03, CH + 0.03, CH + 0.05, 0)
    for rid in ("KIT", "MBA", "BA2", "BA3"):
        rm = room(rid)
        cm.prism([P(x, y) for x, y in rm["poly"]], CH - 0.05 if rid != "KIT" else CH, CH + 0.03, 0)
    cm.build("A_ceiling", ["ceiling"])
    cove.build("E_cove", ["led_warm"])

    # ---------- washitsu (former bedroom 3): raised tatami platform, tokonoma, 雪見障子, shoji to the living room
    wx0, wy0, wx1, wy1 = R([390, 133, 538, 316])
    PH = 0.36
    fx.box(wx0, wy0, 0, wx1, wy1, PH - 0.06, I["ash"])
    fx.box(wx1 - 0.08, wy0, PH - 0.06, wx1, wy1, PH, I["cedar"])                 # 框 (front edge)
    tx0 = wx0 + 0.62                                                             # tokonoma depth on the west
    nx, ny = 3, 5
    for i in range(nx):
        for j in range(ny):
            a0 = tx0 + (wx1 - 0.08 - tx0) * i / nx; a1 = tx0 + (wx1 - 0.08 - tx0) * (i + 1) / nx
            b0 = wy0 + (wy1 - wy0) * j / ny; b1 = wy0 + (wy1 - wy0) * (j + 1) / ny
            fx.box(a0 + 0.002, b0 + 0.002, PH - 0.06, a1 - 0.002, b1 - 0.002, PH, I["tatami_g"], rot=(i + j) % 2 == 1)
    tk_split = wy0 + (wy1 - wy0) * 0.52
    fx.box(wx0, tk_split, PH - 0.06, tx0, wy1, PH + 0.12, I["walnut"])          # 床板 (tokonoma floor)
    fx.box(tx0 - 0.07, tk_split, PH - 0.06, tx0, wy1, PH + 0.13, I["dark_wood"]) # 床框
    fx.box(tx0 - 0.1, tk_split - 0.06, PH, tx0 - 0.02, tk_split + 0.02, CH, I["cedar"])  # 床柱
    fx.box(wx0 + 0.005, tk_split + 0.5, 0.95, wx0 + 0.02, wy1 - 0.5, 2.15, I["scroll"])  # 掛軸
    fx.box(wx0 + 0.004, tk_split + 0.52, 1.0, wx0 + 0.021, wy1 - 0.52, 2.0, I["ash"])
    for sy in (-1, 1):   # oshiire with fusuma on the south half of the west side
        pass
    for k in range(2):
        b0 = wy0 + (tk_split - wy0) * k / 2; b1 = wy0 + (tk_split - wy0) * (k + 1) / 2
        fx.box(tx0 - 0.05, b0 + 0.004, PH, tx0 - 0.02, b1 - 0.004, CH - 0.25, I["fusuma"])
        fx.cyl(tx0 - 0.055, (b0 + b1) / 2 + (0.3 if k else -0.3), 1.0, 1.02, 0.03, 12, I["dark_wood"])
    fx.box(wx0, wy0, CH - 0.25, tx0, tk_split, CH, I["cedar"])
    # 竿縁天井: cedar boards and battens
    fx.box(wx0, wy0, CH - 0.05, wx1, wy1, CH - 0.03, I["cedar"])
    k = 0
    y = wy0 + 0.45
    while y < wy1 - 0.1:
        fx.box(wx0, y - 0.015, CH - 0.08, wx1, y + 0.015, CH - 0.05, I["dark_wood"]); y += 0.45
    fx.box(wx0, wy0, 2.05, wx1, wy0 + 0.1, 2.12, I["cedar"])                        # 長押 on the window wall
    fx.box(wx1 - 0.09, wy0, 2.28, wx1 + 0.02, wy1, 2.36, I["cedar"])                  # 鴨居 over the shoji
    fx.box(wx1 - 0.05, wy0, 2.36, wx1 - 0.02, wy1, CH, I["plaster"])                  # 小壁
    # shoji between washitsu and living room: 4 panels, two slid aside
    W4 = (wy1 - wy0) / 4
    pos = [(wy1 - W4, wy1, 0.022), (wy1 - W4 - 0.06, wy1 - 0.06, -0.022), (wy0, wy0 + W4, 0.022), (wy0 + 0.06, wy0 + W4 + 0.06, -0.022)]
    for b0, b1, off in pos:
        shoji(fx, (wx1 - 0.04 + off, b0), (wx1 - 0.04 + off, b1), PH, 2.28, I["ash"], I["washi"], grid=(3, 7), glass_low=0.0)
    # 雪見障子 on the garden window (north wall)
    gx0, gy0, gx1, gy1 = R([428, 125, 507, 133])
    Lw = gx1 - gx0
    for i, off in ((0, 0.0), (1, 0.03)):
        a, b = gx0 + Lw * 0.5 * i * 0.06, gx0 + Lw * 0.5 * (1 + i * 0.06)          # right half slid open
        shoji(fx, (a, gy0 - 0.06 - off), (b, gy0 - 0.06 - off), HT["window_sill"], HT["window_head"], I["ash"], I["washi"],
              grid=(2, 5), glass_low=0.55, gmb=glm)
    # fusuma closing the former bedroom door to the hall
    fu0, fv0, fu1, fv1 = R([388, 316, 436, 322])
    fx.box(fu0 + 0.01, (fv0 + fv1) / 2 - 0.015, 0.0, fu1 - 0.01, (fv0 + fv1) / 2 + 0.015, HT["door"] - 0.01, I["fusuma"])
    fx.cyl(fu1 - 0.12, fv0 - 0.001, 0.95, 1.0, 0.03, 12, I["dark_wood"])
    # zataku + zaisu + pendant
    cx, cy = (tx0 + wx1) / 2, (wy0 + wy1) / 2
    fx.box(cx - 0.6, cy - 0.42, PH + 0.3, cx + 0.6, cy + 0.42, PH + 0.34, I["walnut"])
    for sx in (-1, 1):
        for sy in (-1, 1):
            fx.box(cx + sx * 0.5 - 0.035, cy + sy * 0.32 - 0.035, PH, cx + sx * 0.5 + 0.035, cy + sy * 0.32 + 0.035, PH + 0.3, I["walnut"])
    for ang, dx, dy in ((0, 0, -0.78), (math.pi, 0, 0.78), (math.pi / 2, 0.88, 0), (-math.pi / 2, -0.88, 0)):
        wd, cu = zaisu(Matrix.Translation((cx + dx, cy + dy, PH)) @ Matrix.Rotation(ang, 4, "Z"))
        sub.append((wd, ["lacquer"])); sub.append((cu, ["zabuton"], True))
    sub.append((woven_pendant(cx, cy, 1.85), ["bamboo"]))

    # ---------- garden in the planter (枯山水): gravel, rocks, a maple, bamboo fence, stone lantern
    px0, py0, px1, py1 = R([415, 72, 517, 125])
    lattice(fx, (px0, py1 - 0.03), (px1, py1 - 0.03), 0.0, 1.9, I["bamboo"], pitch=0.06, slat=0.045, depth=0.04, frame=False)
    fx.box(px0, py1 - 0.08, 0.3, px1, py1 - 0.05, 0.36, I["dark_wood"]); fx.box(px0, py1 - 0.08, 1.4, px1, py1 - 0.05, 1.46, I["dark_wood"])
    lx, ly = px0 + 0.35, py0 + 0.4
    fx.box(lx - 0.16, ly - 0.16, 0, lx + 0.16, ly + 0.16, 0.08, I["stone"])
    fx.cyl(lx, ly, 0.08, 0.5, 0.07, 12, I["stone"])
    fx.box(lx - 0.14, ly - 0.14, 0.5, lx + 0.14, ly + 0.14, 0.56, I["stone"])
    fx.box(lx - 0.1, ly - 0.1, 0.56, lx + 0.1, ly + 0.1, 0.76, I["stone"])
    fx.cyl(lx, ly, 0.76, 0.86, 0.22, 4, I["stone"])
    fx.cyl(lx, ly, 0.86, 0.94, 0.04, 8, I["stone"])
    lamp.box(lx - 0.07, ly - 0.07, 0.6, lx + 0.07, ly + 0.07, 0.72, J["lamp_paper"])
    light("POINT", (lx, ly, 0.66), 8, (1.0, 0.7, 0.4), size=0.03)
    light("SPOT", (px1 - 0.2, py0 + 0.15, 0.1), 60, (1.0, 0.85, 0.65), size=0.03, spot=(math.radians(50), 0.5),
          rot=(math.radians(-25), math.radians(-15), 0))
    # stepping stones
    for i, (sx, sy, r_) in enumerate(((0.9, 0.5, 0.17), (1.25, 0.62, 0.15), (1.55, 0.45, 0.13))):
        fx.cyl(px0 + sx, py0 + sy, -0.06, 0.02, r_, 10, I["stone"], ry=r_ * 0.8)

    # ---------- living room
    lvx0, lvy0, lvx1, lvy1 = R([538, 133, 782, 433])
    tvx = PX(782)
    ty0, ty1 = PY(385), PY(150)
    clad(fx, tvx - 0.02, ty0, tvx, ty1, 0.2, CH, "w", 0.02, I["cement_tile"])
    fx.box(tvx - 0.47, ty0, 0.03, tvx - 0.02, ty1, 0.2, I["ash"])                       # 台度 (low plinth)
    fx.box(tvx - 0.44, ty0 + 0.02, 0.0, tvx - 0.05, ty1 - 0.02, 0.03, I["black"])
    fcy = (ty0 + ty1) / 2 - 0.3
    fx.box(tvx - 0.09, fcy - 1.55, 0.72, tvx - 0.02, fcy + 1.55, 0.78, I["cedar"])      # cedar frame
    fx.box(tvx - 0.09, fcy - 1.55, 2.12, tvx - 0.02, fcy + 1.55, 2.18, I["cedar"])
    fx.box(tvx - 0.09, fcy - 1.55, 0.72, tvx - 0.02, fcy - 1.49, 2.18, I["cedar"])
    fx.box(tvx - 0.09, fcy + 1.49, 0.72, tvx - 0.02, fcy + 1.55, 2.18, I["cedar"])
    fx.box(tvx - 0.04, fcy - 1.49, 0.78, tvx - 0.02, fcy + 1.49, 2.12, I["cedar"])      # 秋田杉 backing
    fx.box(tvx - 0.08, fcy - 1.3, 0.95, tvx - 0.04, fcy + 0.35, 1.9, I["black"])        # television
    lattice(fx, (tvx - 0.07, fcy + 0.62), (tvx - 0.07, fcy + 1.45), 0.8, 2.1, I["cedar"], pitch=0.035, slat=0.014, depth=0.025)
    for sy in (-1, 1):   # tall speakers
        fx.box(tvx - 0.4, fcy + sy * 1.9 - 0.12, 0.2, tvx - 0.14, fcy + sy * 1.9 + 0.12, 1.2, I["black"])
    # tatami rug (Ryukyu squares, charcoal / grey), sofa, oval table, torii chairs
    rx, ry = tvx - 2.2, fcy
    for i in range(2):
        for j in range(3):
            a0 = rx - 0.88 + i * 0.88; b0 = ry - 1.32 + j * 0.88
            fx.box(a0 + 0.003, b0 + 0.003, 0.0, a0 + 0.877, b0 + 0.877, 0.05, I["tatami_b"] if (i + j) % 2 else I["tatami_a"], rot=(i + j) % 2 == 1)
    wd, fb = sofa(fx, Matrix.Translation((rx - 1.45, ry, 0)) @ Matrix.Rotation(-math.pi / 2, 4, "Z"), w=2.4, d=0.95)
    sub.append((wd, ["ash"])); sub.append((fb, ["sofa_fabric"], True))
    sub.append((oval_table(fx, rx + 0.05, ry, 0.62, 0.38, 0.38, 0, rot=math.pi / 2), ["walnut"]))
    wd, cu = zaisu(Matrix.Translation((rx + 0.15, ry + 1.0, 0.05)) @ Matrix.Rotation(math.pi, 4, "Z"))
    sub.append((wd, ["lacquer"])); sub.append((cu, ["sofa_fabric"], True))
    fm, pm = andon(rx - 1.45, ry - 1.55, 0.0)
    sub.append((fm, ["ash"])); sub.append((pm, ["lamp_paper"]))
    fm, pm = andon(rx - 1.45, ry + 1.55, 0.0, h=0.45)
    sub.append((fm, ["ash"])); sub.append((pm, ["lamp_paper"]))
    # 雪見障子 inside the balcony slider (4 panels, half open)
    sx0, sy0, sx1, sy1 = R([560, 125, 704, 133])
    Ls = sx1 - sx0
    for i, (a, b, off) in enumerate(((0, Ls / 4, 0), (Ls / 4 - 0.05, Ls / 2 - 0.05, 0.03), (Ls * 0.75, Ls, 0), (Ls * 0.75 - 0.3, Ls - 0.3, 0.03))):
        shoji(fx, (sx0 + a, sy0 - 0.06 - off), (sx0 + b, sy0 - 0.06 - off), 0.0, HT["slider"] - 0.03, I["ash"], I["washi"],
              grid=(2, 8), glass_low=0.75, gmb=glm)
    downlight_grid(lamp_dl := MB(), rx - 0.2, ry + 0.2, 2, 0.16, 30)
    sub.append((lamp_dl, ["downlight"]))
    dl2 = MB(); downlight_grid(dl2, (lvx0 + lvx1) / 2 - 0.4, PY(165), 2, 0.16, 25); sub.append((dl2, ["downlight"]))
    place_model("potted_plant_04", sx1 - 0.25, sy0 - 0.45, 0.0, 0.3, height=1.6, name="plant_lv")

    # ---------- dining: table, sled-leg chairs, glass pendants, 栓木 grid shelving with lattice panels
    dcx, dcy = P(560, 445)
    fx.box(dcx - 1.2, dcy - 0.5, 0.67, dcx + 1.2, dcy + 0.5, 0.7, I["ash"])
    for sx in (-1, 1):
        fx.box(dcx + sx * 1.0 - 0.04, dcy - 0.4, 0.0, dcx + sx * 1.0 + 0.04, dcy + 0.4, 0.67, I["ash"])
    fx.box(dcx - 1.0, dcy - 0.03, 0.12, dcx + 1.0, dcy + 0.03, 0.18, I["ash"])
    for k in range(3):
        for sy in (-1, 1):
            chx = dcx + (k - 1) * 0.72; chy = dcy + sy * 0.68
            T = Matrix.Translation((chx, chy, 0)) @ Matrix.Rotation(0 if sy < 0 else math.pi, 4, "Z")
            wd, fb = dining_chair(T)
            sub.append((wd, ["walnut"])); sub.append((fb, ["chair_fabric"], True))
    for sx in (-0.55, 0.55):
        sub.append((cone_pendant(dcx + sx, dcy, 1.45), ["ceramic", "black"]))
    shx0, shy0, shx1, shy1 = R([448, 373, 470, 516])
    fx.box(shx0, shy0, 0, shx1, shy1, 0.02, I["ash"])
    cols, rows = 4, 6
    for i in range(cols + 1):
        y = shy0 + (shy1 - shy0) * i / cols
        fx.box(shx0, y - 0.015, 0, shx1, y + 0.015, CH, I["ash"])
    for j in range(rows + 1):
        z = 0.1 + (CH - 0.1) * j / rows
        fx.box(shx0, shy0, z - 0.015, shx1, shy1, z + 0.015, I["ash"])
    fx.box(shx0, shy0, 0, shx0 + 0.02, shy1, CH, I["cedar"])
    for (a, b) in ((0, 0.28), (0.72, 1.0)):
        lattice(fx, (shx1 + 0.02, shy0 + (shy1 - shy0) * a), (shx1 + 0.02, shy0 + (shy1 - shy0) * b), 0.02, CH - 0.02, I["cedar"], pitch=0.04, slat=0.015, depth=0.02)
    place_model("ceramic_vase_02", (shx0 + shx1) / 2, shy0 + (shy1 - shy0) * 0.375, 0.1 + (CH - 0.1) * 3 / 6 + 0.015, height=0.3, name="vase_shelf")
    dl = MB(); downlight_grid(dl, *P(610, 350), 2, 0.16, 25); sub.append((dl, ["downlight"]))

    # ---------- genkan: stone floor, 上がり框, floating shoe cabinet with lattice, cedar slat wall
    gx0_, gy0_, gx1_, gy1_ = R([651, 598, 736, 666])
    fx.box(gx0_, gy0_, 0.0, gx1_, gy1_, 0.006, I["stone"])
    fx.box(gx0_, gy1_ - 0.1, 0.0, gx1_, gy1_, 0.03, I["dark_wood"])
    scx0, scy0, scx1, scy1 = R([631, 525, 651, 633])
    fx.box(scx0, scy0, 0.25, scx1, scy1, 2.2, I["ash"])
    lattice(fx, (scx1 + 0.01, scy0 + 0.05), (scx1 + 0.01, scy1 - 0.05), 0.3, 2.15, I["cedar"], pitch=0.04, slat=0.015, depth=0.02)
    lamp.box(scx0 + 0.05, scy0 + 0.05, 0.23, scx1 - 0.02, scy1 - 0.05, 0.245, J["led_warm"])
    swx = PX(750)
    y = PY(591)
    while y < PY(440) - 0.05:
        fx.box(swx - 0.035, y, 0.0, swx, y + 0.04, CH, I["cedar"]); y += 0.075
    dl = MB(); downlight_grid(dl, *P(692, 560), 2, 0.16, 20); sub.append((dl, ["downlight"]))
    place_model("potted_plant_01", *P(720, 640), 0.006, height=0.9, name="plant_genkan")

    # ---------- kitchen: ash run with stone top, undermount sink + gooseneck, induction under a slim hood,
    #            panel fridge column, back counter with open shelves, sliding door, under-cabinet light
    kx0, ky0, kx1, ky1 = R([415, 525, 625, 633])
    fr0 = kx1 - 0.65                                                              # fridge column
    ks0, ks1, ksy0, ksy1 = kx0 + 0.95, kx0 + 1.65, ky0 + 0.1, ky0 + 0.52          # sink cut-out
    ck0 = kx0 + 2.55                                                              # induction hob
    fx.box(kx0, ky0, 0.1, fr0, ky0 + 0.6, 0.86, I["ash"]); fx.box(kx0, ky0, 0.0, fr0, ky0 + 0.55, 0.1, I["black"])
    for a, b, c, d in ((kx0, ky0, ks0, ky0 + 0.62), (ks1, ky0, fr0, ky0 + 0.62), (ks0, ky0, ks1, ksy0), (ks0, ksy1, ks1, ky0 + 0.62)):
        fx.box(a, b, 0.86, c, d, 0.9, I["stone"])
    fx.well(ks0, ksy0, ks1, ksy1, 0.68, 0.9, I["chrome"])
    fx.cyl(ks0 + 0.35, (ksy0 + ksy1) / 2, 0.68, 0.682, 0.045, 16, I["graphite"])
    gooseneck(fx, (ks0 + ks1) / 2, ky0 + 0.05, 0.9, 0, 1, m=I["chrome"])
    fx.box(ck0, ky0 + 0.07, 0.9, ck0 + 0.76, ky0 + 0.56, 0.906, I["induction"])
    for dx_, dy_, r_ in ((0.2, 0.18, 0.1), (0.56, 0.18, 0.1), (0.2, 0.42, 0.08), (0.56, 0.42, 0.08)):
        fx.cyl(ck0 + dx_, ky0 + 0.07 + dy_, 0.906, 0.907, r_, 32, I["graphite"], caps=True)
    n = max(1, round((fr0 - kx0) / 0.6))
    for i in range(1, n):                                                         # door joints
        x = kx0 + (fr0 - kx0) * i / n
        fx.box(x - 0.003, ky0 + 0.6, 0.12, x + 0.003, ky0 + 0.603, 0.78, I["dark_wood"])
    fx.box(kx0, ky0 + 0.6, 0.79, fr0, ky0 + 0.606, 0.81, I["dark_wood"])          # pull channel
    for z in (0.32, 0.55):                                                        # drawers under the hob
        fx.box(ck0, ky0 + 0.6, z - 0.003, ck0 + 0.76, ky0 + 0.603, z + 0.003, I["dark_wood"])
    fx.box(kx0, ky0, 0.9, fr0, ky0 + 0.012, 1.5, I["marble"])                     # splashback
    fx.box(kx0, ky0, 1.5, fr0 - 0.02, ky0 + 0.35, 2.3, I["ash"])                  # wall units
    for i in range(1, n):
        x = kx0 + (fr0 - kx0) * i / n
        fx.box(x - 0.003, ky0 + 0.35, 1.52, x + 0.003, ky0 + 0.353, 2.28, I["dark_wood"])
    fx.box(ck0 - 0.02, ky0 + 0.012, 1.44, ck0 + 0.78, ky0 + 0.48, 1.5, I["steel"])  # slim hood
    for a, b in ((kx0 + 0.05, ck0 - 0.06), (ck0 + 0.82, fr0 - 0.08)):              # under-cabinet LED
        lamp.box(a, ky0 + 0.29, 1.495, b, ky0 + 0.32, 1.5, J["led_warm"])
        light("AREA", ((a + b) / 2, ky0 + 0.3, 1.48), 30 * (b - a), (1.0, 0.84, 0.66), size=(b - a, 0.05))
    fx.box(fr0, ky0, 0.0, kx1, ky0 + 0.65, 2.3, I["ash"])                         # fridge column (panel-ready)
    fx.box(fr0 + 0.01, ky0 + 0.65, 0.78, kx1 - 0.01, ky0 + 0.653, 0.786, I["dark_wood"])
    fx.box(fr0 + 0.01, ky0 + 0.65, 1.94, kx1 - 0.01, ky0 + 0.653, 1.946, I["dark_wood"])
    for z0_, z1_ in ((0.95, 1.75), (0.3, 0.68)):
        hx_ = fr0 + 0.07
        fx.cylt((hx_, ky0 + 0.69, z0_), (hx_, ky0 + 0.69, z1_), 0.011, 0.011, 10, I["steel"])
        for zz in (z0_ + 0.03, z1_ - 0.03):
            fx.cylt((hx_, ky0 + 0.65, zz), (hx_, ky0 + 0.69, zz), 0.007, 0.007, 8, I["steel"])
    bc0, bc1 = PX(420), PX(505)                                                   # back counter (north wall, west of the door)
    fx.box(bc0, ky1 - 0.45, 0.1, bc1, ky1, 0.86, I["ash"]); fx.box(bc0, ky1 - 0.4, 0.0, bc1, ky1, 0.1, I["black"])
    fx.box(bc0, ky1 - 0.47, 0.86, bc1, ky1, 0.9, I["stone"])
    for k in range(1, 3):
        x = bc0 + (bc1 - bc0) * k / 3
        fx.box(x - 0.003, ky1 - 0.453, 0.12, x + 0.003, ky1 - 0.45, 0.78, I["dark_wood"])
    fx.box(bc0, ky1 - 0.456, 0.79, bc1, ky1 - 0.45, 0.81, I["dark_wood"])
    for z in (1.42, 1.78):                                                        # open shelves
        fx.box(bc0, ky1 - 0.28, z, bc1, ky1, z + 0.03, I["ash"])
    lamp.box(bc0 + 0.05, ky1 - 0.26, 1.415, bc1 - 0.05, ky1 - 0.23, 1.42, J["led_warm"])
    light("AREA", ((bc0 + bc1) / 2, ky1 - 0.25, 1.40), 40, (1.0, 0.84, 0.66), size=(bc1 - bc0 - 0.1, 0.05))
    # sliding door (open, parked on the kitchen side of the wall)
    dk0 = PX(560)
    fx.box(dk0, ky1 - 0.065, 0.005, dk0 + 1.17, ky1 - 0.03, 2.13, I["ash"])
    fx.box(dk0 + 0.04, ky1 - 0.068, 0.95, dk0 + 0.06, ky1 - 0.064, 1.25, I["dark_wood"])
    fx.box(PX(508), ky1 - 0.075, 2.13, dk0 + 1.2, ky1 - 0.02, 2.16, I["dark_wood"])
    for p_ in ((470, 580), (565, 580)):
        dl = MB(); downlight_grid(dl, *P(*p_), 2, 0.16, 22); sub.append((dl, ["downlight"]))
    place_model("vintage_electric_kettle", bc0 + 0.35, ky1 - 0.24, 0.9, 2.6, name="kettle")
    place_model("wooden_cutting_board", ks1 + 0.42, ky0 + 0.3, 0.9, 0.15, name="board")
    place_model("pot_enamel_01", ck0 + 0.2, ky0 + 0.25, 0.907, 0.4, name="pot")
    place_model("wooden_bowl_01", bc0 + 0.35, ky1 - 0.14, 1.45, name="bowl")
    place_model("ceramic_vase_01", bc1 - 0.3, ky1 - 0.14, 1.81, height=0.24, name="vase_kit")
    place_model("wicker_basket_01", bc1 - 0.35, ky1 - 0.14, 1.45, name="basket_kit")

    # ---------- master bedroom
    mx0, my0, mx1, my1 = R([788, 133, 1004, 591])
    bx_, by_ = PX(788), PY(255)
    _f, _s = bed(Matrix.Translation((bx_ + 0.14, by_, 0)), w=1.9, l=2.15, head_h=1.05, head_w=3.4); sub.append((_f, ["ash", "black", "cedar"])); sub.append((_s, ["linen", "bedding"], True))
    sub.append((rug(bx_ + 1.2, by_ - 1.45, bx_ + 3.5, by_ + 1.45), ["rug"], True))
    for sy in (-1, 1):
        sub.append((nightstand(fx, I, bx_ + 0.4, by_ + sy * 1.33, w=0.5, rot=-math.pi / 2), ["ash", "dark_wood"]))
        b_, s_ = table_lamp(bx_ + 0.4, by_ + sy * 1.33, 0.46)
        sub.append((b_, ["ceramic"], True)); sub.append((s_, ["lamp_paper"]))
    ms0, _, ms1, _ = R([805, 125, 951, 133])
    msy = PY(133)
    Lm = ms1 - ms0
    for a, b, off in ((0, Lm / 4, 0), (Lm / 4, Lm / 2, 0.03), (Lm / 2 + 0.3, Lm * 0.75 + 0.3, 0), (Lm * 0.75, Lm, 0.03)):
        shoji(fx, (ms0 + a, msy - 0.06 - off), (ms0 + b, msy - 0.06 - off), 0.0, HT["slider"] - 0.03, I["ash"], I["washi"], grid=(4, 3))
    wardrobe(fx, P(1004, 591), P(1004, 400), 0.6, 0.0, CH, I["ash"], I["dark_wood"])
    wardrobe(fx, P(901, 591), P(1004 - 28, 591), 0.6, 0.0, CH, I["ash"], I["dark_wood"])
    for i, yy in enumerate((PY(150) - 0.55,)):
        for dxm in (-0.7, 0.7):
            cxm = (mx0 + mx1) / 2 + dxm
            T = Matrix.Translation((cxm, yy, 0)) @ Matrix.Rotation(math.pi, 4, "Z")
            wd, fb = lounge_chair(T)
            sub.append((wd, ["ash"])); sub.append((fb, ["sofa_fabric"], True))
    fx.cyl((mx0 + mx1) / 2, PY(150) - 0.55, 0.0, 0.42, 0.24, 24, I["walnut"])
    dl = MB(); downlight_grid(dl, (mx0 + mx1) / 2 + 0.6, by_, 2, 0.16, 20); sub.append((dl, ["downlight"]))

    # ---------- master bath: marble, hinoki tub, twin vessel basins on a cedar vanity under a layered wood cove,
    #            glass wet area (rain + hand shower, hinoki stool and bucket), washlet toilet, towels
    ZB = CH - 0.05                                                                # bath ceilings
    bx0, by0, bx1, by1 = R([756, 440, 896, 591])
    clad_room(fx, [756, 440, 896, 591], 0.0, ZB, I["marble"])
    tx0_, ty0_, tx1_, ty1_ = R([820, 548, 894, 589])
    fx.box(tx0_, ty0_, 0.0, tx1_, ty1_, 0.62, I["hinoki"], skip=("top",))
    fx.box(tx0_ + 0.05, ty0_ + 0.05, 0.08, tx1_ - 0.05, ty1_ - 0.05, 0.62, I["hinoki"], skip=("top",))
    fx.box(tx0_, ty0_, 0.6, tx1_, ty0_ + 0.05, 0.62, I["hinoki"]); fx.box(tx0_, ty1_ - 0.05, 0.6, tx1_, ty1_, 0.62, I["hinoki"])
    fx.box(tx0_, ty0_, 0.6, tx0_ + 0.05, ty1_, 0.62, I["hinoki"]); fx.box(tx1_ - 0.05, ty0_, 0.6, tx1_, ty1_, 0.62, I["hinoki"])
    fx.box(tx0_ + 0.05, ty0_ + 0.05, 0.47, tx1_ - 0.05, ty1_ - 0.05, 0.48, I["water"])
    wall_spout(fx, PX(896) - 0.012, (ty0_ + ty1_) / 2, 0.75, -1, 0, L=0.16, m=I["chrome"])           # tub filler
    vx0, vy0, vx1, vy1 = R([822, 440, 895, 466])
    fx.box(vx0, vy0, 0.42, vx1, vy1 - 0.01, 0.82, I["cedar"])
    fx.box(vx0 + 0.01, vy0 - 0.003, 0.618, vx1 - 0.01, vy0, 0.624, I["dark_wood"])              # drawer joints
    fx.box((vx0 + vx1) / 2 - 0.003, vy0 - 0.003, 0.44, (vx0 + vx1) / 2 + 0.003, vy0, 0.8, I["dark_wood"])
    fx.box(vx0, vy0 - 0.02, 0.82, vx1, vy1 - 0.01, 0.86, I["stone"])
    bas = MB()
    for bxc in (vx0 + 0.42, vx1 - 0.42):
        vessel(bas, bxc, vy1 - 0.3, 0.86, r=0.2, h=0.14)
        wall_spout(fx, bxc, vy1 - 0.012, 1.08, 0, -1, L=0.2, m=I["chrome"])
    sub.append((bas, ["porcelain"], True))
    sub.append((towel_stack((vx0 + vx1) / 2, vy1 - 0.25, 0.86, w=0.26, d=0.2, n=3), ["towel"], True))
    fx.box(vx0 + 0.1, vy1 - 0.03, 1.2, vx1 - 0.1, vy1 - 0.012, 1.95, I["mirror"])
    for k in range(3):
        fx.box(vx0 + 0.05 * k, vy1 - 0.1 - 0.06 * k, 2.0 + 0.08 * k, vx1 - 0.05 * k, vy1 - 0.012, 2.04 + 0.08 * k, I["cedar"])
    lamp.box(vx0 + 0.1, vy1 - 0.12, 1.99, vx1 - 0.1, vy1 - 0.1, 2.0, J["led_warm"])
    sub.append((toilet(Matrix.Translation((PX(778), PY(440) - 0.352, 0)) @ Matrix.Rotation(math.pi, 4, "Z")), ["porcelain"], True))
    fx.cylt((bx0 + 0.012, PY(470), 0.72), (bx0 + 0.1, PY(470), 0.72), 0.008, 0.008, 8, I["chrome"])       # paper holder
    fx.cylt((bx0 + 0.1, PY(470) + 0.08, 0.72), (bx0 + 0.1, PY(470) - 0.08, 0.72), 0.008, 0.008, 8, I["chrome"])
    br_, tw_ = towel_bar(PX(805), PY(440) - 0.012, 1.05, 0.5, 1, 0); sub.append((br_, ["chrome"])); sub.append((tw_, ["towel"], True))
    shx = PX(820)
    pane(gsh, (shx, PY(591) + 0.012), (shx, PY(525)), 0.02, 2.1)                                # wet-area screens
    pane(gsh, (bx0 + 0.012, PY(525)), (PX(800), PY(525)), 0.02, 2.1)
    fx.box(shx - 0.012, PY(591), 2.1, shx + 0.012, PY(525), 2.13, I["chrome"])
    fx.box(bx0, PY(525) - 0.012, 2.1, PX(800), PY(525) + 0.012, 2.13, I["chrome"])
    fx.box(bx0 + 0.02, PY(591) + 0.1, 0.0, shx - 0.02, PY(525) - 0.02, 0.02, I["stone"])
    fx.box(bx0 + 0.05, PY(591) + 0.14, 0.02, shx - 0.06, PY(591) + 0.19, 0.022, I["chrome"])     # linear drain
    rain_shower(fx, PX(790), PY(560), ZB, wall=(bx0 + 0.012, PY(560), 1, 0), m=I["chrome"])
    place_model("wooden_stool_01", PX(795), PY(566), 0.02, 0.3, name="bath_stool")
    place_model("wooden_bucket_01", PX(772), PY(580), 0.02, 1.0, name="bath_bucket")
    light("AREA", ((bx0 + bx1) / 2, (by0 + by1) / 2, ZB - 0.03), 40, (1.0, 0.85, 0.7), size=0.5, name="bath_fill")
    for p_ in ((778, 492), (858, 520), (857, 568)):
        dl = MB(); downlight_grid(dl, *P(*p_), 1, 0.16, 18, z=ZB); sub.append((dl, ["downlight"]))

    # ---------- bedrooms 2, 4, 5: platform beds with night tables and lamps, rugs, shoji on windows, wardrobes, cove
    b2x, b2y = PX(206) + 0.14, PY(230)
    _f, _s = bed(Matrix.Translation((b2x, b2y, 0)), w=1.6, l=2.05, head_h=0.9); sub.append((_f, ["ash", "black", "cedar"])); sub.append((_s, ["linen", "bedding"], True))
    sub.append((rug(b2x + 0.9, b2y - 1.2, b2x + 3.0, b2y + 1.2), ["rug"], True))
    for sy in (-1, 1):
        sub.append((nightstand(fx, I, b2x + 0.24, b2y + sy * 1.13, w=0.42, rot=-math.pi / 2), ["ash", "dark_wood"]))
        b_, s_ = table_lamp(b2x + 0.24, b2y + sy * 1.13, 0.46, h=0.4, r=0.13)
        sub.append((b_, ["ceramic"], True)); sub.append((s_, ["lamp_paper"]))
    wardrobe(fx, P(383, 316), P(383, 133), 0.6, 0.0, CH, I["ash"], I["dark_wood"])
    ax0, ay0, ax1, ay1 = R([219, 66, 334, 74])
    for i in range(3):
        a, b = ax0 + (ax1 - ax0) * i / 3, ax0 + (ax1 - ax0) * (i + 1) / 3
        shoji(fx, (a, ay0 - 0.06 - 0.03 * (i % 2)), (b, ay0 - 0.06 - 0.03 * (i % 2)), HT["window_sill"], HT["window_head"], I["ash"], I["washi"], grid=(2, 5))
    dl = MB(); downlight_grid(dl, b2x + 1.6, b2y, 2, 0.16, 18); sub.append((dl, ["downlight"]))
    b4x, b4y = PX(220), PY(518) + 0.14
    _f, _s = bed(Matrix.Translation((b4x, b4y, 0)) @ Matrix.Rotation(math.pi / 2, 4, "Z"), w=1.6, l=2.0, head_h=0.9); sub.append((_f, ["ash", "black", "cedar"])); sub.append((_s, ["linen", "bedding"], True))
    sub.append((rug(b4x - 1.25, b4y + 1.0, b4x + 1.25, b4y + 2.75), ["rug"], True))
    for sx in (-1, 1):
        sub.append((nightstand(fx, I, b4x + sx * 1.13, b4y + 0.24, w=0.42), ["ash", "dark_wood"]))
        b_, s_ = table_lamp(b4x + sx * 1.13, b4y + 0.24, 0.46, h=0.4, r=0.13)
        sub.append((b_, ["ceramic"], True)); sub.append((s_, ["lamp_paper"]))
    wd, fb = lounge_chair(Matrix.Translation(P(145, 405) + (0,)) @ Matrix.Rotation(-0.75 * math.pi, 4, "Z"))
    sub.append((wd, ["ash"])); sub.append((fb, ["chair_fabric"], True))
    wardrobe(fx, P(331, 518), P(331, 380), 0.55, 0.0, CH, I["ash"], I["dark_wood"])
    cx0_, cy0_, cx1_, cy1_ = R([98, 420, 111, 498])
    for i in range(2):
        a, b = cy0_ + (cy1_ - cy0_) * i / 2, cy0_ + (cy1_ - cy0_) * (i + 1) / 2
        shoji(fx, (cx1_ + 0.06 + 0.03 * i, a), (cx1_ + 0.06 + 0.03 * i, b), HT["window_sill"], HT["window_head"], I["ash"], I["washi"], grid=(2, 5))
    dl = MB(); downlight_grid(dl, b4x, b4y + 1.9, 2, 0.16, 18); sub.append((dl, ["downlight"]))
    b5x, b5y = PX(365), PY(518) + 0.14
    _f, _s = bed(Matrix.Translation((b5x, b5y, 0)) @ Matrix.Rotation(math.pi / 2, 4, "Z"), w=1.0, l=2.0, head_h=0.85, head_w=1.3); sub.append((_f, ["ash", "black", "cedar"])); sub.append((_s, ["linen", "bedding"], True))
    sub.append((nightstand(fx, I, b5x + 0.82, b5y + 0.24, w=0.38), ["ash", "dark_wood"]))
    wardrobe(fx, P(393, 378), P(337, 378), 0.55, 0.0, CH, I["ash"], I["dark_wood"])
    dx0, dy0, dx1, dy1 = R([410, 420, 441, 485])                                  # study desk with side panels, shelves, lamp, chair
    fx.box(dx0, dy0, 0.72, dx1, dy1, 0.75, I["ash"])
    fx.box(dx0, dy0, 0.0, dx1, dy0 + 0.03, 0.72, I["ash"]); fx.box(dx0, dy1 - 0.03, 0.0, dx1, dy1, 0.72, I["ash"])
    fx.box(dx0 + 0.05, dy0 + 0.03, 0.6, dx1, dy1 - 0.03, 0.62, I["ash"])
    for z in (1.25, 1.62):
        fx.box(dx1 - 0.26, dy0, z, dx1, dy1, z + 0.025, I["ash"])
    b_, s_ = table_lamp(dx1 - 0.2, dy0 + 0.22, 0.75, h=0.36, r=0.1)
    sub.append((b_, ["ceramic"], True)); sub.append((s_, ["lamp_paper"]))
    wd, fb = dining_chair(Matrix.Translation((dx0 - 0.12, (dy0 + dy1) / 2, 0)) @ Matrix.Rotation(-math.pi / 2, 4, "Z"))
    sub.append((wd, ["walnut"])); sub.append((fb, ["chair_fabric"], True))
    bk = MB(); x_ = dy0 + 0.1                                                         # a row of books on the upper shelf
    for k, (hh, tt, mi) in enumerate(((0.24, 0.03, 0), (0.22, 0.025, 1), (0.26, 0.035, 2), (0.21, 0.02, 3), (0.23, 0.04, 4), (0.25, 0.03, 1),
                                       (0.2, 0.028, 0), (0.24, 0.022, 2), (0.22, 0.032, 4), (0.19, 0.05, 3))):
        bk.box(dx1 - 0.22, x_, 1.645, dx1 - 0.03, x_ + tt, 1.645 + hh, mi); x_ += tt + 0.002
    for k in range(3):
        bk.box(dx1 - 0.21, dy0 + 0.5 + k * 0.035, 1.275, dx1 - 0.04, dy0 + 0.53 + k * 0.035 - 0.004, 1.275 + 0.22 - 0.02 * k, k)
    sub.append((bk, ["indigo", "linen", "olive", "dark_wood", "scroll"]))
    dl = MB(); downlight_grid(dl, *P(410, 440), 1, 0.16, 20); sub.append((dl, ["downlight"]))

    # ---------- baths 2/3: wainscot marble, full-height marble glass shower with rain head, vessel basin on a floating
    #            cedar vanity, wall spout, mirror under a cedar shelf with LED, washlet toilet, towel bar, downlights
    clad_room(fx, [111, 133, 200, 214], 0.0, 1.2, I["marble"], only="sew")
    clad(fx, *R([111, 133, 142, 133]), 0.0, 1.2, "s", 0.012, I["marble"])
    clad_room(fx, [142, 74, 200, 133], 0.0, ZB, I["marble"], only="new")
    clad_room(fx, [111, 295, 200, 371], 0.0, 1.2, I["marble"], only="sew")
    clad_room(fx, [111, 240, 200, 295], 0.0, ZB, I["marble"], only="new")
    for (sh, gl_, rain, mixer, van, wc, bar, dls) in (
        ([142, 74, 200, 133], (PX(142), PY(133), PX(178)), P(171, 103), (PX(171), PY(74) - 0.012, 0, -1),
         (138, 182), (Matrix.Translation((PX(150), PY(214) + 0.352, 0)), None), (PX(200) - 0.012, PY(196), 0, -1), ((158, 172),)),
        ([111, 240, 200, 295], (PX(111), PY(295), PX(163)), P(150, 267), (PX(150), PY(240) - 0.012, 0, -1),
         (328, 368), (Matrix.Translation((PX(111) + 0.352, PY(312), 0)) @ Matrix.Rotation(-math.pi / 2, 4, "Z"), None),
         (PX(168), PY(371) + 0.012, -1, 0), ((160, 336),)),
    ):
        sx0_, sy0_, sx1_, sy1_ = R(sh)
        fx.box(sx0_ + 0.012, sy0_, 0.0, sx1_ - 0.012, sy1_ - 0.012, 0.02, I["stone"])
        gx0__, gy__, gx1__ = gl_
        pane(gsh, (gx0__ + 0.012, gy__), (gx1__, gy__), 0.02, 2.05)
        fx.box(gx1__ - 0.012, gy__ - 0.012, 0.02, gx1__, gy__ + 0.012, 2.05, I["chrome"])
        rain_shower(fx, rain[0], rain[1], ZB, wall=mixer, m=I["chrome"])
        wx = PX(111) + 0.012
        vy0__, vy1__ = PY(van[1]), PY(van[0])
        vcy = (vy0__ + vy1__) / 2
        fx.box(wx, vy0__, 0.45, wx + 0.5, vy1__, 0.82, I["cedar"])
        fx.box(wx + 0.5, vy0__ + 0.01, 0.635, wx + 0.503, vy1__ - 0.01, 0.641, I["dark_wood"])
        fx.box(wx, vy0__ - 0.01, 0.82, wx + 0.52, vy1__ + 0.01, 0.85, I["stone"])
        vb = MB(); vessel(vb, wx + 0.28, vcy, 0.85, r=0.18, h=0.13); sub.append((vb, ["porcelain"], True))
        wall_spout(fx, wx, vcy, 1.07, 1, 0, L=0.19, m=I["chrome"])
        fx.box(wx, vy0__ + 0.06, 1.22, wx + 0.018, vy1__ - 0.06, 1.88, I["mirror"])
        fx.box(wx, vy0__, 1.95, wx + 0.14, vy1__, 1.98, I["cedar"])
        lamp.box(wx + 0.1, vy0__ + 0.03, 1.945, wx + 0.12, vy1__ - 0.03, 1.95, J["led_warm"])
        light("AREA", (wx + 0.11, vcy, 1.93), 18, (1.0, 0.85, 0.68), size=(0.05, vy1__ - vy0__ - 0.1))
        sub.append((toilet(wc[0]), ["porcelain"], True))
        br_, tw_ = towel_bar(bar[0], bar[1], 1.0, 0.45, bar[2], bar[3]); sub.append((br_, ["chrome"])); sub.append((tw_, ["towel"], True))
        for p_ in dls:
            dl = MB(); downlight_grid(dl, *P(*p_), 1, 0.16, 18, z=ZB); sub.append((dl, ["downlight"]))
        dl = MB(); downlight_grid(dl, *rain, 1, 0.16, 12, z=ZB); sub.append((dl, ["downlight"]))

    # ---------- balconies: cedar decking, outdoor table set, plants
    def deck(rect, w=0.14, gap=0.008, seg=2.4):
        x0, y0, x1, y1 = R(rect)
        y, k = y0 + 0.004, 0
        while y + w <= y1 + 1e-3:
            off = (k % 3) * seg / 3 + 0.3
            cuts = sorted({x0, x1} | {x0 + off + seg * i for i in range(8) if x0 + 0.2 < x0 + off + seg * i < x1 - 0.2})
            for a, b in zip(cuts, cuts[1:]):
                fx.box(a + 0.002, y, -0.06, b - 0.002, y + w, -0.03, I["deck"])
            y += w + gap; k += 1
    deck([525, 72, 717, 125]); deck([788, 72, 969, 125])
    place_model("outdoor_table_chair_set_01", *P(672, 98), -0.03, 0.0, name="patio_set")
    place_model("potted_plant_02", *P(952, 88), -0.03, height=1.1, name="plant_bmb")
    place_model("potted_plant_04", *P(800, 86), -0.03, 1.4, height=1.3, name="plant_bmb2")

    # ---------- service balcony (glass parapet on the south): stacked washer/dryer, utility sink and tall cabinet on the
    #            north wall, drying poles with laundry, basket
    zf = -0.06
    washer(fx, I, PX(381), PY(612) + 0.31, zf, (0, 1))
    wy = PY(525)
    us0, us1 = PX(302), PX(330)
    fx.box(us0, wy - 0.55, zf, us1, wy, 0.8, I["appliance"])
    for a, b, c, d in ((us0, wy - 0.12, us1, wy), (us0, wy - 0.56, us1, wy - 0.5), (us0, wy - 0.56, us0 + 0.05, wy), (us1 - 0.05, wy - 0.56, us1, wy)):
        fx.box(a, b, 0.8, c, d, 0.84, I["steel"])
    fx.well(us0 + 0.05, wy - 0.5, us1 - 0.05, wy - 0.12, 0.55, 0.84, I["steel"])
    gooseneck(fx, (us0 + us1) / 2, wy - 0.06, 0.84, 0, -1, h=0.3, reach=0.2, m=I["chrome"])
    fx.box(us0 + 0.01, wy - 0.553, 0.4, us1 - 0.01, wy - 0.55, 0.406, I["graphite"])
    fx.box(PX(268), wy - 0.45, zf, PX(299), wy, 2.2, I["appliance"])
    fx.box((PX(268) + PX(299)) / 2 - 0.002, wy - 0.453, zf + 0.05, (PX(268) + PX(299)) / 2 + 0.002, wy - 0.45, 2.15, I["graphite"])
    for py_ in (566, 584):
        yy = PY(py_); top = H - 0.45 if 574 <= py_ <= 591 else H
        fx.cylt((PX(125), yy, 2.1), (PX(250), yy, 2.1), 0.014, 0.014, 10, I["chrome"])
        for px_ in (130, 245):
            fx.cylt((PX(px_), yy, 2.1), (PX(px_), yy, top), 0.01, 0.01, 8, I["chrome"])
    laundry = {"towel": MB(), "towel_indigo": MB(), "linen": MB()}
    for px_, py_, mt, ww in ((148, 566, "towel", 0.5), (176, 566, "towel_indigo", 0.45), (206, 566, "linen", 0.6),
                             (160, 584, "linen", 0.55), (194, 584, "towel", 0.5), (228, 584, "towel_indigo", 0.4)):
        laundry[mt].sq(PX(px_), PY(py_), 2.1 - 0.32, ww / 2, 0.02, 0.33, e1=0.15, e2=0.25, nu=20, nv=10)
    for mt, m_ in laundry.items():
        sub.append((m_, [mt], True))
    place_model("wicker_basket_01", *P(345, 562), zf, 0.3, name="basket_svc")
    for p_ in ((200, 560), (360, 555)):
        dl = MB(); downlight_grid(dl, *P(*p_), 1, 0.16, 18, z=H); sub.append((dl, ["downlight"]))

    # ---------- build all
    fx.build("F_fitout", FX, bevel=0.003)
    glm.build("G_shoji_glass", ["glass"])
    gsh.build("G_shower_glass", ["glass_thin"])
    lamp.build("E_lamps", LM)
    groups = {}
    for entry in sub:
        m, mats = entry[0], entry[1]
        smooth = len(entry) > 2 and entry[2]
        groups.setdefault((tuple(mats), smooth), []).append(m)
    for gi, ((mats, smooth), ms) in enumerate(groups.items()):
        merged = MB()
        for m in ms:
            base = len(merged.v)
            merged.v += m.v; merged.m += m.m; merged.rot += m.rot
            merged.f += [[i + base for i in f] for f in m.f]
        pre = "E_" if mats[0] in ("downlight", "lamp_paper") else "F_"
        merged.build(f"{pre}sub{gi}", list(mats), bevel=0.004 if (pre == "F_" and not smooth) else 0.0, smooth=smooth)
    # props from Poly Haven
    place_model("tea_set_01", rx + 0.05, ry, 0.38, 0.4, height=0.12, name="tea_lv")
    place_model("tea_set_01", cx, cy, PH + 0.34, 1.2, height=0.12, name="tea_washitsu")
    place_model("ceramic_vase_02", wx0 + 0.3, (tk_split + wy1) / 2, PH + 0.12, height=0.35, name="vase_toko")
    place_model("rock_moss_set_01", px0 + 1.1, py0 + 0.75, -0.04, 0.6, height=0.35, name="rocks")
    place_model("tree_small_02", px0 + 1.45, py0 + 0.68, -0.05, 0.0, height=1.75, name="maple")
    place_model("shrub_02", px0 + 0.35, py1 - 0.35, -0.05, 0.0, height=0.6, name="shrub")


# ============================================================== light, world, cameras
def world_hdri(name, strength, sun_dir):
    """environment rotated so the HDRI's sun sits in sun_dir (vector from the scene toward the sun)"""
    import numpy as np
    f = glob.glob(os.path.join(A.assets, "hdri", name + "*"))
    world.use_nodes = True; nt = world.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    bg = nt.nodes.new("ShaderNodeBackground"); bg.inputs["Strength"].default_value = strength
    out = nt.nodes.new("ShaderNodeOutputWorld"); nt.links.new(bg.outputs[0], out.inputs[0])
    if not f:
        bg.inputs["Color"].default_value = (0.6, 0.7, 0.8, 1); return
    im = bpy.data.images.load(f[0])
    w, h = im.size
    px = np.empty(w * h * 4, dtype=np.float32); im.pixels.foreach_get(px); px = px.reshape(h, w, 4)
    lum = px[..., 0] * .2126 + px[..., 1] * .7152 + px[..., 2] * .0722
    j, i = np.unravel_index(np.argmax(lum), lum.shape)
    # Blender equirect: u = atan2(y, -x) / 2pi + 0.5 ; rotating the lookup by r shifts that angle by -r
    phi_h = ((i + 0.5) / w - 0.5) * 2 * math.pi
    phi_s = math.atan2(sun_dir.y, -sun_dir.x)
    tc = nt.nodes.new("ShaderNodeTexCoord"); mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Rotation"].default_value[2] = phi_s - phi_h
    env = nt.nodes.new("ShaderNodeTexEnvironment"); env.image = im
    nt.links.new(tc.outputs["Generated"], mp.inputs["Vector"]); nt.links.new(mp.outputs["Vector"], env.inputs["Vector"])
    nt.links.new(env.outputs["Color"], bg.inputs["Color"])
    print(f"HDRI {name}: sun pixel {i},{j} el {90 - (j + 0.5) / h * 180:.0f}")


def make_light(kind, loc, energy, color, size=0.05, spot=None, rot=(0, 0, 0), name=None, portal=False):
    ld = bpy.data.lights.new(name or kind.lower(), kind); ld.energy = energy; ld.color = color
    if kind == "AREA":
        ld.size = size if not isinstance(size, tuple) else size[0]
        if isinstance(size, tuple):
            ld.shape = "RECTANGLE"; ld.size, ld.size_y = size
    elif kind in ("POINT", "SPOT"):
        ld.shadow_soft_size = size
    if spot:
        ld.spot_size, ld.spot_blend = spot
    if portal:
        ld.cycles.is_portal = True
    o = bpy.data.objects.new(f"X_{ld.name}", ld); o.location = loc; o.rotation_euler = rot
    COLL.objects.link(o)
    return o


def lighting():
    night = A.night
    az, el = math.radians(20.0), math.radians(34.0)     # sun over the balconies (plan top), a little from the east
    sun_dir = Vector((math.sin(az) * math.cos(el), math.cos(az) * math.cos(el), math.sin(el)))
    world_hdri("ninomaru_teien", 0.03 if night else 1.0, sun_dir)
    if not night:
        s = bpy.data.lights.new("sun", "SUN"); s.energy = 4.0; s.angle = math.radians(0.8); s.color = (1.0, 0.95, 0.88)
        o = bpy.data.objects.new("X_sun", s); o.rotation_euler = (-sun_dir).to_track_quat("-Z", "Y").to_euler(); COLL.objects.link(o)
    # light portals in every exterior opening (they only guide sampling)
    for op in PLAN["openings"]:
        if op["kind"] not in ("window", "window_high", "slider"):
            continue
        x0, y0, x1, y1 = R(op["r"])
        z0 = {"window": HT["window_sill"], "window_high": HT["bath_sill"], "slider": 0.0}[op["kind"]]
        z1 = HT["slider"] if op["kind"] == "slider" else HT["window_head"]
        horiz = (x1 - x0) >= (y1 - y0)
        c = ((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2)
        if horiz:
            inward = -1 if y1 > PY(300) else 1            # north windows face -y into the room
            rot = (math.radians(-90 if inward < 0 else 90), 0, 0)
            make_light("AREA", c, 0, (1, 1, 1), size=(x1 - x0, z1 - z0), rot=rot, portal=True)
        else:
            rot = (0, math.radians(-90), 0)
            make_light("AREA", c, 0, (1, 1, 1), size=(z1 - z0, y1 - y0), rot=rot, portal=True)
    scale = 2.2 if night else 1.0
    for kind, loc, energy, color, size, spot, rot, name in LIGHTS:
        make_light(kind, loc, energy * scale, color, size, spot, rot, name)
    if night:
        for m in ("led_warm", "lamp_paper", "downlight"):
            if m in MATS:
                MATS[m].node_tree.nodes["Principled BSDF"].inputs["Emission Strength"].default_value *= 1.6


# camera shots in plan px + height (m); lens mm
SHOTS = {
    "axo":      None,
    "living":   ((740, 478, 1.3), (575, 160, 1.2), 16),
    "washitsu": ((528, 306, 1.4), (405, 160, 1.0), 17),
    "dining":   ((650, 345, 1.45), (470, 480, 1.0), 17),
    "entry":    ((692, 658, 1.5), (692, 330, 1.25), 18),
    "master":   ((965, 385, 1.5), (800, 215, 0.85), 16),
    "bath":     ((772, 505, 1.55), (880, 520, 0.95), 15),
    "garden":   ((468, 178, 1.22), (468, 60, 0.95), 20),
    # audit views of every remaining room
    "kitchen":  ((616, 545, 1.55), (430, 612, 0.95), 15),
    "br2":      ((350, 150, 1.5), (215, 250, 0.7), 16),
    "br4":      ((289, 394, 1.5), (150, 492, 0.8), 15),
    "br5":      ((432, 392, 1.5), (350, 500, 0.8), 15),
    "ba2":      ((222, 156, 1.55), (111, 168, 0.95), 14),
    "ba3":      ((188, 252, 1.55), (120, 352, 0.9), 14),
    "hall":     ((525, 346, 1.5), (215, 346, 1.2), 18),
    "balcony":  ((535, 112, 1.5), (717, 95, 0.6), 16),
    "svc":      ((402, 540, 1.6), (120, 585, 0.85), 15),
    "bath2":    ((842, 490, 1.55), (765, 585, 0.8), 14),
    "master2":  ((800, 405, 1.5), (985, 200, 1.0), 16),
}


# walkthrough waypoints: camera (px), look-at (px, height m), label; eye height 1.5 m; ~0.9 m/s, turns in place ~2 s
WALK = [
    ((692, 662), (692, 380, 1.25), "玄關"),
    ((692, 560), (690, 330, 1.3), "玄關"),
    ((700, 460), (600, 250, 1.2), "客廳"),
    ((650, 362), (470, 230, 1.1), "客廳"),
    ((590, 345), (450, 170, 1.05), "和室"),
    ((565, 300), (445, 145, 1.05), "和室・窗景"),
    ((565, 300), (520, 470, 1.0), "餐廳"),
    ((640, 400), (760, 410, 1.3), "餐廳"),
    ((762, 410), (900, 395, 1.3), "主臥"),
    ((860, 418), (815, 230, 0.9), "主臥"),
    ((935, 478), (890, 530, 1.2), "主臥"),
    ((905, 527), (800, 560, 1.0), "主浴"),
    ((815, 497), (868, 580, 0.75), "主浴"),
]
WALK_FPS = 18


def walk_frames():
    """frame number of every waypoint: distance at ~0.9 m/s, in-place turns ~2 s, a 1 s hold at both ends"""
    fr = [1 + WALK_FPS]
    for (p0, l0, _), (p1, l1, _) in zip(WALK, WALK[1:]):
        d = math.hypot(p1[0] - p0[0], p1[1] - p0[1]) * S
        a0 = math.atan2(l0[1] - p0[1], l0[0] - p0[0]); a1 = math.atan2(l1[1] - p1[1], l1[0] - p1[0])
        turn = abs((a1 - a0 + math.pi) % (2 * math.pi) - math.pi)
        fr.append(fr[-1] + max(int(d / 0.9 * WALK_FPS), int(turn / 1.2 * WALK_FPS), 8))
    return fr


def walk_camera():
    cd = bpy.data.cameras.new("cam"); cd.sensor_width = 36; cd.lens = 17; cd.clip_start = 0.05
    o = bpy.data.objects.new("X_cam", cd); COLL.objects.link(o); sc.camera = o
    tgt = bpy.data.objects.new("X_cam_target", None); COLL.objects.link(tgt)
    tc = o.constraints.new("TRACK_TO"); tc.target = tgt; tc.track_axis = "TRACK_NEGATIVE_Z"; tc.up_axis = "UP_Y"
    fr = walk_frames()
    for f, ((x, y), (tx, ty, tz), _) in zip(fr, WALK):
        o.location = (PX(x), PY(y), 1.5); o.keyframe_insert("location", frame=f)
        tgt.location = (PX(tx), PY(ty), tz); tgt.keyframe_insert("location", frame=f)
    for ob in (o, tgt):
        for fc in ob.animation_data.action.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = "BEZIER"; kp.handle_left_type = kp.handle_right_type = "AUTO_CLAMPED"
    sc.frame_start, sc.frame_end = 1, fr[-1] + WALK_FPS
    print("[walk] frames", sc.frame_end, "labels", [(f, w[2]) for f, w in zip(fr, WALK)])
    return fr


def camera(shot):
    cd = bpy.data.cameras.new("cam"); cd.sensor_width = 36
    o = bpy.data.objects.new("X_cam", cd); COLL.objects.link(o); sc.camera = o
    if A.cam:
        v = [float(t) for t in A.cam.split(",")]
        spec = ((v[0], v[1], v[2]), (v[3], v[4], v[5]), v[6] if len(v) > 6 else 18)
    else:
        spec = SHOTS[shot]
    if spec is None:     # axonometric cutaway
        cd.type = "ORTHO"; cd.ortho_scale = 25.0
        cx = (PX(80) + PX(1012)) / 2; cy = (PY(66) + PY(675)) / 2
        d = Vector((1.0, 1.25, -1.35)).normalized()
        o.location = Vector((cx, cy, 1.2)) - d * 40
        o.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
        cd.clip_end = 200
        return
    (x, y, z), (tx, ty, tz), lens = spec
    p = Vector((PX(x), PY(y), z)); t = Vector((PX(tx), PY(ty), tz))
    o.location = p; o.rotation_euler = (t - p).to_track_quat("-Z", "Y").to_euler()
    cd.lens = lens; cd.clip_start = 0.05; cd.shift_y = 0.0


def render_settings(res, samples):
    sc.render.engine = "CYCLES"
    cyc = sc.cycles
    cyc.device = "GPU"
    prefs = bpy.context.preferences.addons["cycles"].preferences
    for backend in ("OPTIX", "CUDA"):
        try:
            prefs.compute_device_type = backend; prefs.get_devices()
            if any(d.type == backend for d in prefs.devices):
                for d in prefs.devices:
                    d.use = d.type == backend
                print("GPU backend", backend); break
        except Exception as e:  # noqa: BLE001
            print("no", backend, e)
    cyc.samples = samples; cyc.use_adaptive_sampling = True; cyc.adaptive_threshold = 0.01
    cyc.use_denoising = True; cyc.denoiser = "OPENIMAGEDENOISE"
    cyc.max_bounces = 12; cyc.diffuse_bounces = 6; cyc.glossy_bounces = 4; cyc.transmission_bounces = 8
    cyc.transparent_max_bounces = 16; cyc.sample_clamp_indirect = 6.0; cyc.caustics_reflective = False; cyc.caustics_refractive = False
    w, h = (int(v) for v in res.split("x"))
    sc.render.resolution_x, sc.render.resolution_y = w, h; sc.render.resolution_percentage = 100
    sc.view_settings.view_transform = "AgX"; sc.view_settings.look = "AgX - Medium High Contrast"
    sc.view_settings.exposure = EXPOSURE
    sc.render.film_transparent = False
    sc.render.image_settings.file_format = "PNG"



# ============================================================== image-based tour (360 panoramas, 360 path clips, turntable)
def run_tour(jobs):
    """jobs: {"kind": "pano", "name", "pos": [px, py, z], "res", "samples"}
             {"kind": "path", "name", "pts": [[px, py, z], ...], "n": frames, "first", "last", "res", "samples"}
             {"kind": "turn", "name", "n", "first", "last", "el": deg, "nodes": {id: [px, py, z]}, "res", "samples"}
    every 360 view is world-aligned (image centre = plan north, +y) so panoramas and clips line up in the viewer"""
    from bpy_extras.object_utils import world_to_camera_view
    cut = [o for o in bpy.data.objects
           if o.name in ("A_slab", "A_ceiling", "A_beams", "E_cove")
           or (o.name.startswith("E_sub") and o.data and any(m.name.startswith("downlight") for m in o.data.materials))
           or (o.type == "LIGHT" and o.data.type == "SPOT")]
    pd = bpy.data.cameras.new("pano"); pd.type = "PANO"; pd.clip_start = 0.05
    try:
        pd.panorama_type = "EQUIRECTANGULAR"
    except AttributeError:
        pd.cycles.panorama_type = "EQUIRECTANGULAR"
    pc = bpy.data.objects.new("X_pano", pd); COLL.objects.link(pc); pc.rotation_euler = (math.pi / 2, 0, 0)
    od = bpy.data.cameras.new("turn"); od.type = "ORTHO"; od.ortho_scale = 27.0; od.clip_end = 200
    oc = bpy.data.objects.new("X_turn", od); COLL.objects.link(oc)
    vd = bpy.data.cameras.new("walkcam"); vd.sensor_fit = "HORIZONTAL"; vd.sensor_width = 36; vd.clip_start = 0.05
    vc = bpy.data.objects.new("X_walkcam", vd); COLL.objects.link(vc)
    render_settings(A.res, A.samples)
    sc.render.use_persistent_data = True
    sc.cycles.seed = 7; sc.cycles.use_animated_seed = False
    os.makedirs(A.outdir, exist_ok=True)

    def setup(j, still=True):
        w, h = (int(v) for v in j.get("res", A.res).split("x"))
        sc.render.resolution_x, sc.render.resolution_y = w, h
        sc.cycles.samples = j.get("samples", A.samples)
        sc.cycles.adaptive_threshold = 0.01 if still else 0.03
        sc.render.image_settings.file_format = "PNG" if still or j["kind"] == "turn" else "JPEG"
        sc.render.image_settings.quality = 93
        sc.render.film_transparent = j["kind"] == "turn"          # turntable: composited on a plain backdrop later
        sc.render.image_settings.color_mode = "RGBA" if j["kind"] == "turn" else "RGB"

    def shoot(path):
        sc.render.filepath = os.path.join(os.path.abspath(A.outdir), path)
        bpy.ops.render.render(write_still=True)

    for j in jobs:
        k = j["kind"]
        for o in cut:
            o.hide_render = k == "turn"
        if k == "pano":
            setup(j); sc.camera = pc
            x, y, z = j["pos"]; pc.location = (PX(x), PY(y), z)
            shoot(f"pano_{j['name']}.png"); tick(f"pano {j['name']}")
        elif k == "path":
            setup(j, still=False); sc.camera = pc
            if j.get("hfov"):            # perspective clip with a locked heading (yaw from plan north, clockwise)
                sc.camera = vc
                vd.lens = 18.0 / math.tan(math.radians(j["hfov"]) / 2)
                vc.rotation_euler = (math.pi / 2 + j.get("pitch", 0.0), 0, -j["yaw"])
            cam = sc.camera
            pts = [Vector((PX(x), PY(y), z)) for x, y, z in j["pts"]]
            seg = [(b - a).length for a, b in zip(pts, pts[1:])]; total = sum(seg)
            for f in range(j["first"], j["last"]):
                t = f / (j["n"] - 1)
                if j.get("ease") == "smooth":
                    e = t * t * (3 - 2 * t)                               # gentler peak speed (1.5x the mean)
                else:
                    e = t * t * t * (t * (6 * t - 15) + 10)               # minimum-jerk ease in / out
                d = total * e
                i = 0
                while i < len(seg) - 1 and d > seg[i]:
                    d -= seg[i]; i += 1
                cam.location = pts[i].lerp(pts[i + 1], min(1.0, d / seg[i]))
                shoot(f"{j['name']}_{f:04d}.jpg")
            tick(f"path {j['name']} {j['first']}-{j['last']}")
        elif k == "turn":
            setup(j, still=False); sc.camera = oc; od.ortho_scale = j.get("scale", 27.0)
            c = Vector(((PX(80) + PX(1012)) / 2, (PY(66) + PY(675)) / 2, 1.0))
            el = math.radians(j.get("el", 46.6)); a0 = math.atan2(-1.25, -1.0)
            proj = {}
            for f in range(j["first"], j["last"]):
                a = a0 + 2 * math.pi * f / j["n"]
                oc.location = c + Vector((math.cos(a) * math.cos(el), math.sin(a) * math.cos(el), math.sin(el))) * 40
                oc.rotation_euler = (c - oc.location).to_track_quat("-Z", "Y").to_euler()
                bpy.context.view_layer.update()
                proj[f] = {nid: [round(v, 4) for v in world_to_camera_view(sc, oc, Vector((PX(x), PY(y), z)))[:2]]
                           for nid, (x, y, z) in j.get("nodes", {}).items()}
                shoot(f"{j['name']}_{f:03d}.png")
            json.dump(proj, open(os.path.join(A.outdir, f"{j['name']}_{j['first']:03d}.json"), "w"))
            tick(f"turn {j['first']}-{j['last']}")


# ============================================================== main
EXPOSURE = (1.5 if WA else 2.4) if not A.night else 0.4
sc.view_settings.view_transform = "AgX"; sc.view_settings.exposure = EXPOSURE
make_materials(); tick("materials")
build_shell(); tick("shell")
build_openings(); tick("openings")
if WA:
    build_wa(); tick("wa fit-out")
else:
    build_empty_extras()
    place_model("shrub_02", *P(440, 100), -0.06, height=0.7, name="planter_a")
    place_model("shrub_02", *P(490, 105), -0.06, 1.5, height=0.6, name="planter_b")
lighting(); tick("lights")

if A.bake:
    import importlib.util
    spec = importlib.util.spec_from_file_location("bake", os.path.join(os.path.dirname(os.path.abspath(__file__)), "bake_export.py"))
    bk = importlib.util.module_from_spec(spec); spec.loader.exec_module(bk)
    bk.run(A, sc, MATS, tick)
else:
    if A.shot == "axo" and not A.walk and not A.tour:
        for o in bpy.data.objects:          # cutaway: no slab, no ceilings, no beams
            if o.name in ("A_slab", "A_ceiling", "A_beams", "E_cove") or (o.name.startswith("E_sub") and o.data and
                                                                         any(m.name.startswith("downlight") for m in o.data.materials)):
                o.hide_render = True
            if o.type == "LIGHT" and o.data.type == "SPOT":
                o.hide_render = True
        if "A_slab" in bpy.data.objects:
            pass
    if A.walk:
        walk_camera()
        render_settings(A.res, A.samples)
        parts = [int(v) for v in A.walk.split(":")]
        sc.frame_start, sc.frame_end = parts[0], min(parts[1], sc.frame_end)
        sc.frame_step = parts[2] if len(parts) > 2 else 1
        sc.render.fps = WALK_FPS
        sc.cycles.adaptive_threshold = 0.03; sc.cycles.max_bounces = 8; sc.cycles.diffuse_bounces = 4
        sc.cycles.seed = 7; sc.cycles.use_animated_seed = False
        sc.render.use_persistent_data = True
        sc.render.image_settings.file_format = "JPEG"; sc.render.image_settings.quality = 94
        os.makedirs(A.outdir, exist_ok=True)
        sc.render.filepath = os.path.join(os.path.abspath(A.outdir), "f_####")
        bpy.ops.render.render(animation=True)
        tick("walk rendered")
        sys.exit(0)
    if A.tour:
        run_tour(json.loads(A.tour))
        sys.exit(0)
    shots = A.shot.split(",")
    render_settings(A.res, A.samples)
    os.makedirs(os.path.dirname(os.path.abspath(A.out)), exist_ok=True)
    sc.render.use_persistent_data = len(shots) > 1
    for shot in shots:                      # several shots from one scene build (audits)
        if sc.camera:
            bpy.data.objects.remove(sc.camera, do_unlink=True)
        camera(shot)
        out = A.out if len(shots) == 1 else A.out.replace(".png", f"_{shot}.png")
        sc.render.filepath = os.path.abspath(out)
        print("objects:", len(bpy.data.objects), "rendering", A.variant, shot, A.res, A.samples)
        bpy.ops.render.render(write_still=True)
        tick(f"rendered {shot}")
