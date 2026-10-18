"""topopt3d.py — the 3D topology problem PETGasus hands to the fea.topopt3d proposer.

What this file decides, from Config and the derived layout, and nothing else:
which cells of a voxel grid MUST be frame (the motor seats, each guard's outer
arc, the FC posts), which MUST stay empty (each prop's band and the inflow above it, the
motor bodies, the screwdriver's way to each motor screw, the board and the strap
under it, the battery and the strap round it, each motor lead's path), what a
designable cell costs (more under a prop: it sits in the downwash), where the
frame is held (the FC posts: the board, battery and pilot's inputs are the body
the arms hang off), and the load cases. The proposer finds the material; the
model turns its field into geometry (geometry.frame); CalculiX judges THAT
geometry (gates/structure.py). Nothing here is a verdict.

Load cases are placed at ONE corner (motor 1, +x +y) and the proposer is told
the problem has D2 symmetry (mirror x, mirror y), so one corner's cases design
all four. D4 (adding the x<->y swap) lost: the battery lies along x, and the
swap smeared its keep-out onto the y arms.

The problem's hash pins a proposal to the inputs it was computed for: build()
draws the chosen field whatever its hash, and publishes `topology_current`;
petgasus.topology_current (C17) fails when the hash is not this problem's.

Known limitations, to fix at the next optimiser run. Each fix changes the
problem's hash, so the chosen field goes stale and must be solved again (~45
min: the 2 mm run and its 1.33 mm refinement). None of them makes a current
verdict wrong: CalculiX and C14 judge the drawn frame, not this problem. Each
fix changes the field, and so the frame and its verdicts.

  1. The guard arcs are rasterised by cell centre (regions). A 1.4 mm annulus
     on 1.33 mm cells is a staircase one cell wide whose cells mostly meet at
     an edge or a corner: parts['guard'] is 44 pieces counted face to face
     (4 counted through edges and corners), 60 pieces on the 2 mm grid. In the
     voxel model those joints are hinges, so the "solid" hoop has almost no
     bending stiffness of its own. The optimiser spends designable cells
     beside it to bridge it (about 9 % of the budget), and the crash cases
     load a hinged ring, not the continuous arc geometry.drawn prints. Fix:
     take every cell the annulus touches, or close the mask, and check each
     arc is one face-connected piece.
  2. The shadow cost is a charge per volume, not a shadow (regions). Each
     designable cell under a prop pays 1 + (topo_prop_cost - 1) / N, where N
     is the number of designable cells in its column, filled or not (15-17 at
     1.33 mm). A one-cell flange pays 1/N of the shadow it casts, and a wide
     flange and a deep web of the same volume pay the same, so nothing rewards
     depth. In the chosen field the members under the props are mostly two
     cells deep, and the surcharge paid is about 1040 mm^3, where one shadow
     per filled column would be about 9640. The charge per mm^3 is also
     (topo_prop_cost - 1) * h / depth, so it falls by a third from the 2 mm
     grid, where topo_prop_cost was swept, to the 1.33 mm one. Fix: a column
     shadow s = 1 - prod(1 - rho) with its own sensitivity in the budget, then
     sweep topo_prop_cost again.
  3. A prop strike is applied in the seat's plane only (load_cases). The blade
     hits at the prop plane, about 11 mm above the seat's top nodes, so the
     seat also takes a couple, 20 N x 11.3 mm = 0.23 N m, which tilts it and
     bends its limbs out of plane. The problem never sees that, and no
     CalculiX gate loads a strike. Fix: add the couple as vertical forces
     across the seat's nodes, or load a stiff motor-body region at prop height.
  4. The 'over' crash patch takes the nodes within one cell of the hoop's top
     (load_cases, guard_patch). On the 1.33 mm grid that is two node layers,
     z = 13.33 and 14.67 (10 nodes each), so half of crash_top lands one cell
     under the top face; 'under' gets one layer, the bottom face. On the 2 mm
     grid it was the other way round. The stored runs put the effect at about
     0.2 % of those cases' compliance. Fix: take the nearest node layer.
"""
from __future__ import annotations

import hashlib
import json
import math
import os

import numpy as np


