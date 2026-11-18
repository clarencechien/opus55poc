exec(open('/home/user/opus55poc/datacenter/runs/opus-5.5/easy/s2-r1/lib.py').read())

# =====================================================================
# RACK A  - closed 42U cabinet 600 x 1200 x 2000, centred at 0,0
# =====================================================================
RA = empty('RackA', None, (0, 0, 0), {'rack_type': 'closed_cabinet', 'rack_units': 42,
                                      'width_mm': 600, 'depth_mm': 1200, 'height_mm': 2000})

# --- feet and casters
g = Geo()
for sx in (-1, 1):
    for sy in (-1, 1):
        cx, cy = sx * 0.22, sy * 0.48
        g.box(cx - 0.022, cx + 0.022, cy - 0.022, cy + 0.022, 0.042, 0.05, ZINC)
        for px in (-1, 1):
            g.box(cx + px * 0.014 - 0.002, cx + px * 0.014 + 0.002, cy - 0.012, cy + 0.012, 0.018, 0.042, ZINC)
        g.cyl((cx, cy, 0.022), 0.022, 0.018, RUB, n=14, axis='x')
        fx, fy = sx * 0.25, sy * 0.55
        g.cyl((fx, fy, 0.004), 0.022, 0.008, RUB, n=14)
        g.cyl((fx, fy, 0.014), 0.012, 0.012, ZINC, n=6)
        g.cyl((fx, fy, 0.035), 0.006, 0.03, ZINC, n=8)
build(g, 'RackA_Feet', RA, {'part': 'casters_and_leveling_feet'})

# --- plinth
g = Geo()
g.box(-0.29, 0.29, -0.59, 0.59, 0.05, 0.10, BLK)
for sy in (-1, 1):
    for i in range(6):
        x = -0.2 + i * 0.075
        g.qy(x, x + 0.05, 0.065, 0.085, sy * 0.5905, HOLE, sy)
build(g, 'RackA_Plinth', RA)

# --- side panels (solid, two per side with seam and latch)
for sx, nm in ((-1, 'L'), (1, 'R')):
    g = Geo()
    x0, x1 = sorted((sx * 0.285, sx * 0.3))
    g.box(x0, x1, -0.6, -0.002, 0.05, 1.98, PANEL)
    g.box(x0, x1, 0.002, 0.6, 0.05, 1.98, PANEL)
    for yc in (-0.3, 0.3):
        g.qx(yc - 0.02, yc + 0.02, 1.0, 1.06, sx * 0.3001, BLK, sx)
        g.qx(yc - 0.006, yc + 0.006, 1.04, 1.052, sx * 0.3002, SILV, sx)
    build(g, 'RackA_SidePanel_' + nm, RA, {'part': 'side_panel_solid'})

# --- top panel with cable entry openings + brush strips
g = Geo()
z0, z1 = 1.98, 2.0
for ya, yb in ((-0.6, -0.45), (-0.33, 0.33), (0.45, 0.6)):
    g.box(-0.3, 0.3, ya, yb, z0, z1, PANEL)
for ya, yb in ((-0.45, -0.33), (0.33, 0.45)):
    g.box(-0.3, -0.2, ya, yb, z0, z1, PANEL)
    g.box(0.2, 0.3, ya, yb, z0, z1, PANEL)
    g.box(-0.2, 0.2, ya, (ya + yb) / 2 - 0.006, 1.972, 1.978, RUB)
    g.box(-0.2, 0.2, (ya + yb) / 2 + 0.006, yb, 1.972, 1.978, RUB)
# small round grommet openings look (dark discs) near sides
for sy in (-1, 1):
    for sx in (-1, 1):
        g.cyl((sx * 0.25, sy * 0.2, 2.0), 0.025, 0.0006, HOLE, n=16)
build(g, 'RackA_TopPanel', RA, {'part': 'top_panel_cable_entry'})

