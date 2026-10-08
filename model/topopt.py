"""topopt.py — 2.5D topology optimisation of PETGasus's base-plate layout.

What it optimises: WHERE the plate material goes (arms, spokes, hub) inside the
frame's footprint, for a fixed plate thickness. The ducts, webs, motor seats and
FC posts are fixed (passive) and modelled at their real height.

Physics, on one square grid of size `h`:
  * bending  — Kirchhoff plate (ACM 12-dof rectangle). One motor's full thrust
               pushing its seat up, hub clamped at the FC posts. This is the
               load path behind arm flex and the vibration complaint.
  * in-plane — plane stress (Q4). A crash: a radial and a tangential hit on one
               duct's outer rim, hub clamped. This is what breaks frames.
Objective: weighted sum of the compliances, each normalised by the starting
design's. Constraint: a weighted area budget, where plate material under a prop
costs `prop_block_mm` of extra depth per mm^2 (see weight_cost): it blocks the downwash.

The density field is forced to the frame's 8-fold (D4) symmetry by averaging
sensitivities over the symmetry group, so one corner's load cases design all
four corners. SIMP (p=3), density filter (radius sets the thinnest member),
optimality-criteria update — the method of Andreassen et al., "Efficient
topology optimization in MATLAB using 88 lines of code" (2011), extended to a
plate element and two physics.

What it does NOT do (read before trusting a pretty picture):
  * no 3D: a duct is a ring of plate elements with its wall height as thickness,
    a 2.5D stand-in; the rib/duct torsion it implies is approximate.
  * no stress, no buckling, no fatigue: compliance (stiffness) only.
  * no direct frequency objective: frequency is MEASURED afterwards
    (`modal()`), on the same model, for the baseline and the optimised layout.

Deterministic: same inputs -> same field. build() caches results under
build/topopt/<input hash>.npz, because a run takes tens of seconds.
"""
from __future__ import annotations

import hashlib
import json
import math
import os

import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spla

NU = 0.35          # PETG Poisson ratio (printed: 0.33-0.38)


# --------------------------------------------------------------------------- #
# element matrices
# --------------------------------------------------------------------------- #
def _q4_plane_stress(nu=NU):
    """Unit-modulus, unit-thickness bilinear square (size-independent in 2D)."""
    k = np.array([1/2 - nu/6, 1/8 + nu/8, -1/4 - nu/12, -1/8 + 3*nu/8,
                  -1/4 + nu/12, -1/8 - nu/8, nu/6, 1/8 - 3*nu/8])
    KE = 1 / (1 - nu**2) * np.array([
        [k[0], k[1], k[2], k[3], k[4], k[5], k[6], k[7]],
        [k[1], k[0], k[7], k[6], k[5], k[4], k[3], k[2]],
        [k[2], k[7], k[0], k[5], k[6], k[3], k[4], k[1]],
        [k[3], k[6], k[5], k[0], k[7], k[2], k[1], k[4]],
        [k[4], k[5], k[6], k[7], k[0], k[1], k[2], k[3]],
        [k[5], k[4], k[3], k[2], k[1], k[0], k[7], k[6]],
        [k[6], k[3], k[4], k[1], k[2], k[7], k[0], k[5]],
        [k[7], k[2], k[1], k[4], k[3], k[6], k[5], k[0]]])
    return KE