def grid(c, d):
    """(nx, ny, nz, h, origin): a square grid centred on the frame (even cell
    counts, so the mirror planes fall on cell faces), from topo_below under the
    seats to the top of the guard hoops, with a node layer at z = 0 (the seats'
    underside and the strap's line)."""
    h = c.topo_h
    half = d["motor_offset"] + d["guard_r_out"] + c.topo_margin
    n = int(math.ceil(half / h)) * 2
    z0 = -c.topo_below
    nz = int(math.ceil((d["guard_z1"] - z0) / h))
    return n, n, nz, h, np.array([-n * h / 2, -n * h / 2, z0])


def centres(nx, ny, nz, h, origin):
    """Cell-centre coordinates, each (nz, ny, nx)."""
    k, j, i = np.meshgrid(np.arange(nz), np.arange(ny), np.arange(nx), indexing="ij")
    return (origin[0] + (i + 0.5) * h, origin[1] + (j + 0.5) * h, origin[2] + (k + 0.5) * h)


def board_footprint(c, X, Y, grow=0.0):
    """The Matrix 1S 3IN1's cross: an arm along x (front/back) and one along y
    (the sides, wider: they carry the ESC sockets), each out to fc_arm_tip_r."""
    tip = c.fc_arm_tip_r + grow
    fb = (np.abs(X) <= tip) & (np.abs(Y) <= c.fc_arm_w_fb / 2 + grow)
    side = (np.abs(Y) <= tip) & (np.abs(X) <= c.fc_arm_w_side / 2 + grow)
    return fb | side


def near_segment(X, Y, Z, p0, p1, r):
    """Points within r of the segment p0-p1."""
    p0, p1 = np.asarray(p0, float), np.asarray(p1, float)
    s = p1 - p0
    t = np.clip(((X - p0[0]) * s[0] + (Y - p0[1]) * s[1] + (Z - p0[2]) * s[2]) / (s @ s), 0, 1)
    return (X - p0[0] - t * s[0]) ** 2 + (Y - p0[1] - t * s[1]) ** 2 + (Z - p0[2] - t * s[2]) ** 2 <= r * r


def keepouts(c, d, X, Y, Z):
    """Every place the frame may not be, as one boolean array. Shared with
    geometry.frame, which cuts the same places out of the finished surface."""
    void = np.zeros(np.broadcast(X, Y, Z).shape, dtype=bool)
    for (mx, my) in d["motor_xy"]:
        r = np.hypot(X - mx, Y - my)
        # the prop's band with its clearance, and the inflow above it
        void |= (r <= d["prop_r"] + c.prop_clear) & (Z >= d["prop_z"] - c.prop_sweep_half_h - c.prop_clear)
        # the motor's body above its seat
        void |= (r <= c.motor_body_d / 2 + c.motor_clear) & (Z >= c.plate_t)
        # under the seat: the shaft's C-clip and a screwdriver's way to each screw
        void |= (r <= c.motor_centre_relief_d / 2 + c.motor_clear) & (Z < 0)
        for (hx, hy) in d["motor_screw_xy"][(mx, my)]:
            void |= (np.hypot(X - hx, Y - hy) <= c.screw_access_d / 2) & (Z < 0)
    # the board: its cross-shaped footprint plus clearance, from the hub's top up
    # (the strap and the bottom-side sockets live under it)
    void |= board_footprint(c, X, Y, c.fc_board_clear) & (Z >= c.hub_t)
    # each motor lead's path, from the motor's base to its socket's plug, and the
    # board's power pigtail down to the battery's plug
    for (p0, p1) in d["lead_path"].values():
        void |= near_segment(X, Y, Z, p0, p1, c.lead_d / 2 + c.lead_clear)
    pig = d["pigtail_path"]
    for p0, p1 in zip(pig, pig[1:]):
        void |= near_segment(X, Y, Z, p0, p1, c.lead_d / 2 + c.lead_clear)
    # battery under the hub along x, and the strap round it across y
    void |= (np.abs(X) <= c.battery_l / 2 + 1) & (np.abs(Y) <= c.battery_w / 2 + 1) & (Z < 0)
    void |= (np.abs(X) <= d["strap_slot_len"] / 2) & (np.abs(Y) <= d["strap_slot_y"] + c.strap_slot_w / 2) & (Z < 0)
    # strap slots through the hub
    for sy in (1, -1):
        void |= (np.abs(X) <= d["strap_slot_len"] / 2) & (np.abs(Y - sy * d["strap_slot_y"]) <= c.strap_slot_w / 2) \
            & (Z < d["z_board"])
    return void


