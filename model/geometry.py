"""geometry.py — the printed frame: the topology proposal's load paths as one smooth
solid, fused to the exact features the bought parts need.

Same frame as petgasus.py: millimetres, +x forward, +y left, +z up, z=0 under the
motor seats.

How the solid is made (frame()):
  1. The proposer's density field (model/topopt3d.py's problem, solved by the
     solid-fea pack's fea.topopt3d) is resampled onto a fine grid and blurred, so
     its cells (topo_h) become round limbs instead of stairs. Where a limb meets a
     seat, guard arc or post, the field is carried into that feature's cells, so the
     limb reaches it instead of stopping a cell short.
  2. The exact features (motor seats, guard arcs and the links between them, FC
     posts, the strap's saddle) are added as signed distance functions with a
     SMOOTH union of radius
     surface_fillet_mm: every joint gets a fillet. The reddit review's sharpest
     point was the opposite —
     flat planks butting into each other with no gusset, a stress concentrator at
     every joint.
  3. Everything that must be empty is cut from that function (topopt3d.keepouts:
     the props' bands, the motor bodies, the board, the battery, the leads, the
     screwdriver's way to each motor screw, the space above the guards), grown
     by surface_clearance_mm, the exact features go back in sharp, and the
     holes come out. Every section thinner than the opening keeps is grown
     where it can (over the props' discs only within the plan the frame
     already covers there); then whatever is still thinner than 2 x
     surface_open_mm (the cuts' feathered edges and lips, and what could not
     grow) is opened away, all but the hub. drawn() puts the exact features
     and holes back exact on that. On cad.wall_thickness's ray from every
     face, all but a few corner facets read at least its 1.26 mm; the level
     set rounds the sharp corners of exact parts there (see
     decisions/thin-walls-thickened-before-the-drawing-is-opene.json).
  4. manifold3d's level set turns that one function into a closed, manifold mesh.

One function and one level set, no mesh booleans: booleans between the field's
surface and the exact solids left 0.01 mm skins where a limb grazed a keep-out
and pinched vertices 0.00004 mm apart where a fillet grazed a guard, which the
print mesh checks (cad.wall_thickness, cad.degenerate_faces) rightly refused.
The planes a part sits on (the seats' and posts' tops) come out exact, because
a linear function's level set is exact; sharp edges are rounded by under half
an edge. CalculiX's surface is the same drawing at its own edge length.

The surface is a function of the field file and the Config fields above, and it
takes ~30 s, so frame() caches it by a hash of both (build/frame_cache/).
"""
from __future__ import annotations

import hashlib
import json
import math
import os

import manifold3d as m3d
import numpy as np

CIRCLE_SEGMENTS = 96


def _cyl(h, r, z0=0.0, seg=CIRCLE_SEGMENTS):
    return m3d.Manifold.cylinder(h, r, r, seg).translate((0, 0, z0))


def _box(sx, sy, sz, cx=0.0, cy=0.0, z0=0.0):
    return m3d.Manifold.cube((sx, sy, sz), True).translate((cx, cy, z0 + sz / 2))


def _ring(r_in, r_out, z0, z1, seg=CIRCLE_SEGMENTS):
    return _cyl(z1 - z0, r_out, z0, seg) - _cyl(z1 - z0 + 2, r_in, z0 - 1, seg)


def motor_centres(d):
    return [tuple(p) for p in d["motor_xy"]]


def motor_screw_xy(c, mx, my):
    """The three M1.4 holes of one seat: one pointing away from the hub, two at
    +-60 deg either side of the hub direction, so the lead (which leaves the
    motor's base between two screws) points at the board."""
    toward = math.atan2(-my, -mx)
    r = c.motor_hole_circle_d / 2
    return [(mx + r * math.cos(toward + math.radians(60 + 120 * k)),
             my + r * math.sin(toward + math.radians(60 + 120 * k))) for k in range(3)]


# --------------------------------------------------------------------------- #
# exact features
# --------------------------------------------------------------------------- #
def seats(c, d):
    return [_cyl(c.plate_t, d["mount_r"]).translate((mx, my, 0)) for (mx, my) in motor_centres(d)]


def guards(c, d):
    """Each prop's guard arc: a solid band with no windows, guard_h tall, centred
    on the prop plane (the review: windows make propwash and ADD weight), round
    guard_arc_deg of the prop facing away from the frame's centre. The rest of
    each ring is the optimiser's to draw."""
    out = []
    for (mx, my) in motor_centres(d):
        ring = _ring(d["guard_r_in"], d["guard_r_out"], d["guard_z0"], d["guard_z1"])
        if c.guard_arc_deg < 360:
            ring = ring ^ _wedge(math.atan2(my, mx), math.radians(c.guard_arc_deg / 2), d["guard_r_out"] + 2,
                                 d["guard_z0"] - 1, d["guard_z1"] + 1)
        out.append(ring.translate((mx, my, 0)))
    return out


#: Each side of the frame by its outward direction (+x forward, +y left).
SIDES = {"front": (1.0, 0.0), "back": (-1.0, 0.0), "left": (0.0, 1.0), "right": (0.0, -1.0)}


def _links(c, d):
    """[(a, b, ux, uy, nx, ny, length)] for each side in c.guard_link_sides: the
    two neighbouring motors on that side (the square's side, not a diagonal), the
    unit vector from a to b, the unit normal pointing away from the frame's centre,
    and the distance between them."""
    ms = motor_centres(d)
    pairs = [(a, b) for i, a in enumerate(ms) for b in ms[i + 1:]]
    short = min(math.dist(a, b) for a, b in pairs)
    out = []
    for a, b in pairs:
        length = math.dist(a, b)
        if length > short + 1e-6:
            continue
        ux, uy = (b[0] - a[0]) / length, (b[1] - a[1]) / length
        nx, ny = uy, -ux
        if nx * (a[0] + b[0]) + ny * (a[1] + b[1]) < 0:
            nx, ny = -nx, -ny
        side = max(SIDES, key=lambda k: SIDES[k][0] * nx + SIDES[k][1] * ny)
        if side in c.guard_link_sides:
            out.append((a, b, ux, uy, nx, ny, length))
    return out


