"""PETGasus's known-good design: the design every control is one change away from.

Frozen from model/petgasus.py by tools/freeze_known_good.py when every project gate
passed on the live design. Every Config field is stated, so a default edit in the
model does not move it. CLAIMS are the acceptance conditions it was calibrated
against; a live claim moved later leaves every control where it is.
"""
from __future__ import annotations

import copy
import dataclasses
import os

from nopekit.modelio import flat_params, load_path
from nopekit.models import Claim, Ledger

_HERE = os.path.dirname(os.path.abspath(__file__))
petgasus = load_path(os.path.join(_HERE, os.pardir, "model", "petgasus.py"))

CONFIG: dict = {   'arm_w': 5.0,
    'battery_h': 6.0,
    'battery_l': 64.0,
    'battery_mah': 320.0,
    'battery_mass_g': 8.2,
    'battery_v_nom': 3.8,
    'battery_w': 10.0,
    'bed_x_mm': 270.0,
    'bed_y_mm': 270.0,
    'bed_z_mm': 270.0,
    'bounce_g': 1.0,
    'bridge_w': 4.0,
    'brim_mm': 5.0,
    'bt20_h': 4.0,
    'bt20_len': 6.5,
    'bt20_w': 5.0,
    'crash_load_n': 20.0,
    'duct_above_prop': 1.0,
    'duct_band_below_prop': 2.0,
    'duct_lattice': True,
    'duct_thrust_factor': 0.9,
    'duct_wall': 1.3,
    'extrusion_width_mm': 0.42,
    'fc_board_clear': 1.0,
    'fc_board_side': 30.0,
    'fc_hole_d': 1.6,
    'fc_hole_spacing': 25.5,
    'fc_mass_g': 4.2,
    'fc_pcb_t': 1.0,
    'fc_pilot_d': 1.1,
    'fc_post_h': 4.5,
    'fc_post_od': 3.8,
    'fc_screw_len': 6.0,
    'fc_top_components_h': 2.0,
    'fc_yaw_deg': 45.0,
    'foot_w': 1.3,
    'hover_eff_g_per_w': 3.0,
    'hub_hole_margin': 2.5,
    'hub_holes': True,
    'hub_margin': 1.2,
    'hub_t': 1.4,
    'infill_fraction': 1.0,
    'joint_margin': 0.4,
    'lattice_above_members': False,
    'lattice_margin': 0.4,
    'lattice_overhang_deg': 40.0,
    'lattice_strut_w': 1.3,
    'layer_height_mm': 0.2,
    'lead_d': 1.2,
    'max_filament_g': 1000.0,
    'max_print_time_h': 3.0,
    'member_clear': 1.0,
    'min_member_w': 1.6,
    'misc_mass_g': 2.0,
    'motor_base_d': 11.0,
    'motor_base_h': 2.0,
    'motor_body_d': 14.0,
    'motor_centre_relief_d': 2.3,
    'motor_h': 13.8,
    'motor_hole_circle_d': 6.6,
    'motor_kv': 21000.0,
    'motor_lead_len': 37.0,
    'motor_mass_g': 2.85,
    'motor_screw_clear_d': 1.7,
    'motor_screw_len': 3.0,
    'motor_thrust_max_g': 46.3,
    'motor_thrust_test_v': 4.2,
    'nozzle_d_mm': 0.4,
    'perimeters': 3,
    'plate_layout': 'spoked',
    'plate_t': 1.8,
    'print_speed_mm_s': 60.0,
    'prop_blade_t': 0.8,
    'prop_blades': 3,
    'prop_block_mm': 3.6,
    'prop_chord': 6.0,
    'prop_d': 45.0,
    'prop_hub_d': 5.0,
    'prop_hub_drop': 2.5,
    'prop_mass_g': 0.32,
    'prop_pitch_deg': 12.0,
    'prop_sweep_half_h': 1.5,
    'prop_tip_gap': 1.0,
    'rib_h': 3.0,
    'rib_w': 1.3,
    'screw_d': 1.4,
    'screw_head_d': 2.6,
    'screw_head_h': 0.8,
    'shaft_d': 1.5,
    'shaft_exposed': 5.0,
    'socket_depth': 3.0,
    'socket_h': 2.5,
    'socket_w': 4.5,
    'spoke_count': 4,
    'spoke_phase_deg': 45.0,
    'spoke_w': 2.0,
    'strap_bay_w': 16.0,
    'strap_slot_w': 2.2,
    'strap_t': 1.5,
    'strap_w': 10.0,
    'topopt_h': 0.75,
    'topopt_iters': 120,
    'topopt_mass_frac': 1.0,
    'topopt_member_h': 4.8,
    'topopt_rmin': 2.0,
    'topopt_smooth': 0.4,
    'topopt_w_crash': 4.0,
    'topopt_w_thrust': 1.0,
    'usable_capacity_frac': 0.8,
    'web_h': 6.0}

