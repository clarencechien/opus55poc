import numpy as np, json, math
from collections import deque

EPS = 1e-6
POLY = [(100.,100.),(25100.,100.),(25100.,12500.),(18800.,12500.),(18800.,18800.),(100.,18800.)]
COLS = [(6000,6000,6600,6600),(12300,6000,12900,6600),(18600,6000,19200,6600),
        (6000,12300,6600,12900),(12300,12300,12900,12900)]
CRAH = [(100,2100,1000,3900),(100,9000,1000,10800),(24200,8400,25100,10200)]
CRAH_SVC = [(1000,2100,2500,3900),(1000,9000,2500,10800),(22700,8400,24200,10200)]
CRAH_C = [(550,3000),(550,9900),(24650,9300)]
DOORS = [(7200,100,9600,1600),(21150,11000,22950,12500)]   # D1 S wall, D2 N wall (UPS)
D1_START = (8400.,600.)

def ov(a,b):
    return (a[0] < b[2]-EPS) and (b[0] < a[2]-EPS) and (a[1] < b[3]-EPS) and (b[1] < a[3]-EPS)

def rect_in_poly(r):
    cx=(r[0]+r[2])/2.; cy=(r[1]+r[3])/2.
    inside=False; n=len(POLY)
    for i in range(n):
        x1,y1=POLY[i]; x2,y2=POLY[(i+1)%n]
        if (y1>cy)!=(y2>cy):
            xin=x1+(cy-y1)*(x2-x1)/(y2-y1)
            if cx<xin: inside=not inside
    if not inside: return False
    for i in range(n):
        x1,y1=POLY[i]; x2,y2=POLY[(i+1)%n]
        if abs(x1-x2)<EPS:
            x=x1
            if r[0]+EPS<x<r[2]-EPS:
                lo,hi=sorted((y1,y2))
                if lo<r[3]-EPS and r[1]+EPS<hi: return False
        else:
            y=y1
            if r[1]+EPS<y<r[3]-EPS:
                lo,hi=sorted((x1,x2))
                if lo<r[2]-EPS and r[0]+EPS<hi: return False
    return True

DIR={'N':(0,1),'S':(0,-1),'E':(1,0),'W':(-1,0)}
OPP={'N':'S','S':'N','E':'W','W':'E'}

def foot(r):
    cx,cy,w,f=r['cx'],r['cy'],r['w'],r['f']
    if f in 'NS': return (cx-w/2.,cy-600.,cx+w/2.,cy+600.)
    return (cx-600.,cy-w/2.,cx+600.,cy+w/2.)

def zone(r, side, depth):
    """side: 'F' front, 'R' rear"""
    x0,y0,x1,y1=foot(r)
    dx,dy=DIR[r['f']]
    if side=='R': dx,dy=-dx,-dy
    if dx==1:  return (x1,y0,x1+depth,y1)
    if dx==-1: return (x0-depth,y0,x0,y1)
    if dy==1:  return (x0,y1,x1,y1+depth)
    return (x0,y0-depth,x1,y0)

def access_pts(r):
    cx,cy,w,f=r['cx'],r['cy'],r['w'],r['f']
    dx,dy=DIR[f]
    # front face centre is 600 from centre (N/S) or w/2 (E/W)
    if f in 'NS':
        d=600.
    else:
        d=w/2.
    F=(cx+dx*d+dx*600., cy+dy*d+dy*600.)
    R=(cx-dx*d-dx*450., cy-dy*d-dy*450.)
    return F,R

def build_grid(racks):
    xs=np.arange(0.,25201.,50.); ys=np.arange(0.,18851.,50.)
    X,Y=np.meshgrid(xs,ys,indexing='ij')
    # inside polygon (vectorized even-odd)
    ins=np.zeros(X.shape,dtype=bool)
    n=len(POLY)
    for i in range(n):
        x1,y1=POLY[i]; x2,y2=POLY[(i+1)%n]
        if abs(y1-y2)<EPS: continue
        cond=(y1>Y)!=(y2>Y)
        xin=x1+(Y-y1)*(x2-x1)/(y2-y1)
        ins^=cond&(X<xin)
    m=ins.copy()
    def sub(rects):
        for (a,b,c,d) in rects:
            dx=np.maximum(np.maximum(a-X,0.),X-c)
            dy=np.maximum(np.maximum(b-Y,0.),Y-d)
            m[(np.hypot(dx,dy)<450.-EPS)&ins]=False
    # walls: distance to polygon boundary
    dwall=np.full(X.shape,1e18)
    for i in range(n):
        x1,y1=POLY[i]; x2,y2=POLY[(i+1)%n]
        if abs(x1-x2)<EPS:
            dx=np.maximum(np.maximum(x1-X,0.),X-x1); dy=np.abs(Y-y1)
            lo,hi=sorted((y1,y2))
            dy=np.maximum(np.maximum(lo-Y,0.),Y-hi)
            dy=np.where((Y>=lo)&(Y<=hi),0.,dy)
        else:
            dx=np.maximum(np.maximum(x1-X,0.),X-x2)
            dx=np.where((X>=x1)&(X<=x2),0.,dx); dy=np.abs(Y-y1)
        dwall=np.minimum(dwall,np.hypot(dx,dy))
    m&=dwall>=450.-EPS
    m&=(np.hypot(X-D1_START[0],Y-D1_START[1])<1e17)
    sub(COLS); sub(CRAH)
    for r in racks: sub([foot(r)])
    return xs,ys,m

