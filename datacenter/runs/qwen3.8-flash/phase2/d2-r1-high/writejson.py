import json, sys
sys.path.insert(0,'.')
import importlib, d2lib as L, build1 as B
importlib.reload(B)
racks=B.build(B.ROWS)
out={"units":"mm","racks":[]}
for r in racks:
    out["racks"].append({"id":r['id'],"center":[r['cx'],r['cy']],
                        "size":[r['w'],1200],"facing":r['f']})
json.dump(out,open('layout_design.json','w'),indent=1)
print("wrote",len(out["racks"]),"racks; gpu",sum(1 for r in racks if r['gpu']))
# re-check straight from the JSON file
d=json.load(open('layout_design.json'))
rr=[{'id':e['id'],'cx':e['center'][0],'cy':e['center'][1],'w':e['size'][0],'f':e['facing'],
     'gpu':e['size'][0]==800} for e in d['racks']]
bad,nv,nb,gv,reached,m=L.evaluate(rr)
print("from json: total %d valid %d bad %d gpu %d"%(len(rr),nv,nb,gv))
