# -*- coding: utf-8 -*-
"""川端橋 Cycles 場景（Blender 4.2，背景模式）。

    blender -b -P kawabata_scene.py -- --shot open|reopen --assets <polyhaven dir> --out out/open.png

座標：x 沿橋（負＝臺北、正＝永和），y 橫橋（負＝下游，新中正橋在 y=-32），z 向上（0＝常水位），單位公尺。
尺寸同 js/scene3d.js：原橋長 300.56 m、14 孔上承式鋼鈑梁、13 座雙柱式拱型橋墩、橋面寬 5.2 m（淨寬）；
新中正橋拱跨 215 m、拱高 50 m、兩側共 28 條鋼纜。

寫實手法參考 pirrer/meiji-bridge-3d（MIT）：Poly Haven CC0 PBR 貼圖以世界座標 box 投影並加大尺度明暗斑駁、
垂直水漬；所有構件加倒角讓邊緣接光；HDRI 天光＋對齊的太陽燈；mist 大氣透視；AgX 色調。
"""
import argparse
import glob
import math
import os
import random
import sys
import time
_T0 = time.time()
def tick(msg):
    print(f'[t {time.time() - _T0:6.1f}s] {msg}', flush=True)

import bmesh
import bpy
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
ap = argparse.ArgumentParser()
ap.add_argument("--shot", default="open")
ap.add_argument("--assets", default="assets")
ap.add_argument("--out", default="out/open.png")
ap.add_argument("--res", default="1920x1080")
ap.add_argument("--samples", type=int, default=256)
ap.add_argument("--cam", default="", help="override camera: x,y,z,tx,ty,tz,lens")
A = ap.parse_args(argv)
TEX = os.path.join(A.assets, "textures")
NIGHT = A.shot == "reopen"
MODERN = A.shot in ("reopen",)
rng = random.Random(1937)

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.unit_settings.system = "METRIC"

# ============================================================== render settings
rx, ry = (int(v) for v in A.res.split("x"))
sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = rx, ry, 100
sc.render.engine = "CYCLES"
prefs = bpy.context.preferences.addons["cycles"].preferences
for dev in ("OPTIX", "CUDA"):
    try:
        prefs.compute_device_type = dev
        prefs.get_devices()
        if any(d.type == dev for d in prefs.devices):
            break
    except Exception:
        continue
for d in prefs.devices:
    d.use = d.type != "CPU"
sc.cycles.device = "GPU" if any(d.use for d in prefs.devices) else "CPU"
print("cycles device:", prefs.compute_device_type, [d.name for d in prefs.devices if d.use])
sc.cycles.samples = A.samples
sc.cycles.use_adaptive_sampling = True
sc.cycles.adaptive_threshold = 0.015
sc.cycles.use_denoising = True
sc.cycles.denoiser = "OPENIMAGEDENOISE"
try:
    sc.cycles.denoising_use_gpu = True
except AttributeError:
    pass
sc.cycles.max_bounces = 8
sc.cycles.transparent_max_bounces = 24
sc.cycles.filter_width = 1.5
sc.cycles.seed = 7
sc.view_settings.view_transform = "AgX"
try:
    sc.view_settings.look = "AgX - Base Contrast"
except TypeError:
    pass
sc.view_settings.exposure = 0.0
sc.render.image_settings.file_format = "PNG"
sc.render.image_settings.color_depth = "8"

world = bpy.data.worlds.new("world"); sc.world = world
vl = sc.view_layers[0]
vl.use_pass_mist = True
vl.use_pass_z = True
vl.use_pass_object_index = True
world.mist_settings.start, world.mist_settings.depth, world.mist_settings.falloff = (180.0, 3800.0, "QUADRATIC")


# ============================================================== materials
_img_cache = {}


def img(path, noncolor=False):
    key = (path, noncolor)
    if key not in _img_cache:
        im = bpy.data.images.load(path, check_existing=True)
        if noncolor:
            im.colorspace_settings.name = "Non-Color"
        _img_cache[key] = im
    return _img_cache[key]


def tex_file(tid, m):
    c = glob.glob(os.path.join(TEX, tid, f"{tid}_{m}_2k.*"))
    return c[0] if c else None


def pbr(name, tid, size=2.0, tint=(1, 1, 1), bright=1.0, sat=1.0, rough_add=0.0, bump=0.35, variation=0.2,
        streak=0.0, metallic=0.0, blend=0.25):
    """Poly Haven 貼圖，世界座標 box 投影（公尺尺度一致）＋大尺度明暗斑駁＋垂直水漬。"""
    m = bpy.data.materials.new(name); m.use_nodes = True
    nt = m.node_tree; N = nt.nodes.new; L = nt.links.new
    bsdf = nt.nodes["Principled BSDF"]
    bsdf.inputs["Metallic"].default_value = metallic
    geo = N("ShaderNodeNewGeometry")
    mp = N("ShaderNodeMapping"); mp.inputs["Scale"].default_value = (1 / size,) * 3
    L(geo.outputs["Position"], mp.inputs["Vector"])

    def teximg(mapname, noncolor):
        f = tex_file(tid, mapname)
        if not f:
            return None
        t = N("ShaderNodeTexImage"); t.image = img(f, noncolor); t.projection = "BOX"; t.projection_blend = blend
        L(mp.outputs["Vector"], t.inputs["Vector"])
        return t
    d, r, n = teximg("Diffuse", False), teximg("Rough", True), teximg("nor_gl", True)
    col = None
    if d:
        hsv = N("ShaderNodeHueSaturation"); hsv.inputs["Saturation"].default_value = sat
        L(d.outputs["Color"], hsv.inputs["Color"]); col = hsv.outputs["Color"]
    tn = N("ShaderNodeMixRGB"); tn.blend_type = "MULTIPLY"; tn.inputs["Fac"].default_value = 1.0
    tn.inputs["Color2"].default_value = (tint[0] * bright, tint[1] * bright, tint[2] * bright, 1)
    if col:
        L(col, tn.inputs["Color1"])
    else:
        tn.inputs["Color1"].default_value = (0.5, 0.5, 0.5, 1)
    # large-scale variation breaks texture repetition
    nz = N("ShaderNodeTexNoise"); nz.inputs["Scale"].default_value = 0.06; nz.inputs["Detail"].default_value = 6
    L(geo.outputs["Position"], nz.inputs["Vector"])
    mr = N("ShaderNodeMapRange"); mr.inputs["To Min"].default_value = 1 - variation; mr.inputs["To Max"].default_value = 1 + variation * 0.4
    L(nz.outputs["Fac"], mr.inputs["Value"])
    vr = N("ShaderNodeMixRGB"); vr.blend_type = "MULTIPLY"; vr.inputs["Fac"].default_value = 1.0
    L(tn.outputs["Color"], vr.inputs["Color1"]); L(mr.outputs["Result"], vr.inputs["Color2"])
    out = vr.outputs["Color"]
    if streak > 0:  # vertical water stains
        sm = N("ShaderNodeMapping"); sm.inputs["Scale"].default_value = (1.4, 1.4, 0.05)
        L(geo.outputs["Position"], sm.inputs["Vector"])
        sn = N("ShaderNodeTexNoise"); sn.inputs["Scale"].default_value = 1.0; sn.inputs["Detail"].default_value = 5
        L(sm.outputs["Vector"], sn.inputs["Vector"])
        sr = N("ShaderNodeMapRange"); sr.inputs["From Min"].default_value = 0.45; sr.inputs["From Max"].default_value = 0.72
        sr.inputs["To Min"].default_value = 1.0; sr.inputs["To Max"].default_value = 1 - streak
        L(sn.outputs["Fac"], sr.inputs["Value"])
        st = N("ShaderNodeMixRGB"); st.blend_type = "MULTIPLY"; st.inputs["Fac"].default_value = 1.0
        L(out, st.inputs["Color1"]); L(sr.outputs["Result"], st.inputs["Color2"]); out = st.outputs["Color"]
    L(out, bsdf.inputs["Base Color"])
    if r:
        ra = N("ShaderNodeMath"); ra.operation = "ADD"; ra.use_clamp = True; ra.inputs[1].default_value = rough_add
        L(r.outputs["Color"], ra.inputs[0]); L(ra.outputs[0], bsdf.inputs["Roughness"])
    if n:
        nm = N("ShaderNodeNormalMap"); nm.inputs["Strength"].default_value = bump * 2
        L(n.outputs["Color"], nm.inputs["Color"]); L(nm.outputs["Normal"], bsdf.inputs["Normal"])
    return m


