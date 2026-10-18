"""Structure gates for PETGasus: CalculiX on the printed shape. Tier 2.

Each gate meshes the frame the model exported for THIS design (`fea.mesh_path`,
named by the design's hash, so a control's design never answers for the live
one) into quadratic tetrahedra (gmsh where its mesh is sound, fTetWild where it
is not), writes a CalculiX deck, runs ccx, and judges what comes back against
its claim's limit. None of them reads the optimiser's field: the field is a
proposal, and the optimiser's own voxel model is not evidence about the shape
that gets printed. That independence (different solver, different mesh, the
real surface) is the point of these gates.

Shared set-up, all from the projection (model/petgasus.py):
  * material: transversely isotropic, its stiff plane the print's layers
    (`fea.layer_normal`), XY and Z moduli and strengths from the filament's data
    sheet. The modes are judged in the everyday filament (`fea.material`, PETG);
    the crashes in the strong one (`fea.strong_material`, nylon-CF), the one the
    author says anyone serious about crashes prints. The guard arcs get their
    own when they are a second material (`fea.guard_separate`);
  * the modes: held where the body bears on the frame, the top faces of the
    four FC posts (the board, on its grommets) and the strap's saddle between
    the slots (the battery, hanging on the strap), with each motor + prop as a
    mass on its seat's top face. An approximation, not a bound: a free-flying
    body moves too, and holding the saddle and lumping each motor on one face
    both stiffen what a real flight sees. (A free-free run would be the exact
    case; this CalculiX build returns nonsense rigid modes for one.)
  * the crashes: the drone is free (inertia relief). The hit is balanced by
    every mass's inertia at the acceleration it causes, and three nodes on the
    posts' tops hold six directions, carrying nothing; held at the posts and
    strap instead, the whole hit had to reach the posts through the hub.

Every static solve is checked for equilibrium against a stiffness built here,
not by the solver (solid_fea_ccx.residual), and every judged number is checked
for convergence on a finer surface and mesh (fea_converged).

The CalculiX wrapper (meshing, deck, run, readers) is the solid-fea pack's
`solid_fea_ccx.py`, smoke-tested against beam theory (tip deflection 0.986 x
Timoshenko, first mode 0.979 x Euler-Bernoulli, bending stress within 0.3 %).
"""
from __future__ import annotations

import json
import math
import os
import sys

from nopekit.gates import gate, GateContext
from nopekit.models import NegativeControl, Tier, Verdict

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_PACK = os.path.join(_ROOT, ".nopekit", "packs", "solid-fea")
if _PACK not in sys.path:
    sys.path.insert(0, _PACK)

import solid_fea_ccx as ccx  # noqa: E402

G = 9.80665

#: mm round a held node whose stresses are not judged. The crash hold carries
#: (almost) nothing, but a point hold is still a local singularity in principle.
EXCLUDE_MM = 2.5

#: mm round an impact point whose stresses are not judged: the 3 mm load patch
#: and one element beyond it, where the nodal forces' contact stresses live. No
#: wider: a guard hit at a point bends hardest AT that point, and excluding
#: 5.5 mm (the first version) hid exactly the stress that breaks it.
PATCH_MM = 3.0
PATCH_EXCLUDE_MM = PATCH_MM + 1.0

#: mm, the critical distance: the utilisation judged at a spot is the volume-
#: weighted mean over the tets that reach within it (the theory of critical
#: distances' volume method; L/2 is ~0.4-0.6 mm for PETG and PA6-CF). One node's
#: stress decided the first version's verdicts, and one node can sit on a sliver
#: tet or a sharp edge; a 0.3 mm ball over nodes held 0-3 of them on the base mesh.
CRIT_MM = 0.5

#: Largest change of the first mode between the two meshes for a result to count
#: as converged, and of a crash number (drop height, wall speed).
CONVERGED = 0.05
CONVERGED_CRASH = 0.10

#: N of out-of-balance force allowed at any node, for a 1 N hit: a sound solve
#: leaves ~0.01 N (the .frd's five digits); a corrupted one left 17-124 N.
RESIDUAL_MAX_N = 0.05

#: Volume meshes, mode solves and impact solves made in this process: the four
#: gates share two surfaces and the same runs between them.
_MESHES: dict = {}
_RUNS: dict = {}


def _mesh(path: str, size: float):
    import hashlib
    with open(path, "rb") as fh:
        key = (hashlib.sha256(fh.read()).hexdigest(), round(size, 6))
    if key not in _MESHES:
        _MESHES[key] = ccx.mesh_surface(path, size)
    return key, _MESHES[key]


