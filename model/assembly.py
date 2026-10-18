"""assembly.py - every part of the drone, placed where it goes, for the 3D view and
for the clearance check (claim C5).

Same frame as geometry.py: millimetres, +x forward, +y left, +z up, z=0 under the
motor seats. The printed frame comes from geometry.frame; everything else here is
a BOUGHT part, drawn at the size its listing or drawing gives (see
inputs/datasheets/datasheet-research-2026-10-17.md), or, where none is
published, at the envelope the model states and the claims carry as an
assumption. These are not CAD of the vendor's parts: they are the space each one
takes, shaped enough to be recognisable and measured exactly enough to be
checked against the frame.

Each part: name -> dict(solid=Manifold, color=(r, g, b), explode=(dx, dy, dz),
group=str, step=int). `explode` is the direction it comes off in the assembly
order: the battery and strap drop away below, the motor screws below the seats,
the motors, the board and its screws lift off above, the props last of all.
"""
from __future__ import annotations

import math

import manifold3d as m3d

import geometry_petgasus as geo

C_FRAME = (255, 122, 26)      # orange PETG
C_GUARD = (40, 40, 44)        # the guard arcs, when they are a second material
C_PCB = (24, 96, 52)
C_CHIP = (30, 30, 34)
C_SOCKET = (235, 235, 225)
C_RUBBER = (60, 60, 64)
C_MOTOR = (150, 150, 165)
C_BELL = (110, 70, 170)
C_PROP = (230, 50, 60)
C_BATT = (95, 45, 165)
C_STRAP = (28, 28, 28)
C_SCREW = (190, 190, 200)
C_WIRE = (35, 35, 35)
C_RED = (205, 35, 35)

NAMES = ("front_left", "front_right", "back_left", "back_right")


def _tube(points, d, seg=16):
    """A wire: a chain of cylinders with ball joints through `points` (x, y, z)."""
    r = d / 2
    balls = [m3d.Manifold.sphere(r, seg).translate(p) for p in points]
    return m3d.Manifold.batch_boolean(
        [m3d.Manifold.batch_hull([a, b]) for a, b in zip(balls, balls[1:])], m3d.OpType.Add)


def polyline_len(points):
    return sum(math.dist(a, b) for a, b in zip(points, points[1:]))


def _screw(x, y, z_head_top, length, head_d, head_h, shank_d, up=True):
    """M1.4 pan-head screw. `up`: head on top, shank down (else head below, shank up)."""
    if up:
        head = geo._cyl(head_h, head_d / 2, z_head_top - head_h)
        shank = geo._cyl(length, shank_d / 2, z_head_top - head_h - length)
    else:
        head = geo._cyl(head_h, head_d / 2, z_head_top - head_h)
        shank = geo._cyl(length, shank_d / 2, z_head_top)
    return (head + shank).translate((x, y, 0))


def motor_lead_route(c, d, mx, my):
    """The 3-wire lead from the motor's base, straight to its plug in the ESC
    socket under the board's side arm. Points (x, y, z); the last one is inside
    the socket. The straight run is kept clear of the frame by the topology
    problem's keep-outs (topopt3d.keepouts, d['lead_path'])."""
    p0, p1 = d["lead_path"][(mx, my)]
    sx, sy = math.copysign(1, mx), math.copysign(1, my)
    sock = d["socket_xy"][(mx, my)]
    inside = (sock[0], sock[1] + sy * (c.socket_depth / 2 - 0.5), p1[2])
    return [tuple(p0), tuple(p1), inside], (sock[0], sock[1], p1[2])


def board(c, d):
    """The Matrix 1S 3IN1: a cross of 1 mm PCB, its four mounting holes at the arm
    tips (on the axes), the MCU on top, the four ESC sockets underneath on the
    side arms. Outline and socket places scaled from BetaFPV's photos (A4)."""
    z_pcb = d["z_board"]
    tip, wfb, wsd = c.fc_arm_tip_r, c.fc_arm_w_fb, c.fc_arm_w_side
    fb = geo._box(2 * (tip - wfb / 2), wfb, c.fc_pcb_t, z0=z_pcb)
    sd = geo._box(wsd, 2 * (tip - wsd / 2), c.fc_pcb_t, z0=z_pcb)
    ends = [geo._cyl(c.fc_pcb_t, w / 2, z_pcb).translate(p) for w, ps in
            ((wfb, ((tip - wfb / 2, 0, 0), (-(tip - wfb / 2), 0, 0))),
             (wsd, ((0, tip - wsd / 2, 0), (0, -(tip - wsd / 2), 0)))) for p in ps]
    pcb = m3d.Manifold.batch_boolean([fb, sd] + ends, m3d.OpType.Add)
    for (px, py) in d["fc_post_xy"]:
        pcb = pcb - geo._cyl(c.fc_pcb_t + 2, c.fc_hole_d / 2, z_pcb - 1).translate((px, py, 0))
    pcb_top = z_pcb + c.fc_pcb_t
    chip = geo._box(7, 7, c.fc_top_components_h, z0=pcb_top)
    sockets = [geo._box(c.socket_w, c.socket_depth, c.socket_h, cx=sx_, cy=sy_, z0=z_pcb - c.socket_h)
               for (sx_, sy_) in d["socket_xy"].values()]
    return pcb + chip, m3d.Manifold.batch_boolean(sockets, m3d.OpType.Add)


