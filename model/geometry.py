"""geometry.py — the printed parts, built from the Config in petgasus.py.

Frame: millimetres. +x forward, +y left, +z up. Origin at the centre of the frame
on the BED: z=0 is the underside of the base plate. The frame is the only printed
part and it prints in the pose it flies in, so the assembly frame IS the print
frame. (A battery tray was the second part until decisions/battery-hangs-under-the-hub-on-a-strap.)

Every dimension here is read from `c` (the Config) or from `d` (the derived dict
petgasus.build() computes before calling in). Nothing is typed twice: if a number
in this file is not 0, 1, 2 or a count, it is a construction detail with its
reason beside it.

Needs manifold3d (watertight booleans, deterministic).
"""
from __future__ import annotations

import math

import manifold3d as m3d

CIRCLE_SEGMENTS = 96
"""Facets on a full circle. 96 keeps the chord error on the 43 mm duct under
0.03 mm — far below one 0.42 mm bead — without making the STL heavy."""


def _cyl(h, r, z0=0.0, seg=CIRCLE_SEGMENTS):
    return m3d.Manifold.cylinder(h, r, r, seg).translate((0, 0, z0))


def _box(sx, sy, sz, cx=0.0, cy=0.0, z0=0.0):
    return m3d.Manifold.cube((sx, sy, sz), True).translate((cx, cy, z0 + sz / 2))


def _bar(p0, p1, width, height, z0=0.0, round_end=True):
    """A flat bar of `width` from p0 to p1 (xy), `height` tall from z0.

    Round at p0; round at p1 too unless round_end is False - a member ending INSIDE
    a duct wall ends flat, because a round cap there poked out of the wall's outer
    face as a 0.2 mm nub."""
    (x0, y0), (x1, y1) = p0, p1
    length = math.hypot(x1 - x0, y1 - y0)
    ang = math.degrees(math.atan2(y1 - y0, x1 - x0))
    body = _box(length, width, height).rotate((0, 0, ang)).translate(
        ((x0 + x1) / 2, (y0 + y1) / 2, z0))
    caps = _cyl(height, width / 2, z0).translate((x0, y0, 0))
    if round_end:
        caps = caps + _cyl(height, width / 2, z0).translate((x1, y1, 0))
    return body + caps


def motor_centres(d):
    a = d["motor_offset"]
    # FL, FR, BL, BR — quadrant order used by every per-motor list in the model
    return [(a, a), (a, -a), (-a, a), (-a, -a)]


def lattice(c, d):
    """The duct lattice's cell layout: dict(z0, z1, n, qh, qv) or None (no lattice).

    Cells tile with horizontal pitch p = hl * tan(theta); take the most cells that
    keep theta at or under the overhang limit, then size them for strut width w.
    Pitch is taken at the INNER face, where the circumference is shortest: sized at
    mid-wall, the struts measured 1.09 mm on the inside.
    """
    r_in = d["duct_r_in"]
    z0 = c.plate_t + c.lattice_margin
    if c.lattice_above_members:
        # start above everything that joins the wall: no joint needs a solid patch
        z0 = max(c.web_h, c.topopt_member_h) + c.lattice_margin
    z1 = d["prop_z"] - c.duct_band_below_prop
    hl = z1 - z0
    w = c.lattice_strut_w
    if not c.duct_lattice or hl <= 3 * w:
        return None
    th_max = math.radians(c.lattice_overhang_deg)
    n = max(6, math.ceil(2 * math.pi * r_in / (hl * math.tan(th_max))))
    th = math.atan(2 * math.pi * r_in / n / hl)
    k = 1 / (1 - w / (hl * math.sin(th)))            # cell half-diagonals = hl/(2k)
    qv = hl / (2 * k)
    return dict(z0=z0, z1=z1, hl=hl, n=n, qv=qv, qh=qv * math.tan(th))


