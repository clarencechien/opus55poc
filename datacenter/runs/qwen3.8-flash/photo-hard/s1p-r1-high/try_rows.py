import bpy, numpy as np, os, json
exec(open('vis.py').read().split('go()')[0])

base = {"rows": [
    {"axis": "EW", "c": 1.16, "a": 12.6, "b": 19.8, "face": "N", "w": 0.6},
    {"axis": "EW", "c": 4.30, "a": 13.6, "b": 20.4, "face": "S", "w": 0.6},
    {"axis": "EW", "c": 4.95, "a": 1.5, "b": 11.1, "face": "N", "w": 0.6},
    {"axis": "EW", "c": 8.85, "a": 3.7, "b": 12.1, "face": "S", "w": 0.6},
    {"axis": "NS", "c": 6.04, "a": 13.5, "b": 17.1, "face": "W", "w": 0.6},
    {"axis": "NS", "c": 3.64, "a": 13.5, "b": 17.1, "face": "E", "w": 0.6}],
    "crah": [[0.6, 2.9, 'E'], [0.6, 7.0, 'E'], [0.6, 11.0, 'E'], [0.6, 14.9, 'E']]}

ns1 = {"axis": "NS", "c": 10.24, "a": 13.5, "b": 17.1, "face": "W", "w": 0.6}
ew1 = {"axis": "EW", "c": 11.05, "a": 12.6, "b": 19.8, "face": "S", "w": 0.6}
ew2 = {"axis": "EW", "c": 13.30, "a": 12.6, "b": 19.8, "face": "N", "w": 0.6}
ew3 = {"axis": "EW", "c": 4.30, "a": 20.4, "b": 23.4, "face": "S", "w": 0.6}

for nm, ex in [('V0', []), ('V1', [ns1]), ('V2', [ew1]), ('V3', [ns1, ew1]),
               ('V4', [ew1, ew2]), ('V5', [ew1, ew2, ns1]), ('V6', [ew3])]:
    for k in list(_phcache):
        if k[0].startswith('cmp/'): del _phcache[k]
    h = {"rows": base["rows"] + ex, "crah": base["crah"]}
    o = render_all(h, res=(320, 240), cams=(1, 2, 3, 4, 5), verbose=False)
    tot = sum(v[0] for v in o.values()) / len(o)
    print('%s extras=%d MAD %.4f frac %.3f  ' % (nm, len(ex), tot, sum(v[1] for v in o.values()) / 5),
          ' '.join('%d:%.3f' % (i, o[i][0]) for i in [1, 2, 3, 4, 5]))
