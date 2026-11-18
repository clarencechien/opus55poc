for n in ("RackG", "RackA", "Rack_B01"):
    o = bpy.data.objects[n]
    print(n, tuple(o.scale), len(o.children), o.matrix_world.to_scale())
    ch = o.children[0]
    print("  ", ch.name, tuple(ch.scale), ch.data.name if ch.data else None, ch.dimensions[:])
