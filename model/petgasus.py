"""petgasus.py — the model: a no-solder, 3D-printed 1S micro drone with low prop guards.

Built by an adult and a 10-year-old together. Flown line-of-sight first (no
camera), in angle mode, indoors and in a calm back yard. Electronics are bought
(no soldering: the motors plug into the flight controller, and the battery lead
is pre-attached); the frame is printed on a Snapmaker U1.

v0.2 (2026-10-17) replaces v0.1's flat plate, tall ducts and lattice windows
after the r/diydrones review (inputs/references/diydrones-feedback-2026-10-17.md):
the frame is now the load path a 3D topology optimiser found (model/topopt3d.py
poses the problem, the solid-fea pack's fea.topopt3d solves it), drawn as one
smooth, filleted solid (model/geometry.py) around exact motor seats, FC posts
and low guard arcs, and judged by CalculiX on the printed shape (gates/structure.py).

This file is the single source of truth (METHOD rule 1). Every printed mesh, every
mass, thrust and clearance figure, and every number a gate judges is derived from
`Config` in `build()`. Every Config field carries its reason in its docstring;
what was tried and lost is in PARAMS and decisions/.

Frame: millimetres, grams, seconds. +x forward, +y left, +z up; origin at the
frame centre, z=0 the underside of the motor seats.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
from dataclasses import asdict, dataclass

_HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(_HERE)

#: Printed-material properties, from the makers' technical data sheets
#: (inputs/datasheets/filament-data-2026-10-17.md). One maker, Bambu Lab, for every
#: row, so the XY (in-layer) and Z (across-layer) figures come from one test
#: method (ISO 527, separate XY and Z specimens, 100 % infill). E in MPa, strength
#: in MPa, density g/cm^3, elongation at break %. `needs` is what the open-frame
#: Snapmaker U1 needs to print it (inputs: Snapmaker U1 specs, Bambu filament guide).
MATERIALS = {
    "PETG": dict(source="Bambu PETG HF V1.0 [B1]", density=1.28, E_xy=1810.0, E_z=1540.0,
                 uts_xy=34.0, uts_z=23.0, elong_xy=8.6, elong_z=5.1, needs=()),
    "PETG-CF": dict(source="Bambu PETG-CF V3.0 [B3]", density=1.25, E_xy=2460.0, E_z=1340.0,
                    uts_xy=35.0, uts_z=29.0, elong_xy=10.4, elong_z=4.7, needs=("hardened nozzle",)),
    "PLA": dict(source="Bambu PLA Basic V3.0 [B6]", density=1.24, E_xy=2580.0, E_z=2060.0,
                uts_xy=35.0, uts_z=31.0, elong_xy=12.2, elong_z=7.5, needs=()),
    "ASA": dict(source="Bambu ASA V3.0 [B7]", density=1.05, E_xy=2450.0, E_z=2120.0,
                uts_xy=37.0, uts_z=31.0, elong_xy=9.2, elong_z=4.6, needs=("top cover (enclosure)",)),
    "PAHT-CF": dict(source="Bambu PAHT-CF V3.0, dry [B5]", density=1.06, E_xy=3860.0, E_z=2180.0,
                    uts_xy=92.0, uts_z=47.0, elong_xy=8.4, elong_z=4.1,
                    needs=("top cover (enclosure)", "hardened nozzle", "dry at 80 C 8-12 h")),
    "PA6-CF": dict(source="Bambu PA6-CF V3.0 [B4]", density=1.09, E_xy=4430.0, E_z=2170.0,
                   uts_xy=102.0, uts_z=48.0, elong_xy=5.8, elong_z=3.7,
                   needs=("top cover (enclosure)", "hardened nozzle", "dry at 80 C 8-12 h")),
    # TPU's stiffness is Polymaker's PolyFlex TPU95 (33.6 MPa, ISO 37) [P9]: Bambu's
    # 9.8 MPa would make a TPU hoop softer, the crash force on the frame behind it
    # smaller, and the comparison kinder to TPU than the data supports.
    "TPU95A": dict(source="Bambu TPU 95A HF V1.0 [B8], modulus Polymaker PolyFlex TPU95 [P9]",
                   density=1.22, E_xy=33.6, E_z=33.6, uts_xy=27.3, uts_z=22.3, elong_xy=650.0,
                   elong_z=480.0, needs=()),
}

G = 9.80665


@dataclass
class Config:
    """Every input. Nothing outside this dataclass is an input."""

    # --- bought parts (each grounded by a datasheet / listing; see inputs/) ---
    motor_mass_g: float = 2.85
    """g per motor, BetaFPV 1102 21000KV (2026), the motors in the Meteor75 Pro II
    O4 kit (BetaFPV drawing). JST1.25 3-pin plug: they plug into the board, no solder."""

    motor_body_d: float = 14.0
    """mm, the bell's envelope for the seat and clearance checks: BetaFPV's
    drawing gives the bell as 13.8 mm; 0.2 mm is the envelope's margin."""

    motor_h: float = 13.6
    """mm, base underside to shaft tip (BetaFPV drawing: 8.6 body + 5 shaft).
    v0.1 used 13.8, which is the bell's DIAMETER on the same drawing."""

    motor_hole_circle_d: float = 6.6
    """mm, 3 x M1.4 on a 6.6 mm circle (BetaFPV drawing)."""

    motor_screw_clear_d: float = 1.7
    """mm, clearance for M1.4. 1.5 is the nominal free fit; FDM holes print about
    0.1-0.2 mm small, and a screw that has to be forced cracks the seat."""

    motor_screw_len: float = 3.0
    """mm, the kit's spare M1.4 x 3. The motor pack's own screws are M1.4 x 4: through
    a 1.8 mm seat they would put 2.2 mm into a base whose thread depth BetaFPV
    does not publish, and a screw that bottoms out presses on the stator."""

    motor_centre_relief_d: float = 2.3
    """mm, hole under the motor for the shaft end and its C-clip. The clip is
    1.6-2.1 mm across on BetaFPV's drawing (not to scale, A3); 2.3 leaves a 1.3 mm
    web to the screw holes (3 beads)."""

    motor_kv: float = 21000.0
    """rpm/V, the kit's 1102 21000KV (2026)."""

    motor_thrust_max_g: float = 66.6
    """g per motor at full throttle: BetaFPV's load table for this motor on the kit's
    GF 1811-3 prop, measured at 3.81 V. v0.1 used 46.3 g, a different motor (the
    22000KV) on a different 40 mm prop at 4.0 V."""

    motor_thrust_test_v: float = 3.81
    """V at the full-throttle row of that table (stated)."""

    motor_eff_table: tuple = ((9.6, 3.05), (16.7, 2.77), (24.8, 2.53), (34.1, 2.46),
                              (42.4, 2.31), (50.2, 2.17), (58.5, 2.06), (66.6, 1.91))
    """(thrust g, efficiency g/W) per motor, the same BetaFPV load table, 30-100 %
    throttle at 3.81-3.92 V. Hover efficiency is read off it at the hover thrust
    (it replaces v0.1's assumed 3.0 g/W, claim A2)."""

    prop_d: float = 45.0
    """mm, Gemfan 1811 3-blade, 1.5 mm shaft: the props in the kit."""

    prop_mass_g: float = 0.32
    """g per prop, GF 1811 (BetaFPV)."""

    prop_hub_h: float = 4.4
    """mm, GF 1811 hub height (BetaFPV diagram). The hub sits on the bell; the
    blades run at its mid-height."""

    fc_mass_g: float = 4.2
    """g, BetaFPV Matrix 1S 3IN1 (FC + 12 A ESC + ELRS receiver) with its BT2.0 lead
    (BetaFPV). No video transmitter: nothing to license or burn out."""

    fc_hole_spacing: float = 25.5
    """mm, the 3IN1's mounting square (BetaFPV). On this board the four holes sit at
    the tips of its cross, so they lie on the axes, 25.5/sqrt(2) from the centre."""

    fc_arm_tip_r: float = 20.0
    """mm, centre to the tip of each arm of the cross. Not published: 40 mm tip to
    tip, scaled from BetaFPV's photo against the 7 mm MCU (A4)."""

    fc_arm_w_fb: float = 10.5
    """mm, front and back arms' width, scaled the same way (A4)."""

    fc_arm_w_side: float = 13.4
    """mm, the side arms' width: they carry the four ESC sockets (scaled, A4)."""

    fc_hole_d: float = 3.6
    """mm, the board's mounting holes, sized for the rubber grommets that come
    with it (scaled, A4)."""

    fc_pcb_t: float = 1.0
    """mm, board thickness (BetaFPV)."""

    fc_top_components_h: float = 2.0
    """mm, tallest part on the board's top face (an envelope; not published)."""

    socket_x: float = 3.6
    socket_y: float = 12.3
    """mm, each ESC socket's centre: +-socket_x along the board, socket_y out along
    a side arm, two per side arm on the BOTTOM face, openings facing out (scaled
    from BetaFPV's bottom photo, A4)."""

    socket_w: float = 5.5
    socket_depth: float = 4.0
    socket_h: float = 3.0
    """mm, a JST 1.25 3-pin side-entry socket under the board (envelope)."""

    plug_l: float = 4.0
    """mm, the motor plug's body beyond the socket's mouth (envelope)."""

    fc_grommet_h: float = 2.6
    """mm, a mounting grommet's height: the board sits in its groove, 0.8 mm of
    rubber either side of the 1.0 mm board. Not published (A4)."""

    fc_grommet_below: float = 0.8
    """mm of grommet under the board, between the post top and the board."""

    fc_grommet_od: float = 4.6
    """mm, grommet's outer diameter (envelope, A4)."""

    fc_screw_len: float = 6.0
    """mm, M1.4 x 6 self-tappers from the assortment, down through the grommets into
    the posts. The board's own M1.4 x 5 leave 2.4 mm in the post, under C8's 3 mm."""

    battery_mass_g: float = 8.2
    """g, BetaFPV LAVA II 1S 320 mAh LiHV, BT2.0 (BetaFPV)."""

    battery_l: float = 64.0
    """mm, LAVA II 320 (BetaFPV 64 x 10 x 6)."""
    battery_w: float = 10.0
    """mm."""
    battery_h: float = 6.0
    """mm."""

    battery_mah: float = 320.0
    """mAh, the LAVA II 320 the BOM buys: the only pack the frame is designed for.
    480 mAh lost (v0.1): 4.4 g heavier for 50 % more energy. It no longer fits
    either: it is 15.5 mm wide, and the frame keeps clear under the hub only for
    a pack battery_w wide, with 1 mm a side (strap_bay_w)."""
    battery_v_nom: float = 3.8
    """V, LiHV nominal (4.35 V full)."""

    misc_mass_g: float = 2.0
    """g, screws, strap, grommets, the receiver's antenna and wire. A guess with a
    margin in it."""

    # --- bought-part shapes, for the assembly view and the clearance check ---
    motor_base_d: float = 11.0
    """mm, the 1102's base (listing: '11 mm', the stator size)."""
    motor_base_h: float = 2.0
    """mm, base height below the bell. Envelope (A3)."""
    shaft_d: float = 1.5
    """mm, 1102 shaft (BetaFPV drawing)."""
    shaft_exposed: float = 5.0
    """mm of shaft above the bell (BetaFPV drawing)."""
    motor_lead_len: float = 37.0
    """mm, the 1102 (2026)'s lead to its plug (BetaFPV drawing: 37 mm, 28 AWG)."""
    lead_d: float = 1.2
    """mm, a motor lead's 3 x 28 AWG wires bundled."""
    prop_hub_d: float = 6.5
    """mm, GF 1811 hub diameter, scaled from BetaFPV's diagram (not published)."""
    prop_blades: int = 3
    prop_chord: float = 8.7
    """mm, GF 1811 widest blade (BetaFPV diagram)."""
    prop_blade_t: float = 0.8
    prop_pitch_deg: float = 12.0
    """GF 1811 3-blade, drawn: hub, three flat pitched blades. Shape for the view;
    the clearance it is checked for is its swept disc."""
    screw_d: float = 1.4
    screw_head_d: float = 2.6
    screw_head_h: float = 0.8
    """mm, M1.4 pan-head screws."""
    bt20_len: float = 6.5
    bt20_w: float = 5.0
    bt20_h: float = 4.0
    """mm, one half of a BT2.0 plug pair."""

    # --- the frame ---
    material: str = "PETG"
    """The frame's filament for the everyday print, a key of MATERIALS: PETG, which
    a stock U1 prints with nothing extra. Every filament went through the same
    CalculiX checks (inputs/data/material-comparison.json); the author chose PETG
    for the casual print and nylon-CF for the strong one (strong_material)."""

    guard_material: str = "PETG"
    """The guard arcs' filament: the frame's own, so the frame prints as one part.
    A different filament would print fused to the frame from the U1's second
    head, but the split between the two is approximate (frame_solids). TPU 95A
    arcs as bumpers lost (decisions/shadow-on-the-props-capped-at-15-crash-checks-ar.json):
    in the linear model they made both crash floors worse, and a linear model
    is a poor judge of TPU."""

    strong_material: str = "PA6-CF"
    """The filament for anyone serious about crashes, and the one the crash claims
    (C15, C16) are judged in: nylon with carbon fibre. In the comparison the two
    nylon-CF filaments were the only ones to clear both crash floors, and PA6-CF
    was the stiffer. It needs a hardened nozzle, the U1's top cover and a dried
    spool. PAHT-CF did nearly as well and minds damp less."""

    strength_knockdown: float = 1.0
    """Printed strength as a fraction of the data sheet's (ISO 527 coupons, 100 %
    infill, annealed and dried). 1.0: the limbs are solid and several beads
    across; a damp spool or a cold print is the reason to lower it."""

    plate_t: float = 1.8
    """mm, motor seat: 9 layers at 0.2. The motor's M1.4 x 3 screws must still reach
    1 mm into the motor through it (claim C9)."""

    prop_tip_gap: float = 2.0
    """mm, radial gap prop tip to the exact guard arc. A hoop is a guard, not a duct:
    it gains nothing from a tight gap, and 2 mm takes a bent blade or a 1 mm print
    error. v0.1's 1.0 mm was a duct's gap. The DRAWN arc's inner face comes
    closer (frame_solids): only the prop's keep-out, prop_r + prop_clear +
    surface_clearance_mm, stops it, so as printed the gap is 1.1-1.7 mm."""

    guard_wall: float = 1.4
    """mm, the exact arc's wall: 3 beads at 0.42 plus 0.14. 1.26 (3 beads exactly)
    lost: the hoop is the part that meets the wall first. The drawn arc is
    thicker, about 2.4 mm away from the limbs (frame_solids)."""

    guard_h: float = 4.0
    """mm, hoop height, centred on the prop plane: the reviewer's 'no more than
    4 mm' (claim C13). It still spans the prop's +-1.5 mm band with 0.5 mm over.
    v0.1's 10.9 mm ducts with lattice windows lost (propwash, weight)."""

    guard_arc_deg: float = 180.0
    """deg of each prop's guard that must be solid, centred on the direction away
    from the frame's centre: the side that meets walls and furniture. The rest of
    the ring faces the other props and the body, and is the optimiser's to fill,
    bridge or leave open. The author chose outer arcs (2026-10-17) over full
    fixed hoops, which were a third of the frame's mass and set its whole look:
    the optimiser only bridged between four given circles."""

    prop_clear: float = 1.0
    """mm the frame keeps from each prop's band and from the inflow above it."""

    motor_clear: float = 0.5
    """mm the frame keeps from the motor's bell, and from the shaft's clip below."""

    screw_access_d: float = 4.0
    """mm, the clear column under each motor screw: a 2.6 mm head plus a driver."""

    fc_post_od: float = 4.6
    """mm, the posts the grommets sit on: the grommet's own diameter."""

    fc_post_h: float = 5.0
    """mm, post top above the seat's top face. The strap (1.5) runs over the hub,
    its top at hub_t + strap_t = 2.9 mm. The board sits fc_grommet_below over the
    posts and the ESC sockets hang 3.0 under it, their undersides at plate_t 1.8
    + 5.0 + 0.8 - 3.0 = 4.6 mm: 1.7 mm over the strap (4.5 would leave 1.2). An earlier sum
    left out the grommet under the board and gave 0.4 and 0.9."""

    fc_pilot_d: float = 1.1
    """mm, pilot for an M1.4 self-tapper into PETG."""

    fc_board_clear: float = 1.0
    """mm minimum between the board's outline and any guard hoop, in plan, and the
    frame's clearance round the board."""

    hub_t: float = 1.4
    """mm, the top of the hub the strap lies on: above it, inside the board's
    footprint, the frame keeps clear for the strap and the sockets."""

    strap_t: float = 1.5
    """mm, thickness of a hook-and-loop strap where it laps over the hub."""
    strap_w: float = 10.0
    """mm, a 10 mm hook-and-loop battery strap."""

    strap_bay_w: float = 16.0
    """mm between the strap slots' inner edges. Sized on the v0.1 plate for the
    LAVA II 480 (15.5 wide). The 3D frame does not take that pack: under the hub
    it keeps clear only battery_w + 2 = 12 mm (topopt3d.keepouts), and its limbs
    run below the hub beside that space, where a wider pack would hang. Only
    the 320 mAh pack the BOM buys is designed for, and C5 places only it."""

    strap_slot_w: float = 2.2
    """mm, slot across the strap's thickness: 1.5 strap + print shrink + fumbling."""

    lead_clear: float = 0.8
    """mm the frame keeps round each motor lead's and the power pigtail's path."""

    # --- the topology problem (model/topopt3d.py; solved by fea.topopt3d) ---
    topology_field: str = "inputs/data/topopt3d-petg-mid-133-d385cf32ab.npz"
    """The chosen proposal (an input under inputs/data/), whose field the frame is
    drawn from. Empty: no proposal yet, and the frame is its exact features alone."""

    topo_h: float = 4.0 / 3.0
    """mm, the optimiser's cell: the field is solved at 2 mm and refined here,
    warm-started (12 mm, the depth under the seats, is nine cells, so z = 0 stays
    a node layer). 2.0 alone lost: limbs one or two cells thick come out as
    staircases and beads. 1.0 lost: ~840k unknowns, and PARDISO's factors ran
    this 21 GB machine out of memory; 1.33 mm is ~365k, 7 GB, ~34 s an iteration."""

    topo_margin: float = 0.5
    """mm of designable space beyond the hoops' outer edge."""

    topo_below: float = 12.0
    """mm of designable space under the seats: room for the limbs to go deep
    (bending stiffness grows as depth cubed) and to carry the battery. Opened
    from 4 after the author's examples (2026-10-17), deep webs with oval
    windows; the optimiser chose to use only about 4 of it (a keel under the
    hub), the webs instead falling from the guard rim to the seats. Under the
    props its members are mostly two cells (2.7 mm) deep: the downwash cost
    (topo_prop_cost) does not reward depth over width."""

    topo_rmin: float = 3.5
    """mm, density filter radius: the optimiser's length scale, so its thinnest
    limb is ~3-4 mm. 2.6 cells at 1.33 mm (the 2 mm run it refines used 5.0, 2.5
    cells). 3.0 at 2 mm (1.5 cells) lost: the optimiser drew a web of one-cell
    limbs at a third of their density, which any surface threshold breaks into
    9-38 pieces."""

    topo_rmin_z: float = 3.5
    """mm, the filter's radius up and down: equal to topo_rmin, so the filter is
    the same in every direction. A filter longer up and down than across (3 mm
    across, 6 mm deep) was tried for deep, thin blades, stiff in bending and
    thin seen from above. It lost (decisions/shadow-on-the-props-capped-at-15-crash-checks-ar.json):
    on the 2 mm grid it drew grid-aligned bars round a square hub, in 3 pieces."""

    topo_nu: float = 0.35
    """Poisson's ratio for the optimiser (PETG 0.33-0.38; the topology barely moves)."""

    topo_design_g: float = 12.0
    """g of budget the optimiser may spend, beyond the seats, posts, guard arcs
    and saddle. The frame came out ~18 g in v0.1; with 66.6 g motors, 12 g keeps
    thrust-to-weight over 4 and the hover time over 3 minutes. The budget is
    cost-weighted (topo_prop_cost), so the plastic placed is less: the chosen
    field holds about 8330 mm^3, 10.7 g of PETG."""

    topo_prop_cost: float = 10.0
    """Steers material out of the downwash: a cell under a prop blocks flow as
    well as weighing. The extra (topo_prop_cost - 1) is divided by the number of
    designable cells in that cell's column, filled or not (topopt3d.regions), so
    every cell under a prop costs a flat 1.53-1.60 on the 1.33 mm grid (1.82-2.0
    on the 2 mm grid). That is a charge per volume, not one shadow per column: a
    wide flange and a deep web of the same volume pay the same, though the
    flange casts more shadow, and the charge changes with topo_h and topo_below
    (topopt3d: known limitations). Swept at 2 mm: 3 drew 22 % shadow, 8 drew
    15.9 %, 16 drew 11.8 %, 30 drew 8.5 % at 2.9x the compliance. 10 was chosen
    for C14's 15 %. The sweep does not carry over to the 1.33 mm grid as it is,
    and C14 judges the drawn frame's real shadow."""

    topo_thrust_factor: float = 2.0
    """Thrust load on a seat, x full static thrust: a hard throttle punch."""

    topo_crash_n: float = 20.0
    """N, the crash load on a hoop for the optimiser (a magnitude only scales its
    compliance; the CalculiX crash check uses the real impact energy)."""

    topo_battery_g: float = 20.0
    """g of deceleration on the battery, hanging on the strap, in a crash."""

    topo_crash_spread_deg: float = 75.0
    """deg either side of the guard arc's middle where it is also hit: the
    crashes land across the whole arc, not at one point."""

    topo_w_thrust: float = 2.0
    topo_w_strike: float = 1.0
    topo_w_crash: float = 0.4
    topo_w_crash_up: float = 0.3
    topo_w_crash_t: float = 0.4
    topo_w_vertical: float = 0.5
    topo_w_top: float = 0.3
    topo_w_battery: float = 0.5
    """Weights of the load cases in the objective (each compliance normalised by its
    start). Crashes weigh as much as the flight load: a 10-year-old's drone is
    mostly a crash-test article (the review: 'it will break after a couple of
    crashes'). Thrust at 2 and the two prop strikes (topo_w_strike) hold the
    motor seats: the first run, with thrust at 1 and no strikes, tied the hoops
    to the posts and left the seats on grey threads. The strikes push the seat
    in its own plane only; the tilt a strike at the prop plane also puts on it
    is not modelled (topopt3d: known limitations). The crashes come from many
    directions: straight in (topo_w_crash) and in-and-up from below
    (topo_w_crash_up) at the arc's middle and both ends, along the arc
    (topo_w_crash_t), up from below (topo_w_vertical), down from above
    (topo_w_top). In-plane hits at two points alone drew straight bars."""

    topo_patch_mm: float = 3.0
    """mm, radius of the patch of hoop a crash load lands on."""

    # --- the surface drawn from the field (geometry.drawn) ---
    surface_edge_mm: float = 0.5
    """mm, the level set's edge length. 0.4 lost: 2x the triangles, no visible change."""
    surface_blur_mm: float = 0.35
    """mm, Gaussian blur on the resampled field: rounds the field's cells' creases.
    0.7 lost: on a limb one cell thick (the thin flanges the optimiser puts in
    the grid's floor, the diagonal staircases) it pulled the density under the
    surface and erased the limb, leaving stubs; CalculiX found the drawn seat
    12x softer than the optimiser's own model (1.25 against 15.3 N/mm). At 0.35
    the two agree (15.7 N/mm). 0 lost too: diagonal joints parted (0.41 N/mm)."""
    surface_iso: float = 0.36
    """Density at the surface: the volume-preserving level, where the limbs drawn
    hold the volume the optimiser placed (measured on the first 2 mm field, the
    sum of rho 6237 mm^3 against ~6200 drawn at 0.36). 0.5 lost: that field's
    thinnest members sat at 0.7-0.9 density behind the 5 mm filter, and 0.5 drew
    half its volume, in 9 pieces."""
    surface_scale_mm: float = 3.0
    """mm per unit density: turns the blurred field into a distance for the fillet blend."""
    surface_fillet_mm: float = 2.0
    """mm, smooth-union radius where a limb meets a seat, hoop or post: the fillet."""
    surface_simplify_mm: float = 1e-5
    """mm, mesh simplification tolerance (faces move less than this): enough to
    remove the level set's zero-length edges and nothing else. 0.02 lost: it let
    a long triangle from a fillet's rim span a seat 0.012 mm proud of its top,
    into the motor (C5 read 0.0175 mm^3)."""
    surface_open_mm: float = 0.3
    """mm, radius of the morphological opening of the drawn frame (geometry._open),
    after the keep-outs are cut and the exact features added: any part thinner
    than about twice this goes. Where the field met a keep-out at a grazing angle
    the cut left a feathered edge down to 0.01 mm, and where its ring ran past a
    guard arc's end, a 0.4 mm lip. 0.63 (half of cad.wall_thickness's 1.26 mm)
    lost: it also deleted the rim's four bridges between neighbouring guards,
    walls ~1.2 mm thick that the optimiser drew, and left the arcs ending in
    stubs (the author's 'nubs', 2026-10-17). 0.75 lost on a 2 mm field: it broke
    the frame apart."""
    surface_cut_round_mm: float = 0.5
    """mm, the radius every keep-out's edges are rounded to (geometry._keepout_sdf),
    so a cut leaves the frame a fillet where it meets the body, as a 0.4 mm
    nozzle prints it. Sharp, those re-entrant edges were stress singularities the
    crash checks' peak sat on, growing with every mesh refinement."""
    surface_clearance_mm: float = 0.1
    """mm the drawn field stands off every keep-out: the level set interpolates
    the cut linearly and the simplification moves faces, each by hundredths of a
    millimetre, and the fit check counts any overlap past 1e-4 mm^3 (C5)."""

    # --- the print pose (geometry.print_rotation) ---
    print_tilt_deg: float = 0.0
    """deg the frame is tilted on the bed from flying-level, about the horizontal
    axis at print_azimuth_deg. The layers lie square to the build direction, so
    this sets which way the printed part is weak (fea.layer_normal). Flat, as it
    flies: the orientation scan on CalculiX's crash stresses found no pose loses
    strength to the layers, and flat stands 20 mm tall with support under 22 % of
    its surface. On edge (90-105 deg) lost: 10 % support, but 111 mm tall on its
    rim, five times the layers."""
    print_azimuth_deg: float = 0.0
    """deg, the tilt axis's direction from +x (forward)."""

    support_area_max_frac: float = 0.35
    """Share of the frame's surface the slicer may support (downward faces past
    45 deg, fdm.overhang). R7 allows supports; past about a third of the surface
    the print is mostly support to peel, and every supported face is a scar."""

    # --- the printer and the process ---
    bed_x_mm: float = 270.0
    """mm, Snapmaker U1 build plate X (Snapmaker specs: 270 mm cube)."""
    bed_y_mm: float = 270.0
    """mm, Snapmaker U1 build plate Y."""
    bed_z_mm: float = 270.0
    """Snapmaker U1 build height."""

    brim_mm: float = 5.0
    """mm of brim per side; snipped off."""
    nozzle_d_mm: float = 0.4
    """mm, the U1's stock nozzle."""
    extrusion_width_mm: float = 0.42
    """mm, 1.05 x nozzle - a stock profile's line width; 3 of them is the wall rule."""
    layer_height_mm: float = 0.2
    """mm, 0.2: half the nozzle, the PETG default."""
    perimeters: int = 3
    """Wall loops."""
    infill_fraction: float = 1.0
    """The limbs are a few mm across: treat as solid."""
    print_speed_mm_s: float = 60.0
    """mm/s nominal; an ordinary PETG speed (the estimate derates it)."""
    max_print_time_h: float = 3.0
    """An afternoon with a 10-year-old: a print that runs overnight is a print he
    does not see."""
    max_filament_g: float = 1000.0
    """g, one spool."""

    # --- flight ---
    guard_thrust_factor: float = 0.925
    """Static thrust with the guards and the limbs under the props, relative to
    the open-prop bench test. ASSUMPTION (A1): low guards neither add (no duct
    lip) nor take much; the limbs' shadow on the disc is capped at 15 % by
    claim C14, and blockage costs roughly half its area fraction."""

    usable_capacity_frac: float = 0.8
    """Land at ~3.5 V/cell: 80% of rated capacity, kinder to cheap 1S packs."""

    prop_sweep_half_h: float = 1.5
    """mm, half-height of the band the prop occupies, for the clearance checks."""

    # --- how the CalculiX gates mesh the printed frame (gates/structure.py) ---
    fea_mesh_mm: float = 1.6
    """mm, the CalculiX tetrahedra's edge (quadratic tets, two to three across a
    3-4 mm limb); solid_fea_ccx refuses a mesh with tets over 2x this or slivers.
    petgasus.fea_converged reruns on the fine surface with tets to 0.75 of it,
    and refuses a first mode that moves more than 5 % or a drop height or wall
    speed that moves more than 10 %. 1.2 lost: fTetWild's mesh of it held ~200k
    tets, and the fine one at 0.9 mm ~2M unknowns, too many for the single-
    threaded equation solver (solid_fea_ccx.run) on a 21 GB machine."""

    fea_surface_mm: float = 0.5
    """mm, edge of the analysis surface (geometry.analysis_surface: the frame as
    one signed function and one level set, no booleans); the convergence check's
    fine surface is 0.7 of it. 0.5, the printed surface's own edge: CalculiX
    judges the very surface that is printed. 0.8 lost: on its coarser lattice a
    rim bridge's 1.2 mm neck thinned to a thread (genus 47 against the print's
    50), the tet mesh cut it, and the frame had a loose piece (a 0 Hz mode, a
    solve 434 N out of equilibrium). The printed surface simplified to 0.1 mm
    lost: the booleans' cut lines left slivers gmsh could not recover a boundary
    from, and simplifying them made the surface intersect itself."""


