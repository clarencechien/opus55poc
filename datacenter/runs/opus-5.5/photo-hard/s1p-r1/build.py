import bpy, math, json
RUN = '/home/user/opus55poc/datacenter/runs/opus-5.5/photo-hard/s1p-r1/'
rows = [
 # name, x0,y0,x1,y1 (mm), facing, list of rack widths (from west/south start)
 ('R1', 13200,1300,20400,2500,'N',[600]*12),
 ('R2', 13200,3700,20400,4900,'S',[800]*3+[600]*8),
 ('A1', 3000,5400,5400,6600,'N',[600]*4),
 ('A2', 6600,5400,11400,6600,'N',[800]*6),
 ('B',  3000,7800,11400,9000,'S',[600]*14),
 ('W1', 3000,13500,4200,17100,'E',[600]*6),
 ('W2', 5400,13500,6600,17100,'W',[600]*6),
]
crahs = [
 ('C1', 100,8700,1000,10500,'E'),
 ('C3', 100,2100,1000,3900,'E'),
 ('C4', 23000,8100,23900,9900,'W'),
]
aisles = [
 [13200,2500,20400,3700],
 [3000,6600,11400,7800],
 [4200,13500,5400,17100],
]
for ob in list(bpy.data.objects):
    if ob.name.startswith('P_'):
        bpy.data.objects.remove(ob, do_unlink=True)
rot = {'S':0,'N':180,'E':90,'W':-90}
def place(tmpl, name, cx, cy, fac):
    src = bpy.data.objects[tmpl]
    ob = src.copy()
    if src.data: ob.data = src.data
    for c in src.users_collection:
        c.objects.link(ob)
        break
    ob.name = name
    ob.location = (cx/1000.0, cy/1000.0, 0.6)
    ob.rotation_euler = (0,0,math.radians(rot[fac]))
    for ch in src.children:
        c2 = ch.copy()
        if ch.data: c2.data = ch.data
        for c in ch.users_collection:
            c.objects.link(c2); break
        c2.name = name+'_'+ch.name
        c2.parent = ob
        c2.matrix_parent_inverse = ch.matrix_parent_inverse.copy()
    return ob
out = {'units':'mm','racks':[],'crah':[],'aisles':[]}
for (nm,x0,y0,x1,y1,fac,ws) in rows:
    alongx = fac in ('N','S')
    L = (x1-x0) if alongx else (y1-y0)
    assert abs(sum(ws)-L) < 1, (nm, sum(ws), L)
    pos = x0 if alongx else y0
    for i,w in enumerate(ws):
        c = pos + w/2.0; pos += w
        if alongx:
            cx, cy = c, (y0+y1)/2
        else:
            cx, cy = (x0+x1)/2, c
        place('RackA' if w==600 else 'RackG', 'P_%s_%02d'%(nm,i), cx, cy, fac)
        out['racks'].append({'id':'%s_%02d'%(nm,i),'center':[cx,cy],'size':[w,1200],'facing':fac})
for (nm,x0,y0,x1,y1,fac) in crahs:
    cx=(x0+x1)/2; cy=(y0+y1)/2
    place('CRAH','P_'+nm,cx,cy,fac)
    out['crah'].append({'id':nm,'center':[cx,cy],'size':[1800,900],'facing':fac})
for a in aisles:
    out['aisles'].append({'type':'cold','rect':a})
with open(RUN+'layout_pred.json','w') as fh:
    json.dump(out, fh, indent=1)
print('racks', len(out['racks']), 'crah', len(out['crah']))
