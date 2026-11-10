"""The merged GUI files: well-formed, complete (every PP and every CM change), PP's protected copies still in use."""

from __future__ import annotations

import re
from collections import Counter

import pytest

from ppcm import gui_merge as gm
from ppcm.context import read


@pytest.fixture(scope="module")
def result(ctx):
    return gm.merge_all(ctx)


def _instances(doc: gm.Doc, name: str) -> int:
    return sum(1 for s in doc.walk() if s.head == (name, "=") and s.block)


def _lines(text: str) -> Counter:
    return Counter(x for x in (" ".join(line.split("#", 1)[0].split()) for line in text.splitlines()) if x)


# --------------------------------------------------------------------------------------------------------------------
# the outputs


def test_outputs(result):
    assert set(result.same_path) == {"in_game/gui/location_window.gui", "in_game/gui/building_view.gui"}
    assert set(result.outputs) == set(result.same_path) | {gm.MERGED_TYPES}


def test_outputs_are_well_formed(result):
    for rel, text in result.outputs.items():
        assert text.startswith("﻿"), rel
        assert "\r" not in text, rel
        assert not re.search(r"(?m)^(<{7}|={7}|>{7}|\|{7})", text), rel
        doc = gm.check_gui(text, rel)  # balanced braces, closed strings, whole statements
        assert sum(t.kind == "{" for t in doc.toks) == sum(t.kind == "}" for t in doc.toks), rel


def test_every_record_is_in_its_output(result):
    for rec in result.records:
        assert rec.merged in result.outputs[rec.out], rec.key


def test_deterministic(ctx, result):
    again = gm.merge_all(ctx)
    assert again.outputs == result.outputs
    assert again.log == result.log


def test_build_returns_the_outputs(ctx, result):
    assert gm.build(ctx) == result.outputs


# --------------------------------------------------------------------------------------------------------------------
# completeness


def test_every_added_identifier_is_kept(result):
    """Every name PP adds to a part (widget, type, loc key, scripted GUI, data-binding function, pp_ name) and every
    name CM adds (cm_/glorpui_ names, loc keys, scripted GUI calls, macros) is in the merged part, except what a part
    rule leaves out on purpose."""
    for rec in result.records:
        merged = gm.identifiers(rec.merged) | ({rec.copy_of} if rec.copy_of else set())
        base = gm.identifiers(rec.base)
        missing_pp = gm.identifiers(rec.ours) - base - merged - rec.pp_dropped
        missing_cm = gm.identifiers(rec.theirs) - base - merged - rec.cm_dropped
        assert not missing_pp, (rec.out, rec.key, "PP", sorted(missing_pp))
        assert not missing_cm, (rec.out, rec.key, "CM", sorted(missing_cm))


def test_mod_prefixed_names_are_kept(result):
    """The mods' own names (pp_, cm_, glorpui_ and the loc keys PP_, CM_, GLORP) in every output."""
    pattern = re.compile(r"\b(?:pp_|cm_|glorpui_|PP_|CM_|GLORP_?UI)\w*", re.IGNORECASE)
    for rec in result.records:
        merged = set(pattern.findall(rec.merged))
        for side, text, dropped in (("PP", rec.ours, rec.pp_dropped), ("CM", rec.theirs, rec.cm_dropped)):
            lost = set(pattern.findall(text)) - set(pattern.findall(rec.base)) - merged - dropped
            if rec.copy_of:
                lost.discard(rec.copy_of)
            assert not lost, (rec.key, side, sorted(lost))


