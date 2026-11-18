# Stage S1P — survey photos to equipment layout

A data hall has been fitted out. You do not have its layout; you have site photos. Work out where every piece of equipment stands.

## Inputs (in `inputs/`)

- `plan_empty.png` — the empty-room drawing:
  - grid, walls, columns, doors and the UPS room (which is not part of the hall)
  - the notes give the standard sizes
- `photo_1.jpg` … `photo_5.jpg` — survey photos taken from just under the ceiling at the hall's corners.
- `cameras.json` — for each photo:
  - the exact camera position and aim point (metres, plan axes)
  - the lens (mm), the sensor width, and the resolution
  - a ready-made `bench render` command that reproduces that camera in the Blender scene

## What you can see in the photos

- **Racks:** black cabinets, 2.0 m high, 1200 mm deep, and 600 mm wide (GPU racks are 800 mm wide). Racks in a row are butted together. The **front** of every rack has a white label strip with a blue LED line under it, across the top of the door. The back has neither.
- **CRAH units:** light-grey cabinets 1800 W × 900 D, with a dark grille on their front (supply side).
- **Floor:** 600 × 600 mm raised-floor tiles on a grid aligned to the plan origin (tile edges at multiples of 600 mm). Cold aisles have darker perforated tiles.

## The Blender scene

The scene is already open with:
- the empty hall: `Wall_*`, `Column_*`, and `RaisedFloor` with its top at z = 0.6
- template objects outside the room, each with its origin at the centre of its footprint at floor level and its front facing −y:
  - `RackA` (0.6 × 1.2 × 2.0 m)
  - `RackG` (0.8 × 1.2 × 2.0 m)
  - `CRAH` (1.8 × 0.9 × 1.95 m)
- the five cameras `Cam_1` … `Cam_5`

You can place copies of the templates and render from the photo cameras to compare your reconstruction with the photos. Your previews are Workbench renders, not photos.

## Deliverable: `layout_pred.json` (in the run directory, plan millimetres)

```json
{
  "units": "mm",
  "racks":  [{"id": "any unique string", "center": [x, y], "size": [w, d], "facing": "N|S|E|W"}],
  "crah":   [{"id": "any unique string", "center": [x, y], "size": [w, d], "facing": "N|S|E|W"}],
  "aisles": [{"type": "cold", "rect": [x0, y0, x1, y1]}]
}
```

- `center` is the footprint centre.
- `size` is `[width, depth]`: width along the row, depth front to back.
- `facing` is the compass direction the front points to.
- List **every** rack individually.
- Rack ids are not checked. Racks are matched to the real ones by position.
- `aisles` lists the cold aisles, each as the rectangle between two facing rows of rack fronts.

## Scoring

The checker looks at:
- the number of racks
- each rack's position (the closer the better; matches beyond 600 mm count as wrong)
- each rack's facing and width
- the CRAH units
- the cold aisles

Finish with `bench submit s1p`.
