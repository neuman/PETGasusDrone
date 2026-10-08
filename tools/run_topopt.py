"""Run the plate topology optimisation for the current Config and draw what it found.

This is the EXPLORATION tool. It does not change the design: its density field
(cached in build/topopt/) is what the 'spoked' layout in model/geometry.py was
drawn from, and the frame is then judged by the same FE on the drawn geometry.
Writes build/topopt/field.png. Usage: python3 tools/run_topopt.py [field=value ...]
"""
import ast, dataclasses, os, sys, time
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "model"))
import numpy as np  # noqa: E402
import petgasus  # noqa: E402
import topopt_petgasus as to  # noqa: E402

over = {}
for a in sys.argv[1:]:
    k, v = a.split("=", 1)
    try:
        over[k] = ast.literal_eval(v)
    except Exception:
        over[k] = v
c = dataclasses.replace(petgasus.CONFIG, **over)
d = petgasus._derive_layout(c)
d["fc_post_xy"] = [list(p) for p in d["fc_post_xy"]]
t = time.time()
g, reg, fe = to.setup(c, d)
rho_b, tb_b, ta_b = to.baseline_density(c, d, g, reg)
rho, tb, ta, hist = petgasus._topopt_cached(c, d, g, reg, fe, rho_b, ta_b)
print(f"optimised in {time.time()-t:.0f}s ({len(hist)} iterations)")
for name, (r, b, a_) in (("arms (hand-drawn)", (rho_b, tb_b, ta_b)), ("optimiser field", (rho, tb, ta))):
    m = to.modal(c, d, g, reg, fe, r, b, a_)[0]
    comp = to.evaluate(c, d, g, reg, fe, r, b, a_)
    print(f"  {name:20s} plate {to.plate_mass_g(g, reg, r, a_):.2f} g  mode1 {m:.0f} Hz  "
          f"bounce C {comp[0]:.3g}  crash C {comp[1] + comp[2]:.3g}")
import matplotlib; matplotlib.use("Agg")  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
fig, ax = plt.subplots(figsize=(6, 6))
ax.imshow(rho.reshape(g.n, g.n), origin="lower", cmap="Blues",
          extent=[-g.half, g.half, -g.half, g.half])
ax.set_title("Topology optimiser: where the plate material goes"); ax.set_xlabel("x mm"); ax.set_ylabel("y mm")
fig.savefig(os.path.join(ROOT, "build", "topopt", "field.png"), dpi=110, bbox_inches="tight")
