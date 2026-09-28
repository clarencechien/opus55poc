"""Bake Cycles lighting into lightmaps and export a phone-friendly GLB (called from interior_scene.py --bake DIR).

Output in DIR/<variant>/:
  scene.glb        geometry (UVMap = texture UVs in texture repeats, LM = lightmap UVs), material names only
  props.glb        imported CC0 props with their own materials (lit in the viewer by an ambient/hemisphere light)
  lm_*.png         lightmaps: sRGB-encoded (L / scale), decode with lightMapIntensity = scale * pi (MeshBasicMaterial)
  tex/*.jpg        albedo textures with the Blender tint / saturation / brightness already applied (1k)
  manifest.json    materials, lightmaps, sky, exposure, cameras, room labels
The viewer draws baked objects with MeshBasicMaterial(map * lightMap): no real-time lighting, so it runs on phones.
"""
import json
import math
import os

import bpy
import numpy as np


def srgb_to_lin(c):
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def lin_to_srgb(c):
    c = np.clip(c, 0, 1)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * np.power(c, 1 / 2.4) - 0.055)


def realize(objs):
    """apply modifiers so the exported / baked mesh is what Cycles renders"""
    dg = bpy.context.evaluated_depsgraph_get()
    for o in objs:
        if o.type != "MESH" or not o.modifiers:
            continue
        me = bpy.data.meshes.new_from_object(o.evaluated_get(dg))
        o.modifiers.clear(); o.data = me


def join(objs, name):
    objs = [o for o in objs if o.type == "MESH"]
    if not objs:
        return None
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    if len(objs) > 1:
        bpy.ops.object.join()
    o = bpy.context.view_layer.objects.active
    o.name = name
    return o


def split_small(o, amax, name, pred=None):
    """move faces smaller than amax (m2) -- or matching pred(face) -- into a new object"""
    import bmesh
    bpy.ops.object.select_all(action="DESELECT")
    o.select_set(True); bpy.context.view_layer.objects.active = o
    bpy.ops.object.mode_set(mode="EDIT")
    bm = bmesh.from_edit_mesh(o.data)
    n = 0
    for f in bm.faces:
        f.select = pred(f) if pred else f.calc_area() < amax
        n += f.select
    bmesh.update_edit_mesh(o.data)
    if n:
        bpy.ops.mesh.separate(type="SELECTED")
    bpy.ops.object.mode_set(mode="OBJECT")
    new = [x for x in bpy.context.selected_objects if x is not o]
    if not new:
        return None
    new[0].name = name
    return new[0]


def bake_corner_colours(o, samples, tick):
    """Cycles diffuse lighting baked per face corner; returns the scale used to normalise"""
    me = o.data
    attr = me.color_attributes.new("LIGHT", "FLOAT_COLOR", "CORNER")
    me.color_attributes.active_color = attr
    bpy.ops.object.select_all(action="DESELECT")
    o.select_set(True); bpy.context.view_layer.objects.active = o
    bpy.context.scene.cycles.samples = samples
    tick(f"baking corner colours {o.name}: {len(me.polygons)} faces")
    bpy.ops.object.bake(type="DIFFUSE", pass_filter={"DIRECT", "INDIRECT"}, target="VERTEX_COLORS")
    c = np.empty(len(attr.data) * 4, np.float32); attr.data.foreach_get("color", c); c = c.reshape(-1, 4)
    scale = float(np.percentile(c[:, :3], 99.7)) * 1.15 or 1.0
    c[:, :3] = np.clip(c[:, :3] / scale, 0, 1); c[:, 3] = 1.0
    attr.data.foreach_set("color", c.ravel())
    tick(f"baked corner colours {o.name}")
    return scale


def mesh_area(o):
    return sum(p.area for p in o.data.polygons)


def lightmap_uv(o, tick):
    bpy.ops.object.select_all(action="DESELECT")
    o.select_set(True); bpy.context.view_layer.objects.active = o
    uv = o.data.uv_layers.new(name="LM")
    o.data.uv_layers.active = uv
    o.data.uv_layers["UVMap"].active_render = True
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(60), island_margin=0.0, area_weight=0.0, correct_aspect=True, scale_to_bounds=False)
    bpy.ops.uv.select_all(action="SELECT")
    bpy.ops.uv.average_islands_scale()
    bpy.ops.uv.pack_islands(rotate=True, margin=0.0008, shape_method="AABB")
    bpy.ops.object.mode_set(mode="OBJECT")
    tick(f"LM uv {o.name}: {len(o.data.polygons)} faces")


