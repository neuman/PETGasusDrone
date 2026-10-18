"""The topology proposal the frame is drawn from, for the front page.

Publishes the proposer's own preview (top and side views of the density field,
written by fea.topopt3d beside the field and filed as an input), its run summary,
and the material comparison table recorded with the material decision. Nothing
here is computed: the page shows what the proposer and the comparison wrote.
"""
from __future__ import annotations

import json
import os

from nopekit.models import View, ViewKind
from nopekit.site import ViewContext, viewgen


@viewgen(
    id="topology",
    kind=ViewKind.TABLE,
    title="Topology proposal",
    description="The optimiser's density field the frame is drawn from, and the filament comparison.",
    order=91,
)
def topology(ctx: ViewContext) -> View | None:
    p = ctx.params
    field = p.get("topology_field") or ""
    if not field:
        ctx.log("topology: no topology_field in the design")
        return None
    root = ctx.root
    stem = os.path.splitext(os.path.join(root, field))[0]
    data = {"field": field, "current": bool(p.get("topology_current")), "variant": p.get("topology_variant")}
    if os.path.exists(stem + ".png"):
        with open(stem + ".png", "rb") as fh:
            data["preview"] = ctx.write_asset("topology.png", fh.read())
    if os.path.exists(stem + ".json"):
        with open(stem + ".json") as fh:
            summary = json.load(fh)
        data["iterations"] = summary.get("iterations")
        data["seconds"] = summary.get("seconds")
    table = os.path.join(root, "inputs", "data", "material-comparison.json")
    rows = []
    if os.path.exists(table):
        with open(table) as fh:
            rows = json.load(fh).get("rows", [])
        data["materials"] = rows
    src = ctx.write_asset("topology.json", json.dumps(data, separators=(",", ":")))
    return View(id="topology", kind=ViewKind.TABLE, title="Topology proposal", src=src,
                data={"columns": [{"key": "material", "label": "Filament", "align": "left"},
                                  {"key": "frame_g", "label": "Frame g", "align": "right"},
                                  {"key": "mode_hz", "label": "First mode Hz", "align": "right"},
                                  {"key": "drop_m", "label": "Drop m", "align": "right"},
                                  {"key": "wall_m_s", "label": "Wall m/s", "align": "right"}],
                      "rows": rows},
                meta={"data_url": src})
