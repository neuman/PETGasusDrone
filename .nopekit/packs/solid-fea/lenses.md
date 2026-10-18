# Lenses: how to attack a 3D printed structure before it is printed

1. **The load case nobody wrote down.** The optimiser only stiffens what it was
   told about. List the crashes, the drops, the hand that squeezes it, the strap
   that pulls on it, and check each one is a case or is covered by one.
2. **Where the optimiser's grid is coarser than the part.** A 2 mm cell cannot
   see a 1.4 mm wall. Passive features drawn at cell size can be heavier
   than when printed or, joined only at cells' edges and corners, much softer.
3. **What the field says against what was printed.** Judge the exported surface
   with CalculiX, never the field.
4. **Layer direction against the stress.** Printed parts are weakest across
   their layers (often half the in-layer strength). Find where the worst stress
   is normal to the layers, and try another print orientation before another
   material.
5. **The joint: fillet, or stress concentrator.** Where a limb meets a seat or
   a hoop, look at the peak stress and its mesh convergence.
6. **Mesh dependence of a peak stress.** A number that moves with the mesh is
   not a result. One node's stress can sit on a sliver tet or a sharp edge:
   average over a critical distance (about a printed line's width) before
   judging it.
7. **The solve that does not balance its loads.** A solver can return
   displacements out of equilibrium with no warning: this CalculiX build's
   multithreaded SPOOLES was off by up to 124 N for a 1 N hit. Check
   K u - f, with a stiffness built without the solver
   (`solid_fea_ccx.residual`), before reading a stress.
8. **The run that stopped, not converged.** A proposal that ended on its
   iteration cap with the objective still falling is an intermediate design.
   Read the history's last iterations, and the warm start it began from,
   before trusting the field.
