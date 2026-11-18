import bpy, numpy as np

src = bpy.data.images.load('/home/user/opus55poc/datacenter/runs/qwen3.8-flash/easy/s1-r2-high/inputs/plan.png')
w, h = src.size[0], src.size[1]
px = np.array(src.pixels[:]).reshape(h, w, 4)

def save_crop(name, x0, x1, y0, y1, rot=0):
    # pixels array row 0 = bottom of image
    sub = px[y0:y1, x0:x1, :3].copy()
    if rot == 90:
        sub = np.rot90(sub, 1)
    if rot == -90:
        sub = np.rot90(sub, -1)
    nh, nw = sub.shape[0], sub.shape[1]
    im = bpy.data.images.new(name, nw, nh, alpha=False)
    big = np.ones((nh, nw, 4), dtype=np.float32)
    big[:, :, :3] = sub[::-1]  # flip vertically back
    im.pixels = big.ravel()
    im.filepath_raw = '/home/user/opus55poc/datacenter/runs/qwen3.8-flash/easy/s1-r2-high/' + name + '.png'
    im.file_format = 'PNG'
    im.save()
    print(name, nw, nh)

# left dimension strip (vertical text) : full height of room area
save_crop('crop_left', 60, 350, 250, 2050, rot=-90)
# right dimension strip
save_crop('crop_right', 2090, 2380, 250, 2050, rot=-90)
