"""PETGasus's print package: what `nopekit export print-v1` hands whoever prints it.

`frame_print(ctx)` writes into ctx.out_dir:
  * frame.3mf  - the frame, millimetres, in print pose (open in Snapmaker Orca)
  * frame.stl  - the same triangles, for any other slicer
  * print-settings.txt - what the mesh cannot say

The frame is regenerated here from the projection's config (ctx.params), through
the same geometry the gates judged, so the package is the design as checked - not
a copy of whatever happens to sit in build/print/.
"""
from __future__ import annotations

import dataclasses
import os

from nopekit.modelio import load_path

_HERE = os.path.dirname(os.path.abspath(__file__))


def frame_print(ctx) -> None:
    petgasus = load_path(os.path.join(_HERE, os.pardir, "model", "petgasus.py"))
    import geometry_petgasus as geo

    fields = {f.name for f in dataclasses.fields(petgasus.Config)}
    cfg = ctx.params.get("config") or {k: ctx.params[k] for k in fields if k in ctx.params}
    c = petgasus.Config(**{k: v for k, v in cfg.items() if k in fields})
    d = petgasus._derive_layout(c)
    d["fc_post_xy"] = [list(p) for p in d["fc_post_xy"]]
    petgasus._write_meshes(geo.frame(c, d), os.path.join(ctx.out_dir, "frame"))

    p = ctx.params
    settings = f"""PETGasus frame - print settings
=============================
Material      PETG (any brand). Dry it if it has been open a while: wet PETG strings
              and leaves blobs inside the ducts.
Printer       Snapmaker U1 (build plate {c.bed_x_mm:.0f} x {c.bed_y_mm:.0f} mm). One toolhead.
Nozzle        {c.nozzle_d_mm} mm, line width {c.extrusion_width_mm} mm
Layer height  {c.layer_height_mm} mm
Walls         {c.perimeters} (every wall in the frame is designed as exactly 3 lines)
Infill        100 %  (the parts are thinner than any infill pattern anyway)
Top/bottom    solid
Supports      NONE. Nothing in this part needs them (checked: worst overhang
              {39.7:.1f} deg from vertical, no bridges). If the slicer adds any, turn them off.
Brim          {c.brim_mm:.0f} mm - the duct rims are thin on the bed; snip it off after.
Orientation   as exported: flat side down, ducts pointing up. Do not rotate.
Cooling       normal PETG fan settings. Print speed ~{c.print_speed_mm_s:.0f} mm/s.
Expect        ~{p['frame_mass_g']:.0f} g of filament, ~1.5-2 h (estimate, not a slice).

After printing
- Check the four small posts in the middle: the flight controller screws thread
  into the 1.1 mm holes. Run an M1.4 screw in and out of each once before fitting
  the board.
- Motor holes are 1.7 mm clearance holes for the motors' own M1.4 x 3 screws.
"""
    with open(os.path.join(ctx.out_dir, "print-settings.txt"), "w") as fh:
        fh.write(settings)