def denoise(image, size, tick):
    """OIDN through the compositor (Image -> Denoise -> Composite), returned as float RGB array"""
    sc = bpy.context.scene
    try:
        sc.use_nodes = True
        nt = sc.node_tree
        for n in list(nt.nodes):
            nt.nodes.remove(n)
        im = nt.nodes.new("CompositorNodeImage"); im.image = image
        dn = nt.nodes.new("CompositorNodeDenoise"); dn.use_hdr = True; dn.prefilter = "FAST"
        comp = nt.nodes.new("CompositorNodeComposite")
        nt.links.new(im.outputs["Image"], dn.inputs["Image"]); nt.links.new(dn.outputs["Image"], comp.inputs["Image"])
        sc.render.resolution_x, sc.render.resolution_y = size
        sc.render.resolution_percentage = 100
        sc.cycles.samples = 1; sc.cycles.use_denoising = False
        cam = bpy.data.objects.get("X_bakecam")
        if cam is None:
            cd = bpy.data.cameras.new("bakecam"); cam = bpy.data.objects.new("X_bakecam", cd)
            sc.collection.objects.link(cam); cam.location = (0, 0, -50)
        sc.camera = cam
        for o in sc.objects:                   # render nothing but keep the compositor running
            o.hide_render = True
        sc.render.image_settings.file_format = "OPEN_EXR"; sc.render.image_settings.color_depth = "32"
        sc.render.image_settings.color_mode = "RGB"
        tmp = os.path.join(bpy.app.tempdir or "/tmp", f"dn_{image.name}.exr")
        bpy.ops.render.render(write_still=False)
        bpy.data.images["Render Result"].save_render(tmp)
        out = bpy.data.images.load(tmp)
        px = np.empty(size[0] * size[1] * 4, dtype=np.float32); out.pixels.foreach_get(px)
        for o in sc.objects:
            o.hide_render = False
        tick(f"denoised {image.name}")
        return px.reshape(size[1], size[0], 4)[..., :3]
    except Exception as e:  # noqa: BLE001
        print("[bake] denoise failed, using raw bake:", e)
        for o in sc.objects:
            o.hide_render = False
        px = np.empty(size[0] * size[1] * 4, dtype=np.float32); image.pixels.foreach_get(px)
        return px.reshape(size[1], size[0], 4)[..., :3]


def dilate(rgb, mask, n=6):
    """push colours into the empty gutter so mip-mapping never samples black"""
    rgb = rgb.copy(); m = mask.copy()
    for _ in range(n):
        acc = np.zeros_like(rgb); cnt = np.zeros(m.shape, np.float32)
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            sh = np.roll(np.roll(rgb, dy, 0), dx, 1); shm = np.roll(np.roll(m, dy, 0), dx, 1)
            acc += sh * shm[..., None]; cnt += shm
        fill = (~m) & (cnt > 0)
        rgb[fill] = acc[fill] / cnt[fill][:, None]
        m = m | fill
    return rgb


def write_png(path, arr8):
    """8-bit image (PNG or JPEG by extension)"""
    h, w, _ = arr8.shape
    im = bpy.data.images.new(os.path.basename(path), w, h, alpha=False)
    rgba = np.ones((h, w, 4), np.float32); rgba[..., :3] = arr8
    im.pixels.foreach_set(rgba.ravel())
    im.filepath_raw = path; im.file_format = "JPEG" if path.endswith(".jpg") else "PNG"
    bpy.context.scene.render.image_settings.quality = 92
    im.save()