def _duct(c, d, cx, cy, solid_at=(), port_deg=None):
    """One duct: a solid band where the prop runs, a diamond lattice below it.

    Below the prop band the wall is a row of diamond windows over a row of
    half-diamonds standing on the foot band. Every window edge is at most
    `lattice_overhang_deg` from vertical, and every window's TOP is a point: there
    is no flat ceiling anywhere, so nothing needs support and nothing bridges.
    (A row of half-diamonds hanging from the prop band was tried: its flat tops were
    3 mm cantilevered ceilings. Square-diamond cells were tried: their 45.0 deg
    edges sat exactly on the overhang limit.) Struts are `lattice_strut_w` wide,
    measured square to their own length. A solid wall was 14 g of ducts; at 1S
    that is the whole thrust budget.

    `port_deg` (degrees, from this duct's centre) phases the pattern so a full
    window is centred there: the motor's lead leaves the duct through it, toward
    the AIO. Without it, whether a window faced the hub was an accident of n.
    """
    r_in, r_out, h = d["duct_r_in"], d["duct_r_out"], d["duct_h"]
    wall = _cyl(h, r_out) - _cyl(h + 2, r_in, -1)
    lat = lattice(c, d)
    if lat:
        z0, hl, n, qv, qh = lat["z0"], lat["hl"], lat["n"], lat["qv"], lat["qh"]
        r_mid = (r_in + r_out) / 2
        cell = (m3d.Manifold.cube((math.sqrt(2), (r_out - r_in) * 6, math.sqrt(2)), True)
                .rotate((0, 45, 0)).scale((qh, 1, qv)))
        # no window where a spoke or a web meets the wall: the joint gets solid wall,
        # and no member end is left half in a window (sliver faces, 0.17 mm walls)
        half_cell = math.degrees(qh / r_in)
        def clear(ang_deg):
            if c.lattice_above_members:
                return True
            for (a_deg, half_w) in solid_at:
                gap = abs((ang_deg - a_deg + 180) % 360 - 180)
                if gap < half_cell + math.degrees((half_w + c.joint_margin) / r_in):
                    return False
            return True
        phase = (port_deg - 90.0) if port_deg is not None else 0.0
        cuts = []
        for j in range(n):
            # cell centres sit at local +y (90 deg) before the rotation about z
            a_mid = phase + 360.0 * j / n
            a_off = phase + 360.0 * (j + 0.5) / n
            if clear(90 + a_mid):
                cuts.append(cell.translate((0, r_mid, z0 + hl / 2)).rotate((0, 0, a_mid)))
            if clear(90 + a_off):
                cuts.append(cell.translate((0, r_mid, z0)).rotate((0, 0, a_off)))
        lattice_cut = m3d.Manifold.batch_boolean(cuts, m3d.OpType.Add) if cuts else m3d.Manifold()
        # the half-cells at z0 open only upward, into the lattice band
        lattice_cut = lattice_cut ^ _cyl(hl, r_out + 1, z0)
        wall = wall - lattice_cut
    return wall.translate((cx, cy, 0))


def _motor_mount(c, d, cx, cy, toward_centre_deg):
    """Motor seat: a disc with 3 screw holes, a centre relief and a wire notch."""
    seat = _cyl(c.plate_t, d["mount_r"])
    holes = [_cyl(c.plate_t + 2, c.motor_screw_clear_d / 2, -1).translate(
        (c.motor_hole_circle_d / 2 * math.cos(math.radians(toward_centre_deg + 60 + 120 * k)),
         c.motor_hole_circle_d / 2 * math.sin(math.radians(toward_centre_deg + 60 + 120 * k)), 0))
        for k in range(3)]
    relief = _cyl(c.plate_t + 2, c.motor_centre_relief_d / 2, -1)
    return seat, m3d.Manifold.batch_boolean(holes + [relief], m3d.OpType.Add), (cx, cy)


