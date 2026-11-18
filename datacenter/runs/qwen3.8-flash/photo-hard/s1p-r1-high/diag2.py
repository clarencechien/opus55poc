import bpy, numpy as np
from mathutils import Vector
sc = bpy.data.scenes[0]
sh = sc.display.shading
for k in ['light', 'color_type', 'cavity_type', 'shadow', 'gamma', 'exposure', 'matcap', 'show_shadows',
          'render_type', 'type', 'show_cavity', 'gradient_type', 'world']:
    try:
        print(k, getattr(sh, k))
    except Exception as e:
        pass
for nm in ['Ceiling', 'RaisedFloor', 'Wall_N', 'Column_B_2', 'Light_1.6_1.3', 'RackA_Base', 'RackA_FrontLabel',
           'RackA_FrontDoor', 'CRAH_Body', 'CRAH_Grille']:
    ob = bpy.data.objects.get(nm)
    if not ob:
        print(nm, 'missing'); continue
    cols = []
    for m in ob.data.materials:
        if m and m.use_nodes:
            b = m.node_tree.nodes.get('Principled BSDF')
            cols.append(tuple(round(x, 3) for x in b.inputs['Base Color'].default_value) if b else tuple(round(x,3) for x in m.diffuse_color))
        elif m:
            cols.append(tuple(round(x, 3) for x in m.diffuse_color))
    bb = [ob.matrix_world @ Vector(c) for c in ob.bound_box]
    print('%-16s %s z %.3f..%.3f' % (nm, cols, min(v.z for v in bb), max(v.z for v in bb)))