def _acm_plate(h, nu=NU):
    """ACM 12-dof Kirchhoff rectangle, side h, unit flexural rigidity D=1.

    Nodes counter-clockwise from (0,0); dofs per node (w, dw/dy, -dw/dx).
    Built numerically from the 12-term polynomial and 4x4 Gauss quadrature, so
    the code can be read against the textbook definition rather than trusted.
    """
    def terms(x, y):
        return np.array([1, x, y, x*x, x*y, y*y, x**3, x*x*y, x*y*y, y**3, x**3*y, x*y**3])

    def dterms(x, y):          # (dw/dx, dw/dy) rows
        dx = np.array([0, 1, 0, 2*x, y, 0, 3*x*x, 2*x*y, y*y, 0, 3*x*x*y, y**3])
        dy = np.array([0, 0, 1, 0, x, 2*y, 0, x*x, 2*x*y, 3*y*y, x**3, 3*x*y*y])
        return dx, dy

    def curv(x, y):            # (w_xx, w_yy, 2 w_xy)
        wxx = np.array([0, 0, 0, 2, 0, 0, 6*x, 2*y, 0, 0, 6*x*y, 0])
        wyy = np.array([0, 0, 0, 0, 0, 2, 0, 0, 2*x, 6*y, 0, 6*x*y])
        wxy = np.array([0, 0, 0, 0, 1, 0, 0, 2*x, 2*y, 0, 3*x*x, 3*y*y])
        return np.vstack([wxx, wyy, 2*wxy])

    nodes = [(0, 0), (h, 0), (h, h), (0, h)]
    C = []
    for (x, y) in nodes:
        dx, dy = dterms(x, y)
        C += [terms(x, y), dy, -dx]
    Cinv = np.linalg.inv(np.array(C))
    Dm = np.array([[1, nu, 0], [nu, 1, 0], [0, 0, (1 - nu) / 2]])
    g, wts = np.polynomial.legendre.leggauss(4)
    K = np.zeros((12, 12))
    for gi, wi in zip(g, wts):
        for gj, wj in zip(g, wts):
            x, y = (gi + 1) * h / 2, (gj + 1) * h / 2
            B = curv(x, y) @ Cinv
            K += B.T @ Dm @ B * wi * wj * (h / 2) ** 2
    return K


# --------------------------------------------------------------------------- #
# the grid and its regions
# --------------------------------------------------------------------------- #
class Grid:
    def __init__(self, half, h):
        self.h = h
        self.n = int(math.ceil(2 * half / h))
        if self.n % 2:
            self.n += 1
        self.half = self.n * h / 2
        c = (np.arange(self.n) + 0.5) * h - self.half
        self.xc, self.yc = np.meshgrid(c, c, indexing="xy")   # [row=y, col=x]
        nn = self.n + 1
        self.nn = nn
        # element -> 4 nodes, counter-clockwise from lower-left
        ey, ex = np.meshgrid(np.arange(self.n), np.arange(self.n), indexing="ij")
        n0 = ey * nn + ex
        self.enodes = np.stack([n0, n0 + 1, n0 + nn + 1, n0 + nn], axis=-1).reshape(-1, 4)
        nyy, nxx = np.meshgrid(np.arange(nn), np.arange(nn), indexing="ij")
        self.nx = nxx.ravel() * h - self.half
        self.ny = nyy.ravel() * h - self.half

    def sym_index(self):
        """For each of the 8 D4 maps, the flat element index each element maps to."""
        n = self.n
        idx = np.arange(n * n).reshape(n, n)
        maps = []
        for k in range(4):
            r = np.rot90(idx, k)
            maps += [r, r.T]
        return [m.ravel() for m in maps]


def _thin(true_w, h):
    """Raster width for a thin feature: at least 2.2 elements, so a diagonal or
    curved strip is joined edge-to-edge. Strips one element wide on a square grid
    touch only at corners - a chain of hinges, which read the first baseline run
    as a 100 mm crash deflection."""
    return max(true_w, 2.2 * h)


def _equiv(true_w, height, raster_w):
    """(t_bend, t_area) for a wall `true_w` wide and `height` tall drawn `raster_w` wide.

    t_bend keeps the out-of-plane bending stiffness (w t^3 constant); t_area keeps
    the axial stiffness and the mass (w t constant). The wall's IN-PLANE bending
    comes out (raster_w/true_w)^2 too stiff - the 2.5D model's stated error.
    """
    return height * (true_w / raster_w) ** (1 / 3), height * true_w / raster_w


def _seg_dist(px, py, x0, y0, x1, y1):
    vx, vy = x1 - x0, y1 - y0
    t = np.clip(((px - x0) * vx + (py - y0) * vy) / (vx * vx + vy * vy), 0, 1)
    return np.hypot(px - (x0 + t * vx), py - (y0 + t * vy))


def _fc_zone(c, d, X, Y):
    """The AIO's footprint (turned by fc_yaw_deg) grown by member_clear."""
    yaw = math.radians(c.fc_yaw_deg)
    u = X * math.cos(yaw) + Y * math.sin(yaw)
    v = -X * math.sin(yaw) + Y * math.cos(yaw)
    half = c.fc_board_side / 2 + c.member_clear
    return (np.abs(u) <= half) & (np.abs(v) <= half)


