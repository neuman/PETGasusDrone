"""fea.print_orientation — propose how to stand a part on the bed.

A proposer: it settles nothing. For every candidate build direction (the part
tilted by `tilt` degrees about a horizontal axis at `azimuth` degrees, in steps),
it measures two things about the part's surface and stress:

  * support: the area of downward faces steeper than the overhang angle (the
    slicer will support them), as a fraction of the whole surface, leaving out
    faces within a layer of the bed;
  * layers: if CalculiX results are given (`--frd`, repeatable, one static
    step per load case, unit loads), the worst tension ACROSS the layers over
    the worst principal tension in any direction (99.9th percentiles over the
    nodes, the worst over every load case). A printed part is weakest across
    its layers, so an orientation that keeps the peak tension in the layers is
    stronger for the same part. With the filament's across-over-in-layer
    strength (`--z-over-xy`), the strength an orientation leaves is
    min(1, z_over_xy / ratio).

A candidate's score is the strength it loses plus `--support-weight` x its
support fraction: lower is better. `--z-over-xy` belongs to the filament the
`--frd` results were computed for (default 0.68, PETG HF: 23/34 MPa).

Writes print-orientation-<stem>.json (every candidate, best first by score)
and a .png chart into $NOPEKIT_PROPOSAL_DIR (or --out).

Usage: nopekit propose fea.print_orientation -- --mesh <part.stl> [--frd <job.frd> ...]
       [--overhang-deg 45] [--step 15] [--support-weight 1.0] [--z-over-xy 0.68]
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def rotation(tilt_deg, azimuth_deg):
    """The rotation that tilts the part by `tilt` about the horizontal axis at
    `azimuth` (a rotation about z then x then back): R @ v maps part to print."""
    a, t = math.radians(azimuth_deg), math.radians(tilt_deg)
    Rz = np.array([[math.cos(a), -math.sin(a), 0], [math.sin(a), math.cos(a), 0], [0, 0, 1]])
    Rx = np.array([[1, 0, 0], [0, math.cos(t), -math.sin(t)], [0, math.sin(t), math.cos(t)]])
    return Rz @ Rx @ Rz.T


def support_fraction(v, f, R, overhang_deg, layer=0.2):
    p = v @ R.T
    tri = p[f]
    n = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    area = 0.5 * np.linalg.norm(n, axis=1)
    nz = n[:, 2] / np.maximum(2 * area, 1e-12)
    zmin = p[:, 2].min()
    on_bed = tri[:, :, 2].max(axis=1) <= zmin + layer
    down = nz < -math.cos(math.radians(90 - overhang_deg))      # facing down, past the overhang angle
    sup = down & ~on_bed
    return float(area[sup].sum() / area.sum()), float(np.ptp(p[:, 0])), float(np.ptp(p[:, 1])), float(np.ptp(p[:, 2]))


def layer_ratio(stresses, layer_normal):
    """Worst across-layer tension over worst max-principal tension, over every
    load case: 1 means the weakest direction carries the peak."""
    import solid_fea_ccx as ccx
    worst_n, worst_1 = 0.0, 0.0
    for S in stresses:
        S = S[np.isfinite(S).all(axis=1)]
        worst_n = max(worst_n, float(np.percentile(np.maximum(ccx.normal_stress(S, layer_normal), 0), 99.9)))
        worst_1 = max(worst_1, float(np.percentile(np.maximum(ccx.principal_max(S), 0), 99.9)))
    return worst_n / worst_1 if worst_1 > 0 else 0.0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--mesh", required=True)
    ap.add_argument("--frd", action="append",
                    help="CalculiX results (static steps) on the same part, flight frame; repeat for several jobs")
    ap.add_argument("--overhang-deg", type=float, default=45.0)
    ap.add_argument("--step", type=float, default=15.0)
    ap.add_argument("--support-weight", type=float, default=1.0,
                    help="score = strength lost (1 - min(1, z_over_xy / across-over-in-layer ratio)) + weight x support fraction")
    ap.add_argument("--z-over-xy", type=float, default=0.68,
                    help="across-layer over in-layer strength of the filament (PETG HF: 23/34)")
    ap.add_argument("--out", default=os.environ.get("NOPEKIT_PROPOSAL_DIR"))
    a = ap.parse_args(argv)
    if not a.out:
        ap.error("no output directory: run through `nopekit propose`, or pass --out")
    import trimesh
    m = trimesh.load(a.mesh, force="mesh")
    v, f = np.asarray(m.vertices), np.asarray(m.faces)
    stresses = None
    if a.frd:
        import solid_fea_ccx as ccx
        stresses = [S for path in a.frd for S in ccx.frd_blocks(path[:-4] if path.endswith(".frd") else path, "STRESS")]
    rows = []
    tilts = np.arange(0, 180 + 1e-9, a.step)
    azis = np.arange(0, 180 - 1e-9, a.step)
    seen = set()
    for t in tilts:
        for az in (azis if 0 < t < 180 else [0.0]):
            R = rotation(t, az)
            n_up = R.T @ np.array([0.0, 0.0, 1.0])                 # the build direction in the part's frame
            key = tuple(np.round(n_up, 6))
            if key in seen:
                continue
            seen.add(key)
            frac, bx, by, bz = support_fraction(v, f, R, a.overhang_deg)
            row = {"tilt_deg": float(t), "azimuth_deg": float(az), "layer_normal": [round(float(x), 6) for x in n_up],
                   "support_frac": round(frac, 4), "bbox_mm": [round(bx, 1), round(by, 1), round(bz, 1)]}
            if stresses is not None:
                lr = layer_ratio(stresses, n_up)
                row["across_over_in_layer"] = round(lr, 4)
                # the strength the weakest direction leaves, relative to an isotropic part
                row["strength_factor"] = round(min(1.0, a.z_over_xy / lr) if lr > 0 else 1.0, 4)
            row["score"] = round((1 - row.get("strength_factor", 1.0)) + a.support_weight * frac, 4)
            rows.append(row)
    rows.sort(key=lambda r: r["score"])
    stem = os.path.splitext(os.path.basename(a.mesh))[0]
    path = os.path.join(a.out, f"print-orientation-{stem}.json")
    with open(path, "w") as fh:
        json.dump({"mesh": a.mesh, "frd": a.frd, "overhang_deg": a.overhang_deg, "candidates": rows}, fh, indent=1)
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(8, 5))
        xs = [r["support_frac"] for r in rows]
        ys = [r.get("strength_factor", 1.0) for r in rows]
        ax.scatter(xs, ys, c=[r["tilt_deg"] for r in rows], cmap="viridis")
        for r in rows[:5]:
            ax.annotate(f"{r['tilt_deg']:.0f}/{r['azimuth_deg']:.0f}", (r["support_frac"], r.get("strength_factor", 1.0)))
        ax.set_xlabel("surface needing support (fraction)")
        ax.set_ylabel("strength left by the layer direction")
        ax.set_title(f"print orientations for {stem} (labels: tilt/azimuth, deg)")
        fig.tight_layout()
        fig.savefig(path[:-5] + ".png", dpi=100)
        plt.close(fig)
    except Exception as exc:                                    # noqa: BLE001 - the chart is optional
        print(f"no chart: {exc}")
    print(f"wrote {path}: best {rows[0]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