#: mm: where the band leaves its arc, the arc curves on under it and the two leave
#: a slot between them that widens from nothing; the band is drawn on down to the
#: arc until the slot is this wide (_link_fill)
LINK_SLOT_MM = 2.0


def _link_fill(d):
    """(s0, s1, rc): along a band from a motor's centre line, the slot between the
    band's inner face and its arc's outer face opens at s0 and is LINK_SLOT_MM
    wide at s1; the band is filled down to a circle of radius rc there, a hair
    inside the arc's outer face so the two overlap."""
    rc = d["guard_r_out"] - 0.05
    return (math.sqrt(rc ** 2 - d["guard_r_in"] ** 2),
            math.sqrt(rc ** 2 - (d["guard_r_in"] - LINK_SLOT_MM) ** 2), rc)


def guard_links(c, d):
    """The rim's bridges on the sides in Config.guard_link_sides: between the two
    neighbouring guards on that side, a straight band of the arcs' own section
    along their outer tangent, from one motor's centre line to the other's. Each
    end meets its arc square at the arc's outermost point, so the band continues
    the arc's faces. Past that point the arc curves on under the band, and the
    slot between them opens from nothing: the band fills it down to the arc
    until it is LINK_SLOT_MM wide (_link_fill). Left open, the field filled its
    tip partly, and the slot came out 0.3-0.5 mm wide, under the drawing's grid,
    with a skin over it 0.11 mm thick (C7). Drawn in the frame's filament even
    when the arcs are a second one."""
    out = []
    s0, s1, rc = _link_fill(d)
    ri, ro = d["guard_r_in"], d["guard_r_out"]
    for a, b, ux, uy, nx, ny, length in _links(c, d):
        arc = [(s, math.sqrt(rc ** 2 - s ** 2)) for s in np.linspace(s0, s1, 12)]
        st = ([(0.0, ro), (0.0, ri)] + arc + [(s1, ri), (length - s1, ri)]
              + [(length - s, t) for s, t in reversed(arc)] + [(length, ri), (length, ro)])
        pts = [(a[0] + s * ux + t * nx, a[1] + s * uy + t * ny) for s, t in st]
        area = sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(pts, pts[1:] + pts[:1]))
        if area < 0:
            pts.reverse()                              # counter-clockwise, as CrossSection wants
        out.append(m3d.CrossSection([pts]).extrude(d["guard_z1"] - d["guard_z0"]).translate((0, 0, d["guard_z0"])))
    return out


def _wedge(mid, half, r, z0, z1, seg=CIRCLE_SEGMENTS):
    """A pie slice about the z axis: angles mid +- half, radius r, z0 to z1."""
    n = max(2, int(seg * half / math.pi))
    pts = [(0.0, 0.0)] + [(r * math.cos(mid - half + 2 * half * k / n), r * math.sin(mid - half + 2 * half * k / n))
                          for k in range(n + 1)]
    return m3d.CrossSection([pts]).extrude(z1 - z0).translate((0, 0, z0))


def posts(c, d):
    return [_cyl(d["z_post_top"], c.fc_post_od / 2).translate((px, py, 0)) for (px, py) in d["fc_post_xy"]]


def saddle(c, d):
    """The strap's saddle (topopt3d.saddle_cells): the hub between the slots."""
    return [_box(d["strap_slot_len"], 2 * (d["strap_slot_y"] - c.strap_slot_w / 2), c.hub_t)]


def exact_features(c, d):
    """Everything drawn exactly: seats, guard arcs and their links, posts, saddle."""
    return m3d.Manifold.batch_boolean(seats(c, d) + guards(c, d) + guard_links(c, d) + posts(c, d) + saddle(c, d),
                                      m3d.OpType.Add)


def holes(c, d):
    """Through-cuts made last: motor screw clearance, the shaft's relief, the FC
    posts' pilots, the strap slots."""
    cuts = []
    for (mx, my) in motor_centres(d):
        for (hx, hy) in d["motor_screw_xy"][(mx, my)]:
            cuts.append(_cyl(c.plate_t + 2, c.motor_screw_clear_d / 2, -1).translate((hx, hy, 0)))
        cuts.append(_cyl(c.plate_t + 2, c.motor_centre_relief_d / 2, -1).translate((mx, my, 0)))
    for (px, py) in d["fc_post_xy"]:
        cuts.append(_cyl(d["z_post_top"] + 2, c.fc_pilot_d / 2, -1).translate((px, py, 0)))
    for sy in (1, -1):
        cuts.append(_box(d["strap_slot_len"], c.strap_slot_w, d["z_post_top"] + 40,
                         cy=sy * d["strap_slot_y"], z0=-20))
    return m3d.Manifold.batch_boolean(cuts, m3d.OpType.Add)


# --------------------------------------------------------------------------- #
# the field -> one smooth signed function -> a manifold
# --------------------------------------------------------------------------- #
def _smax(a, b, k):
    """Polynomial smooth maximum (union, positive inside), blend width k."""
    if k <= 0:
        return np.maximum(a, b)
    h = np.maximum(k - np.abs(a - b), 0.0) / k
    return np.maximum(a, b) + h * h * k / 4.0


