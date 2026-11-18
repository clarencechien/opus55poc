import bpy, math
from mathutils import Vector

# close-up renders with a workbench camera
scene = bpy.context.scene
scene.render.engine = 'BLENDER_WORKBENCH'
scene.display.shading.color_type = 'MATERIAL'
scene.display.shading.light = 'STUDIO'

cam = bpy.data.objects.get("TmpCam")
if cam is None:
    cd = bpy.data.cameras.new("TmpCam")
    cam = bpy.data.objects.new("TmpCam", cd)
    scene.collection.objects.link(cam)
scene.camera = cam

def shoot(name, loc, target, res=(900, 700)):
    cam.location = loc
    d = Vector(target) - Vector(loc)
    cam.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    scene.render.resolution_x, scene.render.resolution_y = res
    scene.render.filepath = f"renders/{name}.png"
    bpy.ops.render.render(write_still=True)
    print("wrote", name)

shoot("closeA_front", (0.15, -1.7, 1.15), (0.05, -0.55, 1.05))
shoot("closeA_door",  (-0.35, -1.1, 0.55), (0.0, -0.6, 0.45), res=(900, 900))
shoot("closeB_front", (1.7, -1.7, 1.3), (1.5, -0.4, 1.0))
shoot("closeB_rear",  (1.4, 1.8, 1.2), (1.5, 0.4, 1.0))
