"""Render fixed review views of a submitted .blend (same Workbench look as bench previews).

    blender -b FILE.blend --python render_views.py -- OUT_DIR [views...]     (default views: top iso)
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "bench"))
from render_common import do_render  # noqa: E402

args = sys.argv[sys.argv.index("--") + 1:]
out, views = args[0], (args[1:] or ["top", "iso"])
os.makedirs(out, exist_ok=True)
for v in views:
    print(do_render({"view": v, "res": "1024x768"}, path=os.path.join(out, f"review_{v}.png")))
