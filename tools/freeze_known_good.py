"""Write selftest/known_good.py from the model's CURRENT Config.

Run this only when the live design is the one every control should be one change
away from: every project gate passes on it, against the live claims or, where
the live design misses one, against CALIBRATE's limit below. It states every
field, so a later default edit in model/petgasus.py does not move the known-good
design.
"""
import dataclasses, os, pprint, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "model"))
import petgasus  # noqa: E402

#: Limits the known-good is calibrated against where the live design misses the
#: live claim, by the author's choice or by a real gap still open: a control can
#: only show its gate is able to fail if the known-good design passes it. Each
#: control's design (selftest/bad_configs.py) falls far below these too.
CALIBRATE = {
    "C4": (100.0, "the author keeps C4 at 200 Hz and expects the PETG frame (~143 Hz) to fail it; "
                  "tpu_frame (~20 Hz) is far below 100"),
}

cfg = dataclasses.asdict(petgasus.CONFIG)
claims = []
import json, glob
for p in sorted(glob.glob(os.path.join(ROOT, "claims", "*.json"))):
    cid = os.path.basename(p)[:-5]
    row = json.load(open(p))
    if row.get("acceptance") and row.get("kind") == "measurable":
        acc = dict(row["acceptance"])
        if cid in CALIBRATE:
            acc["limit"] = CALIBRATE[cid][0]
        claims.append({"id": cid, "statement": row["statement"], "kind": "measurable",
                       "acceptance": acc, "tags": row.get("tags", [])})
import textwrap
calibrated = "\n".join(textwrap.fill(f"{cid}: limit {lim:g} ({why})", 80, initial_indent="  ",
                                     subsequent_indent="    ") for cid, (lim, why) in sorted(CALIBRATE.items()))

src = f'''"""PETGasus's known-good design: the design every control is one change away from.

Frozen from model/petgasus.py by tools/freeze_known_good.py when every project gate
passed on the live design, against CALIBRATE's limits where the live design
misses a claim. Every Config field is stated, so a default edit in the model
does not move it. CLAIMS are the acceptance conditions it was calibrated
against; a live claim moved later leaves every control where it is. Calibrated
below the live claim (tools/freeze_known_good.py CALIBRATE):
{calibrated}
"""
from __future__ import annotations

import copy
import dataclasses
import os

from nopekit.modelio import flat_params, load_path
from nopekit.models import Claim, Ledger

_HERE = os.path.dirname(os.path.abspath(__file__))
petgasus = load_path(os.path.join(_HERE, os.pardir, "model", "petgasus.py"))

CONFIG: dict = {pprint.pformat(cfg, indent=4, sort_dicts=True, width=88)}

CLAIMS: list = {pprint.pformat(claims, indent=4, sort_dicts=True, width=88)}


def params(config: dict | None = None) -> dict:
    """`config` (default CONFIG) built and flattened as `check` flattens it.

    write_meshes=False: a control must never overwrite the real print mesh.
    """
    stated = dict(CONFIG if config is None else config)
    flat, _conflicts = flat_params({{
        "config": stated,
        "derived": petgasus.build(petgasus.Config(**stated), write_meshes=False),
    }})
    return flat


def context(ctx):
    ledger = Ledger(claims=[Claim.from_dict(copy.deepcopy(row)) for row in CLAIMS])
    return dataclasses.replace(ctx, params=params(), ledger=ledger, extra={{}})
'''
open(os.path.join(ROOT, "selftest", "known_good.py"), "w").write(src)
print("wrote selftest/known_good.py")