def saddle_cells(c, d, X, Y, Z):
    """The strap's saddle: the hub's full thickness between the slots' inner
    edges, the strap's width (and the slot's play) along x."""
    return (np.abs(X) <= d["strap_slot_len"] / 2) & (np.abs(Y) <= d["strap_slot_y"] - c.strap_slot_w / 2) \
        & (Z >= 0) & (Z < c.hub_t)


def on_arc(c, mx, my, X, Y):
    """Within guard_arc_deg of the direction from the frame's centre out through
    the motor at (mx, my): the part of its guard that must be solid."""
    a = math.atan2(my, mx)
    half = math.radians(c.guard_arc_deg / 2)
    return np.cos(np.arctan2(Y - my, X - mx) - a) >= math.cos(half) - 1e-9


def regions(c, d, nx, ny, nz, h, origin):
    """region (0 design, 1 solid, 2 void), erel (modulus of a solid cell relative
    to the frame's), cost (budget charged per designable cell), and the masks
    the loads are placed on."""
    X, Y, Z = centres(nx, ny, nz, h, origin)
    void = keepouts(c, d, X, Y, Z)
    solid = np.zeros_like(void)
    guard = np.zeros_like(void)
    post = np.zeros_like(void)
    under_any = np.zeros_like(void)
    near = np.zeros_like(void)
    for (mx, my) in d["motor_xy"]:
        r = np.hypot(X - mx, Y - my)
        solid |= (r <= d["mount_r"]) & (Z >= 0) & (Z < c.plate_t)
        # the arc by cell centre: a staircase whose cells mostly meet at edges and
        # corners, hinged in the voxel model (known limitation 1)
        guard |= (r >= d["guard_r_in"]) & (r <= d["guard_r_out"]) & (Z >= d["guard_z0"]) & (Z <= d["guard_z1"]) \
            & on_arc(c, mx, my, X, Y)
        # downwash: a cell inside the prop disc, below the prop, outside the
        # motor's own shadow, blocks flow the prop would otherwise push through
        under_any |= (r < d["prop_r"]) & (r > c.motor_body_d / 2 + c.motor_clear) & (Z < d["prop_z"])
        near |= r <= d["guard_r_out"] + c.topo_margin
    # the square's corners outside every hoop: nothing there holds anything up
    void |= ~near & (np.abs(X) > d["motor_offset"]) & (np.abs(Y) > d["motor_offset"])
    # nothing above the hoops' top (C13). The grid rounds up past it, and the
    # optimiser filled that part-cell over every hoop (a deeper hoop is a stiffer
    # one): the drawn hoops stood 4.8 mm tall against C13's 4
    void |= Z > d["guard_z1"]
    for (px, py) in d["fc_post_xy"]:
        post |= (np.hypot(X - px, Y - py) <= c.fc_post_od / 2) & (Z >= 0) & (Z < d["z_board"])
    # the strap's saddle: the hub between the two slots, which the strap's top
    # run lies on and the battery hangs from. Left to the optimiser, it could
    # thin it away and leave the strap nothing to bear on
    saddle = saddle_cells(c, d, X, Y, Z)
    solid |= guard | post | saddle
    void &= ~solid                      # a seat, post or hoop wins over a keep-out it touches
    region = np.zeros(void.shape, dtype=np.int8)
    region[void] = 2
    region[solid] = 1
    # what a cell under a prop costs beyond its weight stands for its SHADOW on
    # the downwash. The extra (topo_prop_cost - 1) is divided by the number of
    # designable cells in the cell's column, filled or not, so each shaded cell
    # pays a flat 1 + (topo_prop_cost - 1)/N (1.53-1.60 at 1.33 mm). The full
    # extra on every cell (the first version) kept the frame shallow with 12 mm
    # of depth free under it.
    # Divided, it is still a charge per volume, not one shadow per column: it
    # does not reward the author's deep webs, thin seen from above, over wide
    # flanges (known limitation 2). C14 judges the real shadow.
    shaded = under_any & (region == 0)
    column = np.maximum(shaded.sum(axis=0, keepdims=True), 1)
    cost = np.where(shaded, 1.0 + (c.topo_prop_cost - 1.0) / column, 1.0).astype(np.float32)
    erel = np.ones(void.shape, dtype=np.float32)
    erel[guard] = d["guard_E_rel"]
    return region, erel, cost, {"post": post, "guard": guard, "saddle": saddle}


