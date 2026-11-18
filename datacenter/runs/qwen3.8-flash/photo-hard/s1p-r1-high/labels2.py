import os
os.environ['ZL'] = '2.46'
src = open('labdetect.py').read().replace('ZL = 1.86', 'ZL = 2.46')
exec(src)

allpts = []
for idx in [1, 2, 3, 4, 5]:
    cn = 'Cam_%d' % idx
    cs = comps('inputs/photo_%d.jpg' % idx, cn, thr=0.62)
    print('=== %s: %d comps' % (cn, len(cs)))
    for r in cs:
        print('   u %4d-%4d v %4d-%4d n=%5d  x %7.3f y %7.3f' % (r[0], r[1], r[2], r[3], r[4], r[5], r[6]))
        allpts.append((idx, r[5], r[6], r[4], r[0], r[1]))
import json
json.dump(allpts, open('labels2.json', 'w'))
print('total', len(allpts))
