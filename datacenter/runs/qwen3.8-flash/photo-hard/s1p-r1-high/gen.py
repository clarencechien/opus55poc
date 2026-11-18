import bpy, numpy as np, os, json
exec(open('vis.py').read().split('go()')[0])

def ew(c, face, a, b, w=0.6):
    n = int(round((b - a) / w))
    return [{'center': [round((a + w * (i + 0.5)) * 1000, 1), round(c * 1000, 1)],
             'size': [w * 1000, 1200], 'facing': face} for i in range(n)]

def ns(c, face, a, b, w=0.6):
    n = int(round((b - a) / w))
    return [{'center': [round(c * 1000, 1), round((a + w * (i + 0.5)) * 1000, 1)],
             'size': [w * 1000, 1200], 'facing': face} for i in range(n)]

ROWS = [('EW', 1.16, 'N', 12.6, 19.8),
        ('EW', 4.30, 'S', 13.6, 20.4),
        ('EW', 4.95, 'N', 1.5, 11.1),
        ('EW', 8.85, 'S', 3.7, 12.1),
        ('NS', 6.04, 'W', 13.5, 17.1),
        ('NS', 3.64, 'E', 13.5, 17.1)]
racks = []
for ax, c, f, a, b in ROWS:
    racks += (ew(c, f, a, b) if ax == 'EW' else ns(c, f, a, b))
for k, r in enumerate(racks):
    r['id'] = 'R%02d' % (k + 1)

crah = [{'id': 'C%d' % (k + 1), 'center': [600.0, y * 1000], 'size': [1800, 900], 'facing': 'E'}
        for k, y in enumerate([2.9, 7.0, 11.0, 14.9])]

aisles = [
    {'type': 'cold', 'rect': [13600, 1760, 19800, 3700]},
    {'type': 'cold', 'rect': [1500, 5550, 11100, 8250]},
    {'type': 'cold', 'rect': [4240, 13500, 5440, 17100]},
]
json.dump({'units': 'mm', 'racks': racks, 'crah': crah, 'aisles': aisles},
          open('layout_pred.json', 'w'), indent=1)
print('racks', len(racks))

hyp = {"rows": [{"axis": ax, "c": c, "face": f, "a": a, "b": b, "w": 0.6} for ax, c, f, a, b in ROWS],
       "crah": [[0.6, 2.9, 'E'], [0.6, 7.0, 'E'], [0.6, 11.0, 'E'], [0.6, 14.9, 'E']]}
render_all(hyp, res=(512, 384), cams=(1, 2, 3, 4, 5))
make((1, 2, 3, 4, 5), 512, 384)
