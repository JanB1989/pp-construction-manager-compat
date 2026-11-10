"""Construction Manager's own files that must learn of the Prosper or Perish features, patched at build time.

Each patch replaces an exact anchor in CM's installed file and writes the whole file at CM's path, so the patch's copy
replaces CM's (the patch loads last). An anchor that is gone (CM changed the file) stops the build: look at the new CM
file and move the anchor. The built files carry CM's code and are not committed (``build/`` is ignored).

* ``cm_cmm_effects.txt``: the priority list (Construction Automation) gets three rows, Granaries, Improvements and
  Logistics (items 8 to 10, CM's own items keep their numbers so saved settings stay put); like CM's Auto-Food row
  they have no Min Profit field.
* ``cm_on_action.txt``: CM's dispatcher runs the three rows.
* ``cm_feature_effects.txt``: CM's Auto-Food runs Prosper or Perish's food rule (``ppcm_run_food``). CM's own food
  rule builds vanilla food buildings by vanilla food output; in Prosper or Perish food comes from stored Province
  Food, farms, kitchens and Taverns, so its picks would be wrong.
* CM's food values, triggers and effects and its food filter: their farming village option is switched off
  (Prosper or Perish has no farming_village; the links failed at load).
"""

from __future__ import annotations

import re
from pathlib import Path

from ppcm.context import Context, bom, read

FEATURES = (  # (priority list item, flag, scripted effect)
    (8, "ppcm_feature_granaries", "ppcm_run_granaries"),
    (9, "ppcm_feature_improvements", "ppcm_run_improvements"),
    (10, "ppcm_feature_logistics", "ppcm_run_logistics"),
)
CM_ITEMS = 7  # CM's own rows in the priority list


class AnchorMissing(SystemExit):
    pass


def _replace(text: str, old: str, new: str, where: str) -> str:
    if text.count(old) != 1:
        raise AnchorMissing(f"{where}: anchor found {text.count(old)} times (CM changed?): {old[:120]!r}")
    return text.replace(old, new)


def patch_registration(text: str) -> str:
    where = "cm_cmm_effects.txt"
    text = _replace(text, (
        "\t\tsetting_id = priority_list\n\t\ttab_id = settings\n\t\titem_count = 7\n"
    ), (
        f"\t\tsetting_id = priority_list\n\t\ttab_id = settings\n\t\titem_count = {CM_ITEMS + len(FEATURES)} # Prosper or Perish compatibility: + {len(FEATURES)}\n"
    ), where)
    last = "\tcmm_set_list_item_value = { mod_id = cm setting_id = priority_list item = 7 value = flag:cm_feature_auto_build_capital }\n"
    added = "".join(
        f"\tcmm_set_list_item_value = {{ mod_id = cm setting_id = priority_list item = {item} value = flag:{flag} }} # Prosper or Perish\n"
        for item, flag, _ in FEATURES)
    text = _replace(text, last, last + added, where)
    disabled = "\tcmm_disable_list_field_for_item = { mod_id = cm setting_id = priority_list field_id = min_profit item = 7 }\n"
    added = "".join(
        f"\tcmm_disable_list_field_for_item = {{ mod_id = cm setting_id = priority_list field_id = min_profit item = {item} }} # Prosper or Perish\n"
        for item, _, _ in FEATURES)
    return _replace(text, disabled, disabled + added, where)


def patch_dispatcher(text: str) -> str:
    last = "\t\t\t\t\t\t\t\tflag:cm_feature_auto_build_capital = { scope:cm_country = { cm_run_auto_build_capital = yes } }\n"
    added = "".join(
        f"\t\t\t\t\t\t\t\tflag:{flag} = {{ scope:cm_country = {{ {effect} = yes }} }} # Prosper or Perish\n"
        for _, flag, effect in FEATURES)
    return _replace(text, last, last + added, "cm_on_action.txt")


