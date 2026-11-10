"""Prosper or Perish rules as Construction Manager features (rules.py, cm_patch.py, mod/*/ppcm_*)."""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

from ppcm import cm_patch, rules
from ppcm.context import MOD_SOURCE, Context, read

KINDS = ("scripted_effects", "scripted_triggers", "script_values")


@lru_cache(maxsize=1)
def _built() -> dict[str, str]:
    return rules.build(Context.load())


def _code(text: str) -> str:
    return re.sub(r"#[^\n]*", "", text.lstrip("﻿"))


def _block(text: str, name: str) -> str:
    match = re.search(rf"(?m)^{name} = \{{\n(.*?)^\}}", text, re.DOTALL)
    assert match, name
    return match.group(1)


def _hand(rel: str) -> str:
    return read(MOD_SOURCE / rel)


def _defined(root: Path) -> set[str]:
    names: set[str] = set()
    for sub in ("in_game/common", "main_menu/common"):
        for kind in KINDS:
            folder = root / sub / kind
            if folder.is_dir():
                for path in folder.glob("*.txt"):
                    names |= set(re.findall(r"(?m)^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*\{", read(path)))
    return names


def test_generated_files_are_renamed_and_balanced() -> None:
    built = _built()
    for rel in (rules.EFFECTS, rules.VALUES, rules.TRIGGERS, *map(str, cm_patch.cm_paths())):
        assert rel in built, rel
    for rel, text in built.items():
        code = _code(text)
        assert code.count("{") == code.count("}"), rel
        if not rel.split("/")[-1].startswith("cm_"):
            assert "pp_cplan_" not in text, f"{rel}: a plan name was not renamed"
    effects = built[rules.EFFECTS]
    for picker in ("ppcm_try_farm_here", "ppcm_try_yard_here", "ppcm_try_kitchen_here", "ppcm_try_tavern_here",
                   "ppcm_try_granary_here", "ppcm_try_grange_here", "ppcm_try_improve_here", "ppcm_try_logistics_here",
                   "ppcm_btype_data"):
        assert f"\n{picker} = {{" in effects, picker
    # the plan window's flag list is not part of these rules
    assert "ppcm_declare_flags" not in effects


def test_every_name_is_defined() -> None:
    """Every scripted effect, trigger and script value the patch calls exists in the game, Prosper or Perish,
    Construction Manager, CMF or the patch itself."""
    ctx = Context.load()
    defined = set().union(*(_defined(root) for root in (ctx.vanilla, ctx.pp_mod, ctx.cm, ctx.cmf, MOD_SOURCE)))
    for dlc in (ctx.vanilla / "dlc").glob("*"):
        defined |= _defined(dlc)
    built = _built()
    for rel, text in built.items():
        defined |= set(re.findall(r"(?m)^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*\{", text))
    texts = {rel: text for rel, text in built.items() if not rel.split("/")[-1].startswith("cm_")}
    for path in MOD_SOURCE.rglob("*.txt"):
        texts[str(path.relative_to(MOD_SOURCE))] = read(path)
    # names used as a call, a value or in a comparison; never a variable (var:x), a saved scope (scope:x) or a link
    calls = re.compile(r"(?<![:.\w])((?:ppcm|pp|cm|cmm)_[a-z0-9_]+) = (?:yes|no|\{)")
    values = re.compile(r"(?:value|add|subtract|multiply|divide|min|max|order_by) = ((?:ppcm|pp|cm)_[a-z0-9_]+)\b")
    compared = re.compile(r"(?<![:.\w])((?:ppcm|pp|cm)_[a-z0-9_]+) (?:[<>]=?) ")
    skip = re.compile(r"^(cm_q_|cm_gui_|cm_auto_food_location|ppcm_(hit|old)$|cm_location$|cm_building_type$)")
    for rel, text in texts.items():
        code = _code(text)
        for pattern in (calls, values, compared):
            for name in pattern.findall(code):
                if skip.match(name) or name.startswith("ppcm_on_"):
                    continue
                assert name in defined, f"{rel}: {name} is not defined anywhere"