CONFIG = Config()


PARAMS = [
    {"name": "guard_h", "units": "mm", "rejected": [
        {"value": "10.9 mm duct with lattice windows (v0.1)",
         "why": "propwash in climbs and rolls, and the windows added layer perimeter (weight); r/diydrones review"}]},
    {"name": "prop_tip_gap", "units": "mm", "rejected": [
        {"value": "1.0 mm", "why": "a duct's gap: a hoop gains nothing from it and a bent blade strikes"}]},
    {"name": "topo_h", "units": "mm", "rejected": [
        {"value": "1.0 mm", "why": "~840k unknowns: PARDISO's factors took 18 GB and ran this 21 GB machine out "
                                   "of memory. The 13 load cases share one factorisation an iteration, so memory, "
                                   "not the case count, rules it out; 1.33 mm is ~365k unknowns, 7 GB"}]},
    {"name": "motor_thrust_max_g", "units": "g", "rejected": [
        {"value": "46.3 g at 4.2 V (v0.1)",
         "why": "a different motor (1102 22000KV) on a 40 mm prop, tested at 4.0 V; the kit motor's own table says 66.6 g"}]},
    {"name": "guard_wall", "units": "mm", "rejected": [
        {"value": "1.26 mm (3 beads exactly)", "why": "the guard is the part that meets the wall first"}]},
    {"name": "fc_screw_len", "units": "mm", "rejected": [
        {"value": "5 mm (the board's own M1.4 x 5)", "why": "2.4 mm in the post, under C8's 3 mm"}]},
    {"name": "motor_screw_len", "units": "mm", "rejected": [
        {"value": "4 mm (the motor pack's own M1.4 x 4)",
         "why": "2.2 mm into a base whose thread depth BetaFPV does not publish: a screw that bottoms out presses on the stator"}]},
    {"name": "fc_post_h", "units": "mm", "rejected": [
        {"value": "4.5 mm", "why": "the ESC sockets' undersides only 1.2 mm over the strap"}]},
    {"name": "battery_mah", "units": "mAh", "rejected": [
        {"value": "480 mAh (v0.1)",
         "why": "4.4 g heavier for 50 % more energy, and 15.5 mm wide: it no longer fits the bay under the hub"}]},
    # values that ARE an assumption (SPEC 19): each moves with its claim until a measurement replaces it
    {"name": "guard_thrust_factor", "grounded_by": ["A1"]},
    {"name": "motor_base_d", "units": "mm", "grounded_by": ["A3"]},
    {"name": "motor_base_h", "units": "mm", "grounded_by": ["A3"]},
    {"name": "motor_centre_relief_d", "units": "mm", "grounded_by": ["A3"]},
    {"name": "fc_grommet_h", "units": "mm", "grounded_by": ["A4"]},
    {"name": "fc_grommet_od", "units": "mm", "grounded_by": ["A4"]},
    {"name": "fc_post_od", "units": "mm", "grounded_by": ["A4"]},
]