def _regions(c, d, g: Grid):
    """Element masks and the per-element 2.5D thicknesses of the fixed parts."""
    a = d["motor_offset"]
    X, Y = g.xc.ravel(), g.yc.ravel()
    centres = [(a, a), (a, -a), (-a, a), (-a, -a)]
    r_to = np.min([np.hypot(X - mx, Y - my) for (mx, my) in centres], axis=0)

    ring_w = _thin(c.duct_wall, g.h)
    seat = r_to <= d["mount_r"]
    ring = (r_to >= d["duct_r_out"] - ring_w) & (r_to <= d["duct_r_out"])
    foot = (r_to >= d["duct_r_out"] - c.foot_w) & (r_to <= d["duct_r_out"])
    in_duct = r_to < d["duct_r_out"] - ring_w
    under_prop = in_duct & (r_to <= d["prop_r"]) & ~seat
    central = (np.abs(X) <= a) & (np.abs(Y) <= a)
    web_w = _thin(c.duct_wall, g.h)
    web = (((np.abs(np.abs(X) - a) <= web_w / 2) & (np.abs(Y) <= a)) |
           ((np.abs(np.abs(Y) - a) <= web_w / 2) & (np.abs(X) <= a))) & (r_to > d["duct_r_out"] - ring_w)
    posts = np.zeros_like(seat)
    for (px, py) in d["fc_post_xy"]:
        posts |= np.hypot(X - px, Y - py) <= c.fc_post_od / 2 + c.hub_margin
    slots = np.zeros_like(seat)
    for sy in (1, -1):
        slots |= (np.abs(X) <= d["strap_slot_len"] / 2 + 0.3) & \
                 (np.abs(Y - sy * d["strap_slot_y"]) <= c.strap_slot_w / 2 + 0.3)

    # the hub plate is required, not designable: the battery strap bears on it and
    # it shields the AIO's underside from the pack. The first optimised run (posts
    # clamped, hub free) emptied it - true to the model, useless to the strap.
    s_hub = max(abs(p[0]) + abs(p[1]) for p in d["fc_post_xy"])
    hub = ((np.abs(X) + np.abs(Y)) <= s_hub + (c.fc_post_od / 2 + c.hub_margin) * math.sqrt(2)) & ~slots
    solid = seat | ring | foot | web | posts | hub
    domain = (in_duct | central) & ~solid & ~slots
    # where a designed member must stay plate-thin: under the motor's base (it sits
    # there) and under the AIO (the strap runs over the hub, under the board)
    flat = (r_to <= c.motor_body_d / 2 + c.member_clear) | _fc_zone(c, d, X, Y)
    tb = np.where(domain & ~flat, c.topopt_member_h, c.plate_t).astype(float)
    ta = tb.copy()
    tb[hub], ta[hub] = c.hub_t, c.hub_t
    tb[posts], ta[posts] = c.plate_t, c.plate_t
    tb[web], ta[web] = _equiv(c.duct_wall, c.web_h, web_w)
    tb[ring], ta[ring] = _equiv(c.duct_wall, d["duct_h"], ring_w)
    # the foot flange is inside the ring raster; add its plate on top
    ta[ring & foot] += c.plate_t * (c.foot_w - c.duct_wall) / ring_w if c.foot_w > ring_w else 0
    return {"solid": solid, "domain": domain, "under_prop": under_prop, "posts": posts, "ring": ring,
            "flat": flat, "hub": hub, "slots": slots,
            "seat": seat, "tb": tb, "ta": ta, "centres": centres, "r_to": r_to}