def prep_texture(mat, dst_dir, size=1024):
    """albedo with the node-tree adjustments applied (saturation, value, tint), resized, as JPEG"""
    src = mat.get("albedo_path")
    if not src:
        return None
    im = bpy.data.images.load(src, check_existing=False)
    im.scale(size, size)
    px = np.empty(size * size * 4, np.float32); im.pixels.foreach_get(px); px = px.reshape(size, size, 4)[..., :3]
    lin = srgb_to_lin(px)
    lum = (lin * np.array([0.2126, 0.7152, 0.0722])).sum(-1, keepdims=True)
    lin = lum + (lin - lum) * float(mat.get("sat", 1.0))
    lin = lin * float(mat.get("bright", 1.0)) * np.array(mat.get("tint", [1, 1, 1]))[:3]
    out = lin_to_srgb(lin)
    name = f"{mat.name}.jpg"
    o = bpy.data.images.new(name, size, size, alpha=False)
    rgba = np.ones((size, size, 4), np.float32); rgba[..., :3] = out
    o.pixels.foreach_set(rgba.ravel())
    o.filepath_raw = os.path.join(dst_dir, name); o.file_format = "JPEG"
    bpy.context.scene.render.image_settings.quality = 85
    o.save()
    return f"tex/{name}"


def prep_aux(src, dst_dir, name, size=1024):
    """normal / roughness map, resized, data kept as-is (non-colour)"""
    if not src:
        return None
    im = bpy.data.images.load(src, check_existing=False)
    im.colorspace_settings.name = "Non-Color"
    im.scale(size, size)
    o = bpy.data.images.new(name, size, size, alpha=False)
    px = np.empty(size * size * 4, np.float32); im.pixels.foreach_get(px)
    o.pixels.foreach_set(px)
    o.filepath_raw = os.path.join(dst_dir, name); o.file_format = "JPEG"
    bpy.context.scene.render.image_settings.quality = 88
    o.save()
    return f"tex/{name}"


