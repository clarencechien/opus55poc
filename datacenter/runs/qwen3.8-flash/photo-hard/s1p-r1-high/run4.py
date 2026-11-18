import os
exec(open('labdetect.py').read())
ph = comps('inputs/photo_2.jpg', 'Cam_2')
rn = comps('cmp/r2.png', 'Cam_2')
print('PHOTO (u0,u1,v0,v1,n,planx,plany):')
for r in ph: print('  %5d %5d %5d %5d %5d  x %.2f y %.2f' % r)
print('RENDER:')
for r in rn: print('  %5d %5d %5d %5d %5d  x %.2f y %.2f' % r)