def _reach_into_features(rho, region):
    """Design densities with each passive-solid cell set to the densest of its six
    design neighbours: a limb that ends at a seat, guard or post continues into it
    and meets the exact feature, instead of stopping one cell short. The guard
    arcs' cells get it too, so the resampled field, and the fillet's smooth union
    after it, draw each arc 0.2-0.4 mm proud of its exact faces; only the prop's
    keep-out and the cap over the guards stop it (petgasus.frame_solids)."""
    out = np.where(region == 0, rho, 0.0).astype(np.float32)
    nb = np.zeros_like(out)
    for axis in range(3):
        for shift in (1, -1):
            nb = np.maximum(nb, np.roll(out, shift, axis=axis))
    return np.where(region == 1, nb, out)


def _field_sdf(c, d, rho, g, region, step):
    """The smooth signed function of the whole body (positive inside) on a grid of
    spacing `step`: the field, resampled and blurred, smooth-unioned with the
    exact features' distance functions. Returns (F (nz, ny, nx), lo, n, axes)."""
    from scipy import ndimage
    field = _reach_into_features(rho, region)
    lo = np.array(g["origin"], float) - 1.0
    hi = lo + 2.0 + np.array([g["nx"], g["ny"], g["nz"]]) * g["h"]
    n = np.ceil((hi - lo) / step).astype(int) + 1
    n += (n - 1) % 2                   # an even number of steps: see _level_set
    xs, ys, zs = (np.float32(lo[k]) + np.float32(step) * np.arange(n[k], dtype=np.float32) for k in range(3))
    # trilinear resample of the cell-centred densities onto the fine grid (an
    # axis-aligned scale and shift: fine index o -> cell index (lo - origin)/h - 1/2
    # + o * step/h), then a Gaussian blur
    offset = [(lo[k] - g["origin"][k]) / g["h"] - 0.5 for k in (2, 1, 0)]
    fine = ndimage.affine_transform(field, [step / g["h"]] * 3, offset=offset, output_shape=(n[2], n[1], n[0]),
                                    order=1, mode="constant", cval=0.0).astype(np.float32)
    fine = ndimage.gaussian_filter(fine, c.surface_blur_mm / step).astype(np.float32)
    F = (fine - c.surface_iso) * np.float32(c.surface_scale_mm)
    axes = (zs[:, None, None], ys[None, :, None], xs[None, None, :])
    F = _smax(F, _features_sdf(c, d, *axes), c.surface_fillet_mm).astype(np.float32)
    return F, lo, n, axes


def _features_sdf(c, d, Z, Y, X):
    feat = np.full(np.broadcast(Z, Y, X).shape, -1e3, np.float32)
    for (mx, my) in motor_centres(d):
        r = np.hypot(X - mx, Y - my)
        seat = np.minimum(np.minimum(d["mount_r"] - r, Z - 0.0), c.plate_t - Z)
        ring = np.minimum(np.minimum(r - d["guard_r_in"], d["guard_r_out"] - r),
                          np.minimum(Z - d["guard_z0"], d["guard_z1"] - Z))
        if c.guard_arc_deg < 360:
            # the arc: the ring between two rays from the motor; up to 180 deg the
            # wedge is where both rays' inner half-planes agree, past it where either does
            a, half = math.atan2(my, mx), math.radians(c.guard_arc_deg / 2)
            n1 = np.float32(math.sin(a + half)) * (X - mx) - np.float32(math.cos(a + half)) * (Y - my)
            n2 = -np.float32(math.sin(a - half)) * (X - mx) + np.float32(math.cos(a - half)) * (Y - my)
            ring = np.minimum(ring, np.minimum(n1, n2) if half <= math.pi / 2 else np.maximum(n1, n2))
        feat = np.maximum(feat, np.maximum(seat, ring))
    links = _links(c, d)
    if links:
        zband = np.minimum(Z - d["guard_z0"], d["guard_z1"] - Z)
        s0, s1, rc = (np.float32(v) for v in _link_fill(d))
        for a, b, *axes in links:
            ux, uy, nx, ny, length = (np.float32(v) for v in axes)
            s = (X - np.float32(a[0])) * ux + (Y - np.float32(a[1])) * uy
            t = (X - np.float32(a[0])) * nx + (Y - np.float32(a[1])) * ny
            band = np.minimum(np.minimum(s, length - s), np.minimum(t - d["guard_r_in"], d["guard_r_out"] - t))
            for e in (s, length - s):                  # the slot's tip at each end, filled (guard_links)
                band = np.maximum(band, np.minimum(np.minimum(e - s0, s1 - e),
                                                   np.minimum(np.minimum(t, d["guard_r_out"] - t), np.hypot(e, t) - rc)))
            feat = np.maximum(feat, np.minimum(band, zband))
    for (px, py) in d["fc_post_xy"]:
        r = np.hypot(X - px, Y - py)
        feat = np.maximum(feat, np.minimum(np.minimum(c.fc_post_od / 2 - r, Z - 0.0), d["z_post_top"] - Z))
    feat = np.maximum(feat, _box_sdf(X, Y, Z, 0, 0, d["strap_slot_len"] / 2, d["strap_slot_y"] - c.strap_slot_w / 2,
                                     0.0, c.hub_t))
    return feat.astype(np.float32)


