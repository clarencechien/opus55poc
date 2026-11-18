import bpy, math
from mathutils import Vector

for o in list(bpy.data.objects):
    bpy.data.objects.remove(o, do_unlink=True)
for coll in (bpy.data.meshes, bpy.data.materials, bpy.data.curves):
    for d in list(coll):
        coll.remove(d)

MATS = {}
def M(name, rgb, metal=0.0, rough=0.5, emit=0.0):
    if name in MATS:
        return MATS[name]
    m = bpy.data.materials.new(name)
    m.diffuse_color = (rgb[0], rgb[1], rgb[2], 1.0)
    m.metallic = metal
    m.roughness = rough
    m.use_nodes = True
    b = m.node_tree.nodes.get('Principled BSDF')
    if b:
        b.inputs['Base Color'].default_value = (rgb[0], rgb[1], rgb[2], 1)
        b.inputs['Metallic'].default_value = metal
        b.inputs['Roughness'].default_value = rough
        if emit > 0:
            b.inputs['Emission Color'].default_value = (rgb[0], rgb[1], rgb[2], 1)
            b.inputs['Emission Strength'].default_value = emit
    MATS[name] = m
    return m

BLK = M('cab_black', (0.018, 0.018, 0.02), 0.3, 0.45)
PANEL = M('cab_panel', (0.03, 0.03, 0.032), 0.2, 0.35)
DOOR = M('door_perforated', (0.024, 0.024, 0.026), 0.3, 0.4)
ZINC = M('rail_zinc', (0.42, 0.43, 0.45), 0.8, 0.35)
HOLE = M('hole_black', (0.003, 0.003, 0.003), 0, 0.9)
SRV = M('server_face', (0.07, 0.07, 0.075), 0.4, 0.4)
SRVB = M('server_body', (0.25, 0.25, 0.26), 0.7, 0.4)
BAY = M('drive_bay', (0.14, 0.14, 0.15), 0.3, 0.4)
BLANK = M('blanking_panel', (0.03, 0.03, 0.03), 0.2, 0.5)
SILV = M('silver', (0.6, 0.6, 0.62), 0.9, 0.25)
LEDG = M('led_green', (0.1, 1.0, 0.25), emit=6)
LEDB = M('led_blue', (0.15, 0.45, 1.0), emit=6)
LEDA = M('led_amber', (1.0, 0.55, 0.05), emit=6)
RED = M('lock_red', (0.65, 0.06, 0.04))
RUB = M('rubber', (0.01, 0.01, 0.01), 0, 0.85)
OUTLET = M('outlet', (0.2, 0.2, 0.2))
LABEL = M('label_white', (0.85, 0.85, 0.82))
CBL_BLUE = M('cable_blue', (0.08, 0.25, 0.85), 0, 0.6)
CBL_AQUA = M('cable_aqua', (0.35, 0.75, 0.8), 0, 0.6)
CBL_GREY = M('cable_grey', (0.45, 0.45, 0.47), 0, 0.6)
CBL_BLK = M('cable_black', (0.03, 0.03, 0.03), 0, 0.6)
CBL_SALMON = M('cable_salmon', (0.8, 0.4, 0.35), 0, 0.6)
TRAY = M('tray_silver', (0.62, 0.63, 0.65), 0.8, 0.35)
PORT = M('port_lightblue', (0.55, 0.75, 0.85))
GLASS = M('window_glass', (0.05, 0.07, 0.09), 0.0, 0.1)

U = 0.04445


