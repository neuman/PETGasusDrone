"""petgasus.py — the model: a no-solder, 3D-printed, 1S ducted micro drone.

Built by an adult and a 10-year-old together. Flown line-of-sight first (no
camera), in angle mode, indoors and in a calm back yard. Electronics are bought
(no soldering: the motors plug into the flight controller, and the battery lead
is pre-attached); the one-piece frame is printed in PETG on a
Snapmaker U1.

This file is the single source of truth (METHOD rule 1). Every printed mesh, every
mass, thrust and clearance figure, and every number a gate judges is derived from
`Config` in `build()`. Every Config field carries its reason in its docstring;
what was tried and lost is in PARAMS.

Frame: millimetres, grams, seconds. +x forward, +y left, +z up; origin on the bed
at the frame centre (z=0 is the underside of the base plate).
"""
from __future__ import annotations

import hashlib
import json
import math
import os
from dataclasses import asdict, dataclass

_HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(_HERE)

PETG = {
    "density_g_mm3": 1.27e-3,
    "E_mpa": 1800.0,
    "yield_mpa": 30.0,
    # Conservative FDM modulus, not the 2000-2200 MPa coupon value: a printed arm
    # is beads and bonds, and the bonds are the soft part. The bracket reference
    # model and the fdm-print pack use the same figure.
}

G = 9.80665