def parts(c, d, frame, guard_solid=None):
    out = {}

    def add(name, solid, color, explode, group, step):
        out[name] = dict(solid=solid, color=color, explode=explode, group=group, step=step)

    # `step` is the assembly order the build guide follows: 1 the printed frame,
    # 2 motors and their screws, 3 the flight controller on its grommets, 4 the
    # motor leads plugged in, 5 the battery, its strap and the power plug, 6 the props.
    add("frame", frame, C_FRAME, (0, 0, 0), "printed", 1)
    if guard_solid is not None:
        add("guards", guard_solid, C_GUARD, (0, 0, 0), "printed", 1)

    pcb, sockets = board(c, d)
    add("flight_controller", pcb, C_PCB, (0, 0, 30), "electronics", 3)
    add("motor_sockets", sockets, C_SOCKET, (0, 0, 30), "electronics", 3)

    # --- rubber grommets on the posts, and the screws through them into the posts ---
    zg = d["z_post_top"]
    head_top = zg + c.fc_grommet_h + c.screw_head_h
    for i, (px, py) in enumerate(d["fc_post_xy"]):
        grommet = (geo._cyl(c.fc_grommet_h, c.fc_grommet_od / 2, zg)
                   - geo._cyl(c.fc_grommet_h + 2, c.screw_d / 2 + 0.05, zg - 1)).translate((px, py, 0))
        add(f"fc_grommet_{i + 1}", grommet, C_RUBBER, (0, 0, 38), "electronics", 3)
        add(f"fc_screw_{i + 1}", _screw(px, py, head_top, c.fc_screw_len, c.screw_head_d, c.screw_head_h,
                                       c.screw_d, up=True), C_SCREW, (0, 0, 46), "screws", 3)

    # --- motors, their screws, props, leads ---
    base_top = c.plate_t + c.motor_base_h
    bell_top = c.plate_t + c.motor_h - c.shaft_exposed
    leads_needed = {}
    for name, (mx, my) in zip(NAMES, geo.motor_centres(d)):
        toward = math.degrees(math.atan2(-my, -mx))
        base = geo._cyl(c.motor_base_h, c.motor_base_d / 2, c.plate_t)
        bell = geo._cyl(bell_top - base_top, c.motor_body_d / 2, base_top)
        shaft = geo._cyl(c.motor_h - c.motor_base_h, c.shaft_d / 2, base_top)
        add(f"motor_{name}", (base + bell + shaft).translate((mx, my, 0)), C_BELL, (0, 0, 20), "motors", 2)

        screws = [_screw(hx, hy, 0.0, c.motor_screw_len, c.screw_head_d, c.screw_head_h, c.screw_d, up=False)
                  for (hx, hy) in d["motor_screw_xy"][(mx, my)]]
        add(f"motor_screws_{name}", m3d.Manifold.batch_boolean(screws, m3d.OpType.Add), C_SCREW,
            (0, 0, -14), "screws", 2)

        hub = (geo._cyl(c.prop_hub_h, c.prop_hub_d / 2, bell_top + 0.05)
               - geo._cyl(20, c.shaft_d / 2 + 0.05, bell_top - 5))
        blades = []
        for k in range(c.prop_blades):
            blade = (geo._box(d["prop_r"] - c.prop_hub_d / 2 + 0.5, c.prop_chord, c.prop_blade_t)
                     .rotate((c.prop_pitch_deg, 0, 0))
                     .translate(((d["prop_r"] + c.prop_hub_d / 2 - 0.5) / 2, 0, d["prop_z"] - c.prop_blade_t / 2)))
            blades.append(blade.rotate((0, 0, 360.0 * k / c.prop_blades + toward)))
        prop = (hub + m3d.Manifold.batch_boolean(blades, m3d.OpType.Add)
                - geo._cyl(20, c.shaft_d / 2 + 0.05, bell_top - 5)).translate((mx, my, 0))
        add(f"prop_{name}", prop, C_PROP, (0, 0, 42), "props", 6)

        pts, _ = motor_lead_route(c, d, mx, my)
        leads_needed[name] = polyline_len(pts[:2])
        add(f"motor_lead_{name}", _tube(pts, c.lead_d), C_WIRE, (0, 0, 25), "wires", 4)

    # --- battery under the hub, its lead and the BT2.0 pair at the back, the strap ---
    bz = -c.battery_h
    add("battery", geo._box(c.battery_l, c.battery_w, c.battery_h, z0=bz), C_BATT, (0, 0, -34), "battery", 5)
    xr = -c.battery_l / 2
    zc = bz + c.battery_h / 2
    conn_l = c.bt20_len
    male = geo._box(conn_l, c.bt20_w, c.bt20_h, cx=xr - 4 - conn_l / 2, z0=zc - c.bt20_h / 2)
    female = geo._box(conn_l, c.bt20_w, c.bt20_h, cx=xr - 4 - conn_l * 1.5, z0=zc - c.bt20_h / 2)
    add("battery_lead", _tube([(xr + 0.5, 0, zc), (xr - 4.2, 0, zc)], c.lead_d) + male, C_RED,
        (0, 0, -34), "battery", 5)
    # the board's pigtail: from the BATT pads on the rear arm, down past the rear
    # FC post to the plug, along a path the frame keeps clear (d['pigtail_path'])
    pig = _tube(list(d["pigtail_path"]) + [(xr - 4 - conn_l * 2 + 0.3, 0, zc)], c.lead_d)
    add("power_pigtail", pig + female, C_RED, (0, 0, 30), "electronics", 5)

    st, sy = c.strap_t, d["strap_slot_y"]
    sw = c.strap_w
    zb = bz - st
    strap = m3d.Manifold.batch_boolean([
        geo._box(sw, 2 * sy + st, st, z0=c.hub_t),                     # over the hub, under the board
        geo._box(sw, 2 * sy + st, st, z0=zb),                          # under the battery
        geo._box(sw, st, c.hub_t + st - zb, cy=sy, z0=zb),              # up through each slot
        geo._box(sw, st, c.hub_t + st - zb, cy=-sy, z0=zb),
    ], m3d.OpType.Add)
    add("battery_strap", strap, C_STRAP, (0, 0, -22), "battery", 5)
    return out, leads_needed