def sky_jpeg(dst, width=2048):
    """tone-mapped equirect of the HDRI for the viewer's sky sphere"""
    w = bpy.context.scene.world
    env = next((n for n in w.node_tree.nodes if n.type == "TEX_ENVIRONMENT"), None)
    rot = next((n for n in w.node_tree.nodes if n.type == "MAPPING"), None)
    if env is None:
        return None, 0.0
    im = env.image
    W, H = im.size
    px = np.empty(W * H * 4, np.float32); im.pixels.foreach_get(px); px = px.reshape(H, W, 4)[..., :3]
    step = max(1, W // width)
    px = px[::step, ::step]
    # bake the world rotation and the Blender->three equirect convention (half turn) into the image
    r = float(rot.inputs["Rotation"].default_value[2]) if rot else 0.0
    px = np.roll(px, int(round((r / (2 * math.pi) + 0.5) * px.shape[1])), axis=1)
    px = px * 1.6 / (1 + px * 0.6)                   # soft shoulder
    out = lin_to_srgb(px)
    h, w_ = out.shape[:2]
    o = bpy.data.images.new("sky", w_, h, alpha=False)
    rgba = np.ones((h, w_, 4), np.float32); rgba[..., :3] = out
    o.pixels.foreach_set(rgba.ravel())
    o.filepath_raw = dst; o.file_format = "JPEG"; o.save()
    return os.path.basename(dst), 0.0


def run(A, sc, MATS, tick):
    HQ = getattr(A, "hq", False)
    out = os.path.join(A.bake, A.variant + ("-hq" if HQ else ""))
    os.makedirs(os.path.join(out, "tex"), exist_ok=True)
    objs = list(sc.objects)
    realize([o for o in objs if o.type == "MESH"])
    tick("modifiers applied")
    groups = {
        "arch": [o for o in objs if o.name.startswith("A_") and o.type == "MESH"],
        "furn": [o for o in objs if o.name.startswith("F_") and o.type == "MESH"],
    }
    emit_l = [o for o in objs if o.name.startswith("E_") and o.type == "MESH"]
    glass_l = [o for o in objs if o.name.startswith("G_") and o.type == "MESH"]
    baked = {}
    for g, lst in groups.items():
        o = join(lst, f"BAKE_{g}")
        if o:
            baked[g] = o
    emit_o = join(emit_l, "EMIT")
    glass_o = join(glass_l, "GLASS")
    vc_o = split_small(baked["furn"], 0.03, "VC_furn") if "furn" in baked else None
    if HQ and "arch" in baked:      # two 4096 atlases for the shell: horizontal (floors, ceilings) and vertical faces
        h = split_small(baked["arch"], 0, "BAKE_arch_h", pred=lambda f: abs(f.normal.z) > 0.7)
        if h:
            baked["arch_h"] = h
    tick("joined")

    # ---------- lightmap UVs + bake targets
    sc.render.engine = "CYCLES"; cyc = sc.cycles; cyc.device = "GPU"
    prefs = bpy.context.preferences.addons["cycles"].preferences
    for backend in ("OPTIX", "CUDA"):
        try:
            prefs.compute_device_type = backend; prefs.get_devices()
            if any(d.type == backend for d in prefs.devices):
                for d in prefs.devices:
                    d.use = d.type == backend
                break
        except Exception:  # noqa: BLE001
            pass
    cyc.max_bounces = 8; cyc.diffuse_bounces = 5; cyc.sample_clamp_indirect = 6.0
    manifest = {"variant": A.variant, "lightmaps": {}, "materials": {}, "exposure": sc.view_settings.exposure}
    for g in list(baked):
        if not baked[g].data.polygons:
            bpy.data.objects.remove(baked.pop(g), do_unlink=True)
    for g, o in baked.items():
        lightmap_uv(o, tick)
        area = mesh_area(o)
        side = int(2 ** math.ceil(math.log2(math.sqrt(area * A.texel ** 2 / 0.55))))
        side = max(512, min(4096, side))
        img = bpy.data.images.new(f"lm_{g}", side, side, alpha=False, float_buffer=True)
        for slot in o.material_slots:
            m = slot.material
            if m is None or not m.use_nodes:
                continue
            n = m.node_tree.nodes.get("LM_TARGET") or m.node_tree.nodes.new("ShaderNodeTexImage")
            n.name = "LM_TARGET"; n.image = img
            for nn in m.node_tree.nodes:
                nn.select = False
            n.select = True; m.node_tree.nodes.active = n
        bpy.ops.object.select_all(action="DESELECT")
        o.select_set(True); bpy.context.view_layer.objects.active = o
        cyc.samples = A.samples
        tick(f"baking {g}: {area:.0f} m2 -> {side}px")
        bpy.ops.object.bake(type="DIFFUSE", pass_filter={"DIRECT", "INDIRECT"}, margin=3, margin_type="EXTEND",
                            use_clear=True, target="IMAGE_TEXTURES")
        tick(f"baked {g}")
        raw = np.empty(side * side * 4, np.float32); img.pixels.foreach_get(raw)
        mask = raw.reshape(side, side, 4)[..., :3].sum(-1) > 0
        rgb = denoise(img, (side, side), tick)
        rgb = dilate(rgb, mask | (rgb.sum(-1) > 0), 8)
        scale = float(np.percentile(rgb[mask], 99.7)) * 1.15 if mask.any() else 1.0
        enc = lin_to_srgb(rgb / scale)
        fn = f"lm_{g}.jpg"
        write_png(os.path.join(out, fn), enc)
        manifest["lightmaps"][o.name] = {"file": fn, "intensity": scale * math.pi, "size": side}
        # remove bake nodes so the glTF export is clean
        for slot in o.material_slots:
            if slot.material and "LM_TARGET" in slot.material.node_tree.nodes:
                slot.material.node_tree.nodes.remove(slot.material.node_tree.nodes["LM_TARGET"])

    if vc_o:
        sc_ = bake_corner_colours(vc_o, max(A.samples, 768), tick)
        manifest["vertexlit"] = {vc_o.name: {"intensity": sc_}}

    # ---------- materials for the viewer
    used = set()
    for o in list(baked.values()) + [emit_o, glass_o, vc_o]:
        if o:
            used |= {s.material.name for s in o.material_slots if s.material}
    for name in sorted(used):
        m = bpy.data.materials[name]
        e = {}
        if m.get("glass"):
            e = {"type": "glass"}
        elif "emit" in m:
            e = {"type": "emit", "color": list(m["emit"]), "strength": float(m["strength"])}
        else:
            tex = prep_texture(m, os.path.join(out, "tex"), 2048 if HQ else 1024)
            e = {"type": "baked", "map": tex, "color": list(m.get("color", [1, 1, 1])) if not tex else [1, 1, 1],
                 "rough": float(m.get("rough", 0.5)), "metal": float(m.get("metal", 0.0))}
            if HQ:
                e["normalMap"] = prep_aux(m.get("normal_path"), os.path.join(out, "tex"), f"{name}_n.jpg")
                e["roughMap"] = prep_aux(m.get("rough_path"), os.path.join(out, "tex"), f"{name}_r.jpg")
                e["normalScale"] = float(m.get("bump", 0.5)); e["roughMul"] = float(m.get("rough_mul", 1.0))
                e["coat"] = float(m.get("coat", 0.0))
            if m.get("paper"):
                e["paper"] = True
        manifest["materials"][name] = e
    tick("materials prepared")

    sky, rot = sky_jpeg(os.path.join(out, "sky.jpg"), 4096 if HQ else 2048)
    manifest["sky"] = {"file": sky, "rotation": rot}

    # ---------- export
    def export(path, objs_, materials):
        bpy.ops.object.select_all(action="DESELECT")
        for ob in objs_:
            ob.select_set(True)
        kw = dict(filepath=path, export_format="GLB", use_selection=True, export_apply=True,
                  export_texcoords=True, export_normals=True, export_materials=materials,
                  export_image_format="JPEG", export_yup=True, export_lights=False, export_cameras=False)
        try:
            bpy.ops.export_scene.gltf(**kw, export_vertex_color="ACTIVE")
        except TypeError:
            bpy.ops.export_scene.gltf(**kw, export_colors=True)
    main = [o for o in list(baked.values()) + [emit_o, glass_o, vc_o] if o]
    # named, texture-free materials: the viewer rebuilds them from manifest.json
    for name in used:
        m = bpy.data.materials[name]
        nt = m.node_tree
        for n in list(nt.nodes):
            if n.type not in ("BSDF_PRINCIPLED", "OUTPUT_MATERIAL"):
                nt.nodes.remove(n)
        bs = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None) or nt.nodes.new("ShaderNodeBsdfPrincipled")
        outn = next(n for n in nt.nodes if n.type == "OUTPUT_MATERIAL")
        nt.links.new(bs.outputs[0], outn.inputs["Surface"])
    export(os.path.join(out, "scene.glb"), main, "EXPORT")
    if HQ:                          # props are shared with the standard set
        manifest["props"] = f"../{A.variant}/props.glb"
        tick("exported")
        json.dump(manifest, open(os.path.join(out, "manifest.json"), "w"), ensure_ascii=False, indent=1)
        return
    props = [o for o in sc.objects if o.name.startswith("P_")]
    # phone budget: decimate imported props and shrink their textures
    for o in props:
        if o.type in ("MESH", "CURVE"):
            if o.type == "CURVE":
                realize_curve = bpy.data.meshes.new_from_object(o.evaluated_get(bpy.context.evaluated_depsgraph_get()))
                mo = bpy.data.objects.new(o.name + "_m", realize_curve); mo.matrix_world = o.matrix_world
                sc.collection.objects.link(mo); mo.parent = o.parent; mo.matrix_world = o.matrix_world
                o.hide_render = True; o.hide_set(True); o.name = "X_" + o.name
                o = mo
            tris = sum(len(p.vertices) - 2 for p in o.data.polygons)
            leafy = any(sl.material and any(k in sl.material.name.lower() for k in ("leaf", "leaves", "alpha")) for sl in o.material_slots)
            cap = 30000 if leafy else 4000                       # leaf cards break when decimated
            if tris > cap:
                md = o.modifiers.new("dec", "DECIMATE"); md.ratio = max(0.02, cap / tris)
                print(f"[props] {o.name}: {tris} tris -> ratio {md.ratio:.3f}")
    props = [o for o in sc.objects if o.name.startswith("P_") and not o.name.startswith("X_")]
    realize([o for o in props if o.type == "MESH"])
    seen = set()
    for o in props:
        if o.type != "MESH":
            continue
        for sl in o.material_slots:
            if sl.material and sl.material.use_nodes:
                for n in sl.material.node_tree.nodes:
                    if n.type == "TEX_IMAGE" and n.image and n.image.name not in seen:
                        seen.add(n.image.name)
                        w, h = n.image.size
                        if w > 512:
                            n.image.scale(512, max(1, int(512 * h / w)))
                            n.image.pack()                       # export the scaled pixels, not the source file
    if props:
        export(os.path.join(out, "props.glb"), props, "EXPORT")
    tick("exported")
    json.dump(manifest, open(os.path.join(out, "manifest.json"), "w"), ensure_ascii=False, indent=1)