def flat(name, color, rough=0.5, metal=0.0, emit=None, strength=0.0):
    m = bpy.data.materials.new(name); m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*color, 1); b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    if emit:
        b.inputs["Emission Color"].default_value = (*emit, 1); b.inputs["Emission Strength"].default_value = strength
    return m


def emission(name, color, strength):
    m = bpy.data.materials.new(name); m.use_nodes = True
    nt = m.node_tree; nt.nodes.remove(nt.nodes["Principled BSDF"])
    e = nt.nodes.new("ShaderNodeEmission"); e.inputs["Color"].default_value = (*color, 1); e.inputs["Strength"].default_value = strength
    nt.links.new(e.outputs[0], nt.nodes["Material Output"].inputs["Surface"])
    return m


def water_mat():
    m = bpy.data.materials.new("water"); m.use_nodes = True
    nt = m.node_tree; N = nt.nodes.new; L = nt.links.new
    b = nt.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (0.045, 0.058, 0.045, 1) if not NIGHT else (0.012, 0.018, 0.02, 1)
    b.inputs["Roughness"].default_value = 0.06; b.inputs["IOR"].default_value = 1.333
    b.inputs["Specular IOR Level"].default_value = 0.5
    geo = N("ShaderNodeNewGeometry")
    mp = N("ShaderNodeMapping"); mp.inputs["Scale"].default_value = (1.1, 0.35, 1.0)
    L(geo.outputs["Position"], mp.inputs["Vector"])
    n1 = N("ShaderNodeTexNoise"); n1.inputs["Scale"].default_value = 1.0; n1.inputs["Detail"].default_value = 8
    L(mp.outputs["Vector"], n1.inputs["Vector"])
    n2 = N("ShaderNodeTexNoise"); n2.inputs["Scale"].default_value = 0.04; n2.inputs["Detail"].default_value = 3
    L(geo.outputs["Position"], n2.inputs["Vector"])
    ad = N("ShaderNodeMath"); ad.operation = "ADD"; L(n1.outputs["Fac"], ad.inputs[0]); L(n2.outputs["Fac"], ad.inputs[1])
    bp = N("ShaderNodeBump"); bp.inputs["Strength"].default_value = 0.28; bp.inputs["Distance"].default_value = 0.06
    L(ad.outputs[0], bp.inputs["Height"]); L(bp.outputs["Normal"], b.inputs["Normal"])
    return m