#: Pairs that overlap ON PURPOSE, each with the reason. Matched by part-name
#: prefix. Anything else that shares material is an interference (claim C5).
ALLOWED_OVERLAPS = [
    (("fc_screw_", "frame"), "the board's screws thread into the 1.1 mm pilots in the posts"),
    (("fc_screw_", "fc_grommet_"), "each screw passes through its rubber grommet"),
    (("fc_grommet_", "flight_controller"), "the board sits in the grommets' grooves"),
    (("motor_screws_", "motor_"), "the motor screws thread into the motor's base"),
    (("motor_lead_", "motor_sockets"), "each lead's plug sits in its socket"),
    (("power_pigtail", "flight_controller"), "the pigtail is soldered to the board at the factory"),
    (("battery_lead", "battery"), "the lead comes out of the pack"),
    (("guards", "frame"), "the guard arcs are printed fused to the frame in a second material"),
]


def interferences(items):
    """{'a|b': mm^3} for every pair that shares material and is not allowed."""
    names = sorted(items)
    boxes = {n: items[n]["solid"].bounding_box() for n in names}
    out = {}
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            (ax0, ay0, az0, ax1, ay1, az1), (bx0, by0, bz0, bx1, by1, bz1) = boxes[a], boxes[b]
            if ax1 <= bx0 or bx1 <= ax0 or ay1 <= by0 or by1 <= ay0 or az1 <= bz0 or bz1 <= az0:
                continue
            if any((a.startswith(p) and b.startswith(q)) or (b.startswith(p) and a.startswith(q))
                   for (p, q), _why in ALLOWED_OVERLAPS):
                continue
            v = (items[a]["solid"] ^ items[b]["solid"]).volume()
            if v > 1e-4:
                out[f"{a}|{b}"] = round(v, 4)
    return out
