"""The numbers behind the plain-language front page (site/index.html).

The front page reads two generated files: data/state.json (claims, verdicts -
nopekit's own) and assets/story.json, written here from the model's projection.
Nothing here is computed: every number is a value build() already derived, so
the page cannot show a figure the gates did not see. This viewgen only gathers
them under names a page can use, and groups the parts the way a person thinks of
them (frame, motors, props, electronics, battery, hardware).
"""
from __future__ import annotations

import json

from nopekit.models import View, ViewKind
from nopekit.site import ViewContext, viewgen

#: How the 27 placed parts read to a person. Prefix -> group key. Order matters:
#: the first match wins.
GROUPS = [
    ("frame", "frame"), ("motor_screws_", "hardware"), ("motor_lead_", "hardware"),
    ("motor_", "motors"), ("prop_", "props"), ("fc_screw_", "hardware"),
    ("flight_controller", "electronics"), ("motor_sockets", "electronics"),
    ("power_pigtail", "electronics"), ("battery_strap", "hardware"),
    ("battery", "battery"),
]

GROUP_LABELS = {
    "frame": "Printed frame", "battery": "Battery", "motors": "Motors",
    "electronics": "Flight controller", "props": "Propellers",
    "hardware": "Screws, wires & strap",
}


def _group(name):
    for prefix, key in GROUPS:
        if name.startswith(prefix):
            return key
    return "hardware"


@viewgen(
    id="story",
    kind=ViewKind.TABLE,
    title="Front-page numbers",
    description="The model's derived numbers the plain-language front page draws.",
    order=90,
)
def story(ctx: ViewContext) -> View | None:
    p = ctx.params
    if "auw_g" not in p:
        return None
    mass = [  # grams, the all-up-weight sum build() makes, item by item
        {"group": "battery", "g": p["battery_mass_g"]},
        {"group": "frame", "g": p["frame_mass_g"]},
        {"group": "motors", "g": 4 * p["motor_mass_g"]},
        {"group": "electronics", "g": p["fc_mass_g"]},
        {"group": "props", "g": 4 * p["prop_mass_g"]},
        {"group": "hardware", "g": p["misc_mass_g"]},
    ]
    parts = {name: dict(spec, person_group=_group(name))
             for name, spec in sorted((p.get("assembly_parts") or {}).items())}
    data = {
        "groups": GROUP_LABELS,
        "mass": [dict(m, g=round(m["g"], 2)) for m in mass],
        "auw_g": p["auw_g"],
        "thrust_g": p["thrust_total_g"],
        "thrust_to_weight": p["thrust_to_weight"],
        "hover_throttle": p["hover_throttle_frac"],
        "flight_min": p["flight_time_min"],
        "battery_mah": p["battery_mah"],
        "frame_g": p["frame_mass_g"],
        "mode_hz": p["frame_mode1_hz"],
        "arms_mode_hz": p.get("arms_mode1_hz"),
        "crash_gain": p.get("crash_stiffness_gain"),
        "bounce_gain": p.get("bounce_stiffness_gain"),
        "motor_hover_hz": p["motor_freq_hover_hz"],
        "wheelbase_mm": p["wheelbase_mm"],
        "bbox_mm": p["frame_bbox_mm"],
        "lead_needed_mm": p["motor_lead_needed_mm"],
        "lead_len_mm": p["motor_lead_len"],
        "parts": parts,
        "layout": p.get("layout_2d"),
        "field": p.get("topopt_field"),
        "spoke_count": p["spoke_count"],
        "plate_g": p.get("plate_mass_fe_g"),
        "arms_plate_g": p.get("arms_plate_mass_fe_g"),
    }
    src = ctx.write_asset("story.json", json.dumps(data, separators=(",", ":")))
    rows = [{"what": "all-up weight", "value": f"{p['auw_g']:.1f} g"},
            {"what": "lift", "value": f"{p['thrust_total_g']:.0f} g"},
            {"what": "first frame mode", "value": f"{p['frame_mode1_hz']:.0f} Hz"}]
    return View(id="story", kind=ViewKind.TABLE, title="Front-page numbers", src=src,
                data={"columns": [{"key": "what", "label": "What", "align": "left"},
                                  {"key": "value", "label": "Value", "align": "right"}],
                      "rows": rows},
                meta={"data_url": src})