def _material(m, layer_normal):
    """CalculiX engineering constants for a printed, transversely isotropic
    material: E1 = E2 in the layers, E3 across them (along `layer_normal`).
    CalculiX's nu13 is -strain3/strain1 under stress 1 (compliance S13 =
    -nu13/E1): in the layers' (major) direction, so it takes the full 0.35 and
    nu31 = nu13 E3/E1 follows. The first version wrote nu E3/E1 there."""
    nu = 0.35
    return dict(E1=m["E_xy"], E2=m["E_xy"], E3=m["E_z"], nu12=nu, nu13=nu, nu23=nu,
                G12=m["E_xy"] / (2 * (1 + nu)), G13=m["E_z"] / (2 * (1 + nu)),
                G23=m["E_z"] / (2 * (1 + nu)), density_g_cm3=m["density"])


def _orientation(n):
    """Two vectors (a, b) whose local z is n: CalculiX's RECTANGULAR orientation."""
    import numpy as np
    n = np.asarray(n, float) / np.linalg.norm(n)
    t = np.array([1.0, 0, 0]) if abs(n[0]) < 0.9 else np.array([0, 1.0, 0])
    a = np.cross(t, n)
    a /= np.linalg.norm(a)
    b = np.cross(n, a)
    return tuple(a), tuple(b)


def _one_piece(nodes, tets):
    """Refuse a tet mesh that is not one piece joined face to face: a loose piece
    has a free rigid-body motion, so a 0 Hz 'mode' and a static solve out of
    equilibrium (434 N for a 1 N hit, when a rim bridge's neck was cut on a
    coarser surface)."""
    import numpy as np
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components
    t4 = tets[:, :4]
    faces = np.sort(np.concatenate([t4[:, [0, 1, 2]], t4[:, [0, 1, 3]], t4[:, [0, 2, 3]], t4[:, [1, 2, 3]]]), axis=1)
    owner = np.tile(np.arange(len(tets)), 4)
    _, inv = np.unique(faces, axis=0, return_inverse=True)
    inv = inv.ravel()
    order = np.argsort(inv, kind="stable")
    same = inv[order][1:] == inv[order][:-1]
    a, b = owner[order][:-1][same], owner[order][1:][same]
    n, lab = connected_components(coo_matrix((np.ones(len(a)), (a, b)), shape=(len(tets), len(tets))), directed=False)
    if n > 1:
        sizes = np.bincount(lab)
        small = np.argsort(sizes)[:-1]
        where = [tuple(np.round(nodes[t4[lab == k]].reshape(-1, 3).mean(axis=0), 1)) for k in small[:3]]
        raise RuntimeError(f"the tet mesh is {n} pieces joined face to face, not one: loose pieces of "
                           f"{', '.join(str(int(sizes[k])) for k in small[:3])} tets near {where}")


def _top_face(nodes, footprint, z_design, name, tol=0.05, reach=0.3):
    """The nodes on a footprint's top face: the top-most nodes inside it, which
    must stand within `reach` of the design's height. Selected at the design's
    height exactly, a coarser surface (its top interpolated 0.1-0.3 mm low) held
    nothing and the gate errored instead of judging."""
    import numpy as np
    idx = np.nonzero(footprint)[0]
    if not len(idx):
        raise RuntimeError(f"no mesh node inside the {name}'s footprint")
    z_top = float(nodes[idx, 2].max())
    if abs(z_top - z_design) > reach:
        raise RuntimeError(f"the {name}'s top is at {z_top:.2f} mm, not the design's {z_design:.2f}")
    return idx[nodes[idx, 2] >= z_top - tol]