def _level_set(F, lo, n, step, edge):
    F[:, :, 0] = F[:, :, -1] = F[:, 0, :] = F[:, -1, :] = F[0] = F[-1] = -1.0   # closed at the box
    inv = 1.0 / step
    nx, ny, nz = n

    def sdf(x, y, z):
        i = int((x - lo[0]) * inv + 0.5)
        j = int((y - lo[1]) * inv + 0.5)
        k = int((z - lo[2]) * inv + 0.5)
        if i < 0 or j < 0 or k < 0 or i >= nx or j >= ny or k >= nz:
            return -1.0
        return float(F[k, j, i])

    # manifold spaces its lattice at (bounds / floor(bounds / edge)), so it lands
    # on this grid (step = edge / 2) only when each axis spans an even number of
    # steps, and a hair over, so the floor cannot round down. Off the grid, the
    # nearest-point lookup above moved flat faces by up to half a step: the FC
    # posts' tops came out 0.19 mm low at a 0.8 mm edge, and the structure gates
    # found nothing to hold the frame by.
    return m3d.Manifold.level_set(sdf, [*lo, *(lo + step * (n - 1) + 1e-6)], edge, 0.0)


def _open(F, step, r, spare=None):
    """F with every part thinner than 2r removed, except where `spare` is
    positive or within r plus half a step of it, and thick faces skimmed by
    under half a step: a morphological opening by a ball of radius r mm used
    only as a MASK. Depth is
    measured to the surface (the distance to the nearest outside sample, less
    half a step), the eroded core is grown back by r plus half a step, and F is
    cut (by that grown core's own distance) only where the grown core does not
    reach.
    The first version took min(F, D) everywhere, and D's grid-quantised surface
    cut into thick limbs too: the CalculiX surface (a 0.4 mm step) came out 4-6 %
    thinner than the printed one (0.25 mm), so the checks judged a weaker frame.
    Grown back by r plus a step and a half, the core kept every nub and fringe
    within that of a thick part: on one thickened drawing opened at 0.6 mm,
    5.9 mm^2 of faces read under cad.wall_thickness's 1.26 mm, 3.4 with a
    step, 1.9 with half a step, which took 0.2 g more of the frame.
    What counts as thin still moves by a step with the grid, so drawn() opens
    on the print's grid only and resamples the result for every other edge."""
    from scipy import ndimage
    if r <= 0:
        return F
    depth = ndimage.distance_transform_edt(F > 0, sampling=step) - 0.5 * step
    core = depth > r
    if spare is not None:
        core |= spare > 0
    D = (r + 0.5 * step) - ndimage.distance_transform_edt(~core, sampling=step)
    if spare is not None:
        D = np.maximum(D, spare)
    return np.where(D > 0, F, np.minimum(F, D)).astype(np.float32)


#: mm _thicken's balls reach past the opening's keep radius (_opened), so their
#: centres stay in its core
THICKEN_MARGIN_MM = 0.075
#: mm _thicken grows from the body as first drawn, at most. Unbounded, when the
#: thickening ran after a 0.3 mm opening, a ball grown against a keep-out's wall left
#: a new thin edge on it, the next pass grew another there, and a fin 0.57 mm thick
#: climbed 3.5 mm up each motor's keep-out
THICKEN_REACH_MM = 1.0
#: mm from a cut's face within which _thicken takes a ray's end to lie on it
ON_CUT_MM = 0.1
#: mm off an exact feature's face within which _thicken takes a ray's end to lie on it:
#: the fillet stands up to ~0.2 mm off the guard bands' faces
ON_EXACT_MM = 0.3


def _thicken(F, lo, step, find, radius, keep, room, exact, passes=8):
    """F (the body as drawn, positive inside) with every section thinner than
    `find` grown where it can: about 2 x `radius` thick, nowhere `keep` is
    negative (the keep-outs and the holes), never more than THICKEN_REACH_MM
    from F, and over the props' discs only within the plan `room` gives it
    (_shadow_room). It takes nothing away.

    From each point on the surface (the grid points within a step of it, moved
    onto it along the gradient) a ray goes inward and stops where it leaves the
    body: the wall cad.wall_thickness measures there. Where that is under
    `find`, a ball of `radius` goes on the ray: at its midpoint, so a free
    section grows on both sides, or one radius in from whichever end lies on a
    cut's face, so a section a cut left grows away from the cut. Where the ball
    would not fit the room, a vertical segment as long as the ball is wide goes
    in its place, no higher in value than its column was before, so the
    column's edge does not move: there a section grows up and down only. A
    section cut on both faces has no room and is left as it is (grown anyway,
    its balls crept sideways a ball a pass, and left a 0.07 mm fin where the
    creep met a post), and so is one between two faces of `exact` (the exact
    features' function), which drawn() puts back at its own size. Each pass
    finds the edges the last one left; they stop when none grows, or after
    `passes`.

    What it grows: the sheets the field's grey top cell layer draws, 0.35 mm
    where they join the front and back limbs to the rim, and the sheets the
    props' keep-out leaves of the cell layer under it (its floor at z 10.0
    halves a 1.33 mm cell), 0.47-0.61 mm under the guard arcs. Grown after the
    opening instead of before, the 0.35 mm sheets came with the pinholes the
    opening had punched through them, and their rims stayed 0.5-0.6 mm."""
    from scipy import ndimage
    colmax = F.max(axis=0)
    keep = np.minimum(keep, np.float32(THICKEN_REACH_MM)
                      - ndimage.distance_transform_edt(F <= 0, sampling=step).astype(np.float32))
    for _ in range(passes):
        grown = _thicken_pass(F, lo, step, find, radius, keep, room, exact, colmax)
        if grown is None:
            break
        F = grown
    return F


