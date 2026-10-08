"""Project gates for PETGasus. Tier 0: each reads one number build() derived.

Gate ids are project-scoped (`petgasus.*`). Every limit is read from its claim
(`ctx.acceptance`), never typed here. Every gate's negative control is in
`../selftest/bad_configs.py` and changes ONE physically meaningful thing in the
known-good design (`../selftest/known_good.py`).
"""
from __future__ import annotations

from nopekit.gates import gate, GateContext
from nopekit.models import NegativeControl, Tier, Verdict


def _judge(ctx: GateContext, gate_id: str, claim: str, key: str, units: str, ndp: int,
           detail: str) -> Verdict:
    acc = ctx.acceptance(claim)
    measured = round(float(ctx.params[key]), ndp)
    return Verdict(gate=gate_id, passed=acc.holds(measured), measured=measured,
                   limit=acc.limit, units=units, comparator=acc.comparator.value,
                   detail=detail)


@gate(
    id="petgasus.thrust_to_weight",
    title="Thrust-to-weight at nominal pack voltage",
    claims=["thrust-margin"],
    tier=Tier.INSTANT,
    settles="thrust to weight",
    negative_control=NegativeControl(
        fixture="selftest/bad_configs.py:heavy_battery",
        note="the known-good quad carrying a pack 4x as heavy; nothing else changes"),
)
def thrust_to_weight(ctx: GateContext) -> Verdict:
    """4 x rated thrust x (V_nom/V_test)^2 x duct factor, over all-up weight."""
    p = ctx.params
    return _judge(ctx, "petgasus.thrust_to_weight", "C1", "thrust_to_weight", "ratio", 3,
                  f"{p['thrust_total_g']:.0f} g thrust / {p['auw_g']:.1f} g AUW; "
                  f"hover at {p['hover_throttle_frac']:.0%} of full thrust")


@gate(
    id="petgasus.auw",
    title="All-up weight",
    claims=["auw"],
    tier=Tier.INSTANT,
    settles="all-up weight",
    negative_control=NegativeControl(
        fixture="selftest/bad_configs.py:brick_battery",
        note="a 300 g pack strapped under the known-good quad"),
)
def auw(ctx: GateContext) -> Verdict:
    p = ctx.params
    return _judge(ctx, "petgasus.auw", "C2", "auw_g", "g", 2,
                  f"frame {p['frame_mass_g']:.1f} g printed PETG + bought parts")


@gate(
    id="petgasus.flight_time",
    title="Hover flight time per pack",
    claims=["endurance"],
    tier=Tier.INSTANT,
    settles="hover flight time",
    negative_control=NegativeControl(
        fixture="selftest/bad_configs.py:tiny_pack",
        note="the known-good quad on a 100 mAh pack of the same mass"),
)
def flight_time(ctx: GateContext) -> Verdict:
    p = ctx.params
    return _judge(ctx, "petgasus.flight_time", "C3", "flight_time_min", "min", 2,
                  f"{p['hover_power_w']:.1f} W hover from the pack's usable energy "
                  f"(efficiency is assumption A2)")


@gate(
    id="petgasus.frame_mode",
    title="First out-of-plane frame mode",
    claims=["arm-vibration"],
    tier=Tier.INSTANT,
    settles="first frame mode",
    negative_control=NegativeControl(
        fixture="selftest/bad_configs.py:hand_drawn_plate",
        note="the hand-drawn plate (arms, ribs, spokes) in place of the optimised one"),
)
def frame_mode(ctx: GateContext) -> Verdict:
    """2.5D plate FE (model/topopt.py: modal), hub clamped, motors as masses."""
    p = ctx.params
    return _judge(ctx, "petgasus.frame_mode", "C4", "frame_mode1_hz", "Hz", 1,
                  f"modes {', '.join(f'{x:.0f}' for x in p['frame_modes_hz'])} Hz "
                  f"({p['plate_layout']} plate); motors turn at "
                  f"~{p['motor_freq_hover_hz']:.0f} Hz in a hover")