def _model(ctx: GateContext, size: float, fine: bool = False, strong: bool = False):
    """Mesh, materials, supports and masses for the design in ctx.params. `fine`:
    the finer analysis surface (the convergence check's mesh); `strong`: in the
    strong filament (the crash checks')."""
    import numpy as np
    p = ctx.params
    path = os.path.join(ctx.root, p["fea.mesh_fine_path" if fine else "fea.mesh_path"])
    key, (nodes, tets) = _mesh(path, size)
    _one_piece(nodes, tets)
    cen = nodes[tets[:, :4]].mean(axis=1)
    frame_mat = p["fea.strong_material"] if strong else p["fea.material"]
    mats = {"FRAME": _material(frame_mat, p["fea.layer_normal"])}
    strength = {"FRAME": frame_mat}
    elmat = np.array(["FRAME"] * len(tets), dtype=object)
    motors = [tuple(m) for m in p["motor_xy"]]
    if p["fea.guard_separate"]:
        mats["GUARD"] = _material(p["fea.guard_material"], p["fea.layer_normal"])
        strength["GUARD"] = p["fea.guard_material"]
        half = math.radians(p["guard_arc_deg"] / 2)
        for (mx, my) in motors:
            r = np.hypot(cen[:, 0] - mx, cen[:, 1] - my)
            arc = np.cos(np.arctan2(cen[:, 1] - my, cen[:, 0] - mx) - math.atan2(my, mx)) >= math.cos(half) - 1e-9
            band = (r >= p["guard_r_in"] - 1e-6) & (r <= p["guard_r_out"] + 1e-6) \
                & (cen[:, 2] >= p["guard_z0"] - 1e-6) & (cen[:, 2] <= p["guard_z1"] + 1e-6) & arc
            elmat[band] = "GUARD"
    fixed = np.zeros(len(nodes), bool)
    held = {}                                                  # support -> how many nodes it holds
    post_tops = []
    for k, (px, py) in enumerate(p["fc_post_xy"]):
        foot = np.hypot(nodes[:, 0] - px, nodes[:, 1] - py) <= p["fc_post_od"] / 2 + 0.05
        top = _top_face(nodes, foot & (nodes[:, 2] <= p["z_post_top"] + 1.0), p["z_post_top"], f"post {k + 1}")
        held[f"post {k + 1} top"] = len(top)
        post_tops.append(top)
        fixed[top] = True
    # ...and where the battery hangs: the strap's top run lies on the saddle, the
    # hub between the two slots (an exact feature), and the battery hangs from it
    sy, sw, sl = p["strap_slot_y"], p["strap_slot_w"], p["strap_slot_len"]
    foot = (np.abs(nodes[:, 0]) <= sl / 2) & (np.abs(nodes[:, 1]) <= sy - sw / 2) & (nodes[:, 2] <= p["hub_t"] + 1.0)
    saddle = _top_face(nodes, foot, p["hub_t"], "strap saddle")
    held["strap saddle"] = len(saddle)
    fixed[saddle] = True
    masses = []
    for (mx, my) in motors:
        rr = np.hypot(nodes[:, 0] - mx, nodes[:, 1] - my)
        seat = _top_face(nodes, (rr <= p["mount_r"] - 0.3) & (nodes[:, 2] <= p["plate_t"] + 1.0), p["plate_t"],
                         "motor seat")
        masses.append((seat, p["fea.motor_mass_g"]))
    return dict(key=key, nodes=nodes, tets=tets, materials=mats, strength=strength, elmat=elmat,
                fixed=np.nonzero(fixed)[0], masses=masses, orientation=_orientation(p["fea.layer_normal"]),
                motors=motors, held=held, post_tops=post_tops, saddle=saddle)


def _need_support(m):
    """Every support must hold the frame somewhere. Checking only that SOME node
    was held let a drawing whose post tops came out 0.19 mm low hang the whole
    frame on 15 nodes of one strap slot: first mode 30 Hz, a 'failure' that was
    the gate's, not the frame's."""
    empty = [name for name, n in m["held"].items() if n == 0]
    if empty:
        raise RuntimeError(f"no mesh node on {', '.join(empty)}: the frame is not held where it is supported")
    for nids, _ in m["masses"]:
        if not len(nids):
            raise RuntimeError("a motor seat's top face has no mesh nodes")


def _modes(ctx: GateContext, size: float, tag: str, fine: bool = False):
    """First CalculiX eigenfrequencies of the frame in the everyday filament,
    held at the posts and the saddle, motors as masses."""
    m = _model(ctx, size, fine)
    _need_support(m)
    key = ("modes", m["key"], json.dumps(m["materials"], sort_keys=True), ctx.params["fea.motor_mass_g"],
           json.dumps(ctx.params["fea.layer_normal"]))
    if key in _RUNS:
        return _RUNS[key]
    work = ctx.out_path(f"modal-{tag}")
    os.makedirs(work, exist_ok=True)
    deck = os.path.join(work, "modal.inp")
    ccx.write_deck(deck, m["nodes"], m["tets"], materials=m["materials"], element_material=m["elmat"],
                   fixed_nodes=m["fixed"], point_masses=m["masses"], orientation=m["orientation"],
                   steps=[dict(kind="frequency", n=6)])
    stem = ccx.run(deck)
    freqs = ccx.read_frequencies(stem)
    if not freqs:
        raise RuntimeError("ccx wrote no eigenfrequencies")
    _RUNS[key] = (freqs, len(m["tets"]), stem)
    return _RUNS[key]


# --------------------------------------------------------------------------- #
def _drop_contact(p, nodes, max_deg=80.0, step_deg=0.25):
    """(bank deg, contact xyz): rolling the drone's motor-1 side down, the
    smallest bank at which the lowest point of the frame and the battery is a
    node of motor 1's guard, and that node. A floor can only hit the frame where
    it is lowest. The first version aimed at the exact arc's corner, which the
    drawn guard stands proud of, so no bank ever made it the lowest point."""
    import numpy as np
    mx, my = p["motor_xy"][0]
    u = np.array([mx, my]) / math.hypot(mx, my)
    bl, bw, bh, st = p["battery_l"], p["battery_w"], p["battery_h"], p["strap_t"]
    battery = np.array([(sx * bl / 2, sy * bw / 2, -bh) for sx in (1, -1) for sy in (1, -1)]
                       + [(sx * p["strap_w"] / 2, sy * (bw / 2 + st), -bh - st) for sx in (1, -1) for sy in (1, -1)])
    pts = np.vstack([nodes, battery])
    on_guard = np.zeros(len(pts), bool)
    on_guard[:len(nodes)] = (np.hypot(nodes[:, 0] - mx, nodes[:, 1] - my) >= p["guard_r_in"] - 1.0) \
        & (nodes[:, 2] >= p["guard_z0"] - 1.5)
    for deg in np.arange(0.0, max_deg + 1e-9, step_deg):
        t = math.radians(deg)
        low = int(np.argmin(math.cos(t) * pts[:, 2] - math.sin(t) * (pts[:, :2] @ u)))
        if on_guard[low]:
            return float(deg), tuple(float(v) for v in pts[low])
    raise RuntimeError(f"motor 1's guard is not the lowest point at any bank up to {max_deg} deg")


