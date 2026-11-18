import bpy
S = bpy.context.scene
fix = {"Louvre1":None}
def movex(name, dx):
    o = S.objects.get(name)
    if o:
        o.location.x += dx
def setbb(name, key, val):
    pass
# nudge louvres 1mm in -x, handle 1mm +y, manifold axis -2mm y
for i in range(1,6):
    o = S.objects.get("Louvre%d"%i)
    o.location.x += 0.001
o = S.objects.get("HandleBar"); o.location.y += 0.001
for n in ("Manifold","Valve1","Valve2"):
    o = S.objects.get(n); o.location.y -= 0.002
bpy.ops.object.select_all(action='DESELECT')
print("ok")
