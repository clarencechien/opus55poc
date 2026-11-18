import bpy, math
from mathutils import Vector

sc = bpy.context.scene
cam_data = bpy.data.cameras.new("AisleCam")
cam = bpy.data.objects.new("AisleCam", cam_data)
bpy.context.scene.collection.objects.link(cam)
cam.location = (3.25, 3.15, 1.55)
tgt = Vector((7.8, 3.15, 1.35))
d = tgt - cam.location
cam.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
sc.camera = cam
sc.render.engine = 'BLENDER_WORKBENCH'
sc.render.resolution_x = 1100
sc.render.resolution_y = 760
sc.render.filepath = "renders/aisle_view.png"
sc.display.shading.light = 'STUDIO'
bpy.ops.render.render(write_still=True)
print("wrote", sc.render.filepath)

# second view: from the cold aisle looking back at the west door + tiles
cam.location = (7.6, 3.15, 1.5)
d = Vector((3.0, 3.15, 1.2)) - cam.location
cam.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
sc.render.filepath = "renders/aisle_view2.png"
bpy.ops.render.render(write_still=True)
print("wrote", sc.render.filepath)

bpy.data.objects.remove(cam, do_unlink=True)
bpy.data.cameras.remove(cam_data)
