import bpy, os, numpy as np, sys, math
sys.path.append(os.getcwd())

def loadA(p):
    img = bpy.data.images.load(os.path.abspath(p))
    w,h = img.size
    a = np.array(img.pixels[:], dtype=np.float32).reshape(h,w,4)
    bpy.data.images.remove(img)
    return a[::-1].copy()

S = bpy.context.scene
for nm in list(S.objects):
    if nm.name.startswith("Tmp"):
        bpy.data.objects.remove(nm, do_unlink=True)
cam_data = bpy.data.cameras.new("TmpCam"); cam_data.type='ORTHO'
cam = bpy.data.objects.new("TmpCam", cam_data); S.collection.objects.link(cam)
S.camera = cam
ld = bpy.data.lights.new("TmpLamp","SUN"); ld.energy=3
lo = bpy.data.objects.new("TmpLamp", ld); S.collection.objects.link(lo)
lo.rotation_euler = (0.6,0.2,0.5)
S.render.engine='BLENDER_WORKBENCH'
S.display.shading.light='FLAT'; S.display.shading.color_type='SINGLE'
S.display.shading.single_color=(1,1,1); S.display.shading.show_shadows=False
S.render.film_transparent=True
S.render.image_settings.file_format='PNG'

VIEWS = {
 'front': dict(loc=(0,-10,1.115), rot=(math.pi/2,0,0), res=(790,1315), scale=2.63, bx=(100,690,100,1215), img='inputs/view_front.png'),
 'back':  dict(loc=(0,10,1.115), rot=(math.pi/2,0,math.pi), res=(790,1315), scale=2.63, bx=(100,690,100,1215), img='inputs/view_back.png'),
 'left':  dict(loc=(-10,0,1.115), rot=(math.pi/2,0,-math.pi/2), res=(880,1315), scale=2.63, bx=(100,780,100,1215), img='inputs/view_left.png'),
 'right': dict(loc=(10,0,1.115), rot=(math.pi/2,0,math.pi/2), res=(880,1315), scale=2.63, bx=(100,780,100,1215), img='inputs/view_right.png'),
 'top':   dict(loc=(0,0,10), rot=(0,0,0), res=(790,880), scale=1.76, bx=(100,690,100,780), img='inputs/view_top.png'),
}
def dilate(a, it):
    for _ in range(it):
        b = a.copy()
        b[1:,:] |= a[:-1]; b[:-1,:] |= a[1:]; b[:,1:] |= a[:,:-1]; b[:,:-1] |= a[:,1:]
        a = b
    return a
for k,v in VIEWS.items():
    cam.location=v['loc']; cam.rotation_euler=v['rot']; cam_data.ortho_scale=v['scale']
    S.render.resolution_x, S.render.resolution_y = v['res']
    S.render.resolution_percentage=100
    p='/tmp/v_%s.png'%k; S.render.filepath=p
    bpy.ops.render.render(write_still=True)
    A = loadA(p); mine = A[...,3] > 0.5
    R = loadA(v['img']); rgb = (R[...,:3]*255)
    bg = (np.abs(rgb[...,0]-250)<=2)&(np.abs(rgb[...,1]-250)<=2)&(np.abs(rgb[...,2]-249)<=2)
    theirs = ~bg
    x0,x1,y0,y1=v['bx']
    m = mine[y0:y1+1, x0:x1+1]; t = theirs[y0:y1+1, x0:x1+1]
    md = dilate(m,3); td = dilate(t,3)
    print("%-6s IoU=%.4f  mine-only(beyond 3px of drawing)=%d  drawing-only(beyond 3px of mine)=%d" % (
        k, (m&t).sum()/(m|t).sum(), (m&~td).sum(), (t&~md).sum()))
    ys,xs=np.nonzero(t&~md)
    if len(xs):
        print("     drawing-only px x %d..%d y %d..%d"%(xs.min()+x0,xs.max()+x0,ys.min()+y0,ys.max()+y0))
    ys,xs=np.nonzero(m&~td)
    if len(xs):
        print("     mine-only px x %d..%d y %d..%d"%(xs.min()+x0,xs.max()+x0,ys.min()+y0,ys.max()+y0))
for nm in list(S.objects):
    if nm.name.startswith("Tmp"):
        bpy.data.objects.remove(nm, do_unlink=True)
S.camera = None
print("done")
