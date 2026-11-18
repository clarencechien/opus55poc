import json, bpy
d = json.load(open('/home/user/opus55poc/datacenter/runs/qwen3.8-flash/easy/s1-r2-high/layout_pred.json'))
poly = d['room']['polygon']
a = 0.5*sum(poly[i][0]*poly[(i+1)%len(poly)][1] - poly[(i+1)%len(poly)][0]*poly[i][1] for i in range(len(poly)))
print('keys ok:', sorted(d.keys()))
print('polygon area mm2:', a, 'CCW' if a > 0 else 'CW')
print('counts: racks', len(d['racks']), 'crah', len(d['crah']), 'cols', len(d['columns']), 'doors', len(d['doors']), 'aisles', len(d['aisles']))
print('scene objects:', [o.name for o in bpy.data.objects])