# --- internal frame
g = Geo()
for sy in (-1, 1):
    y0, y1 = sorted((sy * 0.575, sy * 0.6))
    g.box(-0.285, 0.285, y0, y1, 1.96, 1.98, BLK)          # door header
    for sx in (-1, 1):
        a, b = sorted((sx * 0.255, sx * 0.285)); c, d = sorted((sy * 0.545, sy * 0.575))
        g.box(a, b, c, d, 0.10, 1.96, BLK)                  # corner uprights
for sx in (-1, 1):
    a, b = sorted((sx * 0.255, sx * 0.285))
    g.box(a, b, -0.575, 0.575, 1.93, 1.96, BLK)
    g.box(a, b, -0.575, 0.575, 0.10, 0.13, BLK)
    a, b = sorted((sx * 0.2445, sx * 0.285))
    g.box(a, b, -0.50, 0.47, 0.13, 0.15, BLK)               # rail brackets
    g.box(a, b, -0.50, 0.47, 1.93, 1.95, BLK)
build(g, 'RackA_Frame', RA)

# --- 19-inch mounting rails
u0 = 0.11
g = Geo()
for sx in (-1, 1):
    a, b = sorted((sx * 0.2255, sx * 0.2413)); wa, wb = sorted((sx * 0.2413, sx * 0.2443))
    g.box(a, b, -0.482, -0.479, 0.10, 1.978, ZINC)
    g.box(wa, wb, -0.482, -0.44, 0.10, 1.978, ZINC)
    g.box(a, b, 0.440, 0.443, 0.10, 1.978, ZINC)
    g.box(wa, wb, 0.40, 0.443, 0.10, 1.978, ZINC)
    for k in range(42):
        for off in (0.00635, 0.022225, 0.0381):
            z = u0 + k * U + off
            hx = sx * 0.2325
            g.qy(hx - 0.00475, hx + 0.00475, z - 0.00475, z + 0.00475, -0.4822, HOLE, -1)
            g.qy(hx - 0.00475, hx + 0.00475, z - 0.00475, z + 0.00475, 0.4432, HOLE, 1)
build(g, 'RackA_MountingRails_19in', RA, {'part': 'mounting_rails', 'standard': 'EIA-310 19in'})

# --- doors
def door(name, side):
    g = Geo()
    yo = side * 0.597; yi = side * 0.577
    ya, yb = sorted((yo, yi))
    s = side
    g.box(-0.284, -0.254, ya, yb, 0.10, 1.96, DOOR)
    g.box(0.254, 0.284, ya, yb, 0.10, 1.96, DOOR)
    g.box(-0.254, 0.254, ya, yb, 1.91, 1.96, DOOR)
    g.box(-0.254, 0.254, ya, yb, 0.10, 0.15, DOOR)
    ys = side * 0.594
    if side < 0:
        perf(g, -0.254, 0.254, 0.15, 1.91, ys, -1, DOOR)
        hx = 0.268
        handles = [hx]
    else:
        g.box(-0.012, 0.012, ya, yb, 0.15, 1.91, DOOR)
        perf(g, -0.254, -0.012, 0.15, 1.91, ys, 1, DOOR)
        perf(g, 0.012, 0.254, 0.15, 1.91, ys, 1, DOOR)
        handles = [-0.0, ]
    yp = side * 0.599; yl = side * 0.6
    for hx in handles:
        if side > 0:
            pa, pb = sorted((yo, yp))
            g.box(-0.008, 0.008, pa, pb, 0.92, 1.12, BLK)
            la, lb = sorted((yp, yl))
            g.box(-0.005, 0.005, la, lb, 0.95, 1.09, SILV)
            g.box(-0.007, 0.007, pa, pb, 1.125, 1.145, RED)
        else:
            pa, pb = sorted((yo, yp))
            g.box(hx - 0.01, hx + 0.01, pa, pb, 0.92, 1.12, BLK)
            la, lb = sorted((yp, yl))
            g.box(hx - 0.006, hx + 0.006, la, lb, 0.95, 1.09, SILV)
            g.box(hx - 0.007, hx + 0.007, pa, pb, 1.125, 1.145, RED)
    # hinges
    hxs = (-0.281,) if side < 0 else (-0.281, 0.281)
    for hxx in hxs:
        for hz in (0.3, 1.0, 1.7):
            g.cyl((hxx, side * 0.587, hz), 0.004, 0.06, BLK, n=8)
    return build(g, name, RA, {'part': 'perforated_door', 'open_area_pct': 47})