def ground_mat(name, low, high, z0, z1):
    """依高度在兩組貼圖間漸變（泥灘→草地），world z＋雜訊。"""
    m = bpy.data.materials.new(name); m.use_nodes = True
    nt = m.node_tree; N = nt.nodes.new; L = nt.links.new
    bsdf = nt.nodes["Principled BSDF"]
    geo = N("ShaderNodeNewGeometry")

    def layer(tid, size, tint, sat):
        mp = N("ShaderNodeMapping"); mp.inputs["Scale"].default_value = (1 / size,) * 3
        L(geo.outputs["Position"], mp.inputs["Vector"])
        t = N("ShaderNodeTexImage"); f = tex_file(tid, "Diffuse")
        if f:
            t.image = img(f)
        t.projection = "BOX"; t.projection_blend = 0.3
        L(mp.outputs["Vector"], t.inputs["Vector"])
        h = N("ShaderNodeHueSaturation"); h.inputs["Saturation"].default_value = sat; L(t.outputs["Color"], h.inputs["Color"])
        tn = N("ShaderNodeMixRGB"); tn.blend_type = "MULTIPLY"; tn.inputs["Fac"].default_value = 1.0
        tn.inputs["Color2"].default_value = (*tint, 1); L(h.outputs["Color"], tn.inputs["Color1"])
        return tn.outputs["Color"]
    a = layer(*low); b = layer(*high)
    sep = N("ShaderNodeSeparateXYZ"); L(geo.outputs["Position"], sep.inputs[0])
    nz = N("ShaderNodeTexNoise"); nz.inputs["Scale"].default_value = 0.05; nz.inputs["Detail"].default_value = 6
    L(geo.outputs["Position"], nz.inputs["Vector"])
    nzm = N("ShaderNodeMath"); nzm.operation = "MULTIPLY_ADD"; nzm.inputs[1].default_value = 1.6; nzm.inputs[2].default_value = -0.8
    L(nz.outputs["Fac"], nzm.inputs[0])
    zz = N("ShaderNodeMath"); zz.operation = "ADD"; L(sep.outputs["Z"], zz.inputs[0]); L(nzm.outputs[0], zz.inputs[1])
    fr = N("ShaderNodeMapRange"); fr.inputs["From Min"].default_value = z0; fr.inputs["From Max"].default_value = z1
    L(zz.outputs[0], fr.inputs["Value"])
    mx = N("ShaderNodeMixRGB"); L(fr.outputs["Result"], mx.inputs["Fac"]); L(a, mx.inputs["Color1"]); L(b, mx.inputs["Color2"])
    # macro variation (fields, patches)
    mv = N("ShaderNodeTexNoise"); mv.inputs["Scale"].default_value = 0.006; mv.inputs["Detail"].default_value = 4
    L(geo.outputs["Position"], mv.inputs["Vector"])
    mvr = N("ShaderNodeMapRange"); mvr.inputs["To Min"].default_value = 0.72; mvr.inputs["To Max"].default_value = 1.18
    L(mv.outputs["Fac"], mvr.inputs["Value"])
    vm = N("ShaderNodeMixRGB"); vm.blend_type = "MULTIPLY"; vm.inputs["Fac"].default_value = 1.0
    L(mx.outputs["Color"], vm.inputs["Color1"]); L(mvr.outputs["Result"], vm.inputs["Color2"])
    L(vm.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.92
    return m


def city_mat(name, night):
    """Apartment facades: plaster texture + a window grid from world position; random windows lit at night."""
    m = pbr(name, "plastered_wall_02", size=3.0, tint=(0.95, 0.93, 0.9), bright=1.0, sat=0.4, variation=0.35, streak=0.35)
    nt = m.node_tree; N = nt.nodes.new; L = nt.links.new
    bsdf = nt.nodes["Principled BSDF"]
    base_col = bsdf.inputs["Base Color"].links[0].from_socket
    geo = N("ShaderNodeNewGeometry")
    sp = N("ShaderNodeSeparateXYZ"); L(geo.outputs["Position"], sp.inputs[0])
    sn = N("ShaderNodeSeparateXYZ"); L(geo.outputs["Normal"], sn.inputs[0])

    def M(op, a, b=None, clamp=False):
        n = N("ShaderNodeMath"); n.operation = op; n.use_clamp = clamp
        for i, v in enumerate((a, b)):
            if v is None:
                continue
            if isinstance(v, (int, float)):
                n.inputs[i].default_value = v
            else:
                L(v, n.inputs[i])
        return n.outputs[0]
    ax = M("GREATER_THAN", M("ABSOLUTE", sn.outputs["X"]), 0.5)          # wall facing ±x → use y
    wall = M("LESS_THAN", M("ABSOLUTE", sn.outputs["Z"]), 0.5)
    u = M("ADD", M("MULTIPLY", sp.outputs["Y"], ax), M("MULTIPLY", sp.outputs["X"], M("SUBTRACT", 1.0, ax)))
    u = M("DIVIDE", u, 3.4)
    v = M("DIVIDE", M("SUBTRACT", sp.outputs["Z"], 7.6), 3.2)
    fu, fv = M("FRACT", u), M("FRACT", v)
    inside = M("MULTIPLY", M("MULTIPLY", M("GREATER_THAN", fu, 0.26), M("LESS_THAN", fu, 0.74)),
               M("MULTIPLY", M("GREATER_THAN", fv, 0.36), M("LESS_THAN", fv, 0.78)))
    win = M("MULTIPLY", M("MULTIPLY", inside, wall), M("GREATER_THAN", v, 0.9))
    comb = N("ShaderNodeCombineXYZ"); L(M("FLOOR", u), comb.inputs[0]); L(M("FLOOR", v), comb.inputs[1])
    L(M("FLOOR", M("DIVIDE", M("ADD", sp.outputs["X"], sp.outputs["Y"]), 37.0)), comb.inputs[2])
    wn = N("ShaderNodeTexWhiteNoise"); wn.noise_dimensions = "3D"; L(comb.outputs[0], wn.inputs["Vector"])
    lit = M("MULTIPLY", win, M("GREATER_THAN", wn.outputs["Value"], 0.74))
    glass = N("ShaderNodeMixRGB"); L(win, glass.inputs["Fac"]); L(base_col, glass.inputs["Color1"])
    glass.inputs["Color2"].default_value = (0.03, 0.035, 0.04, 1); L(glass.outputs["Color"], bsdf.inputs["Base Color"])
    rough_src = bsdf.inputs["Roughness"].links[0].from_socket if bsdf.inputs["Roughness"].links else None
    rr = N("ShaderNodeMixRGB"); L(win, rr.inputs["Fac"])
    if rough_src:
        L(rough_src, rr.inputs["Color1"])
    rr.inputs["Color2"].default_value = (0.08, 0.08, 0.08, 1)
    L(rr.outputs["Color"], bsdf.inputs["Roughness"])
    if night:
        warm = N("ShaderNodeMixRGB"); L(wn.outputs["Color"], warm.inputs["Fac"])
        warm.inputs["Color1"].default_value = (1.0, 0.72, 0.42, 1); warm.inputs["Color2"].default_value = (0.85, 0.9, 1.0, 1)
        L(warm.outputs["Color"], bsdf.inputs["Emission Color"])
        # uneven brightness: curtains, TV glow, bare bulbs
        L(M("MULTIPLY", lit, M("POWER", M("MULTIPLY", M("SUBTRACT", wn.outputs["Value"], 0.74), 3.85), 2.0), ), bsdf.inputs["Emission Strength"])
    return m


if NIGHT:
    MAT = dict(
        pier=pbr("pier", "dirty_concrete", size=3.0, tint=(0.98, 0.95, 0.9), bright=1.05, sat=0.45, variation=0.3, streak=0.4),
        pedestal=pbr("pedestal", "rough_concrete", size=2.5, tint=(1, 0.99, 0.96), bright=1.15, sat=0.4, variation=0.12),
    )
else:
    MAT = dict(
        pier=pbr("pier", "rough_concrete", size=3.0, tint=(1.0, 0.97, 0.92), bright=1.05, sat=0.5, variation=0.2, streak=0.18),
    )
MAT.update(
    girder=pbr("girder", "green_metal_rust", size=2.5, tint=(0.62, 0.8, 0.55), bright=1.0 if NIGHT else 1.05, sat=0.8,
               metallic=0.35, rough_add=0.05, variation=0.15),
    slab=pbr("slab", "rough_concrete", size=3.0, tint=(0.95, 0.93, 0.88), sat=0.4, streak=0.35),
    rail_old=pbr("rail_old", "rough_concrete", size=1.5, tint=(1.0, 0.98, 0.93), bright=1.12, sat=0.3, variation=0.25),
    rail_new=pbr("rail_new", "rough_concrete", size=1.5, tint=(1.0, 0.99, 0.96), bright=1.35, sat=0.2, variation=0.08),
    stone=pbr("stone", "river_small_rocks", size=1.6, tint=(0.95, 0.93, 0.9), bright=1.0, sat=0.4),
    wood=pbr("wood", "weathered_planks", size=2.0, tint=(0.85, 0.72, 0.58), bright=0.9, sat=0.8),
    mint=pbr("mint", "painted_metal_shutter", size=3.0, tint=(0.66, 0.9, 0.84), bright=1.05, sat=0.1, metallic=0.25, variation=0.08),
    newconc=pbr("newconc", "concrete_wall_004", size=3.0, tint=(0.96, 0.95, 0.92), bright=1.1, sat=0.3, variation=0.15, streak=0.15),
    asphalt=pbr("asphalt", "asphalt_02", size=4.0, bright=0.8, sat=0.4),
    steel=flat("steel", (0.6, 0.62, 0.64), 0.35, 0.8),
    cable=flat("cable", (0.85, 0.88, 0.9), 0.3, 0.9),
    white=flat("paint", (0.85, 0.85, 0.82), 0.6),
    water=water_mat(),
    plaster=pbr("plaster", "plastered_wall_02", size=2.5, tint=(0.96, 0.9, 0.8), bright=1.0, sat=0.5, streak=0.25),
    tile_jp=pbr("tile_jp", "roof_tiles", size=2.5, tint=(0.32, 0.32, 0.34), bright=1.0, sat=0.15, variation=0.25),
    tile_red=pbr("tile_red", "clay_roof_tiles", size=2.5, tint=(0.85, 0.6, 0.5), bright=0.9, sat=0.8),
    brick=pbr("brick", "red_brick_03", size=2.0, tint=(1.0, 0.9, 0.85), bright=0.95, sat=0.9, streak=0.2),
    timber=pbr("timber", "brown_planks_05", size=2.0, tint=(0.55, 0.45, 0.35), bright=0.8, sat=0.7),
    dark=flat("dark", (0.03, 0.03, 0.03), 0.3),
    glass=flat("glass", (0.02, 0.025, 0.03), 0.05, 0.0),
)


# ============================================================== geometry helpers
COLL = sc.collection


def obj(name, bm, mat, bevel=0.0, smooth=False):
    me = bpy.data.meshes.new(name)
    if bm.faces:
        bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.normal_update(); bm.to_mesh(me); bm.free()
    if smooth:
        for p in me.polygons:
            p.use_smooth = True
    o = bpy.data.objects.new(name, me); COLL.objects.link(o)
    if isinstance(mat, (list, tuple)):
        for mm in mat:
            me.materials.append(mm)
    elif mat:
        me.materials.append(mat)
    if bevel > 0:
        md = o.modifiers.new("bevel", "BEVEL"); md.width = bevel; md.segments = 2
        md.limit_method = "ANGLE"; md.angle_limit = math.radians(40)
    return o


def add_box(bm, c, s, rot_z=0.0, mat_index=0):
    r = bmesh.ops.create_cube(bm, size=1.0)
    for v in r["verts"]:
        v.co = Vector((v.co.x * s[0], v.co.y * s[1], v.co.z * s[2]))
        if rot_z:
            x, y = v.co.x, v.co.y
            v.co.x, v.co.y = x * math.cos(rot_z) - y * math.sin(rot_z), x * math.sin(rot_z) + y * math.cos(rot_z)
        v.co += Vector(c)
    for f in {f for v in r["verts"] for f in v.link_faces}:
        f.material_index = mat_index
    return r["verts"]


def add_prism(bm, poly, a0, a1, axis="x", mat_index=0):
    """Extrude a 2D polygon (in the plane normal to `axis`) from a0 to a1 along the axis."""
    def P(p, a):
        if axis == "x":
            return Vector((a, p[0], p[1]))
        if axis == "y":
            return Vector((p[0], a, p[1]))
        return Vector((p[0], p[1], a))
    lo = [bm.verts.new(P(p, a0)) for p in poly]
    hi = [bm.verts.new(P(p, a1)) for p in poly]
    fs = [bm.faces.new(lo[::-1]), bm.faces.new(hi)]
    n = len(poly)
    for i in range(n):
        j = (i + 1) % n
        fs.append(bm.faces.new((lo[i], lo[j], hi[j], hi[i])))
    for f in fs:
        f.material_index = mat_index
    return fs


def add_cyl(bm, c, r, h, seg=20, mat_index=0):
    res = bmesh.ops.create_cone(bm, cap_ends=True, segments=seg, radius1=r, radius2=r, depth=h)
    for v in res["verts"]:
        v.co += Vector((c[0], c[1], c[2] + h / 2))
    for f in {f for v in res["verts"] for f in v.link_faces}:
        f.material_index = mat_index


def add_rod(bm, a, b, r, seg=8, mat_index=0):
    a, b = Vector(a), Vector(b)
    d = b - a; L = d.length
    if L < 1e-4:
        return
    res = bmesh.ops.create_cone(bm, cap_ends=True, segments=seg, radius1=r, radius2=r, depth=L)
    q = Vector((0, 0, 1)).rotation_difference(d.normalized())
    for v in res["verts"]:
        v.co = q @ v.co + (a + b) / 2
    for f in {f for v in res["verts"] for f in v.link_faces}:
        f.material_index = mat_index


def add_sphere(bm, c, r, mat_index=0, seg=12):
    res = bmesh.ops.create_uvsphere(bm, u_segments=seg, v_segments=max(6, seg // 2), radius=r)
    for v in res["verts"]:
        v.co += Vector(c)
    for f in {f for v in res["verts"] for f in v.link_faces}:
        f.material_index = mat_index


def add_hip_roof(bm, c, w, d, h, over=0.9, rot=0.0, mat_index=0):
    """Hip roof over a w×d footprint (w ≥ d), ridge along the long side, deep eaves."""
    W, D = w / 2 + over, d / 2 + over
    ridge = max(0.2, W - D)
    pts = [(-W, -D, 0), (W, -D, 0), (W, D, 0), (-W, D, 0), (-ridge, 0, h), (ridge, 0, h)]
    vs = []
    for x, y, z in pts:
        xr, yr = x * math.cos(rot) - y * math.sin(rot), x * math.sin(rot) + y * math.cos(rot)
        vs.append(bm.verts.new(Vector((c[0] + xr, c[1] + yr, c[2] + z))))
    faces = [(vs[0], vs[1], vs[5], vs[4]), (vs[2], vs[3], vs[4], vs[5]), (vs[1], vs[2], vs[5]), (vs[3], vs[0], vs[4]), (vs[3], vs[2], vs[1], vs[0])]
    for f in faces:
        bm.faces.new(f).material_index = mat_index


def add_gable(bm, c, w, d, h, over=0.5, rot=0.0, mat_index=0):
    W, D = w / 2 + over, d / 2 + over
    pts = [(-W, -D, 0), (W, -D, 0), (W, D, 0), (-W, D, 0), (-W, 0, h), (W, 0, h)]
    vs = []
    for x, y, z in pts:
        xr, yr = x * math.cos(rot) - y * math.sin(rot), x * math.sin(rot) + y * math.cos(rot)
        vs.append(bm.verts.new(Vector((c[0] + xr, c[1] + yr, c[2] + z))))
    for f in [(vs[0], vs[1], vs[5], vs[4]), (vs[2], vs[3], vs[4], vs[5]), (vs[1], vs[2], vs[5]), (vs[3], vs[0], vs[4]), (vs[3], vs[2], vs[1], vs[0])]:
        bm.faces.new(f).material_index = mat_index


# ============================================================== 川端橋 (1937)
L0, NS = 300.56, 14
SPAN = L0 / NS
X0 = -L0 / 2
PIERS = [X0 + i * SPAN for i in range(1, NS)]
Y_CAP, Y_DECK = 7.4, 9.3
RAISE = 1.5 if MODERN else 0.0


def build_kawabata():
    # --- piers: twin round columns joined by an arch, cap and cornice (雙柱式拱型鏤空橋墩)
    bm = bmesh.new()
    for px in PIERS:
        add_box(bm, (px, 0, -2.4), (3.6, 8.6, 3.2))
        add_box(bm, (px, 0, -0.45), (2.8, 7.0, 0.9))
        for sy in (-1, 1):
            add_cyl(bm, (px, sy * 2.15, -4.0), 1.0, 10.2, seg=28)
        arc = [(1.15 * math.cos(math.pi - math.pi * k / 16), 4.0 + 1.15 * math.sin(math.pi - math.pi * k / 16)) for k in range(17)]
        # the arched wall is split at the crown into two simple polygons
        add_prism(bm, [(-2.15, 2.0), (-1.15, 2.0)] + arc[:9] + [(0.0, 6.2), (-2.15, 6.2)], px - 0.75, px + 0.75)
        add_prism(bm, [(0.0, 6.2)] + arc[8:] + [(1.15, 2.0), (2.15, 2.0), (2.15, 6.2)], px - 0.75, px + 0.75)
        add_box(bm, (px, 0, 6.8), (2.1, 6.0, 1.2))
        add_box(bm, (px, 0, 6.25), (2.3, 6.3, 0.18))
    obj("kb_piers", bm, MAT["pier"], bevel=0.05)
    # abutments
    bm = bmesh.new()
    for s in (-1, 1):
        add_box(bm, (s * (L0 / 2 + 3.4), 0, 3.0), (7.0, 7.6, 12.0))
    obj("kb_abut", bm, MAT["stone"], bevel=0.06)
    if RAISE:
        bm = bmesh.new()
        for px in PIERS:
            add_box(bm, (px, 0, Y_CAP + RAISE / 2), (1.9, 5.8, RAISE))
        obj("kb_pedestal", bm, MAT["pedestal"], bevel=0.03)
    z0 = Y_CAP + RAISE
    # --- riveted deck plate girders, cross frames, lateral bracing (上承式鋼鈑梁)
    bm = bmesh.new()
    H = 1.5
    for i in range(NS):
        xa, xb = X0 + i * SPAN + 0.15, X0 + (i + 1) * SPAN - 0.15
        L = xb - xa; xm = (xa + xb) / 2
        for gy in (-1.9, 1.9):
            add_box(bm, (xm, gy, z0 + H / 2), (L, 0.04, H))
            add_box(bm, (xm, gy, z0 + H - 0.035), (L, 0.46, 0.07))
            add_box(bm, (xm, gy, z0 + 0.035), (L, 0.46, 0.07))
            for sx in (-1, 1):  # angle-iron flange cover lines
                add_box(bm, (xm, gy + sx * 0.05, z0 + H - 0.12), (L, 0.06, 0.08))
            n = int(L / 1.3)
            for k in range(n + 1):
                x = xa + k * L / n
                for sx in (-1, 1):
                    add_box(bm, (x, gy + sx * 0.08, z0 + H / 2), (0.1, 0.12, H - 0.16))
        for k in range(6):
            x = xa + k * L / 5
            add_box(bm, (x, 0, z0 + H - 0.2), (0.14, 3.8, 0.16))
            add_box(bm, (x, 0, z0 + 0.25), (0.14, 3.8, 0.16))
            add_rod(bm, (x, -1.9, z0 + 0.25), (x, 1.9, z0 + H - 0.2), 0.05, 6)
            add_rod(bm, (x, 1.9, z0 + 0.25), (x, -1.9, z0 + H - 0.2), 0.05, 6)
    obj("kb_girders", bm, MAT["girder"], bevel=0.008)
    # --- deck slab + edge beams
    bm = bmesh.new()
    add_box(bm, (0, 0, z0 + 1.7), (L0 + 1, 6.0, 0.4))
    for s in (-1, 1):
        add_box(bm, (0, s * 3.05, z0 + 1.55), (L0 + 1, 0.3, 0.7))
    obj("kb_slab", bm, MAT["slab"], bevel=0.03)
    deck = z0 + 1.9
    # --- railings: concrete posts + top and mid rails (1937) / replica (2026)
    bm = bmesh.new()
    n = int(L0 / 2.1)
    for s in (-1, 1):
        y = s * 2.85
        for k in range(n + 1):
            add_box(bm, (X0 + k * L0 / n, y, deck + 0.5), (0.22, 0.22, 1.0))
        add_box(bm, (0, y, deck + 1.02), (L0, 0.28, 0.16))
        add_box(bm, (0, y, deck + 0.55), (L0, 0.12, 0.1))
        for ex in (-1, 1):  # 親柱 name posts
            add_box(bm, (ex * (L0 / 2 + 0.1), y + s * 0.4, deck + 1.3), (0.9, 0.9, 2.6))
            add_box(bm, (ex * (L0 / 2 + 0.1), y + s * 0.4, deck + 2.7), (1.1, 1.1, 0.3))
    obj("kb_rail", bm, MAT["rail_new"] if MODERN else MAT["rail_old"], bevel=0.03)
    if MODERN:
        bm = bmesh.new()
        add_box(bm, (0, 0, deck + 0.05), (L0, 5.3, 0.1))
        obj("kb_wood", bm, MAT["wood"], bevel=0.01)
        bm = bmesh.new()
        for s in (-1, 1):
            add_box(bm, (0, s * 2.68, deck + 0.92), (L0, 0.05, 0.05))
        obj("kb_led", bm, emission("led", (1.0, 0.78, 0.5), 18.0))
    return deck


# ============================================================== 新中正橋 (2019–2024)
NB_Y, NB_W, NB_C = 12.0, 24.0, -32.0


def build_new_bridge():
    L = 520
    bm = bmesh.new()
    add_box(bm, (0, NB_C, NB_Y - 1.4), (L, NB_W - 3, 2.4))
    for z in (-230, -190, -150, 150, 190, 230):
        for dy in (-6.5, 6.5):
            add_cyl(bm, (z, NB_C + dy, -4.0), 1.3, 14.4, seg=24)
        add_box(bm, (z, NB_C, NB_Y - 3.4), (3.2, NB_W - 4, 1.6))
    for z in (-107.5, 107.5):
        add_box(bm, (z, NB_C, 2.3), (10, NB_W + 6, 14))
    obj("nb_concrete", bm, MAT["newconc"], bevel=0.05)
    bm = bmesh.new()
    add_box(bm, (0, NB_C, NB_Y + 0.02), (L, NB_W - 1, 0.06))
    obj("nb_asphalt", bm, MAT["asphalt"])
    bm = bmesh.new()
    for s in (-1, 1):
        add_box(bm, (0, NB_C + s * (NB_W / 2 - 0.25), NB_Y - 0.6), (L, 0.5, 1.5))
    add_box(bm, (0, NB_C, NB_Y - 0.18), (L, NB_W, 0.35))
    obj("nb_edge", bm, MAT["mint"], bevel=0.03)
    bm = bmesh.new()
    for x in range(-L // 2, L // 2, 12):
        for dy in (-7.5, -3.8, 3.8, 7.5):
            add_box(bm, (x, NB_C + dy, NB_Y + 0.06), (5, 0.15, 0.02))
    add_box(bm, (0, NB_C, NB_Y + 0.45), (L, 0.7, 0.9))
    for s in (-1, 1):
        y = NB_C + s * (NB_W / 2 - 0.3)
        for k in range(0, L, 2):
            add_box(bm, (-L / 2 + k, y, NB_Y + 0.55), (0.08, 0.08, 1.1))
        add_box(bm, (0, y, NB_Y + 1.1), (L, 0.1, 0.1))
    obj("nb_lines", bm, MAT["white"])
    # --- three-point open-web arch: one foot at the Taipei end, split into two feet at the Yonghe end
    SPAN_A, RISE, TB = 215.0, 50.0, 0.78
    YU, YD = NB_C + NB_W / 2 + 0.5, NB_C - NB_W / 2 - 0.5

    def main(t):
        return Vector((-SPAN_A / 2 + SPAN_A * t, YU - 8.5 * math.sin(math.pi * t), NB_Y - 2.6 + RISE * 4 * t * (1 - t)))

    def branch(s):
        p = main(TB + (1 - TB) * s)
        k = s * s * (3 - 2 * s)
        p.y = p.y + (YD - p.y) * k
        return p

    def chords(fn, a, b, n, off):
        up, lo = [], []
        for i in range(n + 1):
            t = a + (b - a) * i / n
            p = fn(t); q = fn(min(1, t + 0.002)); r = fn(max(0, t - 0.002))
            tan = (q - r).normalized()
            nrm = tan.cross(Vector((0, 1, 0))).normalized()
            if nrm.z < 0:
                nrm = -nrm
            up.append(p + nrm * off); lo.append(p - nrm * off)
        return up, lo

    bm = bmesh.new()
    for fn, a, b, n in ((main, 0, 1, 90), (branch, 0, 1, 24)):
        up, lo = chords(fn, a, b, n, 1.8)
        for P in (up, lo):
            for i in range(len(P) - 1):
                add_rod(bm, P[i], P[i + 1], 0.78, 16)
            for p in P[1:-1]:
                add_sphere(bm, p, 0.78, seg=16)
        for i in range(len(up)):
            add_rod(bm, lo[i], up[i], 0.32, 10)
        for i in range(0, len(up) - 1, 2):
            add_rod(bm, lo[i], up[i + 1], 0.2, 8)
    obj("nb_arch", bm, MAT["mint"], smooth=True)
    if NIGHT:  # LED strips along the lower chords (琴弦 lighting), facing upstream
        led = bmesh.new()
        for fn, n in ((main, 90), (branch, 24)):
            _, lo_ = chords(fn, 0, 1, n, 1.8)
            pts = [p + Vector((0, 0.85, -0.2)) for p in lo_]
            for i in range(len(pts) - 1):
                add_rod(led, pts[i], pts[i + 1], 0.09, 6)
        obj("nb_arch_led", led, emission("archled", (0.82, 0.92, 1.0), 26.0))
    bm = bmesh.new()
    _, lo = chords(main, 0, 1, 215, 1.8)
    for k in range(14):
        x = -78 + k * 12
        i = int(round((x + SPAN_A / 2) / SPAN_A * 215))
        p = lo[i]
        add_rod(bm, p, (x, YU - 1.2, NB_Y + 0.3), 0.08, 8)
        add_rod(bm, p, (x, YD + 1.2, NB_Y + 0.3), 0.08, 8)
    obj("nb_cables", bm, MAT["cable"], smooth=True)
    # street lamps
    bm = bmesh.new(); heads = bmesh.new()
    lamp_pts = []
    for x in range(-L // 2 + 10, L // 2, 32):
        for s in (-1, 1):
            y = NB_C + s * (NB_W / 2 - 0.6)
            add_cyl(bm, (x, y, NB_Y), 0.14, 10, seg=10)
            add_box(bm, (x, y - s * 1.0, NB_Y + 10), (0.14, 2.0, 0.14))
            add_box(heads, (x, y - s * 1.9, NB_Y + 9.88), (0.45, 0.9, 0.18))
            lamp_pts.append((x, y - s * 1.9, NB_Y + 9.7))
    obj("nb_poles", bm, MAT["steel"], bevel=0.01)
    obj("nb_heads", heads, emission("lamp", (1.0, 0.86, 0.66), 40.0) if NIGHT else flat("lamphead", (0.3, 0.3, 0.3), 0.4, 0.5))
    return lamp_pts


# ============================================================== terrain, city, vegetation
W_RIVER = 128.0


def h_old(x, y):
    d = abs(x)
    n = (math.sin(x * 0.013 + y * 0.021) + math.sin(x * 0.037 - y * 0.011)) * 0.35
    if d < W_RIVER - 10:
        return -4.2
    if d < W_RIVER + 16:
        t = (d - (W_RIVER - 10)) / 26
        return -4.2 + 7.6 * (t * t * (3 - 2 * t)) + n * 0.2
    return 3.6 + n + min(1.0, (d - W_RIVER - 16) / 300) * 0.8


def h_new(x, y):
    d = abs(x)
    n = (math.sin(x * 0.02 + y * 0.03)) * 0.25
    if d < W_RIVER - 10:
        return -4.2
    if d < W_RIVER + 3:
        t = (d - (W_RIVER - 10)) / 13
        return -4.2 + 5.5 * t
    if d < W_RIVER + 66:
        return 1.3 + n
    if d < W_RIVER + 76:
        return 1.3 + 7.9 * (d - W_RIVER - 66) / 10
    if d < W_RIVER + 86:
        return 9.2
    if d < W_RIVER + 94:
        return 9.2 - 2.0 * (d - W_RIVER - 86) / 8
    return 7.2


def axis_samples(lo, hi, dense_ranges, fine=2.0, coarse=20.0):
    xs, x = [], lo
    while x < hi:
        xs.append(x)
        step = fine if any(a <= abs(x) <= b for a, b in dense_ranges) else coarse
        x += step
    xs.append(hi)
    return xs


def build_terrain():
    hf = h_new if MODERN else h_old
    dense = [(W_RIVER - 14, W_RIVER + 100)] if MODERN else [(W_RIVER - 14, W_RIVER + 24)]
    xs = axis_samples(-3200, 3200, dense, 2.0, 24.0)
    ys = axis_samples(-2600, 2600, [(0, 700)], 8.0, 40.0)
    bm = bmesh.new()
    grid = [[bm.verts.new((x, y, hf(x, y))) for x in xs] for y in ys]
    for j in range(len(ys) - 1):
        for i in range(len(xs) - 1):
            bm.faces.new((grid[j][i], grid[j][i + 1], grid[j + 1][i + 1], grid[j + 1][i]))
    if MODERN:
        m = ground_mat("ground", ("gravelly_sand", 4.0, (0.8, 0.78, 0.72), 0.6), ("sparse_grass", 5.0, (0.75, 0.85, 0.65), 0.9), 0.4, 1.6)
    else:
        m = ground_mat("ground", ("coast_sand_01", 5.0, (0.9, 0.85, 0.75), 0.7), ("aerial_grass_rock", 12.0, (0.85, 0.95, 0.7), 1.0), 1.6, 3.2)
    obj("terrain", bm, m, smooth=True)
    if MODERN:  # concrete levee walls and the riverside roads
        bm = bmesh.new()
        for s in (-1, 1):
            add_box(bm, (s * (W_RIVER + 81), 0, 9.25), (10.2, 5200, 0.1))
            add_box(bm, (s * (W_RIVER + 71), 0, 5.3), (0.5, 5200, 7.9))
        obj("levee", bm, MAT["newconc"])
        bm = bmesh.new()
        for s in (-1, 1):
            add_box(bm, (s * (W_RIVER + 130), 0, 7.25), (60, 5200, 0.1))
        obj("city_ground", bm, MAT["asphalt"])
    bm = bmesh.new()
    add_box(bm, (0, 0, -0.02), (2 * W_RIVER + 40, 6000, 0.04))
    obj("water", bm, MAT["water"])
    # distant hills (觀音山 downstream NW, 大屯 north, southern ridges)
    bm = bmesh.new()
    for cx, cy, hgt, rad in ((-7000, -9000, 620, 2600), (-2000, -12500, 1090, 4200), (3500, -12000, 1100, 3600),
                             (9000, 3000, 520, 3000), (-9000, 6000, 480, 3500), (2500, 9000, 600, 3500)):
        seg, rings = 96, 24
        top = bm.verts.new((cx, cy, hgt))
        prev = None
        for r in range(1, rings + 1):
            rr = rad * r / rings
            ring = []
            for k in range(seg):
                a = 2 * math.pi * k / seg
                jitter = 1 + 0.22 * math.sin(a * 2 + cx) + 0.1 * math.sin(a * 5 + cy) + 0.05 * math.sin(a * 9 + cx * 0.3)
                ex = 1.0 + 0.6 * abs(math.cos(a))                     # elongated ridge
                z = hgt * math.exp(-((r / rings) / ex) ** 2 * 3.0) * jitter - 20 * (r == rings)
                ring.append(bm.verts.new((cx + rr * math.cos(a), cy + rr * math.sin(a), z)))
            for k in range(seg):
                if prev is None:
                    bm.faces.new((top, ring[k], ring[(k + 1) % seg]))
                else:
                    bm.faces.new((prev[k], ring[k], ring[(k + 1) % seg], prev[(k + 1) % seg]))
            prev = ring
    obj("hills", bm, pbr("forest", "aerial_grass_rock", size=90.0, tint=(0.22, 0.34, 0.2), bright=0.8, sat=1.0, variation=0.5, bump=0.1), smooth=True)


FARMS = []


def build_old_town():
    """1930s: 川端町 wooden houses with black-tiled hip roofs (Taipei, x<0); farmhouses and fields (Yonghe, x>0)."""
    walls, roofs, wins = bmesh.new(), bmesh.new(), bmesh.new()
    far = bmesh.new(); farroof = bmesh.new()
    for i in range(900):
        x = -rng.uniform(W_RIVER + 22, 1800) ** 1.0
        y = rng.uniform(-1600, 1600)
        if abs(y) < 14 and x > -400:
            continue
        dens = max(0.05, 1 - (abs(x) - W_RIVER) / 1500)
        if rng.random() > dens:
            continue
        w, d, h = rng.uniform(8, 14), rng.uniform(7, 11), rng.uniform(3.4, 5.6)
        rot = rng.uniform(-0.08, 0.08)
        z = h_old(x, y) - 0.3
        add_box(walls, (x, y, z + h / 2), (w, d, h), rot)
        add_hip_roof(roofs, (x, y, z + h), w, d, h * 0.45, 0.95, rot)
        for k in range(int(w / 3)):
            ox = -w / 2 + 1.5 + k * 3
            add_box(wins, (x + ox * math.cos(rot), y + ox * math.sin(rot) + d / 2 + 0.02, z + h * 0.55), (1.6, 0.06, 1.3), rot)
    for i in range(240):  # Yonghe side: farmhouses (三合院) in paddies
        x = rng.uniform(W_RIVER + 40, 2600); y = rng.uniform(-2000, 2000)
        FARMS.append((x, y))
        z = h_old(x, y) - 0.3; rot = rng.choice([0, math.pi / 2]) + rng.uniform(-0.15, 0.15)
        c, s_ = math.cos(rot), math.sin(rot)
        for (ox, oy, w, d) in ((0, -5, 14, 5.5), (-7.4, 2.2, 4.6, 9), (7.4, 2.2, 4.6, 9)):
            px, py = x + ox * c - oy * s_, y + ox * s_ + oy * c
            add_box(far, (px, py, z + 1.6), (w, d, 3.2), rot + (math.pi / 2 if w < d else 0) * 0)
            add_gable(farroof, (px, py, z + 3.2), max(w, d), min(w, d), 1.8, 0.4, rot + (math.pi / 2 if d > w else 0))
    obj("jp_walls", walls, MAT["plaster"], bevel=0.04)
    obj("jp_roofs", roofs, MAT["tile_jp"])
    obj("jp_windows", wins, MAT["timber"])
    obj("farm_walls", far, MAT["brick"], bevel=0.04)
    obj("farm_roofs", farroof, MAT["tile_red"])


def boxes_mesh(name, boxes, mat):
    """Fast path for thousands of axis-aligned boxes: one from_pydata call instead of bmesh ops."""
    V, F = [], []
    for (cx, cy, cz), (sx, sy, sz) in boxes:
        b = len(V); hx, hy, hz = sx / 2, sy / 2, sz / 2
        V += [(cx - hx, cy - hy, cz - hz), (cx + hx, cy - hy, cz - hz), (cx + hx, cy + hy, cz - hz), (cx - hx, cy + hy, cz - hz),
              (cx - hx, cy - hy, cz + hz), (cx + hx, cy - hy, cz + hz), (cx + hx, cy + hy, cz + hz), (cx - hx, cy + hy, cz + hz)]
        F += [(b, b + 3, b + 2, b + 1), (b + 4, b + 5, b + 6, b + 7), (b, b + 1, b + 5, b + 4),
              (b + 1, b + 2, b + 6, b + 5), (b + 2, b + 3, b + 7, b + 6), (b + 3, b, b + 4, b + 7)]
    me = bpy.data.meshes.new(name); me.from_pydata(V, [], F); me.update()
    me.materials.append(mat)
    o = bpy.data.objects.new(name, me); COLL.objects.link(o)
    return o


def build_city():
    """Modern Taipei / Yonghe: apartment blocks; lit windows at night."""
    blocks, tops = [], []
    for side in (-1, 1):
        for gx in range(0, 3000, 40):
            for gy in range(-2600, 2600, 40):
                if rng.random() > 0.78:
                    continue
                x = side * (W_RIVER + 110 + gx + rng.uniform(-4, 4)); y = gy + rng.uniform(-4, 4)
                if abs(y) < 22 and gx < 400:
                    continue
                w, d = rng.uniform(14, 26), rng.uniform(14, 26)
                h = rng.uniform(18, 42) if rng.random() > 0.12 else rng.uniform(60, 140)
                h *= 0.8 + gx / 3000 * 0.6
                blocks.append(((x, y, 7.2 + h / 2), (w, d, h)))
                if gx < 1500:
                    tops.append(((x + rng.uniform(-3, 3), y + rng.uniform(-3, 3), 7.2 + h + 0.8), (2.4, 2.4, 1.6)))
    boxes_mesh("city", blocks, city_mat("city", NIGHT))
    boxes_mesh("city_tops", tops, MAT["newconc"])


def sampans(spots):
    """Wooden ferry boats (網溪渡) with a boatman poling from the stern."""
    hull, ppl = bmesh.new(), bmesh.new()
    for i, (x, y) in enumerate(spots):
        prof = [(-0.95, 0.35), (-0.8, -0.25), (0.0, -0.45), (0.8, -0.25), (0.95, 0.35)]
        L = rng.uniform(7.5, 9.5)
        add_prism(hull, [(py, pz) for py, pz in prof], x - L / 2, x + L / 2, axis="x")
        for sx in (-1, 1):  # raked bow and stern
            add_prism(hull, [(-0.9, 0.35), (0.9, 0.35), (0.0, -0.4)], x + sx * L / 2, x + sx * (L / 2 + 0.9), axis="x")
        add_box(hull, (x - 0.6, y * 0, 0.8), (2.4, 1.6, 0.08))
        bx = x + L / 2 - 1.0
        add_cyl(ppl, (bx, 0, 0.3), 0.2, 1.1, seg=10); add_sphere(ppl, (bx, 0, 1.55), 0.12, seg=10)
        add_cyl(ppl, (bx, 0, 1.64), 0.26, 0.03, seg=12)
        add_rod(ppl, (bx + 0.2, 0, 1.4), (bx + 1.8, 0, -2.5), 0.03, 6)
        for k in range(rng.randrange(2, 5)):
            add_cyl(ppl, (x - 2.5 + k * 1.1, rng.uniform(-0.3, 0.3), 0.3), 0.19, 0.75, seg=10)
            add_sphere(ppl, (x - 2.5 + k * 1.1, 0, 1.2), 0.11, seg=10)
        for bm_ in (hull, ppl):
            for v in bm_.verts:
                if not v.tag:
                    v.co.y += y; v.tag = True
    obj("sampans", hull, MAT["timber"], bevel=0.02)
    obj("boatmen", ppl, flat("boatmen", (0.2, 0.19, 0.17), 0.8), smooth=True)


def load_trees():
    """Append Poly Haven tree models (LOD1 + trunk), make them renderable and fix their texture paths."""
    protos = []
    for f in sorted(glob.glob(os.path.join(A.assets, "models", "*", "*_1k.blend"))):
        before = set(bpy.data.images)
        with bpy.data.libraries.load(f, link=False) as (src, dst):
            dst.objects = [n for n in src.objects if ("LOD1" in n or n.endswith("trunk")) and "geometry_nodes" not in n]
        for im in set(bpy.data.images) - before:
            if im.filepath.startswith("//"):
                im.filepath = os.path.join(os.path.dirname(f), im.filepath[2:])
        meshes = [o for o in dst.objects if o is not None and o.type == "MESH"]
        c = bpy.data.collections.new("proto_" + os.path.basename(f)); sc.collection.children.link(c)
        for o in meshes:
            o.hide_render = False; o.hide_viewport = False
            c.objects.link(o)
        lc = next((l for l in vl.layer_collection.children if l.collection == c), None)
        if lc:
            lc.exclude = True
        dims = [max(o.dimensions) for o in meshes]
        print("tree proto", os.path.basename(f), len(meshes), "objects, size", round(max(dims or [0]), 1), "m")
        protos.append(c)
    return protos


def scatter_trees(protos, n, place):
    if not protos:
        return
    for i in range(n):
        p = place()
        if p is None:
            continue
        e = bpy.data.objects.new(f"tree{i}", None)
        e.instance_type = "COLLECTION"; e.instance_collection = rng.choice(protos)
        e.location = p[:3]; e.rotation_euler = (0, 0, rng.uniform(0, 6.283)); e.scale = ((p[3] if len(p) > 3 else 1.0) * rng.uniform(0.75, 1.25),) * 3
        COLL.objects.link(e)


# ============================================================== people, vehicles, lights
def people_on_deck(deck, n, era):
    bm = bmesh.new()
    cloth = [(0.9, 0.88, 0.82), (0.15, 0.15, 0.17), (0.35, 0.4, 0.5), (0.55, 0.45, 0.35), (0.7, 0.2, 0.2), (0.25, 0.35, 0.3)]
    mats = [flat(f"cloth{i}", c, 0.8) for i, c in enumerate(cloth)] + [flat("skin", (0.62, 0.45, 0.35), 0.6), flat("hat", (0.8, 0.72, 0.5), 0.8)]
    for i in range(n):
        x = rng.uniform(-L0 / 2 + 6, L0 / 2 - 6); y = rng.uniform(-2.2, 2.2)
        c = rng.randrange(6)
        for sx in (-0.1, 0.1):
            add_cyl(bm, (x, y + sx, deck), 0.08, 0.85, seg=8, mat_index=c)
        add_cyl(bm, (x, y, deck + 0.82), 0.2, 0.62, seg=10, mat_index=c)
        add_sphere(bm, (x, y, deck + 1.58), 0.11, mat_index=6, seg=10)
        if era == "old" and rng.random() < 0.5:
            add_cyl(bm, (x, y, deck + 1.66), 0.2, 0.03, seg=12, mat_index=7)
            add_cyl(bm, (x, y, deck + 1.66), 0.11, 0.1, seg=10, mat_index=7)
    obj("people", bm, mats, smooth=True)


def vintage_car(deck, x, y, rot=0.0):
    bm = bmesh.new()
    add_box(bm, (x, y, deck + 0.78), (3.8, 1.55, 0.5))
    add_box(bm, (x - 0.4, y, deck + 1.5), (2.0, 1.45, 0.95))
    add_box(bm, (x + 1.25, y, deck + 1.08), (1.35, 1.05, 0.55))
    for wx in (-1.3, 1.25):
        for wy in (-0.78, 0.78):
            res = bmesh.ops.create_cone(bm, cap_ends=True, segments=16, radius1=0.38, radius2=0.38, depth=0.16)
            for v in res["verts"]:
                v.co = Vector((v.co.x, v.co.z, v.co.y)) + Vector((x + wx, y + wy, deck + 0.38))
    obj("car37", bm, flat("carpaint", (0.03, 0.03, 0.035), 0.25, 0.3), bevel=0.05)


def flags(deck):
    bm = bmesh.new(); red, wht = bmesh.new(), bmesh.new()
    for x in range(int(-L0 / 2) + 8, int(L0 / 2), 16):
        for s in (-1, 1):
            y = s * 2.95
            add_cyl(bm, (x, y, deck + 1.1), 0.03, 2.4, seg=6)
            add_box(red if (x // 16) % 2 else wht, (x + 0.5, y, deck + 3.1), (1.0, 0.02, 0.65))
    obj("flagpoles", bm, MAT["steel"])
    obj("flags_r", red, flat("flagred", (0.7, 0.05, 0.05), 0.8))
    obj("flags_w", wht, flat("flagwhite", (0.9, 0.9, 0.86), 0.8))


def cars_on_new_bridge(n):
    body, head, tail = bmesh.new(), bmesh.new(), bmesh.new()
    cols = [(0.8, 0.8, 0.8), (0.05, 0.05, 0.06), (0.6, 0.6, 0.62), (0.5, 0.05, 0.05), (0.1, 0.2, 0.4), (0.85, 0.7, 0.1)]
    mats = [flat(f"car{i}", c, 0.25, 0.4) for i, c in enumerate(cols)] + [MAT["glass"]]
    for i in range(n):
        lane = rng.choice([-5.7, -1.9, 1.9, 5.7]); d = 1 if lane > 0 else -1
        x = rng.uniform(-240, 240); y = NB_C + lane; c = rng.randrange(6)
        add_box(body, (x, y, NB_Y + 0.62), (4.4, 1.8, 0.75), mat_index=c)
        add_box(body, (x - 0.2 * d, y, NB_Y + 1.28), (2.3, 1.62, 0.6), mat_index=6)
        add_box(head, (x + d * 2.22, y, NB_Y + 0.7), (0.05, 1.4, 0.16))
        add_box(tail, (x - d * 2.22, y, NB_Y + 0.75), (0.05, 1.4, 0.14))
    obj("cars", body, mats, bevel=0.08)
    obj("headl", head, emission("head", (1.0, 0.95, 0.85), 30.0 if NIGHT else 0.5))
    obj("taill", tail, emission("tail", (1.0, 0.08, 0.04), 18.0 if NIGHT else 0.3))


def light(kind, loc, energy, color, rot=None, size=0.3, spot=None):
    ld = bpy.data.lights.new(f"{kind}", kind); ld.energy = energy; ld.color = color
    if kind in ("POINT", "SPOT", "AREA"):
        ld.shadow_soft_size = size
    if spot:
        ld.spot_size, ld.spot_blend = spot
    o = bpy.data.objects.new(ld.name, ld); o.location = loc
    if rot:
        o.rotation_euler = rot
    COLL.objects.link(o)
    return o


def world_hdri(name, strength, sun_az=None):
    world.use_nodes = True
    nt = world.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    im = bpy.data.images.load(glob.glob(os.path.join(A.assets, "hdri", name + "*"))[0])
    import numpy as np
    w, h = im.size
    px = np.empty(w * h * 4, dtype=np.float32); im.pixels.foreach_get(px); px = px.reshape(h, w, 4)
    lum = px[..., 0] * .2126 + px[..., 1] * .7152 + px[..., 2] * .0722
    j, i = np.unravel_index(np.argmax(lum), lum.shape)
    az, el = math.degrees((0.5 - (i + .5) / w) * 2 * math.pi), math.degrees(((j + .5) / h - .5) * math.pi)
    rot = 0.0 if sun_az is None else math.radians(az - sun_az)
    tc = nt.nodes.new("ShaderNodeTexCoord"); mp = nt.nodes.new("ShaderNodeMapping"); mp.inputs["Rotation"].default_value[2] = rot
    env = nt.nodes.new("ShaderNodeTexEnvironment"); env.image = im
    bg = nt.nodes.new("ShaderNodeBackground"); bg.inputs["Strength"].default_value = strength
    out = nt.nodes.new("ShaderNodeOutputWorld")
    nt.links.new(tc.outputs["Generated"], mp.inputs["Vector"]); nt.links.new(mp.outputs["Vector"], env.inputs["Vector"])
    nt.links.new(env.outputs["Color"], bg.inputs["Color"]); nt.links.new(bg.outputs["Background"], out.inputs["Surface"])
    print(f"HDRI {name}: sun az {az:.0f} el {el:.0f}")
    return el


def sun(az, el, energy, color):
    ld = bpy.data.lights.new("sun", "SUN"); ld.energy = energy; ld.angle = math.radians(1.0); ld.color = color
    o = bpy.data.objects.new("sun", ld)
    d = Vector((math.cos(math.radians(el)) * math.cos(math.radians(az)), math.cos(math.radians(el)) * math.sin(math.radians(az)), math.sin(math.radians(el))))
    o.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()
    COLL.objects.link(o)


def camera(loc, target, lens):
    cd = bpy.data.cameras.new("cam"); cd.lens = lens; cd.sensor_width = 36; cd.clip_end = 30000
    o = bpy.data.objects.new("cam", cd); o.location = loc
    o.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    COLL.objects.link(o); sc.camera = o


def haze(color, amount):
    sc.use_nodes = True
    nt = sc.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    rl = nt.nodes.new("CompositorNodeRLayers")
    mul = nt.nodes.new("CompositorNodeMath"); mul.operation = "MULTIPLY"; mul.inputs[1].default_value = amount
    mix = nt.nodes.new("CompositorNodeMixRGB"); mix.inputs[2].default_value = (*color, 1)
    comp = nt.nodes.new("CompositorNodeComposite")
    nt.links.new(rl.outputs["Mist"], mul.inputs[0]); nt.links.new(mul.outputs[0], mix.inputs[0])
    nt.links.new(rl.outputs["Image"], mix.inputs[1]); nt.links.new(mix.outputs[0], comp.inputs["Image"])
    # depth for the AI polish pass: 1 = near (3 m), 0 = far (≥ 3 km) or sky, log scale
    chain = rl.outputs["Depth"]
    for op, v in (("MAXIMUM", 3.0), ("DIVIDE", 3.0), ("LOGARITHM", math.e), ("DIVIDE", math.log(1000.0))):
        n = nt.nodes.new("CompositorNodeMath"); n.operation = op; n.inputs[1].default_value = v
        nt.links.new(chain, n.inputs[0]); chain = n.outputs[0]
    inv = nt.nodes.new("CompositorNodeMath"); inv.operation = "SUBTRACT"; inv.use_clamp = True; inv.inputs[0].default_value = 1.0
    nt.links.new(chain, inv.inputs[1])
    fo = nt.nodes.new("CompositorNodeOutputFile")
    fo.base_path = os.path.dirname(os.path.abspath(A.out))
    fo.format.file_format = "PNG"; fo.format.color_mode = "BW"; fo.format.color_depth = "16"
    fo.file_slots[0].path = os.path.splitext(os.path.basename(A.out))[0] + "_depth"
    nt.links.new(inv.outputs[0], fo.inputs[0])
    # structure mask (both bridges) so the AI polish can treat them gently
    idm = nt.nodes.new("CompositorNodeIDMask"); idm.index = 1; idm.use_antialiasing = True
    nt.links.new(rl.outputs["IndexOB"], idm.inputs[0])
    fo.file_slots.new(os.path.splitext(os.path.basename(A.out))[0] + "_mask")
    nt.links.new(idm.outputs[0], fo.inputs[1])


# ============================================================== shots
deck = build_kawabata(); tick('bridge')
build_terrain(); tick('terrain')
protos = load_trees(); tick('trees loaded')
if A.shot == "open":
    build_old_town()
    people_on_deck(deck, 46, "old")
    vintage_car(deck, 18, 1.2); vintage_car(deck, -64, -1.2)
    flags(deck)
    sampans([(96, -31), (58, -16), (8, 30)])

    def place_old():
        r = rng.random()
        if r < 0.55 and FARMS:                       # groves around the sanheyuan farmhouses
            fx, fy = rng.choice(FARMS); a = rng.uniform(0, 6.283); d = rng.uniform(10, 26)
            x, y = fx + d * math.cos(a), fy + d * math.sin(a)
        elif r < 0.8:                               # rows along both riverbanks
            x = rng.choice([-1, 1]) * rng.uniform(W_RIVER + 22, W_RIVER + 60); y = rng.uniform(-1500, 1500)
        else:
            x = rng.choice([-1, 1]) * rng.uniform(W_RIVER + 30, 2600); y = rng.uniform(-2000, 2000)
        if abs(x) < W_RIVER + 20 or (abs(y) < 12 and abs(x) < 200):
            return None
        return (x, y, h_old(x, y) - 0.2, rng.uniform(1.9, 3.1))
    scatter_trees(protos, 2600, place_old)
    el = world_hdri("kloofendal_48d_partly_cloudy_puresky", 1.0, sun_az=-42)
    sun(-42, 32, 3.4, (1.0, 0.94, 0.86))
    haze((0.72, 0.76, 0.8), 0.5)
    cam = ((150, -52, 6.5), (30, 2, 6.5), 28)
else:
    build_city(); tick('city')
    lamp_pts = build_new_bridge(); tick('new bridge')
    cars_on_new_bridge(44)
    people_on_deck(deck, 60, "new")

    def place_park():
        x = rng.choice([-1, 1]) * rng.uniform(W_RIVER + 8, W_RIVER + 62); y = rng.uniform(-1500, 1500)
        if abs(y) < 40:
            return None
        return (x, y, h_new(x, y) - 0.2, rng.uniform(1.8, 2.8))
    scatter_trees(protos, 900, place_park)
    world_hdri("qwantani_night_puresky", 0.1)
    sun(-128, 25, 0.06, (0.7, 0.78, 1.0))    # moonlight
    # 投射燈：lights at every pier base, pointing up the columns and toward the new bridge
    for px in PIERS:
        for sy in (-1, 1):
            # spots point down -Z by default; rotation_x = pi + tilt aims them up, leaning in toward the columns
            up = (math.pi + sy * math.radians(10), 0, 0)
            light("SPOT", (px + 1.4, sy * 3.3, 0.5), 900, (1.0, 0.7, 0.42), rot=up, size=0.2, spot=(math.radians(70), 0.6))
            light("SPOT", (px - 1.4, sy * 3.3, 0.5), 900, (1.0, 0.7, 0.42), rot=up, size=0.2, spot=(math.radians(70), 0.6))
        # a flood from each pier cap thrown across onto the new bridge's girders (downstream = -y)
        light("SPOT", (px, -3.6, Y_CAP + RAISE + 0.2), 700, (1.0, 0.8, 0.55), rot=(math.pi + math.radians(75), 0, 0), size=0.2, spot=(math.radians(40), 0.7))
    # soft floods from the deck onto the arch ribs
    for k in range(1, 10):
        t = k / 10
        x = -107.5 + 215 * t
        # from the upstream deck edge, tilted toward the rib so its camera-facing side is lit
        lean = math.atan2(8.5 * math.sin(math.pi * t) + 1.0, 42.0)
        light("SPOT", (x, NB_C + NB_W / 2 - 0.6, NB_Y + 0.6), 3200, (0.86, 0.93, 1.0), rot=(math.pi + lean, 0, 0), size=0.4, spot=(math.radians(34), 0.5))
    for (x, y, z) in lamp_pts:
        light("POINT", (x, y, z), 260, (1.0, 0.85, 0.65), size=0.3)
    haze((0.02, 0.025, 0.04), 0.3)
    cam = ((120, 40, 5.5), (-20, -6, 14.5), 20)

if A.cam:
    v = [float(t) for t in A.cam.split(",")]
    cam = (tuple(v[0:3]), tuple(v[3:6]), v[6] if len(v) > 6 else 30)
camera(*cam)
os.makedirs(os.path.dirname(os.path.abspath(A.out)), exist_ok=True)
sc.render.filepath = os.path.abspath(A.out)
print("objects:", len(bpy.data.objects), "rendering", A.shot, A.res, A.samples)
for o in bpy.data.objects:
    if o.name.startswith(("kb_", "nb_")):
        o.pass_index = 1
tick('scene built')
bpy.ops.render.render(write_still=True)
tick('rendered')
print("saved", A.out)