def members(c, d):
    """The plate's members for the chosen layout: one list both the mesh and the FE
    are built from, so the frequency reported is the frame that prints (rule 6).

    Each member: dict(p0, p1, w = flat width at plate_t, rib = None or (q0, q1) the
    stretch carrying a rib_w x member_h rib).

    'arms'   - the hand-drawn first layout: hub-to-motor arms with a rib, and three
               flat spokes per seat. Bounces at ~160 Hz.
    'spoked' - the layout the topology optimiser found (tools/run_topopt.py):
               no hub-to-motor arms at all; each seat hangs on `spoke_count` ribbed
               spokes from its own duct ring, and the hub reaches out to the four
               duct-to-duct webs on short ribbed bridges. The ring of ducts and webs
               is the stiff wheel; the motors are its hubs.
    """
    out = []
    a = d["motor_offset"]
    for (mx, my) in motor_centres(d):
        toward = math.atan2(-my, -mx)
        if c.plate_layout == "arms":
            f = d["rib_end_frac"]
            out.append(dict(p0=(0, 0), p1=(mx, my), w=c.arm_w, rib=((0, 0), (mx * f, my * f)),
                            rib_h=c.rib_h))
            for k in range(3):
                ang = toward + math.pi + (k - 1) * 2 * math.pi / 3
                r = d["duct_r_in"] + 0.5
                out.append(dict(p0=(mx, my), p1=(mx + r * math.cos(ang), my + r * math.sin(ang)),
                                w=c.spoke_w, rib=None))
        elif c.plate_layout == "spoked":
            for k in range(c.spoke_count):
                ang = toward + math.radians(c.spoke_phase_deg) + 2 * math.pi * k / c.spoke_count
                ux, uy = math.cos(ang), math.sin(ang)
                r0 = c.motor_body_d / 2 + c.member_clear
                r1 = d["duct_r_in"] + c.duct_wall / 2          # mid-wall, flat end
                out.append(dict(p0=(mx, my), p1=(mx + r1 * ux, my + r1 * uy), w=c.spoke_w,
                                rib=((mx + r0 * ux, my + r0 * uy), (mx + r1 * ux, my + r1 * uy)),
                                rib_h=c.topopt_member_h - c.plate_t, flat_end=True,
                                duct=(mx, my), ang=math.degrees(ang)))
        else:
            raise ValueError(f"plate_layout must be 'arms' or 'spoked', not {c.plate_layout!r}")
    if c.plate_layout == "spoked":
        # bridges run from each FC post straight out to the web in front of it, ribbed
        # all the way: the rib top (topopt_member_h) stays fc_rib_clear below
        # the AIO, which only overhangs them at its corners, and the strap crosses the
        # hub between the slots, nowhere near them
        s_post = max(math.hypot(*p) for p in d["fc_post_xy"])
        # the rib starts at the post's CENTRE and runs through it (the post is taller):
        # started at the post's surface, its round end was tangent to the post and the
        # boolean left sliver triangles (cad.degenerate_faces)
        r0 = s_post
        for ang in (0, 90, 180, 270):
            ux, uy = math.cos(math.radians(ang)), math.sin(math.radians(ang))
            # flat ends on the web's centre line: a round cap ran past the web into the
            # V between two ducts and left 0.17 mm walls there
            out.append(dict(p0=(s_post * ux, s_post * uy), p1=(a * ux, a * uy), w=c.bridge_w,
                            rib=((r0 * ux, r0 * uy), (a * ux, a * uy)),
                            rib_h=c.topopt_member_h - c.plate_t, flat_end=True))
    return out