door('RackA_FrontDoor', -1)
door('RackA_RearDoor', 1)

# --- equipment
EQ = empty('RackA_Equipment', RA)
layoutA = [('S4', 4), ('S4', 4), ('B', 1), ('S2', 2), ('S2', 2), ('S2', 2), ('B', 2),
           ('S1', 1), ('S1', 1), ('S1', 1), ('S1', 1), ('S1', 1), ('S1', 1), ('B', 1),
           ('S1', 1), ('S1', 1), ('S1', 1), ('S1', 1), ('S2', 2), ('S2', 2), ('B', 1),
           ('S4', 4), ('B', 2), ('SW', 1), ('PP', 1), ('B', 1)]
k = 0
srv_rows = []
for kind, n in layoutA:
    nm = {'B': 'Blank', 'SW': 'Switch', 'PP': 'PatchPanel'}.get(kind) or ('Server' + kind[1:] + 'U')
    r = equip('RackA_%s_U%02d' % (nm, k + 1), k, n, kind, EQ, u0, -0.482, 0.30)
    if kind.startswith('S') and kind != 'SW':
        srv_rows.append(u0 + k * U + 0.012)
    k += n
assert k == 42, k

# --- rear PDUs and cabling
for sx, nm in ((-1, 'L'), (1, 'R')):
    g = Geo()
    a, b = sorted((sx * 0.25, sx * 0.278))
    g.box(a, b, 0.47, 0.52, 0.25, 1.75, BLK)
    for i in range(24):
        z = 0.32 + i * 0.058
        g.qy(sx * 0.264 - 0.007, sx * 0.264 + 0.007, z, z + 0.022, 0.5205, OUTLET, 1)
    g.qy(sx * 0.264 - 0.009, sx * 0.264 + 0.009, 1.66, 1.70, 0.5205, LEDB, 1)
    build(g, 'RackA_PDU_' + nm, RA, {'part': 'vertical_pdu'})

g = Geo()
for i, zc in enumerate(srv_rows):
    sx = 1 if i % 2 == 0 else -1
    zp = min(max(zc, 0.33), 1.72)
    g.tube([(sx * 0.15, 0.30, zc), (sx * 0.2, 0.40, zc), (sx * 0.252, 0.50, zp)], 0.003, CBL_BLK, n=5)
    g.tube([(-0.10, 0.30, zc + 0.004), (-0.13, 0.35, zc + 0.01), (-0.15, 0.385, zc + 0.04)], 0.003, CBL_BLUE if i % 3 else CBL_GREY, n=5)
g.tube([(-0.15, 0.385, 0.15), (-0.15, 0.385, 1.6), (-0.13, 0.39, 1.95), (-0.10, 0.39, 1.985)], 0.016, CBL_BLUE, n=8)
build(g, 'RackA_Cabling', RA, {'part': 'rear_cabling'})

# =====================================================================
# RACK B  - open 4-post frame 600 x 1000 x 2000, centred at 1.5,0
# =====================================================================
RB = empty('RackB', None, (1.5, 0, 0), {'rack_type': 'open_frame_4post', 'rack_units': 42,
                                        'width_mm': 600, 'depth_mm': 1000, 'height_mm': 2000})