def _impact_cases(p, nodes):
    """(name, kind, patch centre xyz, unit direction, note) for motor 1's guard.
    The drop: the floor hits motor 1's guard along the floor's normal, at the
    smallest bank that makes a node of that guard the lowest point (the first
    version hit the guard straight up the body's z, a pose in which the keel
    under the hub, 16 mm lower, would land first). The walls: the outer face
    square on at the point facing +x, and head on along the arm's line."""
    import numpy as np
    mx, my = p["motor_xy"][0]
    r_out = p["guard_r_out"]
    zc = (p["guard_z0"] + p["guard_z1"]) / 2
    u = np.array([mx, my]) / math.hypot(mx, my)
    far = np.array([mx, my]) + r_out * u
    bank, c_drop = _drop_contact(p, nodes)
    t = math.radians(bank)
    d_drop = (-math.sin(t) * u[0], -math.sin(t) * u[1], math.cos(t))
    return [
        ("drop", "drop", c_drop, d_drop, f"banked {bank:.1f} deg"),
        ("wall_side", "wall", (mx + r_out, my, zc), (-1.0, 0.0, 0.0), ""),
        ("wall_head_on", "wall", (far[0], far[1], zc), (-u[0], -u[1], 0.0), ""),
    ]


def _mass_keys(p, strong):
    return ("strong_auw_g", "fea.strong_cg_mm", "fea.strong_inertia_g_mm2", "strong_frame_mass_g") if strong \
        else ("auw_g", "fea.cg_mm", "fea.inertia_g_mm2", "frame_mass_g")


def _inertia(m, p, strong=True):
    """Every mass the flying drone carries, in kg per node: the frame's own (each
    tet's share at its corners, scaled to the printed frame's mass, so the FE and
    Goldsmith's rigid body weigh the same), each motor + prop on its seat, the
    battery on the strap's saddle, and the rest (board, grommets, screws, leads,
    receiver) on the posts' tops: together the all-up weight. The first version
    weighed the frame from the analysis mesh and put the shortfall, 1.3 g of
    frame, on the posts."""
    import numpy as np
    k_auw, _, _, k_frame = _mass_keys(p, strong)
    nodes, tets = m["nodes"], m["tets"]
    vol = ccx.tet_volumes(nodes, tets[:, :4])
    rho = {name: mat["density_g_cm3"] for name, mat in m["materials"].items()}
    tet_g = vol * 1e-3 * np.array([rho[e] for e in m["elmat"]])
    tet_g *= p[k_frame] / tet_g.sum()
    node_g = np.zeros(len(nodes))
    np.add.at(node_g, tets[:, :4].ravel(), np.repeat(tet_g / 4, 4))
    for nids, mass_g in m["masses"]:
        node_g[nids] += mass_g / len(nids)
    node_g[m["saddle"]] += p["battery_mass_g"] / len(m["saddle"])
    posts = np.concatenate(m["post_tops"])
    rest = p[k_auw] - node_g.sum()
    if rest < 0:
        raise RuntimeError(f"the masses placed come to {node_g.sum():.1f} g, over the {p[k_auw]:.1f} g all-up weight")
    node_g[posts] += rest / len(posts)
    return node_g * 1e-3


