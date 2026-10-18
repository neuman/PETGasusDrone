# solid-fea

Three-dimensional structure for printed parts, in two halves that never mark
each other's homework:

1. **`fea.topopt3d`, a proposer.** It finds where material should go: SIMP
   topology optimisation on a voxel problem the project's model writes. It
   settles nothing; its field is an input the model draws geometry from.
2. **`solid_fea_ccx.py`, a CalculiX wrapper.** Evaluators use it to judge the
   shape that will actually be printed. It meshes the exported surface into
   quadratic tetrahedra (gmsh; fTetWild where gmsh fails), refuses a mesh with
   sliver tets or over-long edges, writes a deck, runs `ccx`, and reads back
   displacements, stresses and eigenfrequencies. Its `residual` rebuilds the
   stiffness without CalculiX, so an evaluator can check that a static solve
   balances its loads.

Evaluators that read a claim's limit cannot qualify in a pack yet: a pack
baseline carries no claims (PACK_FORMAT, "A claim's limit"). So this pack ships
the machinery, and each project writes its evaluators in its own `gates/`,
importing the wrapper. PETGasus's `gates/structure.py` is the worked example:
the first mode, held at the FC posts and the strap saddle; elastic crash floors
(drop height, wall speed) by an energy method on the free drone (inertia
relief, Goldsmith's effective mass), with stresses averaged over a 0.3 mm
critical distance; every static solve checked for equilibrium; every judged
number checked for convergence on a finer surface and mesh.

## What it settles

Through a project's evaluators: first natural frequency, stress per newton,
contact stiffness, and the energy a part absorbs elastically before it reaches
its printed strength along or across the layers. It does NOT settle plastic
collapse, fatigue, buckling, contact, or anything a linear model cannot see.

## The proposer

```sh
nopekit propose fea.topopt3d --timeout 14400 -- \
    --problem build/topopt3d/problem.npz --variant <name> [--iters 120] \
    [--warm <earlier field.npz>] [--c0-from <earlier field.npz>] \
    [--checkpoint <path outside the project>]
```

The problem file (`numpy.savez`) holds:

| key | meaning |
|---|---|
| `nx ny nz h origin` | the cell grid, mm |
| `region` | per cell: 0 designable, 1 must be solid, 2 must stay empty |
| `erel` | a solid cell's modulus relative to the frame's (a soft second material) |
| `cost` | budget charged per designable cell (more where material costs more than its mass) |
| `fixed_nodes` | node ids held in x, y and z |
| `load_k_dofs`, `load_k_vals`, `load_names`, `load_weights` | the load cases |
| `budget_mm3` | the designable volume budget, cost-weighted |
| `rmin_mm` | density filter radius across: the thinnest member |
| `rmin_z_mm` | (optional; default `rmin_mm`) the radius up and down. Larger than `rmin_mm`, it lets members be thin across and still deep (blades) |
| `symmetry` | `D2`, `D4` or `none` |
| `problem_hash` | pins a field to the problem it was solved for (below) |

It writes `topopt3d-<variant>-<hash>.npz`: the projected density `rho`, the
design variables `x`, the problem's `region` and hash, the history, and `info`
(c0, the load case names, the warm start). Beside it go a PNG preview and a
JSON summary. `--checkpoint` writes `rho`, `x`, the hash and `info` (beta,
iteration, c0, load case names) every 10 iterations.

The proposer uses the hash only to tell a resume from a refine (below). The
model decides what a stale field means: PETGasus draws the chosen field
whatever its hash, and `gates/flight.py` (`topology_current`) fails when the
hash is not the current problem's.

### Method

references/methods.md has the sources.

- SIMP with penalty 3, a cone density filter (an ellipsoid when `rmin_z_mm`
  differs from `rmin_mm`) and a Heaviside projection, updated by optimality
  criteria. Each load case's compliance is divided by its value at the run's
  start (c0), and the weighted sum is minimised.
- The volume budget is continued from 30 % of the designable volume down to
  the target over the first 20 iterations. Started at a 2 % budget, the
  stiffness matrix is nearly singular and CG stalls.
- After that, beta doubles from 1 to 16: after 20 iterations at one beta, or
  after 10 once no design variable moves by 0.01. At beta 16 the run stops
  when no variable moves by 0.005, or at `--iters`.
- The move limit is 0.1, then 0.05 from beta 8 and 0.025 at 16. It halves when
  the objective zig-zags and grows back by 1.25x on each iteration that does
  not. Without the growth, the objective's rise at every beta step halved it
  for good: the 2 mm PETGasus run reached beta 16 at a quarter of its cap and
  stopped on the iteration cap, still improving ~4 % an iteration.
- `D2` symmetry averages the field and the sensitivities over the planes
  x = 0 and y = 0, so load cases placed at one corner design all four; `D4`
  also mirrors them across the diagonals.

### Warm starts

`--warm` takes an earlier run's beta.

- On the same problem (the same hash), it resumes from that run's `x` and c0.
  A checkpoint resumes from the same design (x stored as float16), beta and c0;
  the move limit, the iteration count and the history restart.
- On another problem (a finer grid, another filter radius), it takes that
  run's `rho`, interpolated onto the new grid. Before the first iteration it
  finds the `x` whose field, under the new filter, reproduces that `rho`. The
  first version took the coarse run's `x`, but `x` means a design only under
  the filter it was optimised with: the 1.33 mm PETGasus refine (rmin 3.5 mm)
  started from the `x` of a 2 mm run filtered at 5.0 mm, and began 63 % over
  its budget. Taking `rho` itself as `x` erodes it: 73 % under. The fitted
  start is 4 % under, and its field correlates 0.96 with the 2 mm design.
- On another problem the load cases are normalised by the new run's start,
  unless `--c0-from` names a run (a proposal or a checkpoint) whose c0 to
  keep. That keeps the coarse run's trade between the cases, instead of
  re-weighting them by how well the coarse design already serves each. Its
  load cases must match the problem's, by name where the file records them.

### Solves

`proposers/_fe3d.py` solves directly where memory allows:

| unknowns | solver |
|---|---|
| up to 600k, with `pypardiso` | PARDISO (MKL's multithreaded sparse LU) |
| up to 150k, without it | SuperLU |
| beyond | CG preconditioned by pyamg's smoothed-aggregation multigrid on the active nodes, with the rigid-body modes as its near-null space |

The CG path raises when it stops short of its tolerance: an unconverged solve
gives the optimiser wrong sensitivities, and it would act on them silently.
PARDISO stops at 600k unknowns because its factors grow about as n^(4/3): the
1.33 mm problem (365k) took about 7 GB, and the 1 mm one (~840k) ran a 21 GB
machine out of memory. Geometric multigrid, rediscretised and then Galerkin,
failed here: thin passive features ringed by empty cells have no smooth coarse
representation.

### Cost

PETGasus frame, 13 load cases, with PARDISO:

| cell | unknowns | per iteration | the run |
|---|---|---|---|
| 2 mm | ~112k | 5.5 s | 120 iterations, 11 min |
| 1.33 mm | ~365k | 34 s, about 7 GB | 60 iterations, 34 min, warm-started from the 2 mm run |
| 1 mm | ~840k | ran out of memory on a 21 GB machine | none |

So solve at 2 mm, then refine at 1.33 mm with `--warm` and `--c0-from` set to
the 2 mm run. Without `pypardiso`, the 1.33 mm problem goes to AMG-CG, which
takes many times longer once the members thin. At 81k unknowns, AMG-CG took
95 s for seven cases where SuperLU took about 36 s (33 s to factorise, then
0.4 s a case).

## The orientation proposer

```sh
nopekit propose fea.print_orientation -- --mesh <part.stl> [--frd <ccx job.frd> ...] \
    [--overhang-deg 45] [--step 15] [--support-weight 1.0] [--z-over-xy 0.68]
```

It turns the part through every build direction on a `--step` grid. For each,
it measures the surface that would need support: downward faces past the
overhang angle, off the bed. Given CalculiX results on the part (static steps,
unit loads), it also measures how much of the worst tension acts across the
layers. Printed parts are weakest across them: PETG about 0.68 of in-layer, the
default `--z-over-xy`. Give the ratio of the filament the results were computed
for. It ranks the candidates by lost strength plus support area and writes a
JSON and a chart. It chooses nothing; the project records its choice as a
decision.

## The CalculiX wrapper

- **Meshing.** `mesh_surface` tries four meshers in turn and keeps the first
  sound mesh: gmsh Delaunay on the surface's own triangles; gmsh after
  reparametrising the surface (at a 180 deg, then a 40 deg feature angle);
  then fTetWild (`wildmeshing`). fTetWild meshes inside an envelope 0.04 mm
  round the surface, so no near-degenerate triangle can stop it. It takes
  minutes, not seconds, so it runs last.
- **Mesh checks.** A mesh is sound when no tet's quality (6 sqrt(2) V / Lmax^3,
  1 for a regular tet) is under 0.02 (`QUALITY_MIN`) and no edge is over 2x
  the asked size (`EDGE_MAX_X`). gmsh's direct mesh of the v0.2 frame held tets
  at 0.004-0.009. Its flat faces kept the level set's 4 mm triangles, whatever
  size was asked.
- **The run.** `run` runs ccx with its equation solver on one thread
  (`CCX_NPROC_EQUATION_SOLVER=1`). Multithreaded, this build's SPOOLES returned
  static solutions out of equilibrium by up to 124 N for a 1 N load, round
  sliver tets, with no warning. The same deck single-threaded: 0.01 N.
  Assembly and stress recovery stay threaded. The solver's environment is
  stated, never copied from the caller's. A run whose log reports an error, or
  whose .frd is missing, raises: no partial result is returned.
- **The equilibrium check.** `residual` builds K from the deck's own materials
  (C3D10, 4-point integration) without CalculiX, and returns |K u - f| per node
  in newtons. A sound solve leaves a few mN (the .frd's five digits). A
  corrupted one leaves newtons. Evaluators should refuse a solve over their
  tolerance.

Smoke test (`solid_fea_ccx`, a 40 x 8 x 8 mm clamped cantilever, 1 mm tets): tip
deflection 0.986 x Timoshenko, first mode 0.979 x Euler-Bernoulli, bending
stress 0.3527 against 0.3516 MPa. The same beam meshed by fTetWild from its
surface: 0.9859 x, against gmsh's 0.9859 x. fTetWild is not bit-reproducible
(three runs: 21166 to 22493 nodes), but the deflection moved by 0.01 %.
Free-free modal runs in this CalculiX build return nonsense rigid modes: hold
the structure somewhere.

The proposer's solver has its own (`_fe3d.selfcheck()`, a 40 x 8 x 8 hex
cantilever): tip deflection 0.976 x Timoshenko. The direct path and the AMG-CG
path (14 iterations) both agree with a sparse direct solve to 1e-12.

## Installing

| tool | command | root |
|---|---|---|
| numpy, scipy | (usually present) | no |
| numba | `pip install --user numba` | no |
| pyamg 5.2.1 | `pip install --user pyamg==5.2.1` | no |
| pypardiso 0.4.7 (optional) | `pip install --user pypardiso==0.4.7` (pulls MKL, ~800 MB) | no |
| gmsh 4.13.1 | `pip install --user gmsh==4.13.1` (~120 MB) | no |
| fTetWild (wildmeshing 0.4.1, MPL-2.0) | `pip install --user wildmeshing==0.4.1` (~15 MB) | no |
| CalculiX 2.21 | `sudo apt install calculix-ccx` (~5 MB) | yes |

A system Python that refuses `--user` installs (PEP 668: "externally managed",
as on Ubuntu 24.04) takes them with `--break-system-packages` added; with
`--user` that still writes only to `~/.local`. A virtual environment avoids it.

pypardiso is optional, and the timings above assume it. It loads MKL's
`libmkl_rt` from the loader's path, from under `sys.prefix` or the user site
(`~/.local`), or from where `PYPARDISO_MKL_RT` points. Without it, or without
MKL, the solver falls back to SuperLU and AMG-CG.

pyamg 5.2.1's own Krylov wrappers do not run on scipy 1.18: use its
`aspreconditioner()` inside `scipy.sparse.linalg.cg`, as `_fe3d.py` does.

## What it does not do

- The proposer's voxel model is not evidence about the printed part. Judge the
  exported surface, with this wrapper, on a different mesh.
- Peak stress at a clamp or a point load is a singularity. Evaluators must
  exclude a neighbourhood of both and show mesh convergence.
- Linear elasticity only. A soft second material (TPU) that deflects by its own
  size is outside the model; treat its numbers as a bound, not a prediction.
