exec(open("/home/user/opus55poc/datacenter/runs/opus-5.5/hard/s3-r1/build.py").read().replace("    root.scale = (1, 1, 1)\n", ""))
for n in ("Rack_B01", "Rack_A01", "Rack_E01", "Rack_F01", "Rack_C01"):
    o = bpy.data.objects[n]
    fwd = o.matrix_world.to_3x3().normalized() @ Vector((0, -1, 0))
    print(n, o["rackId"], tuple(round(v, 3) for v in o.location), tuple(round(v, 3) for v in fwd))