u0b = 0.06
posts = [(1, -1, -1), (2, 1, -1), (3, 1, 1), (4, -1, 1)]
for idx, sx, sy in posts:
    g = Geo()
    xa, xb = sorted((sx * 0.225, sx * 0.275))
    ya, yb = sorted((sy * 0.40, sy * 0.47))
    # C-channel: outer web + front and back flanges
    wa, wb = sorted((sx * 0.270, sx * 0.275))
    g.box(wa, wb, ya, yb, 0.05, 1.95, BLK)
    fa, fb = sorted((sy * 0.467, sy * 0.47))
    g.box(xa, xb, fa, fb, 0.05, 1.95, BLK)
    ba, bb = sorted((sy * 0.40, sy * 0.403))
    g.box(xa, xb, ba, bb, 0.05, 1.95, BLK)
    yh = sy * 0.4702
    for k in range(42):
        for off in (0.00635, 0.022225, 0.0381):
            z = u0b + k * U + off
            hx = sx * 0.2325
            g.qy(hx - 0.00475, hx + 0.00475, z - 0.00475, z + 0.00475, yh, HOLE, sy)
        if k % 2 == 0:
            z = u0b + k * U + 0.044
            g.qy(sx * 0.258 - 0.004, sx * 0.258 + 0.004, z - 0.008, z + 0.008, yh, HOLE, sy)
    # U-number marks
    for k in range(0, 42, 5):
        z = u0b + k * U + 0.022
        g.qy(sx * 0.2665 - 0.003, sx * 0.2665 + 0.003, z - 0.002, z + 0.002, yh, LABEL, sy)
    build(g, 'RackB_Post_%d' % idx, RB, {'post_index': idx, 'part': 'vertical_post'})

# bottom frame
g = Geo()
for sx in (-1, 1):
    a, b = sorted((sx * 0.22, sx * 0.30))
    g.box(a, b, -0.5, 0.5, 0.0, 0.05, BLK)
    a, b = sorted((sx * 0.225, sx * 0.275))
for sy in (-1, 1):
    a, b = sorted((sy * 0.40, sy * 0.47))
    g.box(-0.22, 0.22, a, b, 0.0, 0.05, BLK)
g.box(-0.22, 0.22, -0.03, 0.03, 0.0, 0.03, BLK)
for sx in (-1, 1):
    for sy in (-1, 1):
        g.cyl((sx * 0.26, sy * 0.485, 0.0505), 0.008, 0.001, ZINC, n=8)
build(g, 'RackB_BottomFrame', RB, {'part': 'bottom_frame'})

# top frame
g = Geo()
for sx in (-1, 1):
    a, b = sorted((sx * 0.225, sx * 0.29))
    g.box(a, b, -0.5, 0.5, 1.95, 2.0, BLK)
for sy in (-1, 1):
    a, b = sorted((sy * 0.40, sy * 0.47))
    g.box(-0.225, 0.225, a, b, 1.95, 2.0, BLK)
g.box(-0.225, 0.225, -0.025, 0.025, 1.96, 2.0, BLK)
build(g, 'RackB_TopFrame', RB, {'part': 'top_frame'})

# vertical cable managers (front, finger type) on both sides
for sx, nm in ((-1, 'L'), (1, 'R')):
    g = Geo()
    a, b = sorted((sx * 0.284, sx * 0.29))
    g.box(a, b, -0.5, -0.40, 0.05, 1.95, BLK)
    for i in range(21):
        z = 0.10 + i * 2 * U
        fa, fb = sorted((sx * 0.275, sx * 0.30))
        g.box(fa, fb, -0.5, -0.488, z, z + 0.012, BLK)
        g.box(fa, fb, -0.5, -0.47, z + 0.003, z + 0.009, BLK)
    build(g, 'RackB_VerticalCableManager_' + nm, RB, {'part': 'vertical_cable_management'})