# --------------------------------------------------------------------------- #
def _derive_layout(c: Config) -> dict:
    import geometry_petgasus as geo
    d: dict = {}
    d["prop_r"] = c.prop_d / 2
    d["motor_body_h"] = c.motor_h - c.shaft_exposed
    d["prop_z"] = round(c.plate_t + d["motor_body_h"] + c.prop_hub_h / 2, 4)
    d["guard_r_in"] = d["prop_r"] + c.prop_tip_gap
    d["guard_r_out"] = d["guard_r_in"] + c.guard_wall
    d["guard_z0"] = round(d["prop_z"] - c.guard_h / 2, 4)
    d["guard_z1"] = round(d["prop_z"] + c.guard_h / 2, 4)
    # the seat ends at the bell's edge: inside the motor's own shadow it costs the
    # prop nothing (C14), and 0.75 mm proud of it, as it was, the seat's rim alone
    # was 2.4 % of the disc; 2.85 mm of plastic still rings the screw holes
    d["mount_r"] = c.motor_body_d / 2

    # FC posts at the cross's arm tips, on the axes
    rh = round(c.fc_hole_spacing / math.sqrt(2), 4)
    d["fc_post_xy"] = [(rh, 0.0), (0.0, rh), (-rh, 0.0), (0.0, -rh)]
    d["z_post_top"] = round(c.plate_t + c.fc_post_h, 4)
    d["z_board"] = round(d["z_post_top"] + c.fc_grommet_below, 4)

    # Motor offset a (motors at (+-a, +-a)) is DERIVED: the smallest a at which the
    # board's outline and the grommets clear every hoop by fc_board_clear in plan,
    # so the board lifts straight out. The outline is sampled densely.
    pts = []
    tip, wfb, wsd = c.fc_arm_tip_r, c.fc_arm_w_fb, c.fc_arm_w_side
    for k in range(400):
        t = k / 400
        for (w, along) in ((wfb, "x"), (wsd, "y")):
            for s in (1, -1):
                for side in (1, -1):
                    u = s * (tip - w / 2) * t                    # along the arm's straight edge
                    v = side * w / 2
                    pts.append((u, v) if along == "x" else (v, u))
                ang = math.pi * t - math.pi / 2                 # the rounded tip
                cx = s * (tip - w / 2)
                p = (cx + s * w / 2 * math.cos(ang), w / 2 * math.sin(ang))
                pts.append(p if along == "x" else (p[1], p[0]))
    pts = [(x, y, c.fc_board_clear) for (x, y) in pts]
    pts += [(px, py, c.fc_grommet_od / 2 + c.fc_board_clear) for (px, py) in d["fc_post_xy"]]

    def worst(a):
        return min(math.hypot(px - a, py - a) - d["guard_r_out"] - r for (px, py, r) in pts)
    lo, hi = d["guard_r_out"], 200.0
    for _ in range(60):
        mid = (lo + hi) / 2
        if worst(mid) >= 0:
            hi = mid
        else:
            lo = mid
    a = round(hi + 0.05, 2)
    d["motor_offset"] = a
    d["motor_xy"] = [(a, a), (a, -a), (-a, a), (-a, -a)]
    d["fc_guard_clearance_mm"] = round(worst(a) + c.fc_board_clear, 3)
    d["wheelbase_mm"] = round(2 * math.sqrt(2) * a, 2)
    d["guard_gap_mm"] = round(2 * a - 2 * d["guard_r_out"], 2)
    d["motor_screw_xy"] = {(mx, my): geo.motor_screw_xy(c, mx, my) for (mx, my) in d["motor_xy"]}

    # each lead runs straight from the motor's base to its plug under a side arm
    d["socket_xy"], d["lead_path"] = {}, {}
    z_sock = round(d["z_board"] - c.socket_h / 2, 4)
    for (mx, my) in d["motor_xy"]:
        sx, sy = math.copysign(1, mx), math.copysign(1, my)
        d["socket_xy"][(mx, my)] = (sx * c.socket_x, sy * c.socket_y)
        u = (-mx / math.hypot(mx, my), -my / math.hypot(mx, my))
        r0 = c.motor_base_d / 2 + c.lead_d / 2 + 0.3
        p0 = (round(mx + r0 * u[0], 4), round(my + r0 * u[1], 4), round(c.plate_t + c.motor_base_h / 2, 4))
        p1 = (sx * c.socket_x, round(sy * (c.socket_y + c.socket_depth / 2 + c.plug_l), 4), z_sock)
        d["lead_path"][(mx, my)] = (p0, p1)

    # the power pigtail: from the BATT pads on the rear arm, along y=+3 to clear
    # the rear screw's head, out past the arm tip, down to the battery's plug
    z_top = d["z_board"] + c.fc_pcb_t + c.lead_d / 2 + 0.2
    zc = -c.battery_h / 2
    x_plug = -(c.battery_l / 2 + 4 + c.bt20_len * 2 - 0.3)
    d["pigtail_path"] = [(-(tip - 6), 3.0, round(z_top, 4)), (-(tip + 3), 3.0, round(z_top, 4)),
                         (round(x_plug - 1.5, 4), 0.0, round(zc + 2.0, 4)), (round(x_plug - 1.5, 4), 0.0, zc)]

    d["strap_slot_y"] = round(c.strap_bay_w / 2 + c.strap_slot_w / 2, 2)
    d["strap_slot_len"] = c.strap_w + 1.0
    mat = MATERIALS[c.material]
    d["topo_design_mm3"] = round(c.topo_design_g / (mat["density"] * 1e-3), 3)
    d["guard_E_rel"] = round(MATERIALS[c.guard_material]["E_xy"] / mat["E_xy"], 6)
    return d


