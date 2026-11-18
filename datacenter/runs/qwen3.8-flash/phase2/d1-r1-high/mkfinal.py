import json
d = json.load(open('inputs/design.json'))
# As-built changes found from the survey photos:
#  - racks A03, A04, A05 stand turned round (front now facing S instead of N):
#    photo 6 shows white label strips + blue LEDs on the SOUTH face of row A at
#    plan x ~14.1..15.6, y ~1.3 (exactly A03/A04/A05 slots); photos 1 and 2 show
#    the same south-facing fronts at y ~1.28.
#  - rack E05 stands turned round (front now facing N instead of E):
#    photo 5 shows an unexplained lit front at the north end of row E.
CH = {'A03': 'S', 'A04': 'S', 'A05': 'S', 'E05': 'N'}
out = {'units': 'mm', 'racks': [], 'crah': []}
for r in d['racks']:
    rr = dict(id=r['id'], center=r['center'], size=r['size'], facing=CH.get(r['id'], r['facing']))
    out['racks'].append(rr)
for c in d['crah']:
    out['crah'].append(dict(id=c['id'], center=c['center'], size=c['size'], facing=c['facing']))
json.dump(out, open('asbuilt_pred.json', 'w'), indent=1)
print('racks', len(out['racks']), 'crah', len(out['crah']))
print('changed:', [(k, v) for k, v in CH.items()])