def _impact(ctx: GateContext, kind: str, claim_limit: float, fine: bool = False):
    """For each impact case of `kind`, in the strong filament: CalculiX on the
    FREE drone (inertia relief). A 1 N hit spread over a 3 mm patch is balanced
    by every mass's inertia at the rigid-body acceleration it causes, linear and
    angular, so the hold (three nodes on the posts' tops, six directions,
    statically determinate) carries nothing. The solve is refused unless it is
    in equilibrium everywhere (RESIDUAL_MAX_N). From the result: the strain
    energy per N^2, and the worst utilisation per newton, in the layers (max
    principal / XY strength) and across them (normal stress on the layer plane /
    Z strength), averaged over CRIT_MM and away from the patch and the hold;
    then the energy the frame takes elastically before that reaches strength,
    and the drop height or wall speed that delivers it to the effective mass
    (Goldsmith) behind the hit.

    The first version held the frame at the posts' tops and strap edges, as if
    the board and battery were an immovable anchor: every newton of the hit had
    to reach the posts through the hub, and the hub beside a post broke first
    (drop 0.24 m). A free drone's motors, battery and board each stop
    themselves; the posts carry only the board's share.

    Not judged: shear between the layers (no data sheet gives it), plastic
    work, the floor's give, contact."""
    import numpy as np
    from scipy.spatial import cKDTree
    p = ctx.params
    size = float(p["fea.mesh_mm"]) * (0.75 if fine else 1.0)
    m = _model(ctx, size, fine=fine, strong=True)
    _need_support(m)
    nodes = m["nodes"]
    cases = [cs for cs in _impact_cases(p, nodes) if cs[1] == kind]
    key = ("impact", kind, m["key"], json.dumps(m["materials"], sort_keys=True), json.dumps(m["strength"], sort_keys=True),
           json.dumps([p[k] for k in _mass_keys(p, True)]), p["battery_mass_g"], p["fea.motor_mass_g"],
           json.dumps(p["fea.layer_normal"]), json.dumps([list(cs[2]) + list(cs[3]) for cs in cases]), claim_limit)
    if key in _RUNS:
        return _RUNS[key]
    kg = _inertia(m, p, strong=True)
    M = kg.sum()
    r_m = nodes * 1e-3
    cg = (kg[:, None] * r_m).sum(axis=0) / M
    d_r = r_m - cg
    inertia = np.einsum("n,nij->ij", kg, (d_r ** 2).sum(axis=1)[:, None, None] * np.eye(3)[None]
                        - d_r[:, :, None] * d_r[:, None, :])
    # the hold: three nodes on three posts' tops, A in x y z, B in the two
    # directions square to AB, C in z: no more than stops the body drifting
    tops = m["post_tops"]
    a_n, b_n, c_n = (int(t[np.argmin(np.linalg.norm(nodes[t, :2] - np.array(xy), axis=1))])
                     for t, xy in zip((tops[0], tops[2], tops[1]), (p["fc_post_xy"][0], p["fc_post_xy"][2],
                                                                    p["fc_post_xy"][1])))
    ab = nodes[b_n] - nodes[a_n]
    b_dofs = (2, 3) if abs(ab[0]) >= abs(ab[1]) else (1, 3)
    boundary = [(a_n, 1, 3), (b_n, b_dofs[0], b_dofs[0]), (b_n, b_dofs[1], b_dofs[1]), (c_n, 3, 3)]
    hold = np.array([a_n, b_n, c_n])
    # the surface's corner nodes: the faces that belong to one tetrahedron only
    t4 = m["tets"][:, :4]
    faces = np.sort(np.concatenate([t4[:, [0, 1, 2]], t4[:, [0, 1, 3]], t4[:, [0, 2, 3]], t4[:, [1, 2, 3]]]), axis=1)
    uniq, count = np.unique(faces, axis=0, return_counts=True)
    surf = np.unique(uniq[count == 1])
    loaded = np.nonzero(kg > 0)[0]
    steps, patches, loads_of = [], [], []
    for (_, _, c, d, _) in cases:
        dist = np.linalg.norm(nodes - np.asarray(c), axis=1)
        patch = surf[dist[surf] <= PATCH_MM]
        if not len(patch):
            raise RuntimeError(f"no mesh node within {PATCH_MM} mm of the impact point {tuple(round(v, 2) for v in c)}")
        dv = np.asarray(d, float) / np.linalg.norm(d)
        acc = dv / M                                                   # m/s^2 per N
        torque = np.cross(d_r[patch], np.broadcast_to(dv / len(patch), (len(patch), 3))).sum(axis=0)
        alpha = np.linalg.solve(inertia, torque)
        f_in = -kg[:, None] * (acc[None, :] + np.cross(alpha[None, :], d_r))
        f = np.zeros((len(nodes), 3))
        f[patch] += dv / len(patch)
        f += f_in
        if np.abs(f.sum(axis=0)).max() > 1e-9 or np.abs(np.cross(d_r, f).sum(axis=0)).max() > 1e-11:
            raise RuntimeError("the hit and the inertia do not balance: the masses or the inertia are wrong")
        on = np.unique(np.concatenate([patch, loaded]))
        patches.append(patch)
        loads_of.append(f)
        steps.append(dict(kind="static", loads=[([int(n)], tuple(f[n])) for n in on]))
    work = ctx.out_path(f"impact-{kind}{'-fine' if fine else ''}")
    os.makedirs(work, exist_ok=True)
    deck = os.path.join(work, "impact.inp")
    ccx.write_deck(deck, nodes, m["tets"], materials=m["materials"], element_material=m["elmat"],
                   orientation=m["orientation"], steps=steps, boundary=boundary)
    stem = ccx.run(deck)
    disps = ccx.frd_blocks(stem, "DISP")
    stresses = ccx.frd_blocks(stem, "STRESS")
    if len(disps) != len(steps) or len(stresses) != len(steps):
        raise RuntimeError(f"ccx wrote {len(disps)} displacement and {len(stresses)} stress blocks for {len(steps)} steps")
    lay = np.asarray(p["fea.layer_normal"], float)
    near_hold = cKDTree(nodes[hold]).query(nodes)[0] <= EXCLUDE_MM
    elnode_mat = {}
    for e, name in enumerate(m["elmat"]):
        for nid in m["tets"][e]:
            elnode_mat.setdefault(int(nid), name)
    uts_xy = np.array([m["strength"][elnode_mat.get(i, "FRAME")]["uts_xy"] for i in range(len(nodes))])
    uts_z = np.array([m["strength"][elnode_mat.get(i, "FRAME")]["uts_z"] for i in range(len(nodes))])
    all_tree = cKDTree(nodes)
    tet_vol = ccx.tet_volumes(nodes, m["tets"][:, :4])
    order = np.argsort(m["tets"].ravel(), kind="stable")
    owner = order // m["tets"].shape[1]
    bounds = np.searchsorted(m["tets"].ravel()[order], np.arange(len(nodes) + 1))
    incident = [owner[bounds[i]:bounds[i + 1]] for i in range(len(nodes))]
    # the guard's printed tip gap: its nearest node to motor 1's axis, round the
    # prop's plane, less the prop's radius (the exact arc's is prop_tip_gap)
    mx, my = p["motor_xy"][0]
    rr = np.hypot(nodes[:, 0] - mx, nodes[:, 1] - my)
    band = (np.abs(nodes[:, 2] - p["prop_z"]) <= 1.5) & (rr >= p["prop_r"])
    tip_gap = float(rr[band].min() - p["prop_r"]) if band.any() else float("nan")
    out = []
    for (name, _, c, d, note), patch, f, U, S in zip(cases, patches, loads_of, disps, stresses):
        n = len(nodes)
        U, S = U[:n], S[:n]
        res = ccx.residual(nodes, m["tets"], m["materials"], m["elmat"], m["orientation"], U, f, held=hold)
        if res.max() > RESIDUAL_MAX_N:
            j = int(np.argmax(res))
            raise RuntimeError(f"{name}: ccx's solve is out of equilibrium by {res.max():.3g} N at "
                               f"{tuple(round(float(v), 2) for v in nodes[j])}, for a 1 N hit")
        energy = 0.5 * float((f * U).sum())                            # N mm per N^2: rigid motion does no work
        if energy <= 0:
            raise RuntimeError(f"{name}: the frame stored no strain energy ({energy:.3g})")
        k = 1.0 / (2 * energy)                                         # N/mm: F^2 / (2k) = energy at F
        ok = np.isfinite(S).all(axis=1)
        far_patch = np.linalg.norm(nodes - np.asarray(c), axis=1) > PATCH_EXCLUDE_MM
        judge = np.nonzero(ok & ~near_hold & far_patch)[0]
        s1 = ccx.principal_max(S[judge])
        sn = ccx.normal_stress(S[judge], lay)
        u_in, u_across = np.maximum(s1, 0) / uts_xy[judge], np.maximum(sn, 0) / uts_z[judge]
        util = np.maximum(u_in, u_across)
        # the critical-distance mean round the 300 most-used judged nodes: every
        # tet that reaches within CRIT_MM, each by its volume, at the mean of its
        # nodes' utilisation
        util_all = np.zeros(n)
        util_all[judge] = util
        tet_util = util_all[m["tets"]].mean(axis=1)
        cand = np.argsort(util)[::-1][:300]
        means = []
        for i in cand:
            near = all_tree.query_ball_point(nodes[judge[i]], CRIT_MM)
            ts = np.unique(np.concatenate([incident[j] for j in near]))
            means.append(float((tet_util[ts] * tet_vol[ts]).sum() / tet_vol[ts].sum()))
        means = np.array(means)
        best = int(np.argmax(means))
        worst = int(cand[best])
        u_per_n = float(means[best])
        f_fail = 1.0 / u_per_n                                         # N at which the worst spot reaches strength
        e_fail_mj = f_fail ** 2 * energy                               # N*mm = mJ
        # Goldsmith on the FE's own rigid body: 1/m_eff = 1/M + (r x n).I^-1.(r x n)
        lever = np.cross(np.asarray(c) * 1e-3 - cg, np.asarray(d, float) / np.linalg.norm(d))
        m_eff = 1e3 / (1.0 / M + float(lever @ np.linalg.solve(inertia, lever)))
        where = nodes[judge][worst]
        # how far the hit pushes the patch in at the claim's own energy (linear):
        # a guard pushed further than the tip gap meets the prop before it breaks
        e_claim = (m_eff * 1e-3 * G * claim_limit if kind == "drop" else 0.5 * m_eff * 1e-3 * claim_limit ** 2) * 1e3
        push = math.sqrt(2 * e_claim / k)
        out.append(dict(case=name, note=note, k_n_per_mm=k, f_fail_n=f_fail, e_fail_mj=e_fail_mj, m_eff_g=m_eff,
                        drop_m=e_fail_mj / (m_eff * G * 1e-3 * 1e3) if kind == "drop" else None,
                        speed_m_s=math.sqrt(2 * e_fail_mj * 1e-3 / (m_eff * 1e-3)) if kind == "wall" else None,
                        where=[round(float(v), 1) for v in where], push_mm=push, residual_n=float(res.max()),
                        tip_gap_mm=tip_gap,
                        peak_node_util=float(util[worst]),
                        across_layers=bool(u_across[worst] >= u_in[worst])))
    _RUNS[key] = (out, len(m["tets"]), stem)
    return _RUNS[key]