def test_line_merges_carry_both_sides_whole(result):
    """Where no part rule applies, the merged part holds PP's changes exactly as PP made them and CM's exactly as CM
    made them (as line counts: merged minus CM's = PP's changes, merged minus PP's = CM's changes)."""
    for rec in result.records:
        name = (rec.key[0], rec.copy_of) if rec.copy_of else rec.key
        if name in gm.PART_RULES or not rec.base:
            continue
        base, ours, theirs = _lines(rec.base), _lines(rec.ours), _lines(rec.theirs)
        merged = _lines(gm._rename_first_line(rec.merged, rec.key[1], rec.copy_of) if rec.copy_of else rec.merged)
        assert merged - theirs == ours - base, (rec.key, "PP's additions")
        assert theirs - merged == base - ours, (rec.key, "PP's removals")
        assert merged - ours == theirs - base, (rec.key, "CM's additions")
        assert ours - merged == base - theirs, (rec.key, "CM's removals")


def test_types_both_mods_define_are_merged(ctx, result):
    """Every type or template PP and CM both define, differently, is defined by the patch (which loads last)."""
    pp, cm = gm.index(ctx.pp_mod, "PP"), gm.index(ctx.cm, "CM")
    defined = {r.key for r in result.records}
    for key in set(pp) & set(cm):
        if gm._solid(pp[key][0].text.splitlines()) != gm._solid(cm[key][0].text.splitlines()):
            assert key in defined, key


def test_pp_copies_of_types_cm_changes_are_merged(ctx, result):
    """PP's pp_ copies of a type CM changes carry CM's change (the patch defines them)."""
    pp, cm = gm.index(ctx.pp_mod, "PP"), gm.index(ctx.cm, "CM")
    van = gm.Vanilla(ctx.vanilla)
    defined = {r.key for r in result.records}
    for key, (pdef,) in pp.items():
        orig = (key[0], key[1][len(gm.COPY_PREFIX):])
        if not key[1].startswith(gm.COPY_PREFIX) or orig not in cm:
            continue
        base = van.find(orig, [pdef.rel, cm[orig][0].rel]) or ""
        if gm._solid(cm[orig][0].text.splitlines()) != gm._solid(base.splitlines()):
            assert key in defined, key


def test_same_path_files_keep_pp_structure(ctx, result):
    """The patch's copy of a file both mods ship replaces both: it defines every type, template and window of PP's."""
    for rel in result.same_path:
        pp = gm.Doc(read(ctx.pp_mod / rel), rel).parts()
        out = gm.Doc(result.outputs[rel].lstrip("﻿"), rel).parts()
        assert set(pp) <= set(out), (rel, sorted(set(pp) - set(out)))
        cm = gm.Doc(read(ctx.cm / rel), rel).parts()
        assert set(cm) <= set(out), (rel, sorted(set(cm) - set(out)))


def test_pp_copies_still_instantiated(ctx, result):
    """PP's windows use its protected pp_ copies as before (same number of instances), and each copy is defined."""
    for rel in result.same_path:
        pp = gm.Doc(read(ctx.pp_mod / rel), rel)
        out = gm.Doc(result.outputs[rel].lstrip("﻿"), rel)
        for key in pp.parts():
            if key[0] == "type" and key[1].startswith(gm.COPY_PREFIX):
                assert key in out.parts(), key
                assert _instances(out, key[1]) == _instances(pp, key[1]), key
    assert _instances(gm.Doc(result.outputs["in_game/gui/location_window.gui"].lstrip("﻿"), "lw"), "pp_location_card") > 0
    # the copies the patch redefines in the merged types file: PP's own (unreplaced) windows still use them
    merged = gm.Doc(result.outputs[gm.MERGED_TYPES].lstrip("﻿"), gm.MERGED_TYPES)
    copies = [k[1] for k in merged.parts() if k[0] == "type" and k[1].startswith(gm.COPY_PREFIX)]
    assert "pp_food_production_province" in copies
    for name in copies:
        users = [rel for rel in gm.gui_files(ctx.pp_mod) if rel not in result.same_path
                 and _instances(gm.Doc(read(ctx.pp_mod / rel), rel), name)]
        assert users, f"no PP window instantiates {name}"


# --------------------------------------------------------------------------------------------------------------------
# the part rules