def test_construction_manager_learns_the_features() -> None:
    built = _built()
    registration = built["in_game/common/scripted_effects/cm_cmm_effects.txt"]
    assert f"\t\titem_count = {cm_patch.CM_ITEMS + len(cm_patch.FEATURES)} #" in registration
    assert [flag for _, flag, _ in cm_patch.FEATURES] == [
        "ppcm_feature_granaries", "ppcm_feature_improvements", "ppcm_feature_logistics"]
    dispatcher = built["in_game/common/on_action/cm_on_action.txt"]
    for item, flag, effect in cm_patch.FEATURES:
        assert f"item = {item} value = flag:{flag} }}" in registration
        assert f"field_id = min_profit item = {item} }}" in registration
        assert f"flag:{flag} = {{ scope:cm_country = {{ {effect} = yes }} }}" in dispatcher
    food = _block(built["in_game/common/scripted_effects/cm_feature_effects.txt"], "cm_run_auto_food")
    assert "ppcm_run_food = yes" in food and "cm_food_auto_build_for_rgo_type" not in food
    loc = _hand("main_menu/localization/english/ppcm_l_english.yml")
    for item, _, _ in cm_patch.FEATURES:
        assert f"cm__priority_list_i{item}_name:" in loc and f"cm__priority_list_i{item}_desc:" in loc
    assert "cm__ppcm_improve_line_name:" in loc and "cm__ppcm_access_line_name:" in loc
    assert "cm__priority_list_i5_desc:" in _hand("main_menu/localization/replace/english/ppcm_replace_l_english.yml")


def test_patches_fail_loudly_when_construction_manager_changes() -> None:
    try:
        cm_patch.patch_dispatcher("nothing here")
    except cm_patch.AnchorMissing:
        pass
    else:
        raise AssertionError("a missing anchor must stop the build")


def test_staging_goes_through_construction_manager() -> None:
    """The rules never build themselves: picks go into CM's ungated queue or, where an older tier stands, its upgrade
    queue without the metric gate; a location already staged by an earlier CM feature this month is left alone."""
    effects = _hand("in_game/common/scripted_effects/ppcm_effects.txt")
    built = _built()
    direct = re.compile(r"(?<!\w)construct_building\s*=")
    assert not direct.search(_code(effects)) and not direct.search(_code(built[rules.EFFECTS]))
    scoped = _block(effects, "ppcm_construct_scoped")
    assert "ppcm_location_free = yes" in scoped and "cm_stage_ungated_candidate = yes" in scoped
    assert "ppcm_stage_upgrade = yes" in scoped and "cm_building_meets_minimum_discount" in scoped
    upgrade = _block(effects, "ppcm_stage_upgrade")
    assert "cm_gui_upgrade_building_types" in upgrade and "cm_q_upgrade_gated_types" not in upgrade
    free = _block(_hand("in_game/common/scripted_triggers/ppcm_triggers.txt"), "ppcm_location_free")
    for queue in ("cm_q_locations", "cm_q_ungated_locations", "cm_gui_upgrade_locations", "cm_q_food_locations"):
        assert queue in free, queue
    assert "num_civil_constructions < 1" in free


def test_food_rule_steps() -> None:
    """Prosper or Perish's food rule, without its Granary step (the Granaries row): famine Tavern, farm, kitchen,
    Tavern, Grange, Victualling Yard; the hunger steps wait for farms and Taverns under construction."""
    body = _block(_hand("in_game/common/scripted_effects/ppcm_effects.txt"), "ppcm_food_province")
    order = ["ppcm_try_tavern_here", "ppcm_try_farm_here", "ppcm_try_kitchen_here", "ppcm_try_tavern_here",
             "ppcm_try_grange_here", "ppcm_try_yard_here"]
    position = 0
    for step in order:
        position = body.index(step, position) + 1
    assert "ppcm_try_granary_here" not in body
    assert body.count("NOT = { any_location_in_province = { ppcm_food_queued = yes } }") == 2
    assert "save_temporary_scope_value_as = { name = ppcm_fy value = ppcm_food_in_a_year }" in body