def layout_density(c, d, g: Grid, reg, mems):
    """Rasterise a member list (geometry.members) onto g: (rho, tb, ta).

    A flat member is plate_t thick. A ribbed stretch is drawn _thin(rib_w) wide
    with the equivalent thicknesses of a rib_w x H rib standing in a plate_t
    strip of that width: w*tb^3 and w*ta are kept (bending; mass and axial).
    Members over the hub take plate_t there (the bars are unioned over it).
    """
    X, Y = g.xc.ravel(), g.yc.ravel()
    rho = np.zeros(X.shape)
    tb, ta = reg["tb"].copy(), reg["ta"].copy()
    tb[reg["domain"]] = ta[reg["domain"]] = c.plate_t
    open_ = ~reg["solid"] | reg["hub"]
    wr = _thin(c.rib_w, g.h)
    for mem in mems:
        on = (_seg_dist(X, Y, *mem["p0"], *mem["p1"]) <= mem["w"] / 2) & open_
        rho[on] = 1
        tb[on & reg["hub"]] = ta[on & reg["hub"]] = c.plate_t
        if mem["rib"]:
            H = c.plate_t + mem["rib_h"]
            rib = (_seg_dist(X, Y, *mem["rib"][0], *mem["rib"][1]) <= wr / 2) & open_
            rho[rib] = 1
            tb[rib] = (((wr - c.rib_w) * c.plate_t ** 3 + c.rib_w * H ** 3) / wr) ** (1 / 3)
            ta[rib] = ((wr - c.rib_w) * c.plate_t + c.rib_w * H) / wr
    rho[reg["solid"]] = 1
    rho[~(reg["domain"] | reg["solid"])] = 0
    return rho, tb, ta


def baseline_density(c, d, g: Grid, reg):
    """The hand-drawn 'arms' layout on g - the optimiser's mass budget and its
    yardstick, whatever layout is live."""
    import dataclasses
    import geometry_petgasus as geo
    return layout_density(c, d, g, reg, geo.members(dataclasses.replace(c, plate_layout="arms"), d))


# --------------------------------------------------------------------------- #
# FE assembly
# --------------------------------------------------------------------------- #
class FE:
    def __init__(self, g: Grid, E, reg):
        self.g, self.E, self.reg = g, E, reg
        self.KEp = _acm_plate(g.h)                     # D = 1
        self.KEs = _q4_plane_stress()                  # E = 1, t = 1
        en = g.enodes
        self.edof_p = np.stack([3 * en + k for k in range(3)], axis=-1).reshape(-1, 12)
        self.edof_s = np.stack([2 * en + k for k in range(2)], axis=-1).reshape(-1, 8)
        nn = g.nn * g.nn
        self.ndof_p, self.ndof_s = 3 * nn, 2 * nn
        # clamp: every node of a post element
        post_nodes = np.unique(en[reg["posts"]])
        self.fixed_p = np.concatenate([3 * post_nodes + k for k in range(3)])
        self.fixed_s = np.concatenate([2 * post_nodes + k for k in range(2)])
        self.free_p = np.setdiff1d(np.arange(self.ndof_p), self.fixed_p)
        self.free_s = np.setdiff1d(np.arange(self.ndof_s), self.fixed_s)
        ip = np.kron(self.edof_p, np.ones((12, 1), int)).ravel()
        jp = np.kron(self.edof_p, np.ones((1, 12), int)).ravel()
        self.ij_p = (ip, jp)
        is_ = np.kron(self.edof_s, np.ones((8, 1), int)).ravel()
        js_ = np.kron(self.edof_s, np.ones((1, 8), int)).ravel()
        self.ij_s = (is_, js_)

    def K_plate(self, stiff):          # stiff: per-element D (N mm)
        v = (self.KEp.ravel()[None, :] * stiff[:, None]).ravel()
        K = sp.coo_matrix((v, self.ij_p), shape=(self.ndof_p,) * 2).tocsc()
        return K

    def K_stress(self, stiff):         # stiff: per-element E*t (N/mm)
        v = (self.KEs.ravel()[None, :] * stiff[:, None]).ravel()
        return sp.coo_matrix((v, self.ij_s), shape=(self.ndof_s,) * 2).tocsc()

    def solve(self, K, f, free):
        u = np.zeros(K.shape[0])
        Kf = K[free][:, free]
        u[free] = spla.spsolve(Kf, f[free])
        return u


def _fixed_mass_kg(c, d, g, reg):
    """Per-node mass (kg) of everything the optimiser cannot move: ducts, webs,
    seats, and the motors+props at the seat centres."""
    dens = 1.27e-6                                   # kg/mm^3
    me = np.where(reg["solid"] & ~reg["posts"], reg["ta"], 0.0) * g.h * g.h * dens
    m = np.zeros(g.nn * g.nn)
    np.add.at(m, g.enodes.ravel(), np.repeat(me / 4, 4))
    for (mx, my) in reg["centres"]:
        m[int(np.argmin(np.hypot(g.nx - mx, g.ny - my)))] += (c.motor_mass_g + c.prop_mass_g) / 1000
    return m


