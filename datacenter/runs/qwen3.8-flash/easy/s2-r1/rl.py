# helper library for rack modelling (run inside headless Blender)
import bpy, bmesh, math
from mathutils import Vector, Matrix

# ---------------------------------------------------------------- materials
def _mat(name, color, rough=0.55, metal=0.0):
    m = bpy.data.materials.get(name)
    if m is None:
        m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes.get("Principled BSDF")
    if b:
        b.inputs["Base Color"].default_value = (color[0], color[1], color[2], 1)
        b.inputs["Roughness"].default_value = rough
        b.inputs["Metallic"].default_value = metal
    m.diffuse_color = (color[0], color[1], color[2], 1)
    return m

def mats():
    M = {}
    M['frame']   = _mat("M_Frame",   (0.030, 0.030, 0.035), 0.5)
    M['panel']   = _mat("M_Panel",   (0.020, 0.020, 0.024), 0.6)
    M['door']    = _mat("M_Door",    (0.045, 0.045, 0.050), 0.45)
    M['rail']    = _mat("M_Rail",    (0.16, 0.16, 0.18), 0.4)
    M['server']  = _mat("M_Server",  (0.085, 0.085, 0.095), 0.5)
    M['bezel']   = _mat("M_Bezel",   (0.055, 0.055, 0.065), 0.4)
    M['blank']   = _mat("M_Blank",   (0.016, 0.016, 0.019), 0.7)
    M['metalg']  = _mat("M_MetalG",  (0.30, 0.30, 0.33), 0.45)
    M['led_g']   = _mat("M_LED_G",   (0.15, 1.0, 0.25), 0.3)
    M['led_b']   = _mat("M_LED_B",   (0.10, 0.45, 1.0), 0.3)
    M['led_a']   = _mat("M_LED_A",   (1.0, 0.35, 0.05), 0.3)
    M['port']    = _mat("M_Port",    (0.55, 0.55, 0.58), 0.5)
    M['cbl_k']   = _mat("M_CblBlack",(0.018, 0.018, 0.02), 0.6)
    M['cbl_b']   = _mat("M_CblBlue", (0.035, 0.11, 0.55), 0.6)
    M['cbl_g']   = _mat("M_CblGrey", (0.28, 0.28, 0.30), 0.6)
    M['cbl_c']   = _mat("M_CblCyan", (0.10, 0.55, 0.60), 0.6)
    M['brush']   = _mat("M_Brush",   (0.008, 0.008, 0.008), 0.95)
    M['rubber']  = _mat("M_Rubber",  (0.015, 0.015, 0.015), 0.85)
    return M

# ---------------------------------------------------------------- primitives
def _cube(bm, cx, cy, cz, sx, sy, sz):
    Mx = Matrix.Translation(Vector((cx, cy, cz))) @ Matrix.Diagonal(Vector((sx, sy, sz, 1.0)))
    bmesh.ops.create_cube(bm, size=1.0, matrix=Mx)

def _from_bm(name, bm, parent, mat):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me); bm.free()
    if mat: me.materials.append(mat)
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    if parent is not None:
        ob.parent = parent
        ob.matrix_parent_inverse = Matrix.Identity(4)
    return ob

def box(name, parent, c, s, mat):
    bm = bmesh.new()
    _cube(bm, c[0], c[1], c[2], s[0], s[1], s[2])
    return _from_bm(name, bm, parent, mat)

def boxes(name, parent, items, mat):
    """items: list of (cx,cy,cz,sx,sy,sz) merged into one mesh"""
    bm = bmesh.new()
    for it in items:
        _cube(bm, *it)
    return _from_bm(name, bm, parent, mat)

def cyl(name, parent, c, r, h, mat, axis='Z', verts=16):
    bm = bmesh.new()
    Mx = Matrix.Translation(Vector(c))
    if axis == 'X':
        Mx = Mx @ Matrix.Rotation(math.radians(90), 4, 'Y')
    elif axis == 'Y':
        Mx = Mx @ Matrix.Rotation(math.radians(-90), 4, 'X')
    bmesh.ops.create_cone(bm, cap_ends=True, segments=verts,
                          radius1=r, radius2=r, depth=h, matrix=Mx)
    return _from_bm(name, bm, parent, mat)

def tube(name, parent, c, sx, sy, sz, wall, mat):
    """hollow rectangular shell, open top/bottom (4 walls)"""
    bm = bmesh.new()
    cx, cy, cz = c
    _cube(bm, cx, cy - sy/2 + wall/2, cz, sx, wall, sz)
    _cube(bm, cx, cy + sy/2 - wall/2, cz, sx, wall, sz)
    _cube(bm, cx - sx/2 + wall/2, cy, cz, wall, sy - 2*wall, sz)
    _cube(bm, cx + sx/2 - wall/2, cy, cz, wall, sy - 2*wall, sz)
    return _from_bm(name, bm, parent, mat)

