"""assembly.py - every part of the drone, placed where it goes, for the 3D view and
for the clearance check (claim C5).

Same frame as geometry.py: millimetres, +x forward, +z up, z=0 under the base
plate. The printed frame comes from geometry.frame; everything else here is a
BOUGHT part, drawn at the size its listing gives (or, where none is published, at
the conservative envelope the model already assumes - see A3/A4). These are not
CAD of the vendor's parts: they are the space each one takes, shaped enough to be
recognisable and measured exactly enough to be checked against the frame.

Each part: name -> dict(solid=Manifold, color=(r, g, b), explode=(dx, dy, dz),
group=str). `explode` is the direction it comes off in the assembly order: the
battery and strap drop away below, the motor screws below the seats, the motors,
the board and its screws lift off above, the props last of all.
"""
from __future__ import annotations

import math

import manifold3d as m3d

import geometry_petgasus as geo

C_FRAME = (255, 122, 26)      # orange PETG
C_PCB = (24, 96, 52)
C_CHIP = (30, 30, 34)
C_SOCKET = (235, 235, 225)
C_MOTOR = (150, 150, 165)
C_BELL = (110, 70, 170)
C_PROP = (230, 50, 60)
C_BATT = (95, 45, 165)
C_STRAP = (28, 28, 28)
C_SCREW = (190, 190, 200)
C_WIRE = (35, 35, 35)
C_RED = (205, 35, 35)


def _tube(points, d, seg=16):
    """A wire: a chain of cylinders with ball joints through `points` (x, y, z)."""
    r = d / 2
    parts = [m3d.Manifold.sphere(r, seg).translate(p) for p in points]
    for p0, p1 in zip(points, points[1:]):
        v = [b - a for a, b in zip(p0, p1)]
        L = math.sqrt(sum(x * x for x in v))
        if L < 1e-6:
            continue
        # cylinder along +z, rotated onto v
        tilt = math.degrees(math.acos(max(-1.0, min(1.0, v[2] / L))))
        yaw = math.degrees(math.atan2(v[1], v[0]))
        parts.append(m3d.Manifold.cylinder(L, r, r, seg).rotate((0, tilt, 0))
                     .rotate((0, 0, yaw)).translate(p0))
    return m3d.Manifold.batch_boolean(parts, m3d.OpType.Add)


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
    """The 3-wire lead from the motor's base, out through the duct's port window,
    to the AIO socket on the board edge that faces this motor. Points (x, y, z).

    Returns (points, socket_xyz). The port window is the full lattice cell the
    duct is phased to put on its hub side (geometry._duct port_deg).
    """
    u = (-mx / math.hypot(mx, my), -my / math.hypot(mx, my))       # toward the hub
    lat = geo.lattice(c, d)
    pcb_top = c.plate_t + c.fc_post_h + c.fc_pcb_t
    z_lead = pcb_top + c.socket_h / 2                                 # socket entry height
    if lat:                                                           # ...inside the window?
        zc, qv = lat["z0"] + lat["hl"] / 2, lat["qv"]
        z_lead = min(z_lead, zc + 0.5 * qv)
    z_base = c.plate_t + c.motor_base_h / 2
    r_base = c.motor_base_d / 2 + c.lead_d / 2 + 0.05
    dist = math.hypot(mx, my)
    sock_r = c.fc_board_side / 2                                      # board edge, from centre
    p = [
        (mx + r_base * u[0], my + r_base * u[1], z_base),
        (mx + (r_base + 3) * u[0], my + (r_base + 3) * u[1], z_base),
        (mx + (d["duct_r_in"] - 2) * u[0], my + (d["duct_r_in"] - 2) * u[1], z_lead),
        (mx + (dist - sock_r - 0.2) * u[0], my + (dist - sock_r - 0.2) * u[1], z_lead),
    ]
    return p, (-u[0] * sock_r, -u[1] * sock_r, z_lead)