def _mesh_props(man) -> dict:
    mesh = man.to_mesh()
    import numpy as np
    v = np.asarray(mesh.vert_properties)[:, :3]
    if not len(v):
        return {"volume_mm3": 0.0, "area_mm2": 0.0, "bbox_mm": [0.0, 0.0, 0.0], "lo": [0.0, 0.0, 0.0]}
    lo, hi = v.min(axis=0), v.max(axis=0)
    return {"volume_mm3": round(man.volume(), 2), "area_mm2": round(man.surface_area(), 2),
            "bbox_mm": [round(float(x), 3) for x in (hi - lo)], "lo": [float(x) for x in lo]}


def _write_if_changed(path, data: bytes):
    """Content-addressed write: rebuilding an unchanged design leaves the file alone."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if not (os.path.exists(path) and open(path, "rb").read() == data):
        with open(path, "wb") as fh:
            fh.write(data)


def _threemf(objects) -> bytes:
    """A minimal 3MF (core spec), millimetres: one object per (name, vertices,
    triangles), all placed at the origin, so a two-material frame arrives as two
    objects the slicer assigns a filament each. Written by hand because the
    library writer needs networkx."""
    import io
    import zipfile
    res, items = [], []
    for k, (name, v, t) in enumerate(objects, start=1):
        verts = "".join(f'<vertex x="{x:.6f}" y="{y:.6f}" z="{z:.6f}"/>' for x, y, z in v)
        tris = "".join(f'<triangle v1="{a}" v2="{b}" v3="{c}"/>' for a, b, c in t)
        res.append(f'<object id="{k}" type="model" name="{name}"><mesh>'
                   f'<vertices>{verts}</vertices><triangles>{tris}</triangles></mesh></object>')
        items.append(f'<item objectid="{k}"/>')
    model = ('<?xml version="1.0" encoding="UTF-8"?>'
             '<model unit="millimeter" xml:lang="en-US" '
             'xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02">'
             f'<resources>{"".join(res)}</resources><build>{"".join(items)}</build></model>')
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


def _arrays(man):
    import numpy as np
    mesh = man.to_mesh()
    return np.asarray(mesh.vert_properties)[:, :3].astype(np.float64), np.asarray(mesh.tri_verts)


def _write_meshes(bodies, stem):
    """Write `stem`.ply (indexed, double - what the gates read), .3mf (for the
    slicer, one object per body) and .stl (for anything else, every body merged).

    STL alone was tried: it stores float32 coordinates with no shared vertices, so
    a reader must weld by position, and vertices 1e-4 mm apart welded into
    non-manifold edges on a mesh that was a clean manifold (cad.watertight)."""
    import manifold3d as m3d
    import trimesh
    whole = m3d.Manifold.batch_boolean([b for _, b in bodies], m3d.OpType.Add)
    v, t = _arrays(whole)
    tm = trimesh.Trimesh(vertices=v, faces=t, process=False)
    _write_if_changed(stem + ".ply", tm.export(file_type="ply", encoding="binary"))
    _write_if_changed(stem + ".stl", tm.export(file_type="stl"))
    _write_if_changed(stem + ".3mf", _threemf([(name, *_arrays(b)) for name, b in bodies]))


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


def frame_solids(c, d=None, prob=None):
    """(body, frame_solid, guard_solid or None, topology_current, field_info, field): the
    printed frame drawn from the proposal c.topology_field, split by filament
    when the hoops are a second one. The one place the frame is made: build()
    and the print package both call it, so what is printed is what was judged.

    The two-filament split is approximate. It cuts the body at the EXACT arcs
    (geometry.guards), but the drawn arcs stand 0.2-0.4 mm proud of them on
    every face but the top. The field is carried into the arc cells, then
    resampled and blurred past their faces, and the fillet's smooth union grows
    them further; only the prop's keep-out and the cap over the hoops stop it
    (geometry._reach_into_features). So with a
    second filament the frame object clads the guard object in skins of the
    frame's filament 0.2-0.35 mm thick, under one 0.42 mm line, which a slicer
    drops or prints badly, and a few zero-volume specks on the arcs' tops.
    gates/structure.py splits its tets at the same exact band, by centroid, so
    CalculiX judges the same clad hoop at its 1.2 mm tet size. With one
    filament (guard_material == material, the build) there is no split and
    none of this applies. Fix the split before printing a second filament:
    clip the field off the arcs' free faces, or split at a band grown to the
    drawn faces."""
    import manifold3d as m3d
    import numpy as np
    import geometry_petgasus as geo
    import topopt3d_petgasus as tp
    d = d or _derive_layout(c)
    prob = prob or tp.problem(c, d)
    field, current, info = None, False, {}
    if c.topology_field:
        path = os.path.join(ROOT, c.topology_field)
        if os.path.exists(path):
            rho, g, current = tp.load_field(path, prob["problem_hash"])
            z = np.load(path)
            field = (rho, g, z["region"].reshape(rho.shape))
            info = json.loads(str(z["info"]))
            if "variant" in z.files:
                info["variant"] = str(z["variant"])
    body = geo.frame(c, d, field=field, cache_dir=os.path.join(ROOT, "build", "frame_cache"))
    if c.guard_material != c.material:
        rings = m3d.Manifold.batch_boolean(geo.guards(c, d), m3d.OpType.Add)
        return body, body - rings, body ^ rings, bool(current), info, field
    return body, body, None, bool(current), info, field


def print_bodies(c, frame_solid, guard_solid=None):
    """[(object name, solid in print pose)]: what goes on the bed, one object per
    filament (the slicer assigns each its own)."""
    import geometry_petgasus as geo
    solids = [frame_solid] + ([guard_solid] if guard_solid is not None else [])
    posed = geo.to_print_pose(c, solids)
    names = ["petgasus-frame"] + (["petgasus-guards"] if guard_solid is not None else [])
    return list(zip(names, posed))


def _surface_msh(v, t) -> bytes:
    """A closed triangle surface as a gmsh MSH 2.2 file: shared vertices, double
    precision. STL lost here too: its float32, unshared vertices re-welded the
    simplified surface into a non-watertight one."""
    lines = ["$MeshFormat", "2.2 0 8", "$EndMeshFormat", "$Nodes", str(len(v))]
    lines += [f"{i + 1} {x:.9g} {y:.9g} {z:.9g}" for i, (x, y, z) in enumerate(v)]
    lines += ["$EndNodes", "$Elements", str(len(t))]
    lines += [f"{i + 1} 2 2 0 1 {a + 1} {b + 1} {c + 1}" for i, (a, b, c) in enumerate(t)]
    lines += ["$EndElements", ""]
    return "\n".join(lines).encode()


def _file_sha(rel):
    path = os.path.join(ROOT, rel) if rel else ""
    if not path or not os.path.exists(path):
        return ""
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def _hover_eff(c: Config, thrust_per_motor_g: float) -> float:
    """g/W at this thrust per motor, read off the motor's load table (linear
    between rows, held flat beyond the first and last)."""
    import numpy as np
    t, e = zip(*c.motor_eff_table)
    return float(np.interp(thrust_per_motor_g, t, e))


def _blockage(c, d, frame) -> float:
    """Worst fraction of a prop's disc (outside the motor's own shadow) that the
    frame covers, seen from above: the downwash it blocks."""
    import geometry_petgasus as geo
    worst = 0.0
    r0 = c.motor_body_d / 2 + c.motor_clear
    annulus_area = math.pi * (d["prop_r"] ** 2 - r0 ** 2)
    for (mx, my) in geo.motor_centres(d):
        disc = (geo._cyl(d["prop_z"] + 50, d["prop_r"], -50) - geo._cyl(d["prop_z"] + 60, r0, -55)).translate((mx, my, 0))
        shadow = (frame ^ disc).project()
        worst = max(worst, shadow.area() / annulus_area)
    return worst


def _guard_band_heights(c, d, body, step=0.05):
    """The guard bands' heights as built (mm): at points round each guard's arc,
    off its ends, on the band's mid radius, the height of the solid's vertical run
    that holds the prop plane. Limbs that join a band from below lengthen the run
    at a few points; the median over all of them is the band's height."""
    import numpy as np
    from matplotlib.path import Path
    half = math.radians(c.guard_arc_deg / 2) - math.radians(10)
    r_mid = (d["guard_r_in"] + d["guard_r_out"]) / 2
    pts = []
    for (mx, my) in d["motor_xy"]:
        a = math.atan2(my, mx)
        for phi in np.arange(a - half, a + half + 1e-9, math.radians(5)):
            pts.append((mx + r_mid * math.cos(phi), my + r_mid * math.sin(phi)))
    pts = np.array(pts)
    zs = np.arange(d["guard_z0"] - 6.0, d["guard_z1"] + 1.0, step)
    inside = np.zeros((len(zs), len(pts)), bool)
    for k, z in enumerate(zs):
        cnt = np.zeros(len(pts), int)
        for poly in body.slice(float(z)).to_polygons():
            cnt += Path(np.asarray(poly)).contains_points(pts)
        inside[k] = cnt % 2 == 1
    k0 = int(np.argmin(np.abs(zs - d["prop_z"])))
    heights = []
    for j in range(len(pts)):
        if not inside[k0, j]:
            heights.append(0.0)
            continue
        lo = hi = k0
        while lo > 0 and inside[lo - 1, j]:
            lo -= 1
        while hi < len(zs) - 1 and inside[hi + 1, j]:
            hi += 1
        heights.append(float(zs[hi] - zs[lo] + step))
    return np.array(heights)