def _worst(res, kind):
    return min(res, key=lambda x: x["drop_m" if kind == "drop" else "speed_m_s"])


# --------------------------------------------------------------------------- #
@gate(
    id="petgasus.fea_converged",
    basis="sourced",    # a mesh-convergence study (references/methods.md in the solid-fea pack)
    title="The CalculiX results do not move with the mesh",
    claims=["arm-vibration", "crash-drop", "crash-wall"],
    tier=Tier.SOLVE,
    settles="mesh convergence of the CalculiX results",
    requires_tools=["ccx"],
    requires_python=["gmsh", "wildmeshing", "numpy", "scipy"],
    negative_control=NegativeControl(
        fixture="selftest/bad_configs.py:coarse_fea_mesh",
        note="the known-good frame's analysis surface at a 3 mm edge: coarser than its limbs"),
)
def fea_converged(ctx: GateContext) -> Verdict:
    """A validity guard for the gates below (their `needs`): every number they
    judge, worked out on the analysis mesh (tets to fea.mesh_mm inside the
    fea_surface_mm level set) and on a fine one (the level set at 0.7 of that
    edge, tets to 0.75 of the size): the first mode within CONVERGED, the drop
    height and the wall speed within CONVERGED_CRASH. Measured as the worst
    change over its tolerance (1.0 is the edge). The first version compared only
    the first mode, and a crash number off by 24x passed it."""
    p = ctx.params
    size = float(p["fea.mesh_mm"])
    f1, n1, _ = _modes(ctx, size, "base")
    f2, n2, _ = _modes(ctx, size * 0.75, "fine", fine=True)
    acc15, acc16 = ctx.acceptance("C15"), ctx.acceptance("C16")
    d1 = _worst(_impact(ctx, "drop", float(acc15.limit))[0], "drop")["drop_m"]
    d2 = _worst(_impact(ctx, "drop", float(acc15.limit), fine=True)[0], "drop")["drop_m"]
    w1 = _worst(_impact(ctx, "wall", float(acc16.limit))[0], "wall")["speed_m_s"]
    w2 = _worst(_impact(ctx, "wall", float(acc16.limit), fine=True)[0], "wall")["speed_m_s"]
    changes = {"first mode": (abs(f1[0] - f2[0]) / f2[0], CONVERGED),
               "drop height": (abs(d1 - d2) / d2, CONVERGED_CRASH),
               "wall speed": (abs(w1 - w2) / w2, CONVERGED_CRASH)}
    worst = round(max(ch / tol for ch, tol in changes.values()), 3)
    return Verdict(gate="petgasus.fea_converged", passed=worst <= 1.0, measured=worst, limit=1.0,
                   comparator="<=", units="x tolerance",
                   detail=f"first mode {f1[0]:.0f} Hz on {n1} tets, {f2[0]:.0f} Hz on {n2} (finer surface, "
                          f"tets to {size * 0.75:.2f} mm); drop {d1:.3f} / {d2:.3f} m, wall {w1:.3f} / {w2:.3f} m/s; "
                          + ", ".join(f"{k} {ch:.1%} (tolerance {tol:.0%})" for k, (ch, tol) in changes.items()))