# --------------------------------------------------- perforated sheet (X-Z)
def perf_xz(name, parent, x0, x1, z0, z1, yc, t, pitch, rib, mat, frame_w=0.0):
    """sheet normal = Y, lying in X/Z.  frame_w>0 -> solid border of that width."""
    bm = bmesh.new()
    if frame_w > 0:
        w = frame_w
        _cube(bm, (x0+x1)/2, yc, z0+w/2, (x1-x0), t, w)
        _cube(bm, (x0+x1)/2, yc, z1-w/2, (x1-x0), t, w)
        _cube(bm, x0+w/2, yc, (z0+z1)/2, w, t, (z1-z0)-2*w)
        _cube(bm, x1-w/2, yc, (z0+z1)/2, w, t, (z1-z0)-2*w)
        ix0, ix1, iz0, iz1 = x0+w, x1-w, z0+w, z1-w
    else:
        ix0, ix1, iz0, iz1 = x0, x1, z0, z1
    nz = max(1, int(round((iz1-iz0)/pitch)))
    dz = (iz1-iz0)/(nz+1)
    for i in range(nz+1):
        _cube(bm, (ix0+ix1)/2, yc, iz0+dz*(i+0.5), (ix1-ix0), t, rib)
    nx = max(1, int(round((ix1-ix0)/pitch)))
    dx = (ix1-ix0)/(nx+1)
    for j in range(nx+1):
        _cube(bm, ix0+dx*(j+0.5), yc, (iz0+iz1)/2, rib, t, (iz1-iz0))
    return _from_bm(name, bm, parent, mat)

def perf_yz(name, parent, y0, y1, z0, z1, xc, t, pitch, rib, mat):
    """sheet normal = X"""
    bm = bmesh.new()
    nz = max(1, int(round((z1-z0)/pitch)))
    dz = (z1-z0)/(nz+1)
    for i in range(nz+1):
        _cube(bm, xc, (y0+y1)/2, z0+dz*(i+0.5), t, (y1-y0), rib)
    ny = max(1, int(round((y1-y0)/pitch)))
    dy = (y1-y0)/(ny+1)
    for j in range(ny+1):
        _cube(bm, xc, y0+dy*(j+0.5), (z0+z1)/2, t, rib, (z1-z0))
    return _from_bm(name, bm, parent, mat)

# ---------------------------------------------------------------- cables
def cable(name, parent, pts, r, mat, res_u=8, bev_res=1):
    cu = bpy.data.curves.new(name, 'CURVE')
    cu.dimensions = '3D'
    cu.resolution_u = res_u
    cu.bevel_depth = r
    cu.bevel_resolution = bev_res
    cu.use_fill_caps = True
    sp = cu.splines.new('BEZIER')
    sp.bezier_points.add(len(pts)-1)
    for i, p in enumerate(pts):
        bp = sp.bezier_points[i]
        bp.co = (p[0], p[1], p[2])
        bp.handle_left_type = 'AUTO'
        bp.handle_right_type = 'AUTO'
    ob = bpy.data.objects.new(name, cu)
    bpy.context.scene.collection.objects.link(ob)
    if parent is not None:
        ob.parent = parent
        ob.matrix_parent_inverse = Matrix.Identity(4)
    dg = bpy.context.evaluated_depsgraph_get()
    ev = ob.evaluated_get(dg)
    me = bpy.data.meshes.new_from_object(ev)
    ob2 = bpy.data.objects.new(name, me)
    if mat: me.materials.append(mat)
    bpy.context.scene.collection.objects.link(ob2)
    if parent is not None:
        ob2.parent = parent
        ob2.matrix_parent_inverse = Matrix.Identity(4)
    bpy.data.objects.remove(ob, do_unlink=True)
    return ob2

# ---------------------------------------------------------------- misc
def tri_count(ob):
    dg = bpy.context.evaluated_depsgraph_get()
    n = 0
    objs = [ob] + [o for o in ob.children_recursive]
    for o in objs:
        if o.type == 'MESH':
            me = o.evaluated_get(dg).data
            n += sum(len(p.vertices) - 2 for p in me.polygons)
    return n

def bbox(ob):
    dg = bpy.context.evaluated_depsgraph_get()
    mins = [1e9]*3; maxs = [-1e9]*3
    objs = [ob] + [o for o in ob.children_recursive if o.type == 'MESH']
    for o in objs:
        eo = o.evaluated_get(dg)
        for c in eo.bound_box:
            w = eo.matrix_world @ Vector(c)
            for k in range(3):
                mins[k] = min(mins[k], w[k]); maxs[k] = max(maxs[k], w[k])
    return mins, maxs

def report(root):
    mn, mx = bbox(root)
    print("%s bbox min %s max %s dims %.4f x %.4f x %.4f tris %d" %
          (root.name,
           ["%.4f" % v for v in mn], ["%.4f" % v for v in mx],
           mx[0]-mn[0], mx[1]-mn[1], mx[2]-mn[2], tri_count(root)))