def _loads(c, d, g: Grid, reg, fe: "FE"):
    """Load vectors: one bending case, two in-plane cases.

    Bending: every fixed mass (ducts, webs, seats, motors, props) accelerated
    vertically at `bounce_g` g, hub clamped. That is the shape of the frame's
    first ("umbrella") mode - the duct pods bouncing on the arms - so stiffening
    against it raises the frequency C4 measures. Motor thrust alone, the first
    version, left the ducts' own mass out and drew arms that were stiff at the
    seat and floppy at the duct.
    In-plane: a radial and a tangential hit on the front-left duct's outer rim.
    """
    a = d["motor_offset"]
    m = _fixed_mass_kg(c, d, g, reg)
    f1 = np.zeros(fe.ndof_p)
    f1[3 * np.arange(g.nn * g.nn)] = m * 9.80665 * c.bounce_g      # N
    nx, ny = g.nx, g.ny
    ang = math.pi / 4
    px, py = a + d["duct_r_out"] * math.cos(ang), a + d["duct_r_out"] * math.sin(ang)
    # only nodes OF ring elements: a node just outside the ring belongs to void
    # elements alone, and a load there measured 500 mm of "deflection" (first run)
    ring_nodes = np.unique(g.enodes[reg["ring"]])
    rim = ring_nodes[np.hypot(nx[ring_nodes] - px, ny[ring_nodes] - py) <= 2.0]
    crash_n = c.crash_load_n
    f2 = np.zeros(fe.ndof_s)
    f2[2 * rim] = -crash_n * math.cos(ang) / len(rim)
    f2[2 * rim + 1] = -crash_n * math.sin(ang) / len(rim)
    f3 = np.zeros(fe.ndof_s)
    f3[2 * rim] = -crash_n * math.sin(ang) / len(rim)
    f3[2 * rim + 1] = crash_n * math.cos(ang) / len(rim)
    return f1, [f2, f3]


PENAL = 3.0
XMIN = 1e-6


def _stiffness(rho, tb, ta, E):
    x = XMIN + (1 - XMIN) * rho ** PENAL
    return E * tb ** 3 / (12 * (1 - NU ** 2)) * x, E * ta * x


def evaluate(c, d, g, reg, fe, rho, tb, ta):
    """Compliances (N mm) of a layout under the three load cases, and its mass (g)."""
    D, Et = _stiffness(rho, tb, ta, fe.E)
    f1, fs = _loads(c, d, g, reg, fe)
    u1 = fe.solve(fe.K_plate(D), f1, fe.free_p)
    Ks = fe.K_stress(Et)
    comp = [float(f1 @ u1)] + [float(f @ fe.solve(Ks, f, fe.free_s)) for f in fs]
    return comp


def plate_mass_g(g, reg, rho, ta):
    """Mass of the designable plate (everything not fixed), g."""
    return float((rho * ta)[~reg["solid"]].sum() * g.h * g.h * 1.27e-3)


def modal(c, d, g, reg, fe, rho, tb, ta, k=4):
    """Lowest out-of-plane natural frequencies (Hz), hub clamped at the FC posts.

    Units mm-kg-s throughout: K in N/mm is 1000 kg/s^2 per mm, so K x 1000.
    Lumped mass on the w dof (fixed parts + designed plate + motors/props);
    the rotation dofs get a 1e-12 regulariser so M is definite.
    """
    D, _ = _stiffness(rho, tb, ta, fe.E)
    K = fe.K_plate(D) * 1000.0
    me = rho * ta * g.h * g.h * 1.27e-6
    me = np.where(reg["solid"] & ~reg["posts"], 0.0, me)          # fixed mass added below
    m = np.zeros(fe.ndof_p)
    np.add.at(m, 3 * g.enodes.ravel(), np.repeat(me / 4, 4))
    m[3 * np.arange(g.nn * g.nn)] += _fixed_mass_kg(c, d, g, reg)
    m[3 * np.arange(g.nn * g.nn) + 1] += 1e-12
    m[3 * np.arange(g.nn * g.nn) + 2] += 1e-12
    free = fe.free_p
    # shift -1 (not 0): a part that is not attached (a seat with no spokes) has a
    # zero-frequency mode, and K - 0*M is then singular; K + M never is
    vals = spla.eigsh(K[free][:, free], k=k, M=sp.diags(m[free]), sigma=-1.0, which="LM",
                      return_eigenvectors=False)
    return sorted(float(np.sqrt(max(v, 0)) / (2 * math.pi)) for v in vals)