@gate(
    id="petgasus.frame_mode",
    basis="established",    # CalculiX's own eigenfrequency
    title="First frame mode, CalculiX on the printed shape",
    claims=["arm-vibration"],
    tier=Tier.SOLVE,
    settles="first frame mode",
    requires_tools=["ccx"],
    requires_python=["gmsh", "wildmeshing", "numpy", "scipy"],
    needs=["petgasus.fea_converged"],    # a validity guard: an unconverged mesh's mode means nothing
    negative_control=NegativeControl(
        fixture="selftest/bad_configs.py:tpu_frame",
        note="the known-good frame printed in TPU 95A: the same shape, 54x softer"),
)
def frame_mode(ctx: GateContext) -> Verdict:
    """Quadratic tets in the everyday filament, held at the FC posts' top faces
    and the strap's saddle, motor + prop masses on the seats; the lowest
    eigenfrequency."""
    p = ctx.params
    freqs, n, stem = _modes(ctx, float(p["fea.mesh_mm"]), "base")
    acc = ctx.acceptance("C4")
    f1 = round(freqs[0], 1)
    if f1 < 1.0:
        raise RuntimeError(f"a {f1} Hz first mode is a loose piece or a missing support, not a frequency")
    return Verdict(gate="petgasus.frame_mode", passed=acc.holds(f1), measured=f1, limit=acc.limit,
                   comparator=acc.comparator.value, units="Hz",
                   detail=f"modes {', '.join(f'{f:.0f}' for f in freqs[:4])} Hz on {n} tets, held at the FC posts "
                          f"and the strap saddle; motors turn at ~{p['motor_freq_hover_hz']:.0f} Hz in a hover",
                   evidence=[stem + ".dat"])