@dataclass
class Config:
    """Every input. Nothing outside this dataclass is an input."""

    # --- bought parts (each grounded by a datasheet / listing; see inputs/) ---
    motor_mass_g: float = 2.85
    """g per motor, BetaFPV 1102 21000KV (2026) - the motors in the Meteor75 Pro II
    kit (vendor listing). JST1.25 3-pin plug: they plug into the AIO, no solder."""

    motor_body_d: float = 14.0
    """mm, envelope of the 1102 bell for the seat and clearance checks. The
    listing's '11 mm' is the stator; the bell is wider. ASSUMPTION until one is
    measured with calipers (claim A3 / P4)."""

    motor_h: float = 13.8
    """mm, 1102 (2026) base to shaft tip (listing)."""

    motor_hole_circle_d: float = 6.6
    """mm, 1102 mount: 3 x M1.4 on a 6.6 mm circle (vendor). Shared by most
    08xx/10xx/11xx whoop motors, so the frame takes other motors later."""

    motor_screw_clear_d: float = 1.7
    """mm, clearance for M1.4. 1.5 is the nominal free fit; FDM holes print about
    0.1-0.2 mm small, and a screw that has to be forced through cracks a 1.8 mm seat."""

    motor_screw_len: float = 3.0
    """mm, the M1.4 x 3 screws that come with the motors."""

    motor_centre_relief_d: float = 2.3
    """mm, hole under the motor for the shaft end and its C-clip. Sized by the seat,
    not the clip: the screw holes' inner edges sit 2.45 mm from the centre, and 2.3
    leaves a 1.3 mm web (3 beads, cad.wall_thickness). 3.5 lost: a 0.70 mm web.
    The clip's real size is part of A3 - if it does not clear, open the hole with a
    3 mm drill and expect C7 to flag the thinner web."""

    motor_kv: float = 21000.0
    """rpm/V, the kit's 1102 21000KV (2026)."""

    motor_thrust_max_g: float = 46.3
    """g per motor, full throttle, 1S: BetaFPV's published test of the 1102
    22000KV on a GF-1635 40 mm 3-blade. The 2026 21000KV has no published test;
    this sibling's 40 mm figure is used as a FLOOR for the kit's 45 mm props
    (a bigger disc on the same motor makes more static thrust)."""

    motor_thrust_test_v: float = 4.2
    """V of that thrust test. NOT STATED by the vendor - ASSUMPTION A6. If
    the test was at 3.7 V the real margin is ~30% better than modelled."""

    prop_d: float = 45.0
    """mm, Gemfan 1811 3-blade, 1.5 mm shaft: the props that come in the kit.
    40 mm lost: it needs a separate purchase and gives up disc area."""

    prop_mass_g: float = 0.32
    """g per prop, GF 1811 (vendor)."""

    prop_hub_drop: float = 2.5
    """mm, prop plane below the motor's top: the hub presses down onto the shaft."""

    fc_mass_g: float = 4.2
    """g, BetaFPV Matrix 1S 3-in-1 (FC + 12 A ESC + ELRS receiver), with its
    BT2.0 lead (vendor). No video transmitter: nothing to license or burn out."""

    fc_hole_spacing: float = 25.5
    """mm, Matrix 1S 3IN1 square mounting pattern (vendor: 25.5 x 25.5)."""

    fc_board_side: float = 30.0
    """mm, PCB edge, square. ASSUMPTION A4: not published; whoop boards on a
    25.5 pattern run 28-30 mm. Measure before printing."""

    fc_pcb_t: float = 1.0
    """mm, AIO board thickness, for the screw stack."""

    fc_top_components_h: float = 2.0
    """mm, tallest part on the AIO's top face; only the envelope uses it."""

    battery_mass_g: float = 8.2
    """g, BetaFPV LAVA II 1S 320 mAh LiHV, BT2.0 (vendor; Amazon B0GJSTMT8J, 5-pack)."""

    battery_l: float = 64.0
    """mm, LAVA II 320 (vendor 64 x 10 x 6)."""
    battery_w: float = 10.0
    """mm."""
    battery_h: float = 6.0
    """mm."""

    battery_mah: float = 320.0
    """mAh. 480 mAh lost: 4.4 g heavier, thrust-to-weight 2.85 against C1's
    3.0 - it still fits the strap (strap_bay_w) for longer, gentler flights."""
    battery_v_nom: float = 3.8
    """V, LiHV nominal (4.35 V full)."""

    misc_mass_g: float = 2.0
    """g, screws, strap, the FC antenna and wire. A guess with a margin in it."""

    # --- the frame ---
    plate_t: float = 1.8
    """mm, base plate, arms and motor seats. 9 layers at 0.2: three solid top and
    bottom layers either side of a core. The motor's own M1.4 x 3 screws must
    still reach 1 mm into the motor through it (claim C9)."""

    arm_w: float = 5.0
    """mm, arm width at plate level."""

    rib_w: float = 1.3
    """mm, the stiffening rib along each arm: 3 beads of 0.42."""

    rib_h: float = 3.0
    """mm above the plate. Stiffness goes as h^3, so this rib is most of the arm's
    bending stiffness; it stops below the motor seat so it never meets a prop."""

    spoke_w: float = 2.0
    """mm, flat flange under each spoke's rib (5 beads). The rib carries the
    bending; 2.5 lost: 0.3 g for nothing the FE could see."""

    prop_tip_gap: float = 1.0
    """mm, radial gap prop tip to duct wall. Under ~0.75 a 1 mm print error or a
    bent prop strikes; over ~2 the duct stops helping thrust."""

    duct_wall: float = 1.3
    """mm, 3 beads at 0.42 mm: the fdm min-wall rule."""

    duct_above_prop: float = 1.0
    """mm of duct above the prop plane: the lip that fingers and furniture meet
    before the tips. 3.0, 2.0 and 1.5 lost: 0.8, 0.5 and 0.25 g for no safety a kid
    would notice - the ring around the tips is the guard."""

    duct_lattice: bool = True
    """Below the prop band the duct wall is a 45-degree diamond lattice. A solid
    wall made the ducts ~14 g, over half the frame (see PARAMS)."""

    lattice_overhang_deg: float = 40.0
    """Steepest lattice window edge, degrees from vertical: 5 under the 45 deg
    no-support rule, so slicer rounding never lands a face on the wrong side of it."""

    lattice_above_members: bool = False
    """Start the lattice above the tallest member that joins the duct, instead of
    above the plate with solid patches where members join."""

    joint_margin: float = 0.4
    """mm of solid duct wall kept either side of a spoke or web where it joins the
    duct (no window there). One strut width (1.3) lost: 0.9 g of extra wall."""

    lattice_margin: float = 0.4
    """mm of solid wall between the plate's top face and the lattice (2 layers)."""

    lattice_strut_w: float = 1.3
    """mm, lattice strut width square to the strut: 3 beads, same rule as the wall."""

    duct_band_below_prop: float = 2.0
    """mm of solid duct wall below the prop plane, where the tips run (the
    sweep is +-1.5 mm). 3.0 lost: 0.7 g, which put thrust-to-weight under 3.0 once the
    lattice's flat-ceiling half-cells were taken out."""

    foot_w: float = 1.3
    """mm, flange at each duct's foot. Equal to the wall, i.e. no flange: a
    5 mm brim does the bed-adhesion job and is snipped off; a flange stays and weighs."""

    web_h: float = 6.0
    """mm, height of the wall joining neighbouring ducts. The cheapest stiffness
    in the frame: 4.0 -> 6.0 took the first mode from 213 to 283 Hz for 0.12 g, because
    the duct ring IS the structure in the spoked layout."""

    fc_yaw_deg: float = 45.0
    """The AIO is mounted turned 45 degrees so its corners point between the ducts
    rather than into them; that is worth ~6 mm of wheelbase. Betaflight then needs
    board alignment yaw = 45 (build guide step, physical claim P3)."""

    fc_post_od: float = 3.8
    """mm, printed posts the AIO sits on. 3.6 lost: 1.25 mm of wall round the 1.1 mm
    pilot, under the 1.26 mm process minimum (cad.wall_thickness)."""

    hub_t: float = 1.4
    """mm, the hub plate under the AIO: 7 layers at 0.2. It carries the battery
    strap and shields the board, not the arm loads. 1.2 lost: under the 1.26 mm
    process minimum (cad.wall_thickness), and 1.3 is not a whole number of layers."""

    min_member_w: float = 1.6
    """mm, narrowest optimised member that gets printed (4 beads). Narrower ones
    are removed from the extracted outline, not printed as threads. 2.0 lost: at
    the hub-excluded budget the optimiser's deep members are ~1.5 mm blades, and
    the open deleted them - seats came loose, first mode 7 Hz."""

    hub_holes: bool = True
    """Four triangular lightening holes in the hub, clear of the strap and posts."""

    hub_hole_margin: float = 2.5
    """mm of hub plate kept round each lightening hole (bars to the posts, strap
    path, rim). 3.0 lost: 0.1 g, after phasing the duct lattice for the wire ports
    cost 0.26 g."""

    hub_margin: float = 1.2
    """mm of plate around each FC post in the hub outline. 1.5 lost: 0.1 g
    the strap and the posts did not need."""

    fc_post_h: float = 4.5
    """mm above the plate. The battery strap runs over the hub UNDER the AIO, so
    this is strap_t plus 3 mm for the AIO's bottom-side parts. 3.0 lost: it left
    1.5 mm, and the strap would press on the ESC's FETs."""

    fc_pilot_d: float = 1.1
    """mm, pilot for an M1.4 screw threading into PETG."""

    fc_screw_len: float = 6.0
    """mm, M1.4 x 6 screws down through the AIO into the posts (claim C8)."""

    fc_board_clear: float = 1.0
    """mm minimum between the AIO's edge and any duct wall, in plan."""

    strap_t: float = 1.5
    """mm, thickness of a hook-and-loop strap where it laps over the hub."""
    strap_w: float = 10.0
    """mm, a 10 mm hook-and-loop battery strap."""

    strap_bay_w: float = 16.0
    """mm between the strap slots' inner edges: the widest pack the strap straddles
    (LAVA II 480 is 15.5 wide), so the 320 and the 480 both fit."""

    strap_slot_w: float = 2.2
    """mm, slot across the strap's thickness: 1.5 strap + print shrink + fumbling."""

    # --- bought-part shapes, for the assembly view and the clearance check ---
    # Listing values where one is published; otherwise a stated envelope.
    motor_base_d: float = 11.0
    """mm, the 1102's stator mount/base (listing: '11 mm', the stator size)."""
    motor_base_h: float = 2.0
    """mm, base height below the bell. Envelope (A3)."""
    shaft_d: float = 1.5
    """mm, 1102 shaft (listing)."""
    shaft_exposed: float = 5.0
    """mm of shaft above the bell (listing: shaft length 5 mm)."""
    motor_lead_len: float = 37.0
    """mm, the 1102 (2026)'s lead to its plug (listing: 37 mm cable)."""
    lead_d: float = 1.2
    """mm, a motor lead's 3 x 30 AWG wires bundled."""
    prop_hub_d: float = 5.0
    prop_blades: int = 3
    prop_chord: float = 6.0
    prop_blade_t: float = 0.8
    prop_pitch_deg: float = 12.0
    """GF 1811 3-blade, drawn: hub, three flat pitched blades. Shape for the view;
    the clearance it is checked for is its swept disc and the blade corners."""
    fc_hole_d: float = 1.6
    """mm, the AIO's mounting holes (M1.4 clearance). Assumed."""
    socket_w: float = 4.5
    socket_depth: float = 3.0
    socket_h: float = 2.5
    """mm, a JST 1.25 3-pin motor socket on the AIO's top face, at the edge facing
    its motor. Position assumed; P4 checks the board that arrives."""
    screw_d: float = 1.4
    screw_head_d: float = 2.6
    screw_head_h: float = 0.8
    """mm, M1.4 pan-head screws."""
    bt20_len: float = 6.5
    bt20_w: float = 5.0
    bt20_h: float = 4.0
    """mm, one half of a BT2.0 plug pair."""

    # --- the printer and the process ---
    bed_x_mm: float = 270.0
    """mm, Snapmaker U1 build plate X (user: 270 mm bed)."""
    bed_y_mm: float = 270.0
    """mm, Snapmaker U1 build plate Y."""
    bed_z_mm: float = 270.0
    """Snapmaker U1 build volume (user: 270 mm bed)."""

    brim_mm: float = 5.0
    """mm of brim per side: the duct rims touch the bed on a 1.3 mm wall; a brim
    keeps them down and is snipped off."""
    nozzle_d_mm: float = 0.4
    """mm, the U1's stock nozzle."""
    extrusion_width_mm: float = 0.42
    """mm, 1.05 x nozzle - a stock profile's line width; 3 of them is the wall rule."""
    layer_height_mm: float = 0.2
    """mm, 0.2: half the nozzle, the PETG default; plate_t and hub_t are whole layers."""
    perimeters: int = 3
    """Wall loops. Every thin wall here is designed as exactly 3 of them."""
    infill_fraction: float = 1.0
    """Thin walls everywhere: there is no room for infill; treat as solid."""
    print_speed_mm_s: float = 60.0
    """mm/s nominal; an ordinary PETG speed (the estimate derates it)."""
    max_print_time_h: float = 3.0
    """An afternoon with a 10-year-old: a print that runs overnight is a print he
    does not see."""
    max_filament_g: float = 1000.0
    """g, one spool: the frame uses ~2% of it."""

    # --- flight ---
    duct_thrust_factor: float = 0.9
    """Static thrust with the duct relative to the open-prop test. Tight ducts can
    add 10-20%; a printed duct with a 1 mm gap and no shaped lip is assumed to
    cost 10% instead. ASSUMPTION (A1)."""

    hover_eff_g_per_w: float = 3.0
    """g of thrust per electrical watt at hover. ASSUMPTION (A2): typical of 0802
    class motors on 40 mm props; refine from a blackbox log of a real hover."""

    usable_capacity_frac: float = 0.8
    """Land at ~3.5 V/cell: 80% of rated capacity, kinder to cheap 1S packs."""

    # --- topology optimisation of the plate layout (model/topopt.py) ---
    plate_layout: str = "spoked"
    """'arms' = the hand-drawn first layout (hub-to-motor arms, 3 flat spokes);
    'spoked' = the layout the topology optimiser found (see geometry.members and
    tools/run_topopt.py). 'arms' lost: first mode ~160 Hz against C4's 200."""

    spoke_count: int = 4
    """Spokes per motor seat. The optimiser drew 5; 5 lost: 0.6 g more for a
    thrust-to-weight of 3.025 - no margin on C1. 3 lost: crash stiffness 0.85-1.18x the
    hand-drawn frame's."""

    spoke_phase_deg: float = 45.0
    """Angle of the first spoke from the seat-to-centre direction. 45 (spokes
    on the diagonals of the seat) lost nothing; 0 (one spoke straight at the hub, one
    straight out) gave the same mode and half the crash stiffness (1.0x vs 2.2x)."""

    bridge_w: float = 4.0
    """mm, flat flange under each hub-to-web bridge's rib. 6.0 lost: 0.1 g for
    4 Hz of first mode."""


    topopt_h: float = 0.75
    """mm, FE grid size. 0.5 halves the error and quadruples the run time."""

    topopt_rmin: float = 2.0
    """mm, density-filter radius: the optimiser's length scale. 1.6 lost: with
    projection it drew members under 1 mm wide."""

    prop_block_mm: float = 3.6
    """mm of equivalent depth charged per mm^2 of plate under a prop, on top of its
    mass: blocking downwash costs like 2 x plate_t of material. Replaced
    'prop_area_cost = 3' (a multiplier on mass), which starved every spoke."""

    bounce_g: float = 1.0
    """g of vertical acceleration on the fixed masses for the bending load case.
    The problem is linear, so the value only scales compliance; 1 g keeps it readable."""

    crash_load_n: float = 20.0
    """N, a hit on a duct rim (in-plane). ~ the quad at 4 m/s stopping in ~10 ms."""

    topopt_w_thrust: float = 1.0
    """Objective weight on bounce stiffness (the vibration mode); see topopt_w_crash."""
    topopt_w_crash: float = 4.0
    """Objective weights: bounce stiffness (the vibration mode) vs. crash stiffness.
    2:1 for bounce lost: mode 434 Hz but crash stiffness fell to 0.31x the hand-drawn
    frame's, and a 10-year-old's drone is mostly a crash-test article."""

    topopt_iters: int = 120
    """Optimiser iterations: 20 per projection-sharpness step (beta 1..16), then
    until it stops moving."""

    topopt_member_h: float = 4.8
    """mm, height of an optimised member: plate_t + rib_h, the baseline rib's
    height, so the two layouts are compared at the same depth. A flat 1.8 mm
    optimised plate lost: bending stiffness goes as depth cubed, and the first
    run's flat layout bounced at 116 Hz against the ribbed baseline's 217."""

    member_clear: float = 1.0
    """mm a deep member keeps from the motor's base and from the AIO footprint,
    where the plate stays plate_t thin (motor seat; strap path under the board)."""

    topopt_mass_frac: float = 1.0
    """Optimised plate mass as a fraction of the baseline plate's."""

    topopt_smooth: float = 0.4
    """mm, corner rounding on the extracted outline; also deletes slivers < 0.8 mm."""

    prop_sweep_half_h: float = 1.5
    """mm, half-height of the band the prop occupies, for the clearance check."""


