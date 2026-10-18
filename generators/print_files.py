"""PETGasus's print package: what `nopekit export print-v1` hands whoever prints it.

`frame_print(ctx)` writes into ctx.out_dir:
  * frame.3mf  - the frame in print pose, millimetres, one object per filament
                 (open in Snapmaker Orca and give each object its filament)
  * frame.stl  - every object merged, for any other slicer
  * print-settings.txt - what the mesh cannot say

The frame is regenerated here from the projection's config (ctx.params), through
the same function build() and the gates use (petgasus.frame_solids), so the
package is the design as checked - not a copy of whatever sits in build/print/.
"""
from __future__ import annotations

import dataclasses
import os

from nopekit.modelio import load_path

_HERE = os.path.dirname(os.path.abspath(__file__))


def frame_print(ctx) -> None:
    petgasus = load_path(os.path.join(_HERE, os.pardir, "model", "petgasus.py"))

    fields = {f.name for f in dataclasses.fields(petgasus.Config)}
    cfg = ctx.params.get("config") or {k: ctx.params[k] for k in fields if k in ctx.params}
    c = petgasus.Config(**{k: v for k, v in cfg.items() if k in fields})
    _body, frame_solid, guard_solid, _current, _info, _field = petgasus.frame_solids(c)
    petgasus._write_meshes(petgasus.print_bodies(c, frame_solid, guard_solid), os.path.join(ctx.out_dir, "frame"))

    p = ctx.params
    mat = petgasus.MATERIALS[c.material]
    gmat = petgasus.MATERIALS[c.guard_material]
    two = c.guard_material != c.material
    needs = ", ".join(p["material_needs"]) or "nothing beyond the stock U1"
    smat = petgasus.MATERIALS[c.strong_material]
    sneeds = ", ".join(smat["needs"]) or "nothing beyond the stock U1"
    settings = f"""PETGasus frame - print settings
=============================
Filament      {c.material} for the frame ({mat['source']}){f"; {c.guard_material} for the guard hoops ({gmat['source']})" if two else ""}.
              Dry it if the spool has been open a while: wet filament strings and
              is weaker across its layers.
              The U1 needs: {needs}.
              For a frame that survives hard crashes, print it in {c.strong_material}
              instead ({smat['source']}): it needs {sneeds}.
Printer       Snapmaker U1 (build plate {c.bed_x_mm:.0f} x {c.bed_y_mm:.0f} mm).{" Two toolheads: the 3MF has one object per filament." if two else ""}
Nozzle        {c.nozzle_d_mm} mm, line width {c.extrusion_width_mm} mm
Layer height  {c.layer_height_mm} mm
Walls         {c.perimeters} or more; infill 100 % (the limbs are a few mm across)
Orientation   as exported: tilted {c.print_tilt_deg:.0f} deg about the axis at {c.print_azimuth_deg:.0f} deg
              from forward, so the worst crash stress runs along the layers.
              Do not re-orient it in the slicer.
Supports      ON, tree supports, touching the build plate and the part.
              Use PLA for the support INTERFACE (the layers that touch the part):
              PETG does not stick to PLA, so the supports peel off cleanly. Snapmaker's
              guide "Using a Different Filament for Support (PLA and PETG)" shows how.
Brim          {c.brim_mm:.0f} mm where the part touches the bed; snip it off after.
Cooling       normal {c.material} fan settings. Print speed ~{c.print_speed_mm_s:.0f} mm/s.
Expect        ~{p['frame_mass_g']:.0f} g of frame filament plus the supports.

After printing
- Peel the supports by hand, slowly, from the thin end of each limb towards the
  thick end. If a support will not come off without bending a limb, stop (P6).
- Check the four posts in the middle: the flight controller's screws thread into
  the 1.1 mm holes through rubber grommets. Run an M1.4 screw in and out of each
  once before fitting the board.
- Motor holes are 1.7 mm clearance holes for the kit's M1.4 x 3 screws, driven up
  from below.
"""
    with open(os.path.join(ctx.out_dir, "print-settings.txt"), "w") as fh:
        fh.write(settings)