def _node_ids(nx, ny, i, j, k):
    return i + (nx + 1) * (j + (ny + 1) * k)


def _nodes_where(nx, ny, nz, h, origin, pred):
    k, j, i = np.meshgrid(np.arange(nz + 1), np.arange(ny + 1), np.arange(nx + 1), indexing="ij")
    X, Y, Z = origin[0] + i * h, origin[1] + j * h, origin[2] + k * h
    m = pred(X, Y, Z)
    return _node_ids(nx, ny, i[m], j[m], k[m])


def _cell_nodes(nx, ny, mask):
    """Every node of the cells in mask (nz, ny, nx)."""
    k, j, i = np.nonzero(mask)
    ids = [_node_ids(nx, ny, i + di, j + dj, k + dk) for di in (0, 1) for dj in (0, 1) for dk in (0, 1)]
    return np.unique(np.concatenate(ids)) if ids else np.zeros(0, np.int64)


def _spread(nodes, vec, total):
    """total force (N) along vec, shared evenly over nodes -> (dofs, values)."""
    if not len(nodes):
        raise ValueError("a load case found no nodes to act on")
    vec = np.asarray(vec, float) / np.linalg.norm(vec)
    dofs, vals = [], []
    for k in range(3):
        if vec[k]:
            dofs.append(3 * nodes + k)
            vals.append(np.full(nodes.size, total * vec[k] / nodes.size))
    return np.concatenate(dofs), np.concatenate(vals)


def load_cases(c, d, nx, ny, nz, h, origin, region, parts):
    """[(name, weight, dofs, values)]: one corner's thrust and crash cases and
    the battery's weight on the strap. Magnitudes only scale each compliance (the
    objective normalises each by its starting value); the weights set the trade."""
    mx, my = d["motor_xy"][0]
    solid_nodes = _cell_nodes(nx, ny, region == 1)
    guard_nodes = _cell_nodes(nx, ny, parts["guard"])
    out = []

    # thrust: the motor pushes its seat up; full static thrust x topo_thrust_factor
    f = c.motor_thrust_max_g / 1000 * 9.80665 * c.topo_thrust_factor
    seat_top = h * round(c.plate_t / h)
    n = _nodes_where(nx, ny, nz, h, origin, lambda X, Y, Z: (np.hypot(X - mx, Y - my) <= d["mount_r"])
                     & (np.hypot(X - mx, Y - my) >= 1.0) & (np.abs(Z - seat_top) < 1e-6))
    seat_nodes = np.intersect1d(n, solid_nodes)
    out.append(("thrust", c.topo_w_thrust, *_spread(seat_nodes, (0, 0, 1), f)))
    # a prop strike: the blade hits a wall, the floor or the hoop and yanks the
    # motor sideways on its seat, along the arm and across it. Without these the
    # optimiser served six hoop crashes and left the seats on thin grey threads.
    # The force is applied at the seat's top nodes, in their plane; the couple of
    # a blow at the prop plane, ~11 mm higher, is left out (known limitation 3)
    u = np.array([mx, my]) / math.hypot(mx, my)
    out.append(("prop_strike_radial", c.topo_w_strike, *_spread(seat_nodes, (-u[0], -u[1], 0), c.topo_crash_n)))
    out.append(("prop_strike_tangential", c.topo_w_strike, *_spread(seat_nodes, (-u[1], u[0], 0), c.topo_crash_n)))

    def guard_patch(angle_deg, face):
        a = math.radians(angle_deg)
        px, py = mx + d["guard_r_out"] * math.cos(a), my + d["guard_r_out"] * math.sin(a)
        if face == "out":
            pred = lambda X, Y, Z: (np.hypot(X - px, Y - py) <= c.topo_patch_mm) \
                & (np.hypot(X - mx, Y - my) >= d["guard_r_out"] - h) \
                & (Z >= d["guard_z0"] - h) & (Z <= d["guard_z1"] + h)
        else:
            # within h of the face: at h = 1.33 'over' takes two node layers and
            # 'under' one (known limitation 4)
            zf = d["guard_z0"] if face == "under" else d["guard_z1"]
            pred = lambda X, Y, Z: (np.hypot(X - px, Y - py) <= c.topo_patch_mm + h / 2) \
                & (np.abs(Z - zf) <= h)
        return np.intersect1d(_nodes_where(nx, ny, nz, h, origin, pred), guard_nodes), (math.cos(a), math.sin(a))

    # crashes across the guard arc, from many directions: in, and in-and-up from
    # below, at its middle and both ends; along it; up from below; down from above
    F = c.topo_crash_n
    mid = math.degrees(math.atan2(my, mx))
    for off in (-c.topo_crash_spread_deg, 0.0, c.topo_crash_spread_deg):
        n, (ux, uy) = guard_patch(mid + off, "out")
        out.append((f"crash_in_{off:+.0f}", c.topo_w_crash, *_spread(n, (-ux, -uy, 0), F)))
        out.append((f"crash_up_{off:+.0f}", c.topo_w_crash_up, *_spread(n, (-ux, -uy, 1), F)))
    n, (ux, uy) = guard_patch(mid, "out")
    out.append(("crash_tangential", c.topo_w_crash_t, *_spread(n, (-uy, ux, 0), F)))
    n, _ = guard_patch(mid, "under")
    out.append(("crash_vertical", c.topo_w_vertical, *_spread(n, (0, 0, 1), F)))
    n, _ = guard_patch(mid, "over")
    out.append(("crash_top", c.topo_w_top, *_spread(n, (0, 0, -1), F)))

    # battery: its weight x topo_battery_g hangs on the strap, whose top run
    # presses down on the saddle between the slots
    Fb = c.battery_mass_g / 1000 * 9.80665 * c.topo_battery_g
    out.append(("battery", c.topo_w_battery, *_spread(_cell_nodes(nx, ny, parts["saddle"]), (0, 0, -1), Fb)))
    return out