CONFIG = Config()


PARAMS = [
    {"name": "fc_yaw_deg", "units": "deg", "rejected": [
        {"value": "0 deg", "why": "AIO corners point into the ducts; wheelbase grows ~6 mm to clear them"}]},
    {"name": "prop_tip_gap", "units": "mm", "rejected": [
        {"value": "0.5 mm", "why": "inside one print error plus prop flex of a strike"}]},
    {"name": "duct_lattice", "units": "bool", "rejected": [
        {"value": "solid duct wall", "why": "~14 g of ducts: frame 20.5 g, thrust-to-weight 2.2"},
        {"value": "6 small diamond windows", "why": "took 0.3 g out; not worth the print time"},
        {"value": "round windows", "why": "their tops are bridges/overhangs that need support"}]},
]


# --------------------------------------------------------------------------- #
def _derive_layout(c: Config) -> dict:
    d: dict = {}
    d["prop_r"] = c.prop_d / 2
    d["duct_r_in"] = d["prop_r"] + c.prop_tip_gap
    d["duct_r_out"] = d["duct_r_in"] + c.duct_wall
    d["prop_z"] = c.plate_t + c.motor_h - c.prop_hub_drop
    d["duct_h"] = d["prop_z"] + c.duct_above_prop
    d["mount_r"] = c.motor_body_d / 2 + 0.75

    # FC posts and the board, turned by fc_yaw_deg
    yaw = math.radians(c.fc_yaw_deg)
    h = c.fc_hole_spacing / 2
    d["fc_post_xy"] = [
        (round(sx * h * math.cos(yaw) - sy * h * math.sin(yaw), 4),
         round(sx * h * math.sin(yaw) + sy * h * math.cos(yaw), 4))
        for sx, sy in ((1, 1), (1, -1), (-1, -1), (-1, 1))]

    # Motor offset a (motors at (+-a, +-a)) is DERIVED: the smallest a at which the
    # AIO board and its posts clear every duct by fc_board_clear. Board corners and
    # edge midpoints are the extreme points of a square; checking those plus the
    # posts is exact for a square against a circle centred on the diagonal.
    s = c.fc_board_side / 2
    pts = []
    for sx, sy in ((1, 1), (1, -1), (-1, -1), (-1, 1), (1, 0), (-1, 0), (0, 1), (0, -1)):
        pts.append((sx * s * math.cos(yaw) - sy * s * math.sin(yaw),
                    sx * s * math.sin(yaw) + sy * s * math.cos(yaw), c.fc_board_clear))
    for (px, py) in d["fc_post_xy"]:
        pts.append((px, py, c.fc_post_od / 2 + c.fc_board_clear))

    def worst(a):
        return min(math.hypot(px - a, py - a) - d["duct_r_out"] - r for (px, py, r) in pts)
    # an edge midpoint is not the closest point of an edge to the circle in general:
    # sample the board outline densely as well, so the answer holds for any yaw
    for k in range(400):
        t = k / 400 * 4
        side, f = int(t), t - int(t)
        corners = [(s, s), (s, -s), (-s, -s), (-s, s)]
        (x0, y0), (x1, y1) = corners[side], corners[(side + 1) % 4]
        x, y = x0 + (x1 - x0) * f, y0 + (y1 - y0) * f
        pts.append((x * math.cos(yaw) - y * math.sin(yaw), x * math.sin(yaw) + y * math.cos(yaw),
                    c.fc_board_clear))
    lo, hi = d["duct_r_out"], 200.0
    for _ in range(60):
        mid = (lo + hi) / 2
        if worst(mid) >= 0:
            hi = mid
        else:
            lo = mid
    d["motor_offset"] = round(hi + 0.05, 2)
    d["fc_duct_clearance_mm"] = round(worst(d["motor_offset"]) + c.fc_board_clear, 3)
    d["wheelbase_mm"] = round(2 * math.sqrt(2) * d["motor_offset"], 2)
    d["duct_gap_mm"] = round(2 * d["motor_offset"] - 2 * d["duct_r_out"], 2)

    # rib stops at the motor seat's edge
    arm_len = math.sqrt(2) * d["motor_offset"]
    d["rib_end_frac"] = (arm_len - d["mount_r"]) / arm_len

    # arm section (plate strip + rib, parallel axis) - the arm's bending stiffness
    A1, z1 = c.arm_w * c.plate_t, c.plate_t / 2
    A2, z2 = c.rib_w * c.rib_h, c.plate_t + c.rib_h / 2
    zc = (A1 * z1 + A2 * z2) / (A1 + A2)
    d["arm_I_mm4"] = round(c.arm_w * c.plate_t ** 3 / 12 + A1 * (z1 - zc) ** 2
                           + c.rib_w * c.rib_h ** 3 / 12 + A2 * (z2 - zc) ** 2, 4)
    d["arm_area_mm2"] = A1 + A2
    d["arm_zc"] = zc
    d["strap_slot_y"] = round(c.strap_bay_w / 2 + c.strap_slot_w / 2, 2)
    d["strap_slot_len"] = c.strap_w + 1.0
    return d