CLAIMS: list = [   {   'acceptance': {   'comparator': '>=',
                          'limit': 3.0,
                          'quantity': 'thrust to weight',
                          'units': 'ratio'},
        'id': 'C1',
        'kind': 'measurable',
        'statement': 'Thrust-to-weight at nominal pack voltage is at least 3:1',
        'tags': ['thrust-margin']},
    {   'acceptance': {   'comparator': '<=',
                          'limit': 1,
                          'quantity': 'frame pieces',
                          'units': 'count'},
        'id': 'C11',
        'kind': 'measurable',
        'statement': 'The printed frame is one connected piece',
        'tags': ['one-piece']},
    {   'acceptance': {   'comparator': '>=',
                          'limit': 3.0,
                          'quantity': 'motor lead spare',
                          'units': 'mm'},
        'id': 'C12',
        'kind': 'measurable',
        'statement': "Each motor's 37 mm lead reaches its socket on the flight "
                     'controller with at least 3 mm to spare',
        'tags': ['motor-leads']},
    {   'acceptance': {   'comparator': '<=',
                          'limit': 250.0,
                          'quantity': 'all-up weight',
                          'units': 'g'},
        'id': 'C2',
        'kind': 'measurable',
        'statement': 'All-up weight stays under 250 g',
        'tags': ['auw']},
    {   'acceptance': {   'comparator': '>=',
                          'limit': 3.0,
                          'quantity': 'hover flight time',
                          'units': 'min'},
        'id': 'C3',
        'kind': 'measurable',
        'statement': 'Estimated hover flight time is at least 3 minutes per pack',
        'tags': ['endurance']},
    {   'acceptance': {   'comparator': '>=',
                          'limit': 200.0,
                          'quantity': 'first frame mode',
                          'units': 'Hz'},
        'id': 'C4',
        'kind': 'measurable',
        'statement': "The frame's first out-of-plane mode (duct pods bouncing on the "
                     'arms) is at or above 200 Hz',
        'tags': ['arm-vibration']},
    {   'acceptance': {   'comparator': '<=',
                          'limit': 0.0,
                          'quantity': 'interference volume',
                          'units': 'mm3'},
        'id': 'C5',
        'kind': 'measurable',
        'statement': 'No part of the assembly - frame, flight controller, motors, '
                     'props, battery, strap, screws, wires - shares material with '
                     'another, except the declared threaded, plugged and soldered '
                     'joints',
        'tags': ['envelope-clearance']},
    {   'acceptance': {   'comparator': '<=',
                          'limit': 0.0,
                          'quantity': 'FC screw protrusion below plate',
                          'units': 'mm'},
        'id': 'C8',
        'kind': 'measurable',
        'statement': 'AIO screws (M1.4 x 6) bite at least 3 mm into the printed posts '
                     'and do not poke out under the plate',
        'tags': ['fc-screws']},
    {   'acceptance': {   'comparator': '>=',
                          'limit': 1.0,
                          'quantity': 'motor screw engagement',
                          'units': 'mm'},
        'id': 'C9',
        'kind': 'measurable',
        'statement': 'Motor screws (M1.4 x 3, supplied) reach at least 1 mm into the '
                     'motor through the seat',
        'tags': ['motor-screws']}]


def params(config: dict | None = None) -> dict:
    """`config` (default CONFIG) built and flattened as `check` flattens it.

    write_meshes=False: a control must never overwrite the real print mesh.
    """
    stated = dict(CONFIG if config is None else config)
    flat, _conflicts = flat_params({
        "config": stated,
        "derived": petgasus.build(petgasus.Config(**stated), write_meshes=False),
    })
    return flat


def context(ctx):
    ledger = Ledger(claims=[Claim.from_dict(copy.deepcopy(row)) for row in CLAIMS])
    return dataclasses.replace(ctx, params=params(), ledger=ledger, extra={})
