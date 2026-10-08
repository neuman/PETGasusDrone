"""Quick matplotlib preview of the print meshes (an output check, not a gate)."""
import sys, numpy as np, trimesh, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

def render(paths, out, elev=35, azim=-60):
    fig = plt.figure(figsize=(10, 5))
    for i, p in enumerate(paths):
        m = trimesh.load(p)
        ax = fig.add_subplot(1, len(paths), i + 1, projection="3d")
        tris = m.vertices[m.faces]
        n = m.face_normals
        shade = 0.35 + 0.65 * np.clip(n @ np.array([0.3, -0.4, 0.85]), 0, 1)
        col = np.c_[0.2 * shade, 0.55 * shade, 0.9 * shade, np.ones_like(shade)]
        pc = Poly3DCollection(tris, facecolors=col, edgecolors="none")
        ax.add_collection3d(pc)
        lo, hi = m.bounds
        c = (lo + hi) / 2; r = (hi - lo).max() / 2
        ax.set_xlim(c[0]-r, c[0]+r); ax.set_ylim(c[1]-r, c[1]+r); ax.set_zlim(c[2]-r, c[2]+r)
        ax.view_init(elev=elev, azim=azim); ax.set_axis_off(); ax.set_title(p.split("/")[-1])
    fig.tight_layout(); fig.savefig(out, dpi=110)

if __name__ == "__main__":
    render(sys.argv[2:], sys.argv[1])