def flood(racks):
    xs,ys,m=build_grid(racks)
    j0=int(round(D1_START[0]/50.)); j1=int(round(D1_START[1]/50.))
    reached=np.zeros(m.shape,dtype=bool)
    if not m[j0,j1]:
        return xs,ys,m,reached,False
    dq=deque([(j0,j1)]); reached[j0,j1]=True
    while dq:
        i,j=dq.popleft()
        for di,dj in ((1,0),(-1,0),(0,1),(0,-1)):
            a,b=i+di,j+dj
            if 0<=a<m.shape[0] and 0<=b<m.shape[1] and m[a,b] and not reached[a,b]:
                reached[a,b]=True; dq.append((a,b))
    return xs,ys,m,reached,True

def near(reached,x,y,tol=150.+EPS):
    if reached.size==0: return None
    i0=int(round(x/50.)); j0=int(round(y/50.))
    best=None
    for i in range(i0-4,i0+5):
        for j in range(j0-4,j0+5):
            if 0<=i<reached.shape[0] and 0<=j<reached.shape[1] and reached[i,j]:
                gx,gy=i*50.,j*50.
                d=math.hypot(gx-x,gy-y)
                if d<=tol and (best is None or d<best[0]): best=(d,(gx,gy))
    return best

def evaluate(racks, verbose=True):
    bad={}
    def mark(r,why):
        bad.setdefault(r['id'],[]).append(why)
    F={r['id']:foot(r) for r in racks}
    for r in racks:
        fr=foot(r)
        if not rect_in_poly(fr): mark(r,'R1')
    for i,r in enumerate(racks):
        for s in racks[i+1:]:
            if ov(F[r['id']],F[s['id']]): mark(r,'R2'); mark(s,'R2')
        for c in COLS:
            if ov(F[r['id']],c): mark(r,'R2col')
        for c in CRAH:
            if ov(F[r['id']],c): mark(r,'R2crah')
        for z in CRAH_SVC:
            if ov(F[r['id']],z): mark(r,'R6')
        for z in DOORS:
            if ov(F[r['id']],z): mark(r,'R7')
        for side,dep,tag in (('F',1200,'R3'),('R',900,'R4')):
            z=zone(r,side,dep)
            if not rect_in_poly(z): mark(r,tag+'in')
            for s in racks:
                if s['id']!=r['id'] and ov(z,F[s['id']]):
                    mark(r,tag); mark(s,tag+' occupant')
            for c in COLS+CRAH:
                if ov(z,c): mark(r,tag+'obs')
        cor=zone(r,'F',3000)
        for s in racks:
            if s['id']!=r['id'] and ov(cor,F[s['id']]) and s['f']!=OPP[r['f']]:
                mark(r,'R5'); mark(s,'R5')
        if r.get('gpu'):
            ok=any(math.hypot(r['cx']-a,r['cy']-b)<=7000. for a,b in CRAH_C)
            if not ok: mark(r,'R9')
    xs,ys,m,reached,okstart=flood(racks)
    if not okstart and verbose: print("!! start point not walkable")
    for r in racks:
        fp,rp=access_pts(r)
        if near(reached,*fp) is None: mark(r,'R8front')
        if near(reached,*rp) is None: mark(r,'R8rear')
    nbad=len(bad); nvalid=len(racks)-nbad
    gpu_valid=sum(1 for r in racks if r.get('gpu') and r['id'] not in bad)
    if verbose:
        for r in racks:
            if r['id'] in bad: print("BAD",r['id'],r['cx'],r['cy'],r['w'],r['f'],set(bad[r['id']]))
        print("total %d valid %d bad %d gpu_valid %d"%(len(racks),nvalid,nbad,gpu_valid))
    return bad,nvalid,nbad,gpu_valid,reached,m