def _mass_properties(c, d, body, frame_g, auw):
    """Centre of mass (mm) and the principal-axis inertias about it (g mm^2, about
    x, y, z) of the whole flying drone: the printed frame from its mesh, the bought
    parts as the boxes and points they are drawn as. The crash gates use them for
    the share of an off-centre hit that goes into the frame (Goldsmith)."""
    import numpy as np
    import trimesh
    v, t = _arrays(body)
    tm = trimesh.Trimesh(v, t, process=False)
    parts = []                                                 # (mass g, centre, own inertia diag about it)
    if tm.volume > 0:
        scale = frame_g / tm.volume
        parts.append((frame_g, np.asarray(tm.center_mass), np.diag(tm.moment_inertia) * scale))
    z_motor = c.plate_t + d["motor_body_h"] / 2
    for (mx, my) in d["motor_xy"]:
        parts.append((c.motor_mass_g + c.prop_mass_g, np.array([mx, my, z_motor]), np.zeros(3)))
    L, W, H = c.battery_l, c.battery_w, c.battery_h
    parts.append((c.battery_mass_g, np.array([0.0, 0.0, -H / 2]),
                  c.battery_mass_g / 12 * np.array([W * W + H * H, L * L + H * H, L * L + W * W])))
    r = c.fc_arm_tip_r
    parts.append((c.fc_mass_g, np.array([0.0, 0.0, d["z_board"]]), c.fc_mass_g / 12 * np.array([r * r, r * r, 2 * r * r])))
    parts.append((c.misc_mass_g, np.array([0.0, 0.0, d["z_board"] / 2]), np.zeros(3)))
    m = sum(p[0] for p in parts)
    cg = sum(p[0] * p[1] for p in parts) / m
    I = np.zeros(3)
    for mass, centre, own in parts:
        dx = centre - cg
        I += own + mass * np.array([dx[1] ** 2 + dx[2] ** 2, dx[0] ** 2 + dx[2] ** 2, dx[0] ** 2 + dx[1] ** 2])
    return [round(float(x), 3) for x in cg], [round(float(x), 1) for x in I]


