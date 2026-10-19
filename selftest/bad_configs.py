"""Known-bad fixtures for PETGasus's gates.

Each returns a GateContext whose params are the KNOWN-GOOD design
(`known_good.py`) rebuilt with ONE physically meaningful change, in the direction
its gate cares about. Nothing here reads the host context's design.
"""
from __future__ import annotations

import dataclasses
import os

from nopekit.modelio import load_path

known_good = load_path(os.path.join(os.path.dirname(os.path.abspath(__file__)), "known_good.py"))


def _with(ctx, **overrides):
    config = dict(known_good.CONFIG)
    for k in overrides:
        if k not in config:
            raise TypeError(f"fixture overrides unknown Config field {k!r}")
    config.update(overrides)
    return dataclasses.replace(known_good.context(ctx), params=known_good.params(config))


def heavy_battery(ctx):
    """petgasus.thrust_to_weight — pack mass x8, nothing else: the 66.6 g motors
    carry x4 with thrust to spare."""
    return _with(ctx, battery_mass_g=known_good.CONFIG["battery_mass_g"] * 8)


def brick_battery(ctx):
    """petgasus.auw — a 300 g pack: the quad is now over the 250 g line."""
    return _with(ctx, battery_mass_g=300.0)


def tiny_pack(ctx):
    """petgasus.flight_time — 100 mAh at the same mass: a third of the energy or less."""
    return _with(ctx, battery_mah=100.0)


def oversize_props(ctx):
    """petgasus.interference — the prop tip gap cut by 2.5 mm, to -0.5: the guards
    are drawn round the props (guard_r_in = prop radius + prop_tip_gap), so their
    inner face moves 2.5 mm in and the prop tips now cut 0.5 mm into it."""
    return _with(ctx, prop_tip_gap=known_good.CONFIG["prop_tip_gap"] - 2.5)


def long_fc_screws(ctx):
    """petgasus.fc_screws — M1.4 x 12 through the grommets: the tip pokes out below."""
    return _with(ctx, fc_screw_len=12.0)


def thick_seat(ctx):
    """petgasus.motor_screws — a 2.5 mm seat: the supplied 3 mm screw keeps 0.5 mm."""
    return _with(ctx, plate_t=2.5)


def no_field(ctx):
    """petgasus.one_piece — no topology field: four seats, the guard arcs and
    their links, four posts and the strap saddle with nothing joining them."""
    return _with(ctx, topology_field="")


def short_leads(ctx):
    """petgasus.motor_leads — 20 mm motor leads: the straight run needs ~23 mm."""
    return _with(ctx, motor_lead_len=20.0)


def tall_guards(ctx):
    """petgasus.guard_height — v0.1's duct height, 10.9 mm."""
    return _with(ctx, guard_h=10.9)


def fat_limbs(ctx):
    """petgasus.prop_blockage — the same field drawn at density 0.15 instead of
    0.36: every limb fattens, and those under the props fill the discs."""
    return _with(ctx, surface_iso=0.15)


def moved_motors(ctx):
    """petgasus.topology_current — the guards 1 mm further out (wider tip gap), so
    the motors move out with them: the field was computed for the old keep-outs."""
    return _with(ctx, prop_tip_gap=known_good.CONFIG["prop_tip_gap"] + 1.0)


def coarse_fea_mesh(ctx):
    """petgasus.fea_converged — the analysis surface at a 3 mm edge, coarser than
    the 3-4 mm limbs it describes: its numbers and the fine surface's (2.1 mm)
    disagree. (5 mm tets alone lost: gmsh's mesh followed the surface's
    triangles whatever the tet size, and stayed converged.)"""
    return _with(ctx, fea_surface_mm=3.0)


def tpu_frame(ctx):
    """petgasus.frame_mode — the same shape in TPU 95A (33.6 MPa against PETG's
    1810): its first mode falls by sqrt(54), ~7x."""
    return _with(ctx, material="TPU95A", guard_material="TPU95A")


def weak_layers(ctx):
    """petgasus.crash_drop, petgasus.crash_wall — strength at a tenth of the data
    sheet's (a damp spool, a cold print), in the strong filament the crashes are
    judged in too: the energy the frame takes before it breaks falls 100x, the
    drop height and wall speed 100x and 10x."""
    return _with(ctx, strength_knockdown=0.1)
