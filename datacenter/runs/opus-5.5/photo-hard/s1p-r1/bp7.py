exec(open('/home/user/opus55poc/datacenter/runs/opus-5.5/photo-hard/s1p-r1/bp4.py').read().split("show('cam3 W1")[0])
def hz(ci,u,v,h):
    p,rd = ray(ci,u,v)
    t=(h-p.z)/rd.z
    q=p+rd*t
    return (round(q.x,2),round(q.y,2))
pts = [(430,207),(620,148),(520,118),(300,140),(240,115),(360,170),(700,182)]
for cx,cy in pts:
    u = 385+cx/3.0; v = 430+cy/3.0
    print((cx,cy), hz(2,u,v,2.6))
