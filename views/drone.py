"""The whole drone, every part placed, as an explodable 3D view.

The cad-solid pack's 'Assembly' view draws the project's `meshes` map, which is
deliberately the printed frame alone: the pack's mesh gates read the same map, and
its wall-thickness rule is a PRINTING rule that a bought prop blade, a wire or a
PCB was never meant to meet. This view draws `assembly_parts` instead - the frame
and every bought part, screw and wire, as model/assembly.py places them and as
the clearance check (C5) judges them - one node per part, coloured, with the
explode in assembly order (assembly.py's `explode` vectors, authored there next
to the parts rather than in a separate table).
"""
from __future__ import annotations

import os

from nopekit.models import View, ViewKind
from nopekit.site import ViewContext, derive_explode, viewgen


@viewgen(
    id="drone",
    kind=ViewKind.MODEL3D,
    title="Drone - every part",
    description="Frame, flight controller, motors, props, battery, strap, every screw "
                "and wire, placed as built. Explode to see the assembly order.",
    requires_python=["trimesh", "numpy"],
    order=5,
    gates=["petgasus.interference", "petgasus.motor_leads"],
)
def drone(ctx: ViewContext) -> View | None:
    parts = ctx.params.get("assembly_parts")
    if not parts:
        ctx.log("drone: the projection publishes no assembly_parts")
        return None

    import trimesh
    from trimesh.visual.material import PBRMaterial
    from trimesh.visual.texture import TextureVisuals

    scene = trimesh.Scene()
    bounds, overrides, groups, missing = {}, {}, {}, []
    for name in sorted(parts):
        spec = parts[name]
        path = os.path.join(ctx.root or "", spec["path"])
        if not os.path.isfile(path):
            missing.append(name)
            continue
        mesh = trimesh.load(path, force="mesh")
        r, g, b = spec["color"]
        metal = 0.6 if spec.get("group") in ("screws", "motors") else 0.0
        mesh.visual = TextureVisuals(material=PBRMaterial(
            baseColorFactor=[r, g, b, 255], metallicFactor=metal, roughnessFactor=0.55))
        node = f"{name}__0"
        scene.add_geometry(mesh, node_name=node, geom_name=node)
        low, high = mesh.bounds
        bounds[node] = ([float(v) for v in low], [float(v) for v in high])
        overrides[name] = {"offset": [float(v) for v in spec["explode"]]}
        groups.setdefault(spec.get("group", "other"), []).append(name)
    if not bounds:
        ctx.log("drone: none of the assembly part files exist - run nopekit check first")
        return None

    src = ctx.write_asset("drone.glb", scene.export(file_type="glb"))
    meta = {
        "nodes": sorted(bounds),
        "explode": derive_explode(bounds, overrides=overrides),
        "units": "mm",
        "parts": {n: [f"{n}__0"] for n in sorted(overrides)},
        "groups": {g: sorted(v) for g, v in sorted(groups.items())},
        "frame": "model frame: +x forward, +z up, z=0 under the base plate",
    }
    if missing:
        meta["missing_parts"] = missing
    return View(id="drone", kind=ViewKind.MODEL3D, title="Drone - every part", src=src, meta=meta)