def _mesh_props(man) -> dict:
    mesh = man.to_mesh()
    import numpy as np
    v = np.asarray(mesh.vert_properties)[:, :3]
    lo, hi = v.min(axis=0), v.max(axis=0)
    return {"volume_mm3": round(man.volume(), 2), "area_mm2": round(man.surface_area(), 2),
            "bbox_mm": [round(float(x), 3) for x in (hi - lo)], "lo": [float(x) for x in lo]}


def _write_if_changed(path, data: bytes):
    """Content-addressed write: rebuilding an unchanged design leaves the file alone."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if not (os.path.exists(path) and open(path, "rb").read() == data):
        with open(path, "wb") as fh:
            fh.write(data)


def _threemf(v, t) -> bytes:
    """A minimal 3MF (core spec): one object, millimetres. Written by hand because
    the library writer needs networkx; the vertex and triangle arrays are the same
    ones the PLY the gates read is written from."""
    import io
    import zipfile
    verts = "".join(f'<vertex x="{x:.6f}" y="{y:.6f}" z="{z:.6f}"/>' for x, y, z in v)
    tris = "".join(f'<triangle v1="{a}" v2="{b}" v3="{c}"/>' for a, b, c in t)
    model = ('<?xml version="1.0" encoding="UTF-8"?>'
             '<model unit="millimeter" xml:lang="en-US" '
             'xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02">'
             '<resources><object id="1" type="model" name="petgasus-frame"><mesh>'
             f'<vertices>{verts}</vertices><triangles>{tris}</triangles>'
             '</mesh></object></resources><build><item objectid="1"/></build></model>')
    ct = ('<?xml version="1.0" encoding="UTF-8"?>'
          '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
          '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
          '<Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>'
          '</Types>')
    rels = ('<?xml version="1.0" encoding="UTF-8"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Target="/3D/3dmodel.model" Id="rel0" '
            'Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/></Relationships>')
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for name, body in (("[Content_Types].xml", ct), ("_rels/.rels", rels), ("3D/3dmodel.model", model)):
            info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))   # deterministic bytes
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, body)
    return buf.getvalue()


def _write_meshes(man, stem):
    """Write `stem`.ply (indexed, double - what the gates read), .3mf (for the
    slicer) and .stl (for anything else), all from ONE vertex/triangle array.

    STL alone was tried: it stores float32 coordinates with no shared vertices, so
    a reader must weld by position, and vertices 1e-4 mm apart welded into 8
    non-manifold edges on a mesh that was a clean manifold (cad.watertight)."""
    import numpy as np
    import trimesh
    mesh = man.to_mesh()
    v = np.asarray(mesh.vert_properties)[:, :3].astype(np.float64)
    t = np.asarray(mesh.tri_verts)
    tm = trimesh.Trimesh(vertices=v, faces=t, process=False)
    _write_if_changed(stem + ".ply", tm.export(file_type="ply", encoding="binary"))
    _write_if_changed(stem + ".3mf", _threemf(v, t))
    _write_if_changed(stem + ".stl", tm.export(file_type="stl"))


def _write_assembly(items):
    """build/assembly/<part>.ply, one per placed part, in assembly coordinates.
    Parts no longer in the model are removed so the view never shows a ghost."""
    import numpy as np
    import trimesh
    folder = os.path.join(ROOT, "build", "assembly")
    os.makedirs(folder, exist_ok=True)
    for name, it in items.items():
        mesh = it["solid"].to_mesh()
        tm = trimesh.Trimesh(np.asarray(mesh.vert_properties)[:, :3].astype(np.float64),
                             np.asarray(mesh.tri_verts), process=False)
        _write_if_changed(os.path.join(folder, name + ".ply"), tm.export(file_type="ply", encoding="binary"))
    for f in os.listdir(folder):
        if f.endswith(".ply") and f[:-4] not in items:
            os.remove(os.path.join(folder, f))


def build(config: Config | None = None, write_meshes: bool = True) -> dict:
    """Resolve every derived quantity, and (by default) export the print meshes.

    Writing build/print/*.stl here is a recorded decision (decisions/build-writes-the-print-meshes):
    the mesh gates read files, and generating them in the same call that computes
    their volumes is the one way the numbers and the files cannot disagree.
    """
    c = config or CONFIG
    import geometry_petgasus as geo  # noqa: E402  (sibling module, see _load below)

    import topopt_petgasus as to  # noqa: E402

    d = _derive_layout(c)
    d["fc_post_xy"] = [list(p) for p in d["fc_post_xy"]]

    # --- plate FE: the live layout and the hand-drawn one, same model ---
    g, reg, fe = to.setup(c, d)
    rho, tb, ta = to.layout_density(c, d, g, reg, geo.members(c, d))
    modes = to.modal(c, d, g, reg, fe, rho, tb, ta)
    comp = to.evaluate(c, d, g, reg, fe, rho, tb, ta)
    plate_mass = to.plate_mass_g(g, reg, rho, ta)
    rho_b, tb_b, ta_b = to.baseline_density(c, d, g, reg)
    base_mass = to.plate_mass_g(g, reg, rho_b, ta_b)
    topo = {}
    if c.plate_layout != "arms":
        comp_b = to.evaluate(c, d, g, reg, fe, rho_b, tb_b, ta_b)
        topo = {
            "arms_mode1_hz": round(to.modal(c, d, g, reg, fe, rho_b, tb_b, ta_b)[0], 1),
            "bounce_stiffness_gain": round(comp_b[0] / comp[0], 3),
            "crash_stiffness_gain": round((comp_b[1] + comp_b[2]) / (comp[1] + comp[2]), 3),
        }

    frame = geo.frame(c, d)
    fp = _mesh_props(frame)
    pieces = len(frame.decompose())

    # every part of the assembly against every other: only the declared threaded /
    # plugged / soldered joints may share material (assembly.ALLOWED_OVERLAPS)
    import assembly_petgasus as asm
    items, leads_needed = asm.parts(c, d, frame)
    interference = asm.interferences(items)
    lead_spare = min(c.motor_lead_len - v for v in leads_needed.values())

    # --- masses ---
    frame_g = fp["volume_mm3"] * PETG["density_g_mm3"]
    auw = (frame_g + 4 * c.motor_mass_g + 4 * c.prop_mass_g + c.fc_mass_g
           + c.battery_mass_g + c.misc_mass_g)

    # --- thrust ---
    # Thrust at fixed throttle goes ~ V^2 for a fixed prop (rpm ~ V, thrust ~ rpm^2),
    # so a test at 4.2 V is derated to the pack's nominal 3.7 V: that is the voltage
    # the pilot has for most of the flight, not the first ten seconds.
    v_factor = (c.battery_v_nom / c.motor_thrust_test_v) ** 2
    thrust_total = 4 * c.motor_thrust_max_g * v_factor * c.duct_thrust_factor
    t_w = thrust_total / auw
    hover_throttle_frac = 1 / t_w

    # --- flight time ---
    hover_w = auw / c.hover_eff_g_per_w
    energy_wh = c.battery_mah / 1000 * c.battery_v_nom * c.usable_capacity_frac
    flight_min = energy_wh / hover_w * 60

    # --- motor rotation frequency, for reading the frame modes against ---
    # Full-throttle loaded rpm ~ 80% of KV x full-charge voltage; at hover thrust ~
    # rpm^2, so rpm_hover = rpm_full * sqrt(hover thrust / full thrust). (A cantilever
    # estimate of the arm used to live here: it left the duct's own mass off the arm
    # and read 452 Hz where the FE with the ducts on says ~190 Hz - see C4.)
    f_motor = 0.8 * c.motor_kv * 4.2 / 60
    thrust_full_v = 4 * c.motor_thrust_max_g * (4.2 / c.motor_thrust_test_v) ** 2 * c.duct_thrust_factor
    f_motor_hover = f_motor * math.sqrt(min(1.0, auw / thrust_full_v))

    # arm geometry for the stress estimate below
    hub_edge = max(math.hypot(*p) for p in d["fc_post_xy"]) + c.fc_post_od / 2
    L = math.sqrt(2) * d["motor_offset"] - hub_edge
    I, zc = d["arm_I_mm4"], d["arm_zc"]                                     # mm^4, mm

    # --- arm root stress at full thrust, for fdm.layer_alignment ---
    # Full static thrust of one motor at the arm tip, x2 for the jolt of a hard
    # throttle punch. Bending stress runs ALONG the arm, in the layer plane.
    f_tip = c.motor_thrust_max_g / 1000 * G * 2.0                          # N
    z_far = max(zc, c.plate_t + c.rib_h - zc)
    sigma = f_tip * L * z_far / I                                           # MPa
    util = sigma / (PETG["yield_mpa"] / 2.0)

    # --- screw stacks ---
    fc_stack = c.fc_pcb_t + c.fc_post_h + c.plate_t
    engagement = c.fc_screw_len - c.fc_pcb_t
    motor_screw_engage = c.motor_screw_len - c.plate_t

    meshes = {"frame": "build/print/frame.ply"}
    if write_meshes:
        _write_meshes(frame, os.path.join(ROOT, "build", "print", "frame"))
        _write_assembly(items)

    design_hash = hashlib.sha256(json.dumps(asdict(c), sort_keys=True).encode()).hexdigest()[:12]

    out = {
        **{k2: v for k2, v in d.items()},
        "frame_mass_g": round(frame_g, 2),
        "auw_g": round(auw, 2),
        "thrust_total_g": round(thrust_total, 1),
        "thrust_to_weight": round(t_w, 3),
        "hover_throttle_frac": round(hover_throttle_frac, 3),
        "hover_power_w": round(hover_w, 2),
        "flight_time_min": round(flight_min, 2),
        "frame_mode1_hz": round(modes[0], 1),
        "frame_modes_hz": [round(x, 1) for x in modes],
        "bounce_compliance_nmm": round(comp[0], 6),
        "crash_compliance_nmm": round(comp[1] + comp[2], 3),
        "plate_mass_fe_g": round(plate_mass, 3),
        "arms_plate_mass_fe_g": round(base_mass, 3),
        **topo,
        "arm_len_mm": round(L, 2),
        "motor_freq_full_hz": round(f_motor, 1),
        "motor_freq_hover_hz": round(f_motor_hover, 1),
        "fc_stack_mm": round(fc_stack, 2),
        "fc_screw_engagement_mm": round(engagement, 2),
        "fc_screw_protrusion_mm": round(c.fc_screw_len - fc_stack, 2),
        "motor_screw_engagement_mm": round(motor_screw_engage, 2),
        "frame_pieces": pieces,
        "interference_mm3": interference,
        "interference_total_mm3": round(sum(interference.values()), 3),
        "motor_lead_needed_mm": {k: round(v, 1) for k, v in leads_needed.items()},
        "motor_lead_spare_mm": round(lead_spare, 2),
        "assembly_parts": {n: {"path": f"build/assembly/{n}.ply", "color": list(it["color"]),
                               "explode": list(it["explode"]), "group": it["group"], "step": it["step"]}
                           for n, it in sorted(items.items())},
        "layout_2d": _layout_2d(c, d),
        "topopt_field": _topopt_field(c, d, g, reg, rho_b, ta_b),
        "arm_root_stress_mpa": round(sigma, 2),
        "frame_bbox_mm": fp["bbox_mm"],
        "design_hash": design_hash,
        # --- fdm-print keys: the set, and the largest part as the single-part view ---
        "mesh_paths": meshes,
        "bbox_by_part_mm": {"frame": fp["bbox_mm"]},
        "fdm.part_bbox_mm": fp["bbox_mm"],
        "fdm.part_volume_mm3": fp["volume_mm3"],
        "surface_area_mm2": fp["area_mm2"],
        "fdm.part_min_wall_mm": min(c.duct_wall, c.rib_w, c.plate_t),
        "mesh_path": meshes["frame"],
        "meshes": dict(meshes),
        "build_axis": "z",
        "cad.process_min_wall_mm": round(c.perimeters * c.extrusion_width_mm, 3),
        "load_axis": "x",
        "bom_path": "bom/bom.json",
        "utilisation": round(util, 3),
        "utilisation_kind": "stress",
    }
    return out


def _layout_2d(c, d):
    """Top-view outlines of BOTH plate layouts and the fixed parts, for the site's
    side-by-side comparison. Straight from geometry.members - nothing redrawn."""
    import dataclasses
    import geometry_petgasus as geo

    def mems(layout):
        return [{"p0": list(m["p0"]), "p1": list(m["p1"]), "w": m["w"],
                 "rib": [list(m["rib"][0]), list(m["rib"][1])] if m["rib"] else None}
                for m in geo.members(dataclasses.replace(c, plate_layout=layout), d)]
    return {
        "arms": mems("arms"), "spoked": mems("spoked"),
        "motors": [list(p) for p in geo.motor_centres(d)],
        "duct_r_in": d["duct_r_in"], "duct_r_out": d["duct_r_out"], "mount_r": d["mount_r"],
        "motor_offset": d["motor_offset"], "posts": d["fc_post_xy"],
        "post_r": c.fc_post_od / 2 + c.hub_margin, "rib_w": c.rib_w,
        "hub_outline": [[[round(x, 2), round(y, 2)] for (x, y) in poly]
                        for poly in geo._hub_cs(c, d).to_polygons()],
    }


def _topopt_field(c, d, g, reg, rho_b, ta_b):
    """The optimiser's density field for THESE inputs, if it has been run (it is
    never run from build(): five minutes is not a tier-0 cost). Downsampled 2x for
    the site. None when tools/run_topopt.py has not been run for this design."""
    import numpy as np
    import topopt_petgasus as to
    wcost = to.weight_cost(c, reg, ta_b)
    dom = reg["domain"]
    budget = float((rho_b[dom] * wcost[dom]).sum() * g.h * g.h) * c.topopt_mass_frac
    path = os.path.join(ROOT, "build", "topopt", f"{to.input_hash(c, d, round(budget, 3))}.npz")
    if not os.path.exists(path):
        return None
    rho = np.load(path)["rho"].reshape(g.n, g.n)
    n2 = g.n // 2
    small = rho[: n2 * 2, : n2 * 2].reshape(n2, 2, n2, 2).mean(axis=(1, 3))
    return {"n": n2, "half": g.half, "rho": [round(float(v), 2) for v in small.ravel()]}


def _topopt_cached(c, d, g, reg, fe, rho_b, ta_b):
    """Run (or reload) the optimiser at topopt_mass_frac of the baseline plate's mass.

    The budget is the baseline's designable plate volume, prop-weighted, so at
    topopt_mass_frac = 1 the comparison is at equal grams. Cached by a hash of
    every input and of topopt.py's source.
    """
    import numpy as np
    import topopt_petgasus as to
    wcost = to.weight_cost(c, reg, ta_b)
    dom = reg["domain"]
    budget = float((rho_b[dom] * wcost[dom]).sum() * g.h * g.h) * c.topopt_mass_frac
    key = to.input_hash(c, d, round(budget, 3))
    path = os.path.join(ROOT, "build", "topopt", f"{key}.npz")
    if os.path.exists(path):
        z = np.load(path)
        return z["rho"], z["tb"], z["ta"], list(z["history"])
    rho, tb, ta, history = to.optimise(c, d, g, reg, fe, budget_vol_mm3=budget)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    np.savez_compressed(path, rho=rho, tb=tb, ta=ta, history=np.array(history))
    return rho, tb, ta, history


# the geometry and the optimiser live in sibling files; load them by path so two
# copies of this project in one process never share them
import importlib.util as _ilu  # noqa: E402
import sys as _sys  # noqa: E402

for _name, _file in (("geometry_petgasus", "geometry.py"), ("topopt_petgasus", "topopt.py"),
                     ("assembly_petgasus", "assembly.py")):
    if _name not in _sys.modules:
        _spec = _ilu.spec_from_file_location(_name, os.path.join(_HERE, _file))
        _mod = _ilu.module_from_spec(_spec)
        _spec.loader.exec_module(_mod)
        _sys.modules[_name] = _mod


if __name__ == "__main__":
    print(json.dumps(build(), indent=2, sort_keys=True))