def frame(c, d):
    """The one-piece frame: hub, plate members, motor seats, ducts, webs, FC posts,
    strap slots. The plate members come from members(c, d)."""
    solids, cuts = [], []
    centres = motor_centres(d)

    # hub plate: hub_t thin - it carries the strap and shields the AIO, not the arms
    solids.append(m3d.Manifold.extrude(_hub_cs(c, d), c.hub_t))

    mems = members(c, d)
    for mem in mems:
        flat = mem.get("flat_end", False)
        solids.append(_bar(mem["p0"], mem["p1"], mem["w"], c.plate_t, round_end=not flat))
        if mem["rib"]:
            solids.append(_bar(mem["rib"][0], mem["rib"][1], c.rib_w, c.plate_t + mem["rib_h"],
                               round_end=not flat))

    for (mx, my) in centres:
        toward = math.degrees(math.atan2(-my, -mx))
        seat, holes, _ = _motor_mount(c, d, mx, my, toward)
        solids.append(seat.translate((mx, my, 0)))
        cuts.append(holes.translate((mx, my, 0)))
        if c.foot_w > c.duct_wall:
            # a flange inside the duct's foot; at foot_w == duct_wall it would be the
            # wall itself, and two coincident cylinders export as non-manifold edges
            solids.append((_cyl(c.plate_t, d["duct_r_out"]) - _cyl(c.plate_t + 2, d["duct_r_out"] - c.foot_w, -1))
                          .translate((mx, my, 0)))
        # angles (deg, from this duct's centre) where something joins the wall: its
        # spokes, and the webs to its two neighbours
        solid_at = [(m_["ang"], max(m_["w"], c.rib_w) / 2) for m_ in mems if m_.get("duct") == (mx, my)]
        solid_at += [(0.0 if mx < 0 else 180.0, c.duct_wall / 2), (90.0 if my < 0 else 270.0, c.duct_wall / 2)]
        solids.append(_duct(c, d, mx, my, solid_at, port_deg=toward))

    # webs joining neighbouring ducts across the gap between them: four ducts become
    # one closed ring, which is most of the frame's stiffness for little mass
    a = d["motor_offset"]
    for (x0, y0), (x1, y1) in (((a, a), (a, -a)), ((-a, a), (-a, -a)),
                               ((a, a), (-a, a)), ((a, -a), (-a, -a))):
        ux, uy = (x1 - x0) / (2 * a), (y1 - y0) / (2 * a)
        r = d["duct_r_out"] - c.duct_wall / 2
        solids.append(_bar((x0 + ux * r, y0 + uy * r), (x1 - ux * r, y1 - uy * r),
                           c.duct_wall, c.web_h))

    # FC posts, on the 45-deg-rotated hole square when fc_yaw_deg is 45
    for (px, py) in d["fc_post_xy"]:
        solids.append(_cyl(c.plate_t + c.fc_post_h, c.fc_post_od / 2).translate((px, py, 0)))
        cuts.append(_cyl(c.plate_t + c.fc_post_h + 2, c.fc_pilot_d / 2, -1)
                    .translate((px, py, 0)))

    # battery strap: the pack hangs under the hub along x, and a 10 mm strap wraps
    # it across y, up through one slot, over the hub under the AIO, down the other
    for sy in (1, -1):
        cuts.append(_box(d["strap_slot_len"], c.strap_slot_w, c.plate_t + 2,
                         cy=sy * d["strap_slot_y"], z0=-1))

    body = m3d.Manifold.batch_boolean(solids, m3d.OpType.Add)
    return body - m3d.Manifold.batch_boolean(cuts, m3d.OpType.Add)


def prop_sweeps(c, d):
    """The volume each spinning prop sweeps, with its tip gap and a height band.

    Not cut from the frame: a frame that intrudes here is a design error, and
    cutting it away would hide the error. build() intersects this with the frame
    and publishes the overlap for a gate to refuse.
    """
    return m3d.Manifold.batch_boolean(
        [_cyl(2 * c.prop_sweep_half_h, d["prop_r"], d["prop_z"] - c.prop_sweep_half_h)
         .translate((mx, my, 0)) for (mx, my) in motor_centres(d)], m3d.OpType.Add)


def _hub_cs(c, d):
    """The hub plate's outline: hull of the post discs, less four lightening holes.

    The holes sit in the four quadrants between the post-to-post bars, clear of
    the strap's path (|x| < strap_w/2 + 1, between the slots) by hub_hole_margin.
    The strap slots are cut once, through everything, in frame(); cutting them here
    as well left two coincident slot walls - non-manifold edges in the export.
    """
    hub = m3d.CrossSection.batch_hull(
        [m3d.CrossSection.circle(c.fc_post_od / 2 + c.hub_margin, CIRCLE_SEGMENTS).translate((px, py))
         for (px, py) in d["fc_post_xy"]])
    if c.hub_holes:
        reach = max(abs(px) + abs(py) for (px, py) in d["fc_post_xy"]) \
            + (c.fc_post_od / 2 + c.hub_margin) * math.sqrt(2)          # diamond |x|+|y| <= reach
        x0 = d["strap_slot_len"] / 2 + c.hub_hole_margin                  # clear of the strap path
        y0 = c.hub_hole_margin
        top = reach - c.hub_hole_margin * math.sqrt(2)
        if top - x0 - y0 > 2.0:
            tri = m3d.CrossSection([[(x0, y0), (top - y0, y0), (x0, top - x0)]])
            holes = [tri.mirror((1, 0)) if sx < 0 else tri for sx in (1, -1)]
            holes = [h.mirror((0, 1)) if sy < 0 else h for h in holes for sy in (1, -1)]
            hub = hub - m3d.CrossSection.batch_boolean(holes, m3d.OpType.Add)
    return hub