@gate(
    id="petgasus.interference",
    title="No two parts of the assembly overlap",
    claims=["envelope-clearance"],
    tier=Tier.INSTANT,
    settles="interference volume",
    negative_control=NegativeControl(
        fixture="selftest/bad_configs.py:oversize_props",
        note="props 3 mm bigger than the ducts were sized for, ducts unchanged"),
)
def interference(ctx: GateContext) -> Verdict:
    p = ctx.params
    pairs = ", ".join(f"{k} {v:.3f}" for k, v in sorted(p["interference_mm3"].items()))
    n = len(p["assembly_parts"])
    return _judge(ctx, "petgasus.interference", "C5", "interference_total_mm3", "mm3", 3,
                  f"{n} placed parts, every pair intersected: "
                  + (f"overlaps (mm3) {pairs}" if pairs else "no undeclared overlap"))


@gate(
    id="petgasus.fc_screws",
    title="AIO screws engage the posts and stay inside the plate",
    claims=["fc-screws"],
    tier=Tier.INSTANT,
    settles="FC screw protrusion below plate",
    negative_control=NegativeControl(
        fixture="selftest/bad_configs.py:long_fc_screws",
        note="M1.4 x 12 screws in the known-good stack"),
)
def fc_screws(ctx: GateContext) -> Verdict:
    p = ctx.params
    v = _judge(ctx, "petgasus.fc_screws", "C8", "fc_screw_protrusion_mm", "mm", 2,
               f"{p['fc_screw_engagement_mm']:.1f} mm engaged (>= 3.0 needed) in a "
               f"{p['fc_stack_mm']:.1f} mm stack")
    if v.passed and round(float(p["fc_screw_engagement_mm"]), 2) < 3.0:
        v = Verdict(gate=v.gate, passed=False, measured=v.measured, limit=v.limit,
                    units=v.units, comparator=v.comparator,
                    detail="screw too short: " + v.detail)
    return v


@gate(
    id="petgasus.motor_screws",
    title="Supplied motor screws reach into the motor",
    claims=["motor-screws"],
    tier=Tier.INSTANT,
    settles="motor screw engagement",
    negative_control=NegativeControl(
        fixture="selftest/bad_configs.py:thick_seat",
        note="a 2.5 mm motor seat with the same supplied M1.4 x 3 screws"),
)
def motor_screws(ctx: GateContext) -> Verdict:
    p = ctx.params
    return _judge(ctx, "petgasus.motor_screws", "C9", "motor_screw_engagement_mm", "mm", 2,
                  f"{p['motor_screw_len']:.1f} mm screw through a "
                  f"{p['plate_t']:.1f} mm seat")


@gate(
    id="petgasus.one_piece",
    title="Frame mesh is one connected piece",
    claims=["one-piece"],
    tier=Tier.INSTANT,
    settles="frame pieces",
    negative_control=NegativeControl(
        fixture="selftest/bad_configs.py:no_spokes",
        note="the known-good frame with no spokes: the motor seats float free"),
)
def one_piece(ctx: GateContext) -> Verdict:
    p = ctx.params
    return _judge(ctx, "petgasus.one_piece", "C11", "frame_pieces", "count", 0,
                  f"{p['frame_pieces']} connected solid(s) in the frame mesh")


@gate(
    id="petgasus.motor_leads",
    title="Motor leads reach the flight controller",
    claims=["motor-leads"],
    tier=Tier.INSTANT,
    settles="motor lead spare",
    negative_control=NegativeControl(
        fixture="selftest/bad_configs.py:short_leads",
        note="motors with 20 mm leads on the known-good frame"),
)
def motor_leads(ctx: GateContext) -> Verdict:
    p = ctx.params
    need = ", ".join(f"{k} {v:.1f}" for k, v in sorted(p["motor_lead_needed_mm"].items()))
    return _judge(ctx, "petgasus.motor_leads", "C12", "motor_lead_spare_mm", "mm", 2,
                  f"route lengths, mm: {need}; lead {p['motor_lead_len']:.0f} mm")