def _thicken_pass(F, lo, step, find, radius, keep, room, exact, colmax):
    """One pass of _thicken: the grown F, or None when nothing grew."""
    from scipy import ndimage
    gz, gy, gx = np.gradient(F, step)
    g = np.sqrt(gx * gx + gy * gy + gz * gz)
    near = (F > 0) & (F < step * g) & (g > 1e-6)
    k, j, i = np.nonzero(near)
    if not len(k):
        return None
    u = np.stack([gx[k, j, i], gy[k, j, i], gz[k, j, i]], axis=1) / g[k, j, i][:, None]   # inward
    p = (np.stack([i, j, k], axis=1) * step + lo) - u * (F[k, j, i] / g[k, j, i])[:, None]
    del gx, gy, gz, g

    def at(A, q, cval):
        return ndimage.map_coordinates(A, [(q[:, 2] - lo[2]) / step, (q[:, 1] - lo[1]) / step,
                                           (q[:, 0] - lo[0]) / step], order=1, mode="constant", cval=cval)
    thick = np.full(len(p), np.inf)
    entered = np.zeros(len(p), bool)
    for s in np.arange(0.01, find + 0.02, 0.02):
        inn = at(F, p + u * s, -1.0) > 0
        left = entered & ~inn & ~np.isfinite(thick)
        thick[left] = s
        entered |= inn
    thin = thick < find
    p, u, thick = p[thin], u[thin], thick[thin]
    exit_ = p + u * thick[:, None]
    cut_far = at(keep, exit_, 1.0) < ON_CUT_MM           # the far face is a cut's: grow back from it
    cut_near = at(keep, p, 1.0) < ON_CUT_MM              # this face is a cut's: grow in from it
    # a section between two faces of the exact features is theirs, drawn to its size (the guard
    # arcs' and links' 1.4 mm wall, the saddle's 1.4 mm) and put back exact by drawn(); with the
    # fillet the guard band is 1.75 mm across at its foot, and grown there, its ball reached 0.65 mm
    # under it, lengthening the guards' printed height (C13) from 4.15 mm to 4.6
    own = (at(exact, exit_, -1.0) > -ON_EXACT_MM) & (at(exact, p, -1.0) > -ON_EXACT_MM)
    free = ~(cut_far & cut_near) & ~own
    if not free.any():
        return None
    p, u, thick, exit_, cut_far, cut_near = p[free], u[free], thick[free], exit_[free], cut_far[free], cut_near[free]
    r = radius
    centre = p + u * (thick / 2)[:, None]
    centre[cut_far] = exit_[cut_far] - u[cut_far] * r
    centre[cut_near] = p[cut_near] + u[cut_near] * r
    idx = np.rint((centre - lo) / step).astype(int)
    idx = idx[np.all((idx >= 0) & (idx < np.array(F.shape[::-1])), axis=1)]
    fits = room[idx[:, 1], idx[:, 0]] >= r
    new = np.full(F.shape, -1e3, np.float32)
    for sel, sampling in ((fits, step), (~fits, (step, 1e3, 1e3))):    # balls; vertical segments
        if not sel.any():
            continue
        mark = np.zeros(F.shape, bool)
        mark[idx[sel, 2], idx[sel, 1], idx[sel, 0]] = True
        grow = r - ndimage.distance_transform_edt(~mark, sampling=sampling).astype(np.float32)
        new = np.maximum(new, np.minimum(grow, room[None] if sel is fits else colmax[None]))
    new = np.minimum(new, keep)
    if not (new > F).any():
        return None
    return np.maximum(F, new).astype(np.float32)


def _shadow_room(c, d, F, step, Y, X):
    """Where _thicken may grow outward, in plan (mm, positive where it may):
    anywhere clear of the props' discs (outside each motor's own shadow, as C14
    counts them), and on a disc only over what the frame F already covers there.
    Both hold back two steps, as far as the level set can carry a surface from
    the grid point that moved it. On a disc, where a ball would not fit that, a
    section grows up and down instead, and the frame's shadow on the props
    (C14) is no more than the field drew. Grown freely, the sheets under the
    guard arcs spread into the discs and the shadow went from 14.8 % to
    15.06 %, over C14's 15."""
    from scipy import ndimage
    inside = ndimage.distance_transform_edt((F > 0).any(axis=0), sampling=step)   # to the nearest bare column
    r0 = c.motor_body_d / 2 + c.motor_clear
    disc = np.full(inside.shape, -1e3, np.float32)
    for (mx, my) in motor_centres(d):
        r = np.hypot(X - mx, Y - my)[0]
        disc = np.maximum(disc, np.minimum(r - r0, d["prop_r"] - r))
    return (np.maximum(-disc, inside) - 2 * step).astype(np.float32)


def _hub_sdf(c, d, Z, Y, X):
    """The hub, positive inside: the board's footprint between z = 0 and hub_t.
    Over the battery's and the strap's keep-outs it is the plate they and the
    board's leave exactly hub_t thick (_keepout_sdf); elsewhere in the
    footprint the field's limbs run on below it."""
    gclr = c.fc_board_clear
    tip = c.fc_arm_tip_r + gclr
    return np.maximum(_box_sdf(X, Y, Z, 0, 0, tip, c.fc_arm_w_fb / 2 + gclr, 0.0, c.hub_t),
                      _box_sdf(X, Y, Z, 0, 0, c.fc_arm_w_side / 2 + gclr, tip, 0.0, c.hub_t))


def _smin(a, b, k):
    """Polynomial smooth minimum (intersection, positive inside), blend width k."""
    if k <= 0:
        return np.minimum(a, b)
    h = np.maximum(k - np.abs(a - b), 0.0) / k
    return np.minimum(a, b) - h * h * k / 4.0


