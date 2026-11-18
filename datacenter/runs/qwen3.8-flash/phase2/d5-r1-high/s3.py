import os, sys
sys.path.append(os.getcwd())
from tool import load
F = load('inputs/view_front.png')
pts = {'handle':(700,455),'bg':(50,50),'cab':(700,550),'door':(700,300),'disp':(420,300),
       'pipe':(150,230),'green':(200,250),'red_dome':(180,300),'ylw':(700,650),'plinth':(1170,300),'feet':(1200,190)}
for k,(py,px) in pts.items():
    print(k, F[py,px])
