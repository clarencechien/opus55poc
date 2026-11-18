import json, sys
sys.path.insert(0,'.')
import d2lib as L, build1 as B

ROWS2=[
 (1000,'N',[(2500,7200),(9600,25100)], {0:1}),
 (3400,'S',[(2500,25100)],             {0:1}),
 (5500,'N',[(1000,2200),(2500,6000),(6600,12300),(12900,18600),(19200,25100)], {1:1,4:1}),
 (7900,'S',[(2500,22700)],             {0:1}),
 (10000,'N',[(2500,6000),(6600,12300),(12900,21150)], {0:1,2:1}),
 (12400,'S',[(1000,2200),(2500,6000),(6600,12300),(12900,18800)], {1:1}),
 (14500,'N',[(1000,2200),(2500,18800)], {}),
]
racks=B.build(ROWS2)
print("racks",len(racks),"gpu",sum(1 for r in racks if r['gpu']))
bad,nv,nb,gv,reached,m=L.evaluate(racks)
if nb==0 and gv==8:
    json.dump(racks,open('cand2.json','w'))
    print("KEEP candidate 2")
