"""Project gates for PETGasus. Tier 0: each reads one number build() derived.
(The CalculiX gates, tier 2, are in structure.py.)

Gate ids are project-scoped (`petgasus.*`). Every limit is read from its claim
(`ctx.acceptance`), never typed here. Every gate's negative control is in
`../selftest/bad_configs.py` and changes ONE physically meaningful thing in the
known-good design (`../selftest/known_good.py`).
"""
from __future__ import annotations

from nopekit.gates import gate, GateContext
from nopekit.models import NegativeControl, Tier, Verdict

#: Where these gates' verdicts come from (SPEC 38): the model's own geometry and
#: arithmetic (screw stacks, lead routes, overlap and shadow volumes, a hash), as
#: cad-solid's mesh gates are. The three that answer from the motor's published
#: load table and the vendors' masses say basis="sourced" themselves.
PACK_BASIS = "model-only"


def _judge(ctx: GateContext, gate_id: str, claim: str, key: str, units: str, ndp: int,
           detail: str) -> Verdict:
    acc = ctx.acceptance(claim)
    measured = round(float(ctx.params[key]), ndp)
    return Verdict(gate=gate_id, passed=acc.holds(measured), measured=measured,
                   limit=acc.limit, units=units, comparator=acc.comparator.value,
                   detail=detail)


@gate(
    id="petgasus.thrust_to_weight",
    basis="sourced",    # the motor's load table and the vendors' masses (inputs/datasheets)
    title="Thrust-to-weight at nominal pack voltage",
    claims=["thrust-margin"],
    tier=Tier.INSTANT,
    settles="thrust to weight",
    negative_control=NegativeControl(
        fixture="selftest/bad_configs.py:heavy_battery",
        note="the known-good quad carrying a pack 8x as heavy; nothing else changes"),
)
def thrust_to_weight(ctx: GateContext) -> Verdict:
    """4 x rated thrust x (V_nom/V_test)^2 x guard factor, over all-up weight."""
    p = ctx.params
    return _judge(ctx, "petgasus.thrust_to_weight", "C1", "thrust_to_weight", "ratio", 3,
                  f"{p['thrust_total_g']:.0f} g thrust / {p['auw_g']:.1f} g AUW; "
                  f"hover at {p['hover_throttle_frac']:.0%} of full thrust")


@gate(
    id="petgasus.auw",
    basis="sourced",    # the motor's load table and the vendors' masses (inputs/datasheets)
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
    basis="sourced",    # the motor's load table and the vendors' masses (inputs/datasheets)
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
                  f"{p['hover_power_w']:.1f} W hover at {p['hover_eff_g_per_w']:.2f} g/W (the motor's load "
                  f"table at hover thrust) from the pack's usable energy")


@gate(
    id="petgasus.interference",
    title="No two parts of the assembly overlap",
    claims=["envelope-clearance"],
    tier=Tier.INSTANT,
    settles="interference volume",
    negative_control=NegativeControl(
        fixture="selftest/bad_configs.py:oversize_props",
        note="the prop tip gap cut by 2.5 mm to -0.5: the guards drawn 2.5 mm further in, into the props' tips"),
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
    title="Board screws engage the posts and stay inside the frame",
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
               f"{p['fc_screw_engagement_mm']:.1f} mm engaged (>= 3.0 needed) under a "
               f"{p['fc_grommet_h']:.1f} mm grommet, in {p['fc_stack_mm']:.1f} mm of post and grommet")
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
        fixture="selftest/bad_configs.py:no_field",
        note="the known-good design with no topology field: seats, guard arcs, posts and saddle with nothing joining them"),
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


@gate(
    id="petgasus.guard_height",
    title="Guards are low, solid bands",
    claims=["guard-height"],
    tier=Tier.INSTANT,
    settles="guard height",
    negative_control=NegativeControl(
        fixture="selftest/bad_configs.py:tall_guards",
        note="the known-good design with v0.1's 10.9 mm duct height"),
)
def guard_height(ctx: GateContext) -> Verdict:
    """The guard bands' height as built (guard_band_h_mm, petgasus._guard_band_heights):
    at points round each guard's arc, the height of the printed solid's vertical
    run that holds the prop plane, the median over them all. Read from the
    parameters (guard_z1 - guard_z0), it was 4.00 whatever was drawn: the drawn
    band once stood 0.8 mm proud of its top, and the optimiser's rim under it
    adds to its depth. The bands have no windows by construction (geometry.guards
    is a solid band)."""
    p = ctx.params
    acc = ctx.acceptance("C13")
    h = round(float(p["guard_band_h_mm"]), 2)
    return Verdict(gate="petgasus.guard_height", passed=acc.holds(h), measured=h, limit=acc.limit,
                   comparator=acc.comparator.value, units="mm",
                   detail=f"median {h:.2f} mm, tallest {p['guard_band_h_max_mm']:.2f} mm where a limb joins from "
                          f"below; drawn {p['guard_z0']:.1f} to {p['guard_z1']:.1f} mm, {p['guard_wall']:.1f} mm wall, "
                          f"round a {2 * p['prop_r']:.0f} mm prop at {p['prop_z']:.1f} mm; the frame's top at "
                          f"{p['frame_top_z']:.2f} mm")


@gate(
    id="petgasus.prop_blockage",
    title="The frame blocks little of each prop's downwash",
    claims=["downwash"],
    tier=Tier.INSTANT,
    settles="prop disc blockage",
    negative_control=NegativeControl(
        fixture="selftest/bad_configs.py:fat_limbs",
        note="the known-good field drawn at density 0.15: every limb fattens, and those under the props fill the discs"),
)
def prop_blockage(ctx: GateContext) -> Verdict:
    """The frame's shadow, seen from above, over the worst prop's disc outside the
    motor's own shadow (build(): the frame cut by that annulus, projected)."""
    p = ctx.params
    acc = ctx.acceptance("C14")
    b = round(float(p["prop_blockage_frac"]), 4)
    return Verdict(gate="petgasus.prop_blockage", passed=acc.holds(b), measured=b, limit=acc.limit,
                   comparator=acc.comparator.value, units="ratio",
                   detail=f"{b:.1%} of the worst disc covered (annulus outside the motor's "
                          f"{p['motor_body_d']:.0f} mm bell)")


@gate(
    id="petgasus.topology_current",
    title="The frame is drawn from a field computed for this design",
    claims=["topology-current"],
    tier=Tier.INSTANT,
    settles="topology proposal current",
    negative_control=NegativeControl(
        fixture="selftest/bad_configs.py:moved_motors",
        note="the known-good field with the guards moved 1 mm out: the field was computed for other keep-outs"),
)
def topology_current(ctx: GateContext) -> Verdict:
    """Method rule 6, agreement across representations: the proposal's recorded
    problem hash against the problem this design poses (model/topopt3d.py). A
    field computed for other seats, hoops, keep-outs or loads puts limbs where
    the design no longer wants them, and nothing else would notice."""
    p = ctx.params
    acc = ctx.acceptance("C17")
    current = 1 if p["topology_current"] else 0
    return Verdict(gate="petgasus.topology_current", passed=acc.holds(current), measured=current,
                   limit=acc.limit, comparator=acc.comparator.value, units="bool",
                   detail=(f"field {p['topology_field'] or '(none)'} "
                           + ("was computed for this problem" if current else
                              f"was NOT computed for this problem ({p['problem_hash']}): re-run fea.topopt3d")))
