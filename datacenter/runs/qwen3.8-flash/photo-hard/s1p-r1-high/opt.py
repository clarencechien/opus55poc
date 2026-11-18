import bpy, numpy as np, os, json
exec(open('vis.py').read().split('go()')[0])

rows = [
    {"axis": "EW", "c": 1.16, "a": 12.6, "b": 19.8, "face": "N", "w": 0.6},
    {"axis": "EW", "c": 4.30, "a": 13.6, "b": 20.4, "face": "S", "w": 0.6},
    {"axis": "EW", "c": 4.95, "a": 1.5, "b": 11.1, "face": "N", "w": 0.6},
    {"axis": "EW", "c": 8.85, "a": 3.7, "b": 12.1, "face": "S", "w": 0.6},
    {"axis": "NS", "c": 6.04, "a": 13.5, "b": 17.1, "face": "W", "w": 0.6},
    {"axis": "NS", "c": 3.64, "a": 13.5, "b": 17.1, "face": "E", "w": 0.6}]
crah = [[0.6, 2.9, 'E'], [0.6, 7.0, 'E'], [0.6, 11.0, 'E'], [0.6, 14.9, 'E']]

def score(rs):
    for k in list(_phcache):
        if k[0].startswith('cmp/'): del _phcache[k]
    o = render_all({"rows": rs, "crah": crah}, res=(320, 240), cams=(1, 2, 3, 4, 5), verbose=False)
    return sum(v[0] for v in o.values()) / len(o)

best = [dict(r) for r in rows]
b0 = score(best)
print('base %.4f' % b0)
for i in range(6):
    cur = best[i]['c']
    res = {}
    for d in (-0.6, 0.6):
        t = [dict(r) for r in best]
        t[i]['c'] = round(cur + d, 3)
        res[d] = score(t)
    bd = min(res, key=res.get)
    print('row%d c %.2f: -0.6->%.4f +0.6->%.4f' % (i, cur, res[-0.6], res[0.6]))
    if res[bd] < b0 - 0.0008:
        best[i]['c'] = round(cur + bd, 3)
        b0 = res[bd]
        print('   accepted shift %+0.1f -> %.4f' % (bd, b0))
print('FINAL %.4f' % b0)
for r in best: print('  ', r['axis'], r['c'], r['face'])
json.dump(best, open('rows_final.json', 'w'), indent=1)