def test_every_part_rule_is_used(result):
    used = {(r.key[0], r.copy_of) if r.copy_of else r.key for r in result.records}
    assert set(gm.PART_RULES) <= used, sorted(set(gm.PART_RULES) - used)


def test_dropped_only_by_part_rules(result):
    for rec in result.records:
        name = (rec.key[0], rec.copy_of) if rec.copy_of else rec.key
        if name not in gm.PART_RULES:
            assert not rec.pp_dropped and not rec.cm_dropped, rec.key


def _record(result, key):
    return next(r for r in result.records if r.key == key)


def test_build_entry(result):
    text = " ".join(_record(result, ("template", "build_location_entry")).merged.split())
    assert "using = pp_build_location_values" in text  # PP's value columns
    assert "cm_auto_expand_building_button_bll" in text  # CM's auto-expand button
    assert "cm_check_for_auto_expand_when_removing_building" in text
    assert "cm_check_for_auto_expand_when_upgrading_building" in text
    assert "GLORP_UI_BL_ROI_MONTHS_VALUE" in text  # GlorpUI's ROI stays
    # PP's slot columns, with CM's slot size, and no single slot column left
    assert text.count("production_method_slot_circle = { size = { 22 22 } }") == 3
    assert "DataModelSkipFirst(LocationToBuildItem.GetBuildingSlots, '(int32)4')" in text
    assert "production_method_slot_circle = {}" not in text
    assert 'visible = "[Not(LocationToBuildItem.GetBuildingType.IsProducing)]"' in text
    assert "# expand = {} # GlorpUI: disabled" not in text


def test_build_list_rows(result):
    rec = _record(result, ("type", "build_location_lateralview_panel_content"))
    doc = gm.Doc(rec.merged, "panel")
    layout = gm._block(doc, ("blockoverride", '"scroll_list_layout"'))
    sizes = [" ".join(doc.raw(s).split()) for s in doc.walk(layout) if s.head == ("size", "=")]
    rows = " ".join(doc.raw(layout).split()).count("using = build_location_entry")  # the selected sort + each payback band
    assert rows >= 12
    assert sizes.count("size = { 930 56 }") == rows and sizes.count("size = { 100% 54 }") == rows
    assert "size = { 930 60 }" not in sizes and "size = { 100% 58 }" not in sizes
    assert "addrow = 56" in " ".join(rec.merged.split())
    assert "cm_mass_auto_expand_button_bll" in rec.merged  # CM's header buttons
    assert "pp_payback_order" in rec.merged  # PP's payback sort


def test_pp_row_header(result):
    rec = _record(result, ("type", "pp_location_filtered_header_with_candidate"))
    assert "cm_auto_expand_existing_building_button" in rec.merged
    assert "glorpui_is_cm_active" in rec.merged
    assert "GLORP_UI_BL_ROI" not in rec.merged  # not carried: PP's rows show payback in their own column
    # PP's efficiency columns untouched by CM's compaction (70x18 lines, spacing 6)
    ours, merged = _lines(rec.ours), _lines(rec.merged)
    pp_columns = [x for x in ours if "Building.GetProductionMethods" in x] + ["size = { 70 18 }", "spacing = 6"]
    assert all(ours[x] and merged[x] == ours[x] for x in pp_columns), pp_columns


# --------------------------------------------------------------------------------------------------------------------
# the merge engine on small cases


def _merge(base: str, ours: str, theirs: str) -> str:
    log: list[str] = []
    tagged = gm.merge3_tagged(base.splitlines(True), ours.splitlines(True), theirs.splitlines(True), "test",
                              lambda h: gm.resolve_default(h, log))
    gm.check_nesting(tagged, "test")
    return "".join(x for x, _ in tagged)


BASE = """hbox = {
\tsize = { 10 10 }
\ttext_single = {
\t\ttext = "A"
\t}
\ticon = {
\t\ttexture = "x.dds"
\t}
}
"""


