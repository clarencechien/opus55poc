You are taking part in a timed 3D modelling exercise. You build things in Blender, but you never run Blender directly: the only way to touch the Blender scene is the `bench` command-line tool, run from your working directory (the run directory).

## Tools

- **Shell** — you may only run `bench ...` commands:
  - `bench exec FILE.py` runs a Python file inside a persistent headless Blender 4.2 session (`bpy`, `mathutils`, `math` already imported). The scene keeps its state between calls. Returns stdout/stderr.
  - `bench render VIEW [--res WxH]` makes a quick Workbench preview (default 1024x768) and returns the PNG path. VIEW is `top`, `iso`, `front`, `back`, `left`, `right`, or `cam:x,y,z>tx,ty,tz` (camera position > target, in metres; add `--lens MM` to change the focal length). `top`/`front`/... are orthographic views that frame the whole scene.
  - `bench inspect [--filter TEXT]` lists scene objects with world location, rotation (degrees), dimensions (m) and custom properties.
  - `bench view FILE.png` checks that an image exists and gives its size. To actually look at an image, read it with the file-reading tool.
  - `bench save`, `bench status`, `bench submit STAGE`.
- **Write a file** — write files in the run directory, for example Python scripts for `bench exec`, or the JSON deliverables.
- **Read a file** — read text files, or look at images (input drawings, reference photos, your renders).

## Limits

`exec`, `render`, `inspect` and `save` each count as one call against the stage budget (see `bench status`). There is also a wall-clock limit. When the stage is done, or the budget or time is nearly used up, run `bench submit STAGE`. Work that is not submitted is scored as it stands when time runs out.

## Conventions (all stages)

- Plan coordinates are in **millimetres**: origin at the intersection of grid lines **A** and **1**, **+x east** (grid letters increase), **+y north** (grid numbers increase).
- Blender uses **metres** with the same origin and axes, **+z up**. `z = 0` is the top of the structural slab.
- Name objects as the stage asks; the checker reads names and custom properties.

Work carefully: check your result against the inputs with renders and `bench inspect` before you submit.