def _keepout_sdf(c, d, Z, Y, X):
    """topopt3d.keepouts as one function, positive inside any keep-out, each
    keep-out's edges rounded by surface_cut_round_mm: where a cut meets the body
    the frame gets a fillet, as a 0.4 mm nozzle prints it. Sharp, those re-entrant
    edges were stress singularities, and the crash checks' peak sat on one (where
    the battery's and the strap's keep-outs met the saddle's underside).

    _opened grows every keep-out by surface_clearance_mm, except the hub's two
    faces: the board's keep-outs start that far above hub_t, and the battery's and
    the strap's end that far below z = 0, so the hub comes out hub_t thick, its
    faces on the same planes as the saddle's. Grown there too, the hub between
    the battery and the board was 1.2 mm thick, under cad.wall_thickness's 1.26.
    A plane is drawn exact (a linear function's level set is exact), so the fit
    check (C5) finds no overlap on it, as it finds none under the saddle."""
    big = 200.0
    k = np.float32(c.surface_cut_round_mm)
    flat = c.surface_clearance_mm
    K = np.full(np.broadcast(Z, Y, X).shape, -1e3, np.float32)
    z_band = d["prop_z"] - c.prop_sweep_half_h - c.prop_clear
    for (mx, my) in motor_centres(d):
        K = np.maximum(K, _cyl_sdf(X, Y, Z, mx, my, d["prop_r"] + c.prop_clear, z_band, big, k))
        K = np.maximum(K, _cyl_sdf(X, Y, Z, mx, my, c.motor_body_d / 2 + c.motor_clear, c.plate_t, big, k))
        K = np.maximum(K, _cyl_sdf(X, Y, Z, mx, my, c.motor_centre_relief_d / 2 + c.motor_clear, -big, 0.0, k))
        for (hx, hy) in d["motor_screw_xy"][(mx, my)]:
            K = np.maximum(K, _cyl_sdf(X, Y, Z, hx, hy, c.screw_access_d / 2, -big, 0.0, k))
    gclr = c.fc_board_clear
    tip = c.fc_arm_tip_r + gclr
    K = np.maximum(K, _box_sdf(X, Y, Z, 0, 0, tip, c.fc_arm_w_fb / 2 + gclr, c.hub_t + flat, big, k))
    K = np.maximum(K, _box_sdf(X, Y, Z, 0, 0, c.fc_arm_w_side / 2 + gclr, tip, c.hub_t + flat, big, k))
    for (p0, p1) in d["lead_path"].values():
        K = np.maximum(K, _capsule_sdf(X, Y, Z, p0, p1, c.lead_d / 2 + c.lead_clear))
    pig = d["pigtail_path"]
    for p0, p1 in zip(pig, pig[1:]):
        K = np.maximum(K, _capsule_sdf(X, Y, Z, p0, p1, c.lead_d / 2 + c.lead_clear))
    K = np.maximum(K, _box_sdf(X, Y, Z, 0, 0, c.battery_l / 2 + 1, c.battery_w / 2 + 1, -big, -flat, k))
    K = np.maximum(K, _box_sdf(X, Y, Z, 0, 0, d["strap_slot_len"] / 2, d["strap_slot_y"] + c.strap_slot_w / 2,
                               -big, -flat, k))
    K = np.maximum(K, Z - np.float32(d["guard_z1"]))              # nothing above the guards (C13)
    return K


def _holes_sdf(c, d, Z, Y, X):
    """holes() as one function, positive inside any hole."""
    H = np.full(np.broadcast(Z, Y, X).shape, -1e3, np.float32)
    for (mx, my) in motor_centres(d):
        for (hx, hy) in d["motor_screw_xy"][(mx, my)]:
            H = np.maximum(H, _cyl_sdf(X, Y, Z, hx, hy, c.motor_screw_clear_d / 2, -1.0, c.plate_t + 1))
        H = np.maximum(H, _cyl_sdf(X, Y, Z, mx, my, c.motor_centre_relief_d / 2, -1.0, c.plate_t + 1))
    for (px, py) in d["fc_post_xy"]:
        H = np.maximum(H, _cyl_sdf(X, Y, Z, px, py, c.fc_pilot_d / 2, -1.0, d["z_post_top"] + 1))
    for sy in (1, -1):
        H = np.maximum(H, _box_sdf(X, Y, Z, 0, sy * d["strap_slot_y"], d["strap_slot_len"] / 2, c.strap_slot_w / 2,
                                   -20.0, d["z_post_top"] + 20))
    return H


def _cyl_sdf(X, Y, Z, cx, cy, r, z0, z1, k=0.0):
    """A cylinder, positive inside; k > 0 rounds its edges (a keep-out's)."""
    return _smin(_smin(r - np.hypot(X - cx, Y - cy), Z - z0, k), z1 - Z, k)


def _box_sdf(X, Y, Z, cx, cy, hx, hy, z0, z1, k=0.0):
    """An upright box, positive inside; k > 0 rounds its edges (a keep-out's)."""
    return _smin(_smin(hx - np.abs(X - cx), hy - np.abs(Y - cy), k), _smin(Z - z0, z1 - Z, k), k)


def _capsule_sdf(X, Y, Z, p0, p1, r):
    p0, p1 = np.asarray(p0, np.float32), np.asarray(p1, np.float32)
    s = p1 - p0
    t = np.clip(((X - p0[0]) * s[0] + (Y - p0[1]) * s[1] + (Z - p0[2]) * s[2]) / float(s @ s), 0, 1)
    return r - np.sqrt((X - p0[0] - t * s[0]) ** 2 + (Y - p0[1] - t * s[1]) ** 2 + (Z - p0[2] - t * s[2]) ** 2)


