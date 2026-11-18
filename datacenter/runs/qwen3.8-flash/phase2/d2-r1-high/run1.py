import json, sys
sys.path.insert(0,'.')
import importlib
import d2lib as L
import build1 as B
importlib.reload(B)
racks=B.build(B.ROWS)
print("racks",len(racks),"gpu",sum(1 for r in racks if r['gpu']))
bad,nv,nb,gv,reached,m=L.evaluate(racks)
json.dump(racks,open('cand.json','w'))
