import json, sys
sys.path.insert(0,'.')
import d2lib as L

ROWS=[
 (1000,'N',[(2500,7200),(9600,25100)], {0:1}),
 (3400,'S',[(2500,25100)],             {0:1}),
 (5500,'N',[(1000,1600),(2500,6000),(6600,12300),(12900,18600),(19200,25100)], {1:1,4:1}),
 (7900,'S',[(2500,22700)],             {0:1}),
 (10000,'N',[(2500,6000),(6600,12300),(12900,21150)], {0:1,2:1}),
 (12400,'S',[(1000,1600),(2500,6000),(6600,12300),(12900,18800)], {1:1}),
 (14500,'N',[(1000,1600),(2500,18800)], {}),
]

def build(rows):
    racks=[]; n=0
    for (y0,f,segs,gpus) in rows:
        cy=y0+600
        for si,seg in enumerate(segs):
            items=[]
            x=seg[0]
            while x+600<=seg[1]+1e-6:
                items.append([x,x+600,False]); x+=600
            g=gpus.get(si,0)
            for k in range(g):
                if not items: break
                it=items[-1-k]
                if it[1]+200<=seg[1]+1e-6:
                    it[1]=it[1]+200.; it[2]=True
            for it in items:
                n+=1
                w=800 if it[2] else 600
                racks.append({'id':'R%03d'%n,'cx':(it[0]+it[1])/2.0,'cy':float(cy),
                              'w':w,'f':f,'gpu':it[2]})
    return racks