def _opened(c, d, field):
    """The body as drawn() draws it on the print's grid (step surface_edge_mm /
    2): the field cut by the keep-outs, the exact features in, the holes cut;
    then thickened and opened there, whatever edge the caller draws at, so the
    printed frame and every CalculiX surface have the same walls. The first
    version opened on each surface's own grid, and at a 0.4 mm step the analysis
    surface lost 1.8 mm members the printed frame kept.

    Every section the opening (surface_open_mm) would take is first grown
    where it can (_thicken), so the opening takes what could not grow: the
    feathered edges and lips a cut leaves, and sections cut on both faces. The
    hub is spared: its two faces are planes, 1.4 mm apart, which the 0.25 mm
    grid reads as 0.625 mm deep, a hair under the opening's 0.65 mm radius:
    unspared, the opening would take it whole."""
    rho, g, region = field
    key = _cache_key(c, d, rho.tobytes() + region.tobytes())
    if key not in _OPENED:
        step = c.surface_edge_mm / 2
        F, lo, n, axes = _field_sdf(c, d, rho, g, region, step)
        keep = -(_keepout_sdf(c, d, *axes) + np.float32(c.surface_clearance_mm))
        holes = _holes_sdf(c, d, *axes)
        # thickened as drawn, so the walls it measures are the printed ones; grown into a hole, a
        # section would come back as a skin round it when the hole is cut
        feat = _features_sdf(c, d, *axes)
        F = np.minimum(np.maximum(np.minimum(F, keep), feat), -holes)
        # the opening keeps a point whose depth on the grid is over r + step / 2 (_open): a section at
        # every grid phase only from (2 x (floor((r + step/2) / step) + 1) - 1) steps across, 1.75 mm at
        # 0.65 on the 0.25 mm grid (the 0.02 is _thicken's ray step); a ball centred on a grid point
        # is in the core when its radius is over r + step / 2
        r = c.surface_open_mm
        find = (2 * (math.floor((r + step / 2) / step) + 1) - 1) * step + 0.02
        F = _thicken(F, lo, step, find, r + step / 2 + THICKEN_MARGIN_MM, np.minimum(keep, -holes),
                     _shadow_room(c, d, F, step, axes[1], axes[2]), feat)
        O = _open(F, step, c.surface_open_mm, _hub_sdf(c, d, *axes))
        _OPENED.clear()                                # one design at a time: ~70 MB each
        _OPENED[key] = (O, lo, n, step)
    return _OPENED[key]


_OPENED: dict = {}


def drawn(c, d, field, edge):
    """The printed frame drawn from `field` (rho, grid, region) at `edge` mm, as
    ONE signed function and one level set: the opened body (_opened), resampled
    to this edge's lattice, with the exact features and holes put back exact on
    it (opened and left, the 1.4 mm saddle's and arcs' faces were shaved by up to
    a grid step, and the gates found no node on the saddle)."""
    from scipy import ndimage
    O, lo, n0, step0 = _opened(c, d, field)
    step = edge / 2                                    # the level set samples a BCC lattice at edge/2
    if abs(step - step0) < 1e-9:
        n = n0
    else:
        n = np.ceil(step0 * (n0 - 1) / step).astype(int) + 1
        n += (n - 1) % 2                               # an even number of steps: see _level_set
        O = ndimage.affine_transform(O, [step / step0] * 3, offset=0.0, output_shape=(n[2], n[1], n[0]),
                                     order=1, mode="nearest").astype(np.float32)
    xs, ys, zs = (np.float32(lo[k]) + np.float32(step) * np.arange(n[k], dtype=np.float32) for k in range(3))
    axes = (zs[:, None, None], ys[None, :, None], xs[None, None, :])
    F = np.maximum(O, _features_sdf(c, d, *axes))
    F = np.minimum(F, -_holes_sdf(c, d, *axes)).astype(np.float32)
    exact = exact_features(c, d)
    # the level set snaps lattice points onto the surface, which can leave
    # zero-length edges (gmsh: 'overlapping facets'); simplifying removes them
    solid = _drop_floaters(_level_set(F, lo, n, step, edge), exact).simplify(c.surface_simplify_mm)
    # ...and can leave zero-volume specks where a guard meets a limb
    parts = [p for p in solid.decompose() if p.volume() > 1.0]
    return _unpinch(m3d.Manifold.batch_boolean(parts, m3d.OpType.Add) if parts else solid)


#: mm: vertices closer than this are one vertex to a mesh checker (the cad-solid
#: pack welds at 1e-4 mm), so two of the body's sheets that meet there pinch it
PINCH_MM = 1e-4


def _unpinch(body):
    """Part every pinch: where the level set snapped two separate sheets onto one
    lattice point (the drawing has 1-2, at the 0.15 mm ledge between a seat's rim
    and its motor's keep-out), move each sheet's vertex 2 x PINCH_MM into its own
    faces. A checker that welds near vertices would otherwise join the sheets and
    find edges with four faces. Nothing moves further than that."""
    from scipy.spatial import cKDTree
    mesh = body.to_mesh64()
    v = np.array(mesh.vert_properties, dtype=np.float64)
    pairs = cKDTree(v[:, :3]).query_pairs(PINCH_MM)
    if not pairs:
        return body
    t = np.array(mesh.tri_verts, dtype=np.uint64)            # a copy: nanobind refuses the read-only view
    for i in {k for pair in pairs for k in pair}:
        fan = v[t[(t == i).any(axis=1)], :3].mean(axis=1).mean(axis=0) - v[i, :3]
        v[i, :3] += 2 * PINCH_MM * fan / max(np.linalg.norm(fan), 1e-12)
    return m3d.Manifold(m3d.Mesh64(vert_properties=np.ascontiguousarray(v), tri_verts=t))