class Geo:
    def __init__(s):
        s.v = []; s.f = []; s.fm = []; s.mats = []

    def mi(s, m):
        if m not in s.mats:
            s.mats.append(m)
        return s.mats.index(m)

    def poly(s, pts, m):
        i = s.mi(m); b = len(s.v)
        s.v.extend(pts)
        s.f.append(tuple(range(b, b + len(pts)))); s.fm.append(i)

    def box(s, x0, x1, y0, y1, z0, z1, m):
        i = s.mi(m); b = len(s.v)
        for z in (z0, z1):
            s.v += [(x0, y0, z), (x1, y0, z), (x1, y1, z), (x0, y1, z)]
        for f in ((0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)):
            s.f.append(tuple(b + k for k in f)); s.fm.append(i)

    def qy(s, x0, x1, z0, z1, y, m, facing=-1):
        if facing < 0:
            s.poly([(x0, y, z0), (x1, y, z0), (x1, y, z1), (x0, y, z1)], m)
        else:
            s.poly([(x1, y, z0), (x0, y, z0), (x0, y, z1), (x1, y, z1)], m)

    def qx(s, y0, y1, z0, z1, x, m, facing=1):
        pts = [(x, y0, z0), (x, y1, z0), (x, y1, z1), (x, y0, z1)]
        if facing < 0:
            pts = pts[::-1]
        s.poly(pts, m)

    def cyl(s, c, r, h, m, n=12, axis='z'):
        cx, cy, cz = c
        def mp(a, b, hh):
            if axis == 'z':
                return (cx + a, cy + b, cz + hh)
            if axis == 'x':
                return (cx + hh, cy + a, cz + b)
            return (cx + b, cy + hh, cz + a)
        i = s.mi(m); b0 = len(s.v)
        for hh in (-h / 2, h / 2):
            for k in range(n):
                t = 2 * math.pi * k / n
                s.v.append(mp(r * math.cos(t), r * math.sin(t), hh))
        for k in range(n):
            k2 = (k + 1) % n
            s.f.append((b0 + k, b0 + k2, b0 + n + k2, b0 + n + k)); s.fm.append(i)
        s.f.append(tuple(b0 + n + k for k in range(n))); s.fm.append(i)
        s.f.append(tuple(b0 + k for k in reversed(range(n)))); s.fm.append(i)

    def tube(s, pts, r, m, n=6):
        P = [Vector(p) for p in pts]; i = s.mi(m); b0 = len(s.v); N = len(P)
        pu = None
        for j in range(N):
            if j == 0:
                t = P[1] - P[0]
            elif j == N - 1:
                t = P[-1] - P[-2]
            else:
                t = (P[j + 1] - P[j]).normalized() + (P[j] - P[j - 1]).normalized()
            t.normalize()
            if pu is None:
                ref = Vector((0, 0, 1)) if abs(t.z) < 0.9 else Vector((1, 0, 0))
                u = t.cross(ref).normalized()
            else:
                u = (pu - t * pu.dot(t))
                if u.length < 1e-6:
                    ref = Vector((0, 0, 1)) if abs(t.z) < 0.9 else Vector((1, 0, 0))
                    u = t.cross(ref)
                u.normalize()
            pu = u
            w = t.cross(u).normalized()
            for k in range(n):
                a = 2 * math.pi * k / n
                s.v.append(tuple(P[j] + r * (math.cos(a) * u + math.sin(a) * w)))
        for j in range(N - 1):
            for k in range(n):
                k2 = (k + 1) % n
                s.f.append((b0 + j * n + k, b0 + j * n + k2, b0 + (j + 1) * n + k2, b0 + (j + 1) * n + k)); s.fm.append(i)


def build(g, name, parent, props=None):
    xs = [v[0] for v in g.v]; ys = [v[1] for v in g.v]; zs = [v[2] for v in g.v]
    c = ((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2, (min(zs) + max(zs)) / 2)
    verts = [(v[0] - c[0], v[1] - c[1], v[2] - c[2]) for v in g.v]
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], g.f)
    for m in g.mats:
        me.materials.append(m)
    me.polygons.foreach_set('material_index', g.fm)
    me.update()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    ob.parent = parent
    ob.location = c
    dc = g.mats[0].diffuse_color
    ob.color = (dc[0], dc[1], dc[2], 1)
    if props:
        for k, v in props.items():
            ob[k] = v
    return ob