def _fixed_cs(c, d):
    """2D footprint of everything the optimiser may not move (seats, ducts, webs, hub)."""
    parts = [_hub_cs(c, d)]
    a = d["motor_offset"]
    for (mx, my) in motor_centres(d):
        parts.append(m3d.CrossSection.circle(d["mount_r"], CIRCLE_SEGMENTS).translate((mx, my)))
        parts.append((m3d.CrossSection.circle(d["duct_r_out"], CIRCLE_SEGMENTS) -
                      m3d.CrossSection.circle(d["duct_r_in"], CIRCLE_SEGMENTS)).translate((mx, my)))
    for (x0, y0), (x1, y1) in (((a, a), (a, -a)), ((-a, a), (-a, -a)), ((a, a), (-a, a)), ((a, -a), (-a, -a))):
        L = math.hypot(x1 - x0, y1 - y0)
        parts.append(m3d.CrossSection.square((L, c.duct_wall), True)
                     .rotate(math.degrees(math.atan2(y1 - y0, x1 - x0)))
                     .translate(((x0 + x1) / 2, (y0 + y1) / 2)))
    return m3d.CrossSection.batch_boolean(parts, m3d.OpType.Add)


def plate_cs_from_density(c, d, grid, rho):
    """The optimiser's layout as a clean 2D outline, ready to extrude.

    1. the rho = 0.5 contour (field padded with zeros so every contour closes);
    2. an OPEN at min_member_w/2 - every member narrower than min_member_w is
       deleted rather than printed as a thread (the first extraction printed the
       grey spokes as dashes);
    3. a CLOSE at topopt_smooth - rounds re-entrant corners;
    4. only the part connected to the fixed structure is kept: a member that the
       open cut loose is debris on the bed, not structure.
    """
    import contourpy
    import numpy as np

    n = grid.n
    field = np.zeros((n + 2, n + 2))
    field[1:-1, 1:-1] = rho.reshape(n, n)
    coords = (np.arange(n + 2) - 0.5) * grid.h - grid.half
    gen = contourpy.contour_generator(coords, coords, field, fill_type="OuterOffset")
    polys = []
    for verts, offsets in zip(*gen.filled(0.5, 2.0)):
        for i in range(len(offsets) - 1):
            ring = verts[offsets[i]:offsets[i + 1]]
            polys.append([(float(x), float(y)) for x, y in ring[:-1]])
    cs = m3d.CrossSection(polys, m3d.FillRule.EvenOdd)
    r_open = c.min_member_w / 2
    cs = cs.offset(-r_open, m3d.JoinType.Round).offset(r_open, m3d.JoinType.Round)
    s = c.topopt_smooth
    cs = cs.offset(s, m3d.JoinType.Round).offset(-s, m3d.JoinType.Round)
    fixed = _fixed_cs(c, d)
    whole = cs + fixed
    comps = sorted(whole.decompose(), key=lambda k: -k.area())
    keep = comps[0]
    cs = (cs ^ keep).simplify(0.02)
    return cs


def plate_from_density(c, d, grid, rho):
    """Extrude the clean outline: plate_t everywhere, members deep where allowed.

    Deep (topopt_member_h) except within member_clear of a motor base and of the
    AIO footprint, where the plate stays plate_t - the same zones the FE used.
    """
    cs = plate_cs_from_density(c, d, grid, rho)
    flat = [m3d.CrossSection.circle(c.motor_body_d / 2 + c.member_clear, CIRCLE_SEGMENTS).translate((mx, my))
            for (mx, my) in motor_centres(d)]
    half = c.fc_board_side + 2 * c.member_clear
    flat.append(m3d.CrossSection.square((half, half), True).rotate(c.fc_yaw_deg))
    deep_cs = cs - m3d.CrossSection.batch_boolean(flat, m3d.OpType.Add)
    plate = m3d.Manifold.extrude(cs, c.plate_t)
    deep = m3d.Manifold.extrude(deep_cs, c.topopt_member_h)
    return plate + deep, cs
