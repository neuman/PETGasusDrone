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
    """petgasus.thrust_to_weight — pack mass x4, nothing else."""
    return _with(ctx, battery_mass_g=known_good.CONFIG["battery_mass_g"] * 4)


def brick_battery(ctx):
    """petgasus.auw — a 300 g pack: the quad is now over the 250 g line."""
    return _with(ctx, battery_mass_g=300.0)


def tiny_pack(ctx):
    """petgasus.flight_time — 100 mAh at the same mass: a third of the energy or less."""
    return _with(ctx, battery_mah=100.0)


def hand_drawn_plate(ctx):
    """petgasus.frame_mode — the hand-drawn arms, ribs and spokes in place of the
    optimised plate, everything else unchanged. It bounces at ~160 Hz, under C4's
    200 Hz, which is the printed-frame vibration complaint the optimiser fixed."""
    return _with(ctx, plate_layout="arms")


def oversize_props(ctx):
    """petgasus.interference — props 3 mm larger in diameter than the ducts allow.

    The duct radius derives from prop_d, so growing prop_d alone would grow the
    ducts with it; the gap is cut by the same amount instead, which is what
    fitting the wrong props to a printed frame does.
    """
    return _with(ctx, prop_tip_gap=known_good.CONFIG["prop_tip_gap"] - 1.5 - 0.5)


def long_fc_screws(ctx):
    """petgasus.fc_screws — M1.4 x 12 in the known-good stack: the tip pokes out below."""
    return _with(ctx, fc_screw_len=12.0)


def thick_seat(ctx):
    """petgasus.motor_screws — a 2.5 mm seat: the supplied 3 mm screw keeps 0.5 mm."""
    return _with(ctx, plate_t=2.5)


def no_spokes(ctx):
    """petgasus.one_piece — zero spokes: the four motor seats float free in their ducts."""
    return _with(ctx, spoke_count=0)


def short_leads(ctx):
    """petgasus.motor_leads — 20 mm motor leads: the route needs ~21 mm."""
    return _with(ctx, motor_lead_len=20.0)