def test_separate_changes_merge():
    ours = BASE.replace('text = "A"', 'text = "PP_A"')
    theirs = BASE.replace('texture = "x.dds"', 'texture = "cm.dds"')
    merged = _merge(BASE, ours, theirs)
    assert 'text = "PP_A"' in merged and 'texture = "cm.dds"' in merged


def test_whitespace_is_no_change():
    theirs = BASE.replace("\t", "    ").replace("\n", "  \n")
    ours = BASE.replace("{ 10 10 }", "{ 20 10 }")
    assert _merge(BASE, ours, theirs) == ours


def test_both_insert_keeps_both_pp_first():
    ours = BASE.replace("\ticon = {", "\tpp_widget = {}\n\ticon = {")
    theirs = BASE.replace("\ticon = {", "\tcm_widget = {}\n\ticon = {")
    merged = _merge(BASE, ours, theirs)
    assert merged.index("pp_widget") < merged.index("cm_widget") < merged.index("icon = {")


def test_both_set_the_same_attribute_stops():
    ours = BASE.replace("\ticon = {", "\tvisible = yes\n\ticon = {")
    theirs = BASE.replace("\ticon = {", "\tvisible = no\n\ticon = {")
    with pytest.raises(gm.GuiMergeError, match="no rule covers it"):
        _merge(BASE, ours, theirs)


def test_same_line_changed_both_ways_stops():
    ours = BASE.replace("{ 10 10 }", "{ 20 10 }")
    theirs = BASE.replace("{ 10 10 }", "{ 30 10 }")
    with pytest.raises(gm.GuiMergeError, match="no rule covers it"):
        _merge(BASE, ours, theirs)


def test_adjacent_changes_merge():
    ours = BASE.replace("\tsize = { 10 10 }\n", "\tsize = { 20 20 }\n")
    theirs = BASE.replace("\tsize = { 10 10 }\n", "\tsize = { 10 10 }\n\tcm_child = {}\n").replace('text = "A"', 'text = "B"')
    merged = _merge(BASE, ours, theirs)
    assert "{ 20 20 }" in merged and "cm_child" in merged and '"B"' in merged


def test_box_closed_by_the_other_side_stops():
    # a box PP opened, closed by a brace CM added: CM's change nests into PP's box (or the other way round)
    gm.check_nesting([("vbox = {\n", "pp"), ("\tcm_child = {}\n", "cm"), ("}\n", "pp")], "test")  # CM's child in PP's box: fine
    gm.check_nesting([("vbox = {\n", "pp"), ("}\n", "=")], "test")  # PP changed vanilla's opening line: fine
    with pytest.raises(gm.GuiMergeError, match="one mod's change nests"):
        gm.check_nesting([("vbox = {\n", "pp"), ("\tsize = { 1 1 }\n", "="), ("}\n", "cm")], "test")


def test_unbalanced_output_is_refused():
    with pytest.raises(gm.GuiMergeError):
        gm.check_gui("hbox = {\n\tsize = { 1 1 }\n", "test")
    with pytest.raises(gm.GuiMergeError):
        gm.check_gui('hbox = {\n\ttext = "open\n}\n', "test")
    with pytest.raises(gm.GuiMergeError, match="conflict marker"):
        gm.check_gui("<<<<<<< PP\nhbox = {}\n", "test")


def test_identifiers_skip_comments_and_read_strings():
    text = 'widget = { # pp_comment_only\n\tvisible = "[GetScriptedGui(\'cm_x\').IsShown(GuiScope.End)]"\n\ttext = "PP_KEY"\n}\n'
    ids = gm.identifiers(text)
    assert {"widget", "visible", "GetScriptedGui", "cm_x", "IsShown", "PP_KEY"} <= ids
    assert "pp_comment_only" not in ids


def test_pairs_patience():
    a = ["a", "}", "b", "}", "c"]
    b = ["a", "}", "x", "b", "}", "c"]
    assert gm.pairs(a, b) == [(0, 0), (1, 1), (2, 3), (3, 4), (4, 5)]
