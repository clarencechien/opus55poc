src = open("build.py").read()
src = src.replace('scene.view_layer.update()', 'bpy.context.view_layer.update()')
open("build.py", "w").write(src)
print("patched3", src.count('bpy.context.view_layer.update()'))