def build(config: Config | None = None, write_meshes: bool = True) -> dict:
    """Resolve every derived quantity, and (by default) export the print meshes.

    Writing build/print/* here is a recorded decision (decisions/build-writes-the-print-meshes):
    the mesh gates read files, and generating them in the same call that computes
    their volumes is the one way the numbers and the files cannot disagree. The
    analysis mesh the structure gates read is ALWAYS written, under a name that
    is this design's hash (build/fea/), so a control's design never overwrites
    the live one and the live one never answers for a control.
    """
    c = config or CONFIG
    import manifold3d as m3d
    import numpy as np
    import geometry_petgasus as geo  # noqa: E402  (sibling modules, see _load below)
    import topopt3d_petgasus as tp  # noqa: E402
    import assembly_petgasus as asm  # noqa: E402

    mat, gmat = MATERIALS[c.material], MATERIALS[c.guard_material]
    d = _derive_layout(c)

    # --- the topology problem, and the frame drawn from its proposal ---
    prob = tp.problem(c, d)
    if write_meshes:
        tp.write_problem(prob, os.path.join(ROOT, "build", "topopt3d", "problem.npz"))
    body, frame_solid, guard_solid, topology_current, field_info, field = frame_solids(c, d, prob)
    pieces = len(body.decompose())
    frame_top_z = body.bounding_box()[5]
    fp = _mesh_props(body)
    vol_guard = guard_solid.volume() if guard_solid is not None else 0.0
    vol_frame = frame_solid.volume()

    items, leads_needed = asm.parts(c, d, frame_solid, guard_solid)
    interference = asm.interferences(items)
    lead_spare = min(c.motor_lead_len - v for v in leads_needed.values())

    # --- masses ---
    frame_g = vol_frame * mat["density"] * 1e-3 + vol_guard * gmat["density"] * 1e-3
    auw = (frame_g + 4 * c.motor_mass_g + 4 * c.prop_mass_g + c.fc_mass_g
           + c.battery_mass_g + c.misc_mass_g)

    # --- thrust ---
    # Thrust at fixed throttle goes ~ V^2 for a fixed prop (rpm ~ V, thrust ~ rpm^2),
    # so the table's 3.81 V row is scaled to the pack's nominal voltage: the
    # voltage the pilot has for most of the flight.
    v_factor = (c.battery_v_nom / c.motor_thrust_test_v) ** 2
    thrust_total = 4 * c.motor_thrust_max_g * v_factor * c.guard_thrust_factor
    t_w = thrust_total / auw

    # --- flight time: hover power from the motor's own efficiency at hover thrust ---
    hover_eff = _hover_eff(c, auw / 4 / c.guard_thrust_factor)
    hover_w = auw / c.guard_thrust_factor / hover_eff
    energy_wh = c.battery_mah / 1000 * c.battery_v_nom * c.usable_capacity_frac
    flight_min = energy_wh / hover_w * 60

    # --- motor rotation frequency, for reading the frame modes against ---
    f_motor = 0.8 * c.motor_kv * 4.2 / 60
    f_motor_hover = f_motor * math.sqrt(min(1.0, auw / (thrust_total / c.guard_thrust_factor)))

    # --- screw stacks ---
    head_bottom = d["z_post_top"] + c.fc_grommet_h
    fc_engagement = c.fc_screw_len - c.fc_grommet_h
    fc_protrusion = c.fc_screw_len - head_bottom
    motor_screw_engage = c.motor_screw_len - c.plate_t

    meshes = {"frame": "build/print/frame.ply"}
    bodies = print_bodies(c, frame_solid, guard_solid)
    pp = _mesh_props(m3d.Manifold.batch_boolean([b for _, b in bodies], m3d.OpType.Add))
    R = geo.print_rotation(c)
    layer_normal = [round(float(x), 6) for x in R.T @ [0.0, 0.0, 1.0]]
    if write_meshes:
        _write_meshes(bodies, os.path.join(ROOT, "build", "print", "frame"))
        _write_assembly(items)

    design_hash = hashlib.sha256(json.dumps(asdict(c), sort_keys=True).encode()).hexdigest()[:12]
    # the analysis mesh is named by the design, the field's bytes and the drawing's
    # version: a field file rewritten under the same name, or a drawing fixed,
    # must never be answered by the old mesh
    shape_key = hashlib.sha256((design_hash + _file_sha(c.topology_field)
                                + f"drawing{geo.DRAWING_VERSION}").encode()).hexdigest()[:12]
    fea_dir = os.path.join(ROOT, "build", "fea", shape_key)
    fea_mesh = os.path.join(fea_dir, "frame.msh")
    fea_fine = os.path.join(fea_dir, "frame-fine.msh")
    for path, edge in ((fea_mesh, c.fea_surface_mm), (fea_fine, c.fea_surface_mm * 0.7)):
        if not os.path.exists(path):
            solid = geo.analysis_surface(c, d, field, edge) if field is not None else body
            _write_if_changed(path, _surface_msh(*_arrays(solid)))

    blockage = _blockage(c, d, body)
    cg, inertia = _mass_properties(c, d, body, frame_g, auw)
    # the same frame in the strong filament, for the crash gates (C15, C16)
    smat = MATERIALS[c.strong_material]
    strong_frame_g = vol_frame * smat["density"] * 1e-3 + vol_guard * gmat["density"] * 1e-3
    strong_auw = auw - frame_g + strong_frame_g
    strong_cg, strong_inertia = _mass_properties(c, d, body, strong_frame_g, strong_auw)
    band = _guard_band_heights(c, d, body)
    out = {
        **{k: v for k, v in d.items() if k not in ("motor_screw_xy", "socket_xy", "lead_path")},
        "frame_mass_g": round(frame_g, 2),
        "guard_mass_g": round(vol_guard * gmat["density"] * 1e-3, 2),
        "auw_g": round(auw, 2),
        "thrust_total_g": round(thrust_total, 1),
        "thrust_to_weight": round(t_w, 3),
        "hover_throttle_frac": round(1 / t_w, 3),
        "hover_eff_g_per_w": round(hover_eff, 3),
        "hover_power_w": round(hover_w, 2),
        "flight_time_min": round(flight_min, 2),
        "motor_freq_full_hz": round(f_motor, 1),
        "motor_freq_hover_hz": round(f_motor_hover, 1),
        "fc_stack_mm": round(head_bottom, 2),
        "fc_screw_engagement_mm": round(fc_engagement, 2),
        "fc_screw_protrusion_mm": round(fc_protrusion, 2),
        "motor_screw_engagement_mm": round(motor_screw_engage, 2),
        "frame_pieces": pieces,
        "frame_top_z": round(frame_top_z, 3),
        "interference_mm3": interference,
        "interference_total_mm3": round(sum(interference.values()), 3),
        "motor_lead_needed_mm": {k: round(v, 1) for k, v in leads_needed.items()},
        "motor_lead_spare_mm": round(lead_spare, 2),
        "assembly_parts": {n: {"path": f"build/assembly/{n}.ply", "color": list(it["color"]),
                               "explode": list(it["explode"]), "group": it["group"], "step": it["step"]}
                           for n, it in sorted(items.items())},
        "frame_bbox_mm": fp["bbox_mm"],
        "design_hash": design_hash,
        "material_name": mat["source"],
        "material_needs": list(mat["needs"]) + [n for n in gmat["needs"] if n not in mat["needs"]],
        # --- the topology proposal ---
        "problem_hash": prob["problem_hash"],
        "topology_current": bool(topology_current),
        "topology_variant": field_info.get("variant") if field_info else None,
        "guard_h_mm": c.guard_h,
        "guard_band_h_mm": round(float(np.median(band)), 3),
        "guard_band_h_max_mm": round(float(band.max()), 3),
        "prop_blockage_frac": round(blockage, 4),
        # --- what the structure gates read (gates/structure.py) ---
        "fea.mesh_path": os.path.relpath(fea_mesh, ROOT),
        "fea.mesh_fine_path": os.path.relpath(fea_fine, ROOT),
        "fea.material": {**{k: mat[k] for k in ("density", "E_xy", "E_z")},
                         "uts_xy": mat["uts_xy"] * c.strength_knockdown, "uts_z": mat["uts_z"] * c.strength_knockdown},
        "fea.guard_material": {**{k: gmat[k] for k in ("density", "E_xy", "E_z")},
                               "uts_xy": gmat["uts_xy"] * c.strength_knockdown,
                               "uts_z": gmat["uts_z"] * c.strength_knockdown},
        "fea.guard_separate": c.guard_material != c.material,
        "fea.strong_name": c.strong_material,
        "fea.strong_material": {**{k: smat[k] for k in ("density", "E_xy", "E_z")},
                                "uts_xy": smat["uts_xy"] * c.strength_knockdown,
                                "uts_z": smat["uts_z"] * c.strength_knockdown},
        "strong_frame_mass_g": round(strong_frame_g, 2),
        "strong_auw_g": round(strong_auw, 2),
        "fea.strong_cg_mm": strong_cg,
        "fea.strong_inertia_g_mm2": strong_inertia,
        "fea.layer_normal": layer_normal,
        "fea.motor_mass_g": round(c.motor_mass_g + c.prop_mass_g, 3),
        "fea.body_mass_g": round(c.fc_mass_g + c.battery_mass_g, 3),
        "fea.mesh_mm": c.fea_mesh_mm,
        "fea.cg_mm": cg,
        "fea.inertia_g_mm2": inertia,
        "fea.thrust_n": round(c.motor_thrust_max_g / 1000 * G * c.topo_thrust_factor, 4),
        # --- fdm-print keys: the set, and the largest part as the single-part view ---
        "mesh_paths": meshes,
        "bbox_by_part_mm": {"frame": pp["bbox_mm"]},
        "fdm.part_bbox_mm": pp["bbox_mm"],
        "fdm.part_volume_mm3": pp["volume_mm3"],
        "surface_area_mm2": pp["area_mm2"],
        "fdm.part_min_wall_mm": min(c.guard_wall, c.plate_t),
        "mesh_path": meshes["frame"],
        "meshes": dict(meshes),
        "build_axis": "z",
        # the support budget, and the direction the limbs' tension runs (along
        # the arms, flight +x+y) in the print pose, for fdm.overhang and
        # fdm.layer_alignment; CalculiX judges the stress across the layers itself
        "overhang_area_allow_frac": c.support_area_max_frac,
        "load_axis": [round(float(x), 6) for x in R @ [math.sqrt(0.5), math.sqrt(0.5), 0.0]],
        "cad.process_min_wall_mm": round(c.perimeters * c.extrusion_width_mm, 3),
        "bom_path": "bom/bom.json",
    }
    return out


# the geometry, the topology problem and the assembly live in sibling files; load
# them by path so two copies of this project in one process never share them
import importlib.util as _ilu  # noqa: E402
import sys as _sys  # noqa: E402

for _name, _file in (("geometry_petgasus", "geometry.py"), ("topopt3d_petgasus", "topopt3d.py"),
                     ("assembly_petgasus", "assembly.py")):
    if _name not in _sys.modules:
        _spec = _ilu.spec_from_file_location(_name, os.path.join(_HERE, _file))
        _mod = _ilu.module_from_spec(_spec)
        _spec.loader.exec_module(_mod)
        _sys.modules[_name] = _mod


if __name__ == "__main__":
    print(json.dumps(build(), indent=2, sort_keys=True, default=str))
