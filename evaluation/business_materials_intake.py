"""Compatibility entry for NBIB synthetic material loading.

Runtime parsing is owned by cfm_id.materials. Keep the historical NBIB default
and callable names so frozen requests and existing research scripts still work.
"""
from pathlib import Path
from cfm_id import materials as _materials
from cfm_id.materials import _rows, goal_slots, prompt_materials, sources, validate_tables

PUBLIC = Path(__file__).parent / "nbib/public/cases"


def load_bundle(case_id, *, public_root=PUBLIC, clarification=None, design_addendum=None):
    return _materials.load_bundle(case_id, public_root=public_root,
        clarification=clarification, design_addendum=design_addendum)