def problem(c, d):
    """Everything the proposer needs, as arrays, plus `problem_hash`, which pins
    a field to the problem it was computed for."""
    nx, ny, nz, h, origin = grid(c, d)
    region, erel, cost, parts = regions(c, d, nx, ny, nz, h, origin)
    fixed = _cell_nodes(nx, ny, parts["post"] & (region == 1))
    cases = load_cases(c, d, nx, ny, nz, h, origin, region, parts)
    p = {
        "nx": nx, "ny": ny, "nz": nz, "h": h, "origin": origin, "nu": c.topo_nu,
        "region": region.ravel(), "erel": erel.ravel(), "cost": cost.ravel(),
        "fixed_nodes": fixed.astype(np.int64), "budget_mm3": d["topo_design_mm3"], "rmin_mm": c.topo_rmin, "rmin_z_mm": c.topo_rmin_z,
        "symmetry": "D2", "load_names": np.array([cs[0] for cs in cases]),
        "load_weights": np.array([cs[1] for cs in cases], float),
    }
    for k, (_, _, dofs, vals) in enumerate(cases):
        p[f"load_{k}_dofs"] = dofs.astype(np.int64)
        p[f"load_{k}_vals"] = vals.astype(float)
    hsh = hashlib.sha256()
    for key in sorted(p):
        v = p[key]
        hsh.update(key.encode())
        hsh.update(np.ascontiguousarray(v).tobytes() if isinstance(v, np.ndarray) else json.dumps(v).encode())
    p["problem_hash"] = hsh.hexdigest()[:16]
    return p


def write_problem(p, path):
    """Content-addressed: rewriting an unchanged problem leaves the file alone."""
    import io
    buf = io.BytesIO()
    np.savez_compressed(buf, **p)
    data = buf.getvalue()
    if os.path.exists(path):
        try:
            if str(np.load(path)["problem_hash"]) == p["problem_hash"]:
                return
        except Exception:                                    # noqa: BLE001 - unreadable: rewrite it
            pass
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(data)


def load_field(path, problem_hash):
    """The proposal at `path` as (rho (nz, ny, nx) float32, grid dict), and whether
    it was computed for `problem_hash`."""
    z = np.load(path, allow_pickle=False)
    nx, ny, nz = int(z["nx"]), int(z["ny"]), int(z["nz"])
    rho = z["rho"].astype(np.float32).reshape(nz, ny, nx)
    g = {"nx": nx, "ny": ny, "nz": nz, "h": float(z["h"]), "origin": z["origin"].astype(float)}
    return rho, g, str(z["problem_hash"]) == problem_hash