def analysis_surface(c, d, field, edge):
    """The printed frame for CalculiX: frame()'s drawing at `edge` mm, so gmsh or
    fTetWild meshes the shape that is printed, at the analysis's resolution."""
    return drawn(c, d, field, edge)


#: Bumped whenever the drawing changes for the same Config and field: it keys
#: frame()'s cache and the analysis surfaces build() writes (build/fea/<key>/).
DRAWING_VERSION = 25


def _cache_key(c, d, field_bytes):
    keys = ("surface_edge_mm", "surface_blur_mm", "surface_iso", "surface_scale_mm", "surface_fillet_mm",
            "surface_simplify_mm", "surface_open_mm", "surface_clearance_mm", "surface_cut_round_mm",
            "guard_arc_deg", "guard_link_sides", "plate_t", "fc_post_od",
            "prop_clear", "motor_clear", "motor_body_d", "motor_centre_relief_d", "screw_access_d",
            "fc_board_clear", "fc_arm_tip_r", "fc_arm_w_fb", "fc_arm_w_side", "lead_d", "lead_clear", "battery_l", "battery_w", "strap_slot_w", "hub_t",
            "motor_screw_clear_d", "fc_pilot_d", "prop_sweep_half_h")
    dk = ("motor_xy", "mount_r", "guard_r_in", "guard_r_out", "guard_z0", "guard_z1", "fc_post_xy", "z_post_top",
          "prop_r", "prop_z", "strap_slot_len", "strap_slot_y", "lead_path", "pigtail_path", "motor_screw_xy")
    blob = json.dumps({"c": {k: getattr(c, k) for k in keys},
                       "d": {k: (repr(d[k]) if isinstance(d[k], dict) else d[k]) for k in dk},
                       "v": DRAWING_VERSION}, sort_keys=True, default=str)
    return hashlib.sha256(blob.encode() + field_bytes).hexdigest()[:16]


def frame(c, d, field=None, cache_dir=None):
    """The one-piece printed frame. `field`: (rho, grid, region) from the chosen
    proposal, or None (then the frame is its exact features alone: four seats,
    the guard arcs and their links, four posts and the saddle with nothing joining
    them, which the one-piece gate refuses)."""
    exact = exact_features(c, d)
    if field is None:
        return exact - holes(c, d)
    rho, g, region = field
    key = _cache_key(c, d, rho.tobytes() + region.tobytes() + json.dumps(
        {k: (list(v) if hasattr(v, "__len__") else v) for k, v in g.items()}).encode())
    path = os.path.join(cache_dir, key + ".npz") if cache_dir else None
    if path and os.path.exists(path):
        z = np.load(path)
        body = m3d.Manifold(m3d.Mesh64(vert_properties=np.ascontiguousarray(z["v"], dtype=np.float64),
                                       tri_verts=np.ascontiguousarray(z["t"], dtype=np.uint64)))
        if body.status() == m3d.Error.NoError and not body.is_empty():
            return body
    body = drawn(c, d, field, c.surface_edge_mm)
    if path:
        os.makedirs(cache_dir, exist_ok=True)
        mesh = body.to_mesh64()                        # lossless: a cached frame IS the fresh one
        np.savez_compressed(path, v=np.asarray(mesh.vert_properties, np.float64),
                            t=np.asarray(mesh.tri_verts, np.uint64))
    return body


def print_rotation(c):
    """3x3 rotation taking the frame from its flight pose to its print pose: tilted
    by print_tilt_deg about the horizontal axis at print_azimuth_deg."""
    import numpy as np
    a, t = math.radians(c.print_azimuth_deg), math.radians(c.print_tilt_deg)
    Rz = np.array([[math.cos(a), -math.sin(a), 0], [math.sin(a), math.cos(a), 0], [0, 0, 1]])
    Rx = np.array([[1, 0, 0], [0, math.cos(t), -math.sin(t)], [0, math.sin(t), math.cos(t)]])
    return Rz @ Rx @ Rz.T


def to_print_pose(c, solids):
    """The solids rotated into the print pose and moved together so the lowest
    point sits on the bed (z=0) and the plate's centre on the bed's centre line."""
    R = print_rotation(c)
    m = [[float(R[i, j]) for j in range(3)] + [0.0] for i in range(3)]
    turned = [s.transform(m) for s in solids]
    whole = m3d.Manifold.batch_boolean(turned, m3d.OpType.Add)
    x0, y0, z0, x1, y1, _ = whole.bounding_box()
    return [s.translate((-(x0 + x1) / 2, -(y0 + y1) / 2, -z0)) for s in turned]


def _drop_floaters(body, exact):
    """The body less every piece that touches no seat, guard or post: blobs the
    surface draws round grey cells of the field, held by nothing and holding
    nothing. A seat, guard or post cut off from the rest is NOT dropped (it
    touches itself), so the one-piece gate still sees it."""
    parts = body.decompose()
    if len(parts) <= 1:
        return body
    keep = [p for p in parts if not (p ^ exact).is_empty() and (p ^ exact).volume() > 1e-3]
    return m3d.Manifold.batch_boolean(keep, m3d.OpType.Add) if keep else body


def prop_sweeps(c, d):
    """The volume each spinning prop sweeps, a height band at the prop plane.

    Not cut from the frame: a frame that intrudes here is a design error, and
    cutting it away would hide the error. The assembly check intersects it with
    the frame and publishes the overlap for a gate to refuse.
    """
    return m3d.Manifold.batch_boolean(
        [_cyl(2 * c.prop_sweep_half_h, d["prop_r"], d["prop_z"] - c.prop_sweep_half_h)
         .translate((mx, my, 0)) for (mx, my) in motor_centres(d)], m3d.OpType.Add)