def patch_auto_food(text: str) -> str:
    match = re.search(r"(?m)^cm_run_auto_food = \{\n.*?^\}\n", text, re.DOTALL)
    if not match or "cm_food_auto_build_for_rgo_type = yes" not in match.group(0):
        raise AnchorMissing("cm_feature_effects.txt: cm_run_auto_food is not CM's food rule any more (CM changed?)")
    body = (
        "cm_run_auto_food = {\n"
        "\t# Prosper or Perish compatibility: Prosper or Perish's food rule (ppcm_effects.txt) instead of CM's vanilla\n"
        "\t# food rule, which picks vanilla food buildings by their vanilla food output.\n"
        "\tppcm_run_food = yes\n"
        "}\n"
    )
    return text[:match.start()] + body + text[match.end():]


# ---- Vanilla buildings Prosper or Perish removed ----
# Prosper or Perish has no farming_village (its crop farms took its place). CM's vanilla food rule has a farming
# village option, and every `building_type:farming_village` link fails when the game loads ("Failed to find
# 'farming_village' from database"). That rule no longer runs (patch_auto_food), so the option is switched off where
# it is defined and the links are taken out; CM's other food options stay as they are.

def _body(text: str, name: str, body: str, where: str) -> str:
    match = re.search(rf"(?m)^{name} = \{{\n.*?^\}}\n", text, re.DOTALL)
    if not match:
        raise AnchorMissing(f"{where}: {name} is gone (CM changed?)")
    return text[:match.start()] + f"{name} = {{\n\t# Prosper or Perish compatibility: no farming_village in Prosper or Perish\n{body}}}\n" + text[match.end():]


def patch_food_values(text: str) -> str:
    where = "cm_food_auto_build_script_values.txt"
    text = _body(text, "cm_food_farming_village_level", "\tvalue = 0\n", where)
    return _body(text, "cm_food_expected_gold_for_farming_village", "\tvalue = 0\n", where)


def patch_food_triggers(text: str) -> str:
    where = "cm_food_auto_build_triggers.txt"
    for name in ("cm_food_can_build_farming_village", "cm_food_option_farming_village_discounted",
                 "cm_food_option_farming_village_unshortaged"):
        text = _body(text, name, "\talways = no\n", where)
    return text


def patch_food_effects(text: str) -> str:
    return _replace(text, "\t\tcm_food_stage_building_option = { ACTION = 2 BT = building_type:farming_village }\n",
                    "\t\t# Prosper or Perish compatibility: no farming_village in Prosper or Perish\n",
                    "cm_food_auto_build_effects.txt")


def patch_filter_values(text: str) -> str:
    return _replace(text, (
        "\tsubtract = {\n"
        "\t\tvalue = \"location_building_level(building_type:farming_village)\"\n"
        "\t\tmultiply = \"building_efficiency(building_type:farming_village)\"\n"
        "\t\tmultiply = 0.025  # FV 2.5%/level\n"
        "\t}\n"
    ), "\t# Prosper or Perish compatibility: no farming_village in Prosper or Perish\n", "cm_filter_script_values.txt")


PATCHES = {
    "in_game/common/scripted_effects/cm_cmm_effects.txt": patch_registration,
    "in_game/common/on_action/cm_on_action.txt": patch_dispatcher,
    "in_game/common/scripted_effects/cm_feature_effects.txt": patch_auto_food,
    "in_game/common/script_values/cm_food_auto_build_script_values.txt": patch_food_values,
    "in_game/common/scripted_triggers/cm_food_auto_build_triggers.txt": patch_food_triggers,
    "in_game/common/scripted_effects/cm_food_auto_build_effects.txt": patch_food_effects,
    "in_game/common/script_values/cm_filter_script_values.txt": patch_filter_values,
}


def build(ctx: Context) -> dict[str, str]:
    out = {}
    for rel, patch in PATCHES.items():
        source = ctx.cm / rel
        if not source.is_file():
            raise AnchorMissing(f"Construction Manager has no {rel} any more")
        out[rel] = bom(patch(read(source)))
    return out


def cm_paths() -> list[Path]:
    return [Path(rel) for rel in PATCHES]