# --------------------------------------------------------------------------- #
# optimisation
# --------------------------------------------------------------------------- #
def setup(c, d):
    g = Grid(d["motor_offset"] + d["duct_r_out"] + 1.0, c.topopt_h)
    reg = _regions(c, d, g)
    fe = FE(g, 1800.0, reg)
    return g, reg, fe


def weight_cost(c, reg, ta):
    """Per-element cost per mm^2 of plan area: its depth (mass, as mm^3) plus, under
    a prop, `prop_block_mm` of equivalent depth for blocking the downwash.

    Blockage goes with PLAN area, mass with volume; the first version multiplied
    the two (3x cost x depth), which charged a deep spoke under a prop 14 mm^3 per
    mm^2 and starved every spoke to a grey thread."""
    return ta + np.where(reg["under_prop"], c.prop_block_mm, 0.0)


def optimise(c, d, g, reg, fe, *, budget_vol_mm3, log=None):
    """SIMP + density filter + OC, D4-symmetric. Returns (rho, tb, ta, history).

    Constraint: prop-weighted designable VOLUME (sum rho * cost * ta * h^2), so a
    deep member and a flat one are charged for the grams they actually weigh."""
    domain, solid = reg["domain"], reg["solid"]
    tb, ta = reg["tb"].copy(), reg["ta"].copy()
    wcost = weight_cost(c, reg, ta)
    syms = g.sym_index()

    rmin = c.topopt_rmin
    rr = int(math.ceil(rmin / g.h))
    n = g.n
    rows, cols, vals = [], [], []
    iy, ix = np.divmod(np.arange(n * n), n)
    for dy in range(-rr, rr + 1):
        for dx in range(-rr, rr + 1):
            w = rmin - g.h * math.hypot(dx, dy)
            if w <= 0:
                continue
            jy, jx = iy + dy, ix + dx
            ok = (jy >= 0) & (jy < n) & (jx >= 0) & (jx < n)
            rows.append(np.arange(n * n)[ok]); cols.append((jy * n + jx)[ok]); vals.append(np.full(ok.sum(), w))
    H = sp.coo_matrix((np.concatenate(vals), (np.concatenate(rows), np.concatenate(cols))),
                      shape=(n * n, n * n)).tocsr()
    Hs = np.asarray(H.sum(axis=1)).ravel()

    # Heaviside projection (Wang, Lazarov & Sigmund 2011) with beta continuation:
    # the filtered field is pushed to 0/1 so the layout that is extruded is the
    # layout that was optimised. Without it the first run left 12% of the domain
    # grey, and thresholding at 0.5 threw away 43% of the plate it had designed.
    eta = 0.5
    beta = [1.0]

    def project(xt):
        b = beta[0]
        return (math.tanh(b * eta) + np.tanh(b * (xt - eta))) / (math.tanh(b * eta) + math.tanh(b * (1 - eta)))

    def dproject(xt):
        b = beta[0]
        return b * (1 - np.tanh(b * (xt - eta)) ** 2) / (math.tanh(b * eta) + math.tanh(b * (1 - eta)))

    def phys(x):
        r = project(np.asarray(H @ x).ravel() / Hs)
        r[solid] = 1.0
        r[~(domain | solid)] = 0.0
        return r

    def vol_of(r):
        return (r[domain] * wcost[domain]).sum() * g.h * g.h

    x = np.where(domain, min(1.0, budget_vol_mm3 / (wcost[domain].sum() * g.h * g.h)), 0.0)
    x[solid] = 1.0
    f1, fs = _loads(c, d, g, reg, fe)
    weights = [c.topopt_w_thrust, c.topopt_w_crash / 2, c.topopt_w_crash / 2]
    c0, history = None, []
    dD_unit = 3 * (1 - XMIN) * fe.E * tb ** 3 / (12 * (1 - NU ** 2))
    dEt_unit = 3 * (1 - XMIN) * fe.E * ta
    for it in range(c.topopt_iters):
        rho = phys(x)
        D, Et = _stiffness(rho, tb, ta, fe.E)
        u1 = fe.solve(fe.K_plate(D), f1, fe.free_p)
        ue = u1[fe.edof_p]
        comps = [float(f1 @ u1)]
        dcs = [-dD_unit * rho ** 2 * np.einsum("ij,jk,ik->i", ue, fe.KEp, ue)]
        Ks = fe.K_stress(Et)
        lu = spla.splu(Ks[fe.free_s][:, fe.free_s].tocsc())
        for f in fs:
            u = np.zeros(fe.ndof_s)
            u[fe.free_s] = lu.solve(f[fe.free_s])
            comps.append(float(f @ u))
            us = u[fe.edof_s]
            dcs.append(-dEt_unit * rho ** 2 * np.einsum("ij,jk,ik->i", us, fe.KEs, us))
        if c0 is None:
            c0 = comps
        obj = sum(w * ci / c0i for w, ci, c0i in zip(weights, comps, c0))
        dc = sum(w * dci / c0i for w, dci, c0i in zip(weights, dcs, c0))
        dc = np.mean([dc[s] for s in syms], axis=0)                 # D4 symmetry
        dp = dproject(np.asarray(H @ x).ravel() / Hs)
        dc = np.asarray(H.T @ (dc * dp / Hs)).ravel()
        dv = np.asarray(H.T @ (wcost * dp / Hs)).ravel()
        dv = np.maximum(dv, 1e-12)
        l1, l2, move = 1e-12, 1e12, 0.15
        while (l2 - l1) / (l1 + l2) > 1e-5:
            lm = 0.5 * (l1 + l2)
            xn = np.clip(x * np.sqrt(np.maximum(-dc, 1e-30) / (dv * lm)),
                         np.maximum(0, x - move), np.minimum(1, x + move))
            xn[~domain] = x[~domain]
            if vol_of(phys(xn)) > budget_vol_mm3:
                l1 = lm
            else:
                l2 = lm
        change = float(np.abs(xn - x).max())
        x = xn
        history.append(round(obj, 5))
        if log:
            log(f"it {it:3d} obj {obj:.4f} change {change:.3f}")
        # continuation: sharpen the projection every 20 iterations up to beta 16
        if (it + 1) % 20 == 0 and beta[0] < 16:
            beta[0] *= 2
        elif beta[0] >= 16 and change < 0.01:
            break
    rho = phys(x)
    return rho, tb, ta, history


