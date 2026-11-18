# Stage S1 — from floor plan to 3D room

Input: `inputs/plan.png`, an equipment layout plan of a data hall (read it as an image).

## Deliverable 1: `layout_pred.json` (in the run directory)

Read the drawing and write down everything on it in plan coordinates (mm, origin at grid A/1, +x east, +y north):

```json
{
  "units": "mm",
  "grid": {"x": {"A": 0, "B": 0}, "y": {"1": 0, "2": 0}},
  "room": {
    "polygon": [[x, y], ...],
    "wall_thickness": 0,
    "clear_height": 0,
    "raised_floor_height": 0
  },
  "columns": [{"id": "B/2", "center": [x, y], "size": [w, d]}],
  "doors":   [{"id": "D1", "center": [x, y], "width": 0, "wall": "N|S|E|W"}],
  "crah":    [{"id": "CRAH-1", "center": [x, y], "size": [w, d], "facing": "N|S|E|W"}],
  "racks":   [{"id": "A01", "center": [x, y], "size": [w, d], "facing": "N|S|E|W"}],
  "aisles":  [{"type": "cold|hot", "rect": [x0, y0, x1, y1]}]
}
```

- `room.polygon` is the **inner face** of the data hall's walls, listed counter-clockwise, with as many vertices as the hall has corners. Rooms outside the data hall are not part of it.
- `center` is the centre of the footprint.
- `size` is `[width, depth]`, where depth is measured front to back.
- `facing` is the compass direction the equipment front points to.
- Each door's `center` is on the wall centreline.
- `aisles`: list the **cold aisles only**, each as an axis-aligned rectangle between the two facing rows of rack fronts, spanning the length of those rows.
- `racks`: list every rack drawn, with the id exactly as labelled.
- Grid values are the grid-line positions.

## Deliverable 2: the room shell in Blender (metres, z up)

| Object | Requirement |
|---|---|
| Walls | Objects named `Wall_*` around the data hall, full height from z = 0 to z = raised floor + clear height, with the correct thickness and an opening for each door |
| Columns | One object per column, named `Column_<id>` with `/` replaced by `_` (for example `Column_B_2`), from z = 0 to the same height as the walls |
| Raised floor | One object named `RaisedFloor` covering the room interior, top face at the raised-floor height |

Do not model racks or CRAH units in this stage.

Finish with `bench submit s1`.