def empty(name, parent=None, loc=(0, 0, 0), props=None):
    ob = bpy.data.objects.new(name, None)
    bpy.context.scene.collection.objects.link(ob)
    ob.empty_display_type = 'PLAIN_AXES'
    ob.empty_display_size = 0.2
    ob.parent = parent
    ob.location = loc
    if props:
        for k, v in props.items():
            ob[k] = v
    return ob


def perf(g, x0, x1, z0, z1, y, facing, m, pitch=0.016, hole=0.011):
    """Perforated sheet (staggered square holes), real openings."""
    bar = pitch - hole
    nz = int((z1 - z0 - bar) // pitch)
    oz = z0 + ((z1 - z0) - (nz * pitch + bar)) / 2
    nx = int((x1 - x0 - bar) // pitch)
    ox = x0 + ((x1 - x0) - (nx * pitch + bar)) / 2
    zc = z0
    for j in range(nz):
        zh0 = oz + bar + j * pitch; zh1 = zh0 + hole
        g.qy(x0, x1, zc, zh0, y, m, facing)
        off = 0 if j % 2 == 0 else pitch / 2
        xc = x0
        for i in range(nx):
            h0 = ox + bar + i * pitch + off; h1 = h0 + hole
            if h1 > x1 - bar:
                break
            g.qy(xc, h0, zh0, zh1, y, m, facing)
            xc = h1
        g.qy(xc, x1, zh0, zh1, y, m, facing)
        zc = zh1
    g.qy(x0, x1, zc, z1, y, m, facing)


def ports(g, x0, pitch, n, zc, yF, w=0.0115, h=0.0095, m=None, group=6, ggap=0.006, led=None):
    m = m or HOLE
    x = x0
    xs = []
    for i in range(n):
        if i > 0 and i % group == 0:
            x += ggap
        g.qy(x, x + w, zc - h / 2, zc + h / 2, yF, m)
        if led is not None and i % 2 == 0:
            g.qy(x + w - 0.003, x + w, zc + h / 2 + 0.001, zc + h / 2 + 0.003, yF - 0.0004, led)
        xs.append(x + w / 2)
        x += pitch
    return xs


def equip(name, k, n, kind, parent, u0, yface, depth_end=0.30, rear=True):
    """Generic 19in equipment. yface = rail mounting face (y), front is -y."""
    zb = u0 + k * U; zt = zb + n * U; g = Geo()
    f1 = yface - 0.008; yF = f1 - 0.0004
    info = {'u_start': k + 1, 'u_size': n, 'kind': kind}
    if kind == 'B':
        g.box(-0.2413, 0.2413, yface - 0.004, yface, zb + 0.0004, zt - 0.0004, BLANK)
        for sx in (-1, 1):
            g.qy(sx * 0.2325 - 0.003, sx * 0.2325 + 0.003, (zb + zt) / 2 - 0.003, (zb + zt) / 2 + 0.003, yface - 0.0042, SILV)
        return build(g, name, parent, info)
    if kind == 'PP':
        g.box(-0.2413, 0.2413, f1, yface, zb + 0.0005, zt - 0.0005, SRV)
        g.box(-0.215, 0.215, yface, yface + 0.06, zb + 0.004, zt - 0.004, SRV)
        xs = ports(g, -0.205, 0.0165, 24, (zb + zt) / 2 - 0.002, yF, m=PORT if yface > -0.475 else HOLE, ggap=0.004)
        g.qy(-0.205, 0.205, zt - 0.0085, zt - 0.005, yF, LABEL)
        return build(g, name, parent, info), xs, (zb + zt) / 2
    g.box(-0.2205, 0.2205, f1 + 0.001, depth_end, zb + 0.0008, zt - 0.0008, SRVB)
    g.box(-0.2413, 0.2413, f1, yface, zb + 0.0005, zt - 0.0005, SRV)
    for sx in (-1, 1):
        g.qy(sx * 0.236 - 0.0035, sx * 0.236 + 0.0035, zb + 0.006, zt - 0.006, yF, SILV)
    if kind in ('S1', 'S2', 'S4'):
        cols, rows = {'S1': (10, 1), 'S2': (4, 3), 'S4': (6, 4)}[kind]
        bx0, bx1 = -0.222, 0.15; bz0, bz1 = zb + 0.004, zt - 0.004
        gap = 0.003
        bw = (bx1 - bx0 - gap * (cols - 1)) / cols; bh = (bz1 - bz0 - gap * (rows - 1)) / rows
        for r in range(rows):
            for c in range(cols):
                x = bx0 + c * (bw + gap); z = bz0 + r * (bh + gap)
                g.qy(x, x + bw, z, z + bh, yF, BAY)
                lm = LEDA if (c * 7 + r * 3 + k) % 17 == 0 else LEDG
                g.qy(x + bw - 0.006, x + bw - 0.002, z + bh - 0.006, z + bh - 0.002, yF - 0.0005, lm)
        g.qy(0.158, 0.222, zb + 0.004, zt - 0.004, yF, HOLE)
        g.qy(0.204, 0.211, zt - 0.0115, zt - 0.0055, yF - 0.0005, LEDB)
        g.qy(0.214, 0.221, zt - 0.0115, zt - 0.0055, yF - 0.0005, LEDG)
    elif kind in ('SW', 'SW2'):
        rowsz = [zb + 0.013, zb + 0.029] if kind == 'SW' else [zb + 0.024, zb + 0.040, zb + 0.056, zb + 0.072]
        for zr in rowsz:
            ports(g, -0.205, 0.0135, 24, zr, yF, w=0.0105, h=0.0085, group=8, ggap=0.005, led=LEDG)
        for i in range(4):
            g.qy(0.150 + i * 0.017, 0.163 + i * 0.017, zb + 0.012, zb + 0.022, yF, BAY)
        g.qy(0.150, 0.157, zt - 0.012, zt - 0.006, yF - 0.0005, LEDG)
        g.qy(0.160, 0.167, zt - 0.012, zt - 0.006, yF - 0.0005, LEDB)
    elif kind == 'FIB':
        g.qy(-0.20, 0.12, zb + 0.012, zt - 0.012, yF, GLASS)
        for i in range(8):
            g.qy(-0.19 + i * 0.038, -0.165 + i * 0.038, zb + 0.03, zt - 0.03, yF + 0.0002, CBL_AQUA)
        g.qy(-0.20, 0.12, zb + 0.012, zt - 0.012, yF - 0.0002, GLASS)
        g.qy(0.16, 0.2, zt - 0.03, zt - 0.02, yF, LABEL)
        g.cyl((0.18, yF - 0.004, (zb + zt) / 2), 0.008, 0.008, SILV, n=10, axis='y')
    if rear and kind in ('S1', 'S2', 'S4', 'SW', 'SW2'):
        yR = depth_end + 0.0005
        g.qy(0.08, 0.215, zb + 0.004, zb + 0.004 + min(0.035, n * U - 0.008), yR, BAY, 1)
        g.qy(-0.21, 0.05, zb + 0.004, zt - 0.004, yR, HOLE, 1)
        g.qy(0.19, 0.196, zb + 0.006, zb + 0.012, yR + 0.0005, LEDG, 1)
    return build(g, name, parent, info)


def tri_count(root):
    t = 0
    for ob in root.children_recursive:
        if ob.type == 'MESH':
            t += sum(len(p.vertices) - 2 for p in ob.data.polygons)
    return t


def bbox(root):
    bpy.context.view_layer.update()
    lo = [1e9] * 3; hi = [-1e9] * 3
    for ob in root.children_recursive:
        if ob.type == 'MESH':
            for c in ob.bound_box:
                w = ob.matrix_world @ Vector(c)
                for i in range(3):
                    lo[i] = min(lo[i], w[i]); hi[i] = max(hi[i], w[i])
    return [round(v, 4) for v in lo], [round(v, 4) for v in hi]