#: Config fields the optimiser reads (directly or through baseline_density, whose
#: mass sets the budget). The cache key is these, the derived layout and this
#: file's source - NOT the whole Config, so a battery or screw change reuses a
#: finished optimisation instead of re-running a five-minute one.
TOPOPT_INPUTS = (
    "plate_t", "arm_w", "rib_w", "rib_h", "spoke_w", "duct_wall", "web_h", "foot_w",
    "fc_post_od", "hub_margin", "hub_t", "strap_slot_w", "motor_body_d", "member_clear",
    "fc_board_side", "fc_yaw_deg", "motor_mass_g", "prop_mass_g", "topopt_h", "topopt_rmin",
    "prop_block_mm", "bounce_g", "crash_load_n", "topopt_w_thrust", "topopt_w_crash",
    "topopt_iters", "topopt_member_h", "topopt_mass_frac",
)


def input_hash(c, d, budget):
    blob = json.dumps({"c": {k: getattr(c, k) for k in TOPOPT_INPUTS}, "d": {k: d[k] for k in sorted(d)},
                       "b": budget, "code": hashlib.sha256(open(__file__, "rb").read()).hexdigest()},
                      sort_keys=True, default=str)
    return hashlib.sha256(blob.encode()).hexdigest()[:16]


def rasterise(g: Grid, polys):
    """Element-centre point-in-polygon (even-odd) of a CrossSection's polygons.

    Puts the EXTRACTED, smoothed, cleaned plate back on the FE grid, so the
    frequencies and stiffnesses reported are those of the geometry that prints,
    not of the optimiser's density field (rule 6)."""
    from matplotlib.path import Path
    pts = np.column_stack([g.xc.ravel(), g.yc.ravel()])
    inside = np.zeros(len(pts), bool)
    for poly in polys:
        if len(poly) >= 3:
            inside ^= Path(np.asarray(poly)).contains_points(pts)
    return inside.astype(float)