@gate(
    id="petgasus.crash_drop",
    basis="sourced",    # CalculiX's stresses, then Goldsmith's effective mass and Taylor's critical distance
    title="A drop onto a guard stays under the printed strength",
    claims=["crash-drop"],
    tier=Tier.SOLVE,
    settles="survivable drop height",
    requires_tools=["ccx"],
    requires_python=["gmsh", "wildmeshing", "numpy", "scipy"],
    needs=["petgasus.fea_converged"],
    negative_control=NegativeControl(
        fixture="selftest/bad_configs.py:weak_layers",
        note="the known-good frame with a filament at a tenth of its strength"),
)
def crash_drop(ctx: GateContext) -> Verdict:
    """Elastic energy method (Roark's falling-weight case, with Goldsmith's
    effective mass for a hit away from the centre of mass), in the strong
    filament: the height from which the drone, landing on one guard's outermost
    underside, brings the frame's worst spot (outside the hold and the contact
    patch) to its strength. A floor, not a prediction: it ignores the plastic
    work the filament does before it breaks and anything the floor gives."""
    acc = ctx.acceptance("C15")
    res, n, stem = _impact(ctx, "drop", float(acc.limit))
    r = _worst(res, "drop")
    h = round(r["drop_m"], 3)
    p = ctx.params
    return Verdict(gate="petgasus.crash_drop", passed=acc.holds(h), measured=h, limit=acc.limit,
                   comparator=acc.comparator.value, units="m",
                   detail=f"in {p['fea.strong_name']}, guard underside {r['note']}: {r['k_n_per_mm']:.1f} N/mm, breaks at "
                          f"{r['f_fail_n']:.1f} N ({'across' if r['across_layers'] else 'along'} the layers at "
                          f"{r['where']}), {r['e_fail_mj']:.1f} mJ; {r['m_eff_g']:.1f} g of the "
                          f"{p['strong_auw_g']:.0f} g takes the hit; {n} tets, residual {r['residual_n']:.3f} N",
                   evidence=[stem + ".frd"])


@gate(
    id="petgasus.crash_wall",
    basis="sourced",    # CalculiX's stresses, then Goldsmith's effective mass and Taylor's critical distance
    title="A hit on a wall stays under the printed strength",
    claims=["crash-wall"],
    tier=Tier.SOLVE,
    settles="survivable wall speed",
    requires_tools=["ccx"],
    requires_python=["gmsh", "wildmeshing", "numpy", "scipy"],
    needs=["petgasus.fea_converged"],
    negative_control=NegativeControl(
        fixture="selftest/bad_configs.py:weak_layers",
        note="the known-good frame with a filament at a tenth of its strength"),
)
def crash_wall(ctx: GateContext) -> Verdict:
    """As crash_drop, for two wall hits on a guard's outer face: square on at the
    point facing forward (off the centre of mass: the drone spins) and head on
    along the arm's line, in line with the centre in plan (most of its mass behind
    the hit). The slower of the two."""
    acc = ctx.acceptance("C16")
    res, n, stem = _impact(ctx, "wall", float(acc.limit))
    r = _worst(res, "wall")
    v = round(r["speed_m_s"], 3)
    p = ctx.params
    others = "; ".join(f"{x['case']} {x['speed_m_s']:.2f} m/s" for x in res)
    return Verdict(gate="petgasus.crash_wall", passed=acc.holds(v), measured=v, limit=acc.limit,
                   comparator=acc.comparator.value, units="m/s",
                   detail=f"in {p['fea.strong_name']}, {r['case']}: {r['k_n_per_mm']:.1f} N/mm, breaks at "
                          f"{r['f_fail_n']:.1f} N ({'across' if r['across_layers'] else 'along'} the layers at "
                          f"{r['where']}), {r['e_fail_mj']:.1f} mJ into {r['m_eff_g']:.1f} g; at {acc.limit:g} m/s the "
                          f"guard is pushed in {max(x['push_mm'] for x in res):.1f} mm (the printed tip gap "
                          f"{r['tip_gap_mm']:.1f}); {others}; {n} tets",
                   evidence=[stem + ".frd"])