# rear lacing bars (vertical + horizontal)
g = Geo()
for sx in (-1, 1):
    g.cyl((sx * 0.20, 0.485, 1.0), 0.006, 1.9, ZINC, n=8)
    a, b = sorted((sx * 0.20, sx * 0.27))
    for z in (0.08, 1.92):
        g.box(a, b, 0.47, 0.49, z - 0.008, z + 0.008, BLK)
for z in (0.5, 0.9, 1.3, 1.7):
    g.cyl((0, 0.485, z), 0.005, 0.40, ZINC, n=8, axis='x')
build(g, 'RackB_RearLacingBars', RB, {'part': 'cable_management'})

# equipment
EQB = empty('RackB_Equipment', RB)
layoutB = [(3, 1, 'TRAY'), (6, 2, 'SW2'), (10, 1, 'TRAY'), (18, 2, 'HCM'), (20, 1, 'PP'), (21, 1, 'PP'),
           (22, 2, 'HCMC'), (24, 1, 'PP'), (25, 1, 'PP'), (26, 2, 'HCM'), (28, 1, 'PP'), (29, 1, 'SW'),
           (30, 2, 'HCM'), (34, 4, 'FIB'), (39, 1, 'TRAY')]
pp_info = {}
hcm_z = {}
for k, n, kind in layoutB:
    zb = u0b + k * U; zt = zb + n * U
    if kind in ('HCM', 'HCMC'):
        g = Geo()
        g.box(-0.2413, 0.2413, -0.478, -0.470, zb + 0.001, zt - 0.001, BLK)
        if kind == 'HCM':
            for i in range(7):
                x = -0.225 + i * 0.075
                g.box(x - 0.006, x + 0.006, -0.5, -0.478, zb + 0.004, zt - 0.004, BLK)
            g.box(-0.235, 0.235, -0.5, -0.478, zb + 0.001, zb + 0.004, BLK)
        else:
            g.box(-0.235, 0.235, -0.5, -0.494, zb + 0.002, zt - 0.002, BLK)
            for sx in (-1, 1):
                a, b = sorted((sx * 0.229, sx * 0.235))
                g.box(a, b, -0.494, -0.478, zb + 0.002, zt - 0.002, BLK)
        build(g, 'RackB_HorizCableManager_U%02d' % (k + 1), EQB, {'u_start': k + 1, 'u_size': n, 'part': 'horizontal_cable_management'})
        hcm_z[k] = (zb + zt) / 2
    elif kind == 'TRAY':
        g = Geo()
        g.box(-0.25, 0.25, -0.497, -0.494, zb + 0.003, zt - 0.003, TRAY)
        for r in range(2):
            zr = zb + 0.012 + r * 0.017
            for i in range(10):
                x = -0.215 + i * 0.044
                g.qy(x, x + 0.03, zr, zr + 0.008, -0.4972, HOLE)
        for sx in (-1, 1):
            a, b = sorted((sx * 0.236, sx * 0.25))
            g.box(a, b, -0.494, -0.47, zb + 0.003, zt - 0.003, TRAY)
        g.box(-0.236, 0.236, -0.494, -0.43, zb, zb + 0.002, TRAY)
        build(g, 'RackB_CableTray_U%02d' % (k + 1), EQB, {'u_start': k + 1, 'u_size': n, 'part': 'horizontal_cable_management'})
    elif kind == 'PP':
        ob, xs, zc = equip('RackB_PatchPanel_U%02d' % (k + 1), k, n, 'PP', EQB, u0b, -0.47)
        pp_info[k] = (xs, zc)
    else:
        nm = {'SW': 'Switch', 'SW2': 'Switch2U', 'FIB': 'FiberEnclosure'}[kind]
        de = {'SW': 0.0, 'SW2': 0.1, 'FIB': -0.15}[kind]
        equip('RackB_%s_U%02d' % (nm, k + 1), k, n, kind, EQB, u0b, -0.47, de)
        if kind == 'SW':
            sw_k = k