def parts(c, d, frame):
    out = {}

    def add(name, solid, color, explode, group, step):
        out[name] = dict(solid=solid, color=color, explode=explode, group=group, step=step)

    # `step` is the assembly order the build guide follows: 1 the printed frame,
    # 2 motors and their screws, 3 the flight controller and its screws, 4 the motor
    # leads plugged in, 5 the battery, its strap and the power plug, 6 the props.
    add("frame", frame, C_FRAME, (0, 0, 0), "printed", 1)

    # --- the AIO: PCB on the posts, turned fc_yaw_deg, with its parts ---
    z_pcb = c.plate_t + c.fc_post_h
    pcb_top = z_pcb + c.fc_pcb_t
    yaw = c.fc_yaw_deg
    pcb = geo._box(c.fc_board_side, c.fc_board_side, c.fc_pcb_t, z0=z_pcb)
    hole = c.fc_hole_spacing / 2
    for sx in (1, -1):
        for sy in (1, -1):
            pcb = pcb - geo._cyl(c.fc_pcb_t + 2, c.fc_hole_d / 2, z_pcb - 1).translate((sx * hole, sy * hole, 0))
    chip = geo._box(7, 7, 1.0, z0=pcb_top)
    fets = m3d.Manifold.batch_boolean(
        [geo._box(3, 3, 0.8, cx=sx * 6, cy=sy * 6, z0=z_pcb - 0.8) for sx in (1, -1) for sy in (1, -1)],
        m3d.OpType.Add)
    board = (pcb + chip + fets).rotate((0, 0, yaw))
    sockets = []
    for (mx, my) in geo.motor_centres(d):
        _, (sx_, sy_, _z) = motor_lead_route(c, d, mx, my)
        ang = math.degrees(math.atan2(sy_, sx_))
        sockets.append(geo._box(c.socket_depth, c.socket_w, c.socket_h, z0=pcb_top)
                       .translate((math.hypot(sx_, sy_) - c.socket_depth / 2, 0, 0)).rotate((0, 0, ang)))
    add("flight_controller", board, C_PCB, (0, 0, 30), "electronics", 3)
    add("motor_sockets", m3d.Manifold.batch_boolean(sockets, m3d.OpType.Add), C_SOCKET, (0, 0, 30),
        "electronics", 3)

    # --- AIO screws: down through the board into the posts ---
    for i, (px, py) in enumerate(d["fc_post_xy"]):
        add(f"fc_screw_{i + 1}", _screw(px, py, pcb_top + c.screw_head_h, c.fc_screw_len,
                                       c.screw_head_d, c.screw_head_h, c.screw_d, up=True),
            C_SCREW, (0, 0, 46), "screws", 3)

    # --- motors, their screws, props, leads ---
    names = ("front_left", "front_right", "back_left", "back_right")
    bell_z0 = c.plate_t + c.motor_base_h
    bell_top = c.plate_t + c.motor_h - c.shaft_exposed
    leads_needed = {}
    for name, (mx, my) in zip(names, geo.motor_centres(d)):
        toward = math.degrees(math.atan2(-my, -mx))
        base = geo._cyl(c.motor_base_h, c.motor_base_d / 2, c.plate_t)
        bell = geo._cyl(bell_top - bell_z0, c.motor_body_d / 2, bell_z0)
        shaft = geo._cyl(c.motor_h - c.motor_base_h, c.shaft_d / 2, c.plate_t + c.motor_base_h)
        add(f"motor_{name}", (base + bell + shaft).translate((mx, my, 0)), C_BELL, (0, 0, 20), "motors", 2)

        screws = []
        for k in range(3):
            a = math.radians(toward + 60 + 120 * k)
            sx_, sy_ = mx + c.motor_hole_circle_d / 2 * math.cos(a), my + c.motor_hole_circle_d / 2 * math.sin(a)
            screws.append(_screw(sx_, sy_, 0.0, c.motor_screw_len, c.screw_head_d, c.screw_head_h,
                                 c.screw_d, up=False))
        add(f"motor_screws_{name}", m3d.Manifold.batch_boolean(screws, m3d.OpType.Add), C_SCREW,
            (0, 0, -14), "screws", 2)

        hub = (geo._cyl(c.motor_h - (bell_top - c.plate_t) - 0.05, c.prop_hub_d / 2, bell_top + 0.05)
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
        leads_needed[name] = polyline_len(pts)
        add(f"motor_lead_{name}", _tube(pts, c.lead_d), C_WIRE, (0, 0, 25), "wires", 4)

    # --- battery under the hub, its lead and the BT2.0 pair, the strap ---
    bz = -c.battery_h
    add("battery", geo._box(c.battery_l, c.battery_w, c.battery_h, z0=bz), C_BATT, (0, 0, -34), "battery", 5)
    xf = c.battery_l / 2
    zc = bz + c.battery_h / 2
    conn_l = c.bt20_len
    male = geo._box(conn_l, c.bt20_w, c.bt20_h, cx=xf + 4 + conn_l / 2, z0=zc - c.bt20_h / 2)
    female = geo._box(conn_l, c.bt20_w, c.bt20_h, cx=xf + 4 + conn_l * 1.5, z0=zc - c.bt20_h / 2)
    add("battery_lead", _tube([(xf - 0.5, 0, zc), (xf + 4.2, 0, zc)], c.lead_d) + male, C_RED,
        (0, 0, -34), "battery", 5)
    # the AIO's pigtail: from the board's front corner, over the front web, down to
    # the plug - between the two front ducts, where nothing else runs
    corner = c.fc_board_side / math.sqrt(2) if abs(yaw % 90 - 45) < 1e-6 else c.fc_board_side / 2
    xp = xf + 4 + conn_l * 2 + 1.5
    z_over = max(c.web_h, c.topopt_member_h) + c.lead_d
    pig = _tube([(corner + 0.3, 0, pcb_top - c.fc_pcb_t / 2), (corner + 2, 0, z_over),
                 (xp, 0, z_over), (xp, 0, zc), (xf + 4 + conn_l * 2 - 0.3, 0, zc)], c.lead_d)
    add("power_pigtail", pig + female, C_RED, (0, 0, 30), "electronics", 5)

    st, sy = c.strap_t, d["strap_slot_y"]
    sw = c.strap_w
    zb = bz - st
    strap = m3d.Manifold.batch_boolean([
        geo._box(sw, 2 * sy + st, st, z0=c.hub_t),                     # over the hub, under the AIO
        geo._box(sw, 2 * sy + st, st, z0=zb),                          # under the battery
        geo._box(sw, st, c.hub_t + st - zb, cy=sy, z0=zb),              # up through each slot
        geo._box(sw, st, c.hub_t + st - zb, cy=-sy, z0=zb),
    ], m3d.OpType.Add)
    add("battery_strap", strap, C_STRAP, (0, 0, -22), "battery", 5)
    return out, leads_needed


#: Pairs that overlap ON PURPOSE, each with the reason. Matched by part-name
#: prefix. Anything else that shares material is an interference (claim C5).
ALLOWED_OVERLAPS = [
    (("fc_screw_", "frame"), "the AIO screws thread into the 1.1 mm pilots in the posts"),
    (("motor_screws_", "motor_"), "the motor screws thread into the motor's base"),
    (("motor_lead_", "motor_sockets"), "each lead's plug sits in its socket"),
    (("power_pigtail", "flight_controller"), "the pigtail is soldered to the board at the factory"),
    (("battery_lead", "battery"), "the lead comes out of the pack"),
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