# cabling
g = Geo()
target = {20: 18, 21: 18, 24: 26, 25: 26, 28: 26}
for k, (xs, zc) in pp_info.items():
    zh = hcm_z[target[k]]
    mat = CBL_BLUE if k in (20, 21, 28) else CBL_SALMON
    for i, xp in enumerate(xs):
        if i % 2:
            continue
        side = -1 if xp < 0 else 1
        xt = side * 0.27
        dz = zh - zc
        g.tube([(xp, -0.479, zc), (xp, -0.487, zc), (xp + (xt - xp) * 0.15, -0.490, zc + dz * 0.7),
                (xp + (xt - xp) * 0.5, -0.490, zh), (side * 0.288, -0.485, zh + 0.02 * side)], 0.0022, mat, n=5)
    # rear bundle from back of each patch panel to rear vertical bundle
    g.tube([(0.0, -0.40, zc), (-0.05, -0.2, zc - 0.01), (-0.15, 0.3, zc - 0.03), (-0.17, 0.44, zc - 0.08)], 0.011, CBL_BLUE, n=8)
# switch patch cords up into HCM above
xs_sw = [-0.205 + i * 0.0135 + (i // 8) * 0.005 + 0.005 for i in range(24)]
zsw = u0b + sw_k * U + 0.021
for i, xp in enumerate(xs_sw):
    if i % 3 == 2:
        continue
    zh = hcm_z[30]
    side = -1 if xp < 0 else 1
    g.tube([(xp, -0.479, zsw), (xp, -0.487, zsw), (xp, -0.49, zh - 0.01), (xp + side * 0.05, -0.49, zh)], 0.002, CBL_AQUA if i % 2 else CBL_BLUE, n=5)
# vertical bundles inside the front finger managers
for sx, mat in ((-1, CBL_BLUE), (1, CBL_AQUA)):
    for j, (dx, dy) in enumerate(((0.0, 0.0), (0.004, 0.006), (-0.003, 0.009))):
        g.tube([(sx * (0.288 + dx), -0.483 + dy, 0.06), (sx * (0.288 + dx), -0.483 + dy, 1.0), (sx * (0.288 + dx), -0.483 + dy, 1.94)], 0.006, mat, n=6)
# main rear vertical bundle, going to the floor (raised-floor entry) and over the top
g.tube([(-0.17, 0.44, 0.06), (-0.17, 0.44, 1.3), (-0.17, 0.44, 1.75), (-0.10, 0.30, 1.93), (0.0, 0.05, 1.965)], 0.02, CBL_BLUE, n=10)
# loose grey cables hanging at front left (as in photo)
g.tube([(-0.255, -0.485, 1.55), (-0.235, -0.492, 1.3), (-0.215, -0.495, 1.05), (-0.22, -0.495, 0.8), (-0.24, -0.49, 0.62)], 0.003, CBL_GREY, n=5)
g.tube([(-0.25, -0.485, 1.52), (-0.225, -0.493, 1.25), (-0.205, -0.496, 1.0), (-0.19, -0.494, 0.78), (-0.20, -0.488, 0.6)], 0.003, CBL_GREY, n=5)
# power cords from switch rears to floor
g.tube([(0.15, 0.10, u0b + 7 * U), (0.2, 0.25, u0b + 6 * U), (0.21, 0.42, 0.3), (0.21, 0.44, 0.06)], 0.004, CBL_BLK, n=6)
g.tube([(0.15, 0.0, zsw), (0.22, 0.2, zsw - 0.1), (0.215, 0.44, 0.5), (0.215, 0.445, 0.06)], 0.004, CBL_BLK, n=6)
build(g, 'RackB_Cabling', RB, {'part': 'cabling'})

for r in (RA, RB):
    print(r.name, 'tris', tri_count(r), 'bbox', bbox(r))
