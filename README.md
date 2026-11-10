# Prosper or Perish - Construction Manager Compatibility

An EU5 (1.4) patch that lets [Construction Manager](https://steamcommunity.com/sharedfiles/filedetails/?id=3736668860)
(which needs the [Community Mod Framework](https://github.com/Europa-Universalis-5-Modding-Co-op/community-mod-framework))
run together with [Prosper or Perish](https://steamcommunity.com/sharedfiles/filedetails/?id=3613232232).

**Load order:** Community Mod Framework, Prosper or Perish, Construction Manager, this patch (last).

## What it does

**Interface.** Both mods replace the location window and the building view, and both change a few shared interface
types (the build panel, the food view). The patch carries merged versions built from both mods as installed, so the
additions of both show.

**Prosper or Perish's rules as Construction Manager features.** Construction Manager's priority list (Construction
Automation, on its Settings tab) gets Prosper or Perish's rules. They pick what to build; Construction Manager builds
it with its own checks: the engine's cost against your Gold Reserve, a free construction slot, the construction goods
in the market. The Min Discount field of each row works as for Construction Manager's own rows.

| Row | What it builds |
| --- | --- |
| Auto-Food (Prosper or Perish) | Replaces Construction Manager's vanilla food rule. Per province, one construction a month, the first that applies, reading the food store a normal year would leave a year from now: a Tavern in famine; the farm, orchard, fishery, herd or forest village that pays back fastest when short of food; a Cookshop or Public Kitchen whenever the province's budget allows; a Tavern when short and no farm is possible; a Grange on a full, growing store; a Victualling Yard while it pays back. A location whose Auto-Food button is off is left out. |
| Granaries (Prosper or Perish) | A Granary level where a province's store has little room, is nearly full and still grows. |
| Improvements (Prosper or Perish) | Where a location's population reaches the **Improvement Line** (a setting, % of capacity), the improvement that adds the most capacity for its price; the fullest locations first. |
| Logistics (Prosper or Perish) | Where a location's market access, short-lived event effects taken out, is below the **Logistics Line** (a setting, %), the logistics building that location can have; the most urgent first. |

Where an older tier of the chosen building stands, its upgrade is staged instead (through Construction Manager's
upgrade queue, without its profit gate: improvements and Granaries earn nothing). Every row leaves a location alone
when an earlier row staged something there that month, when it is already building (Prosper or Perish builds a
location's constructions one after another), or when you excluded that building type there from auto-expand.

The rules are Prosper or Perish's Construction Plan rules (constructor branch `location-profiles`); `src/ppcm/plan_core.py`
is that branch's generator, kept as it is, and the patch renames its names (`pp_cplan_` to `ppcm_`).

## Building it

The patch is generated: the merged files come from both mods as installed, so it is rebuilt whenever either changes
(an anchor or merge conflict that is new stops the build with a message). The built mod is not committed: it carries
Construction Manager's code.

```bash
cp ppcm.local.toml.example ppcm.local.toml   # fix the paths
uv run ppcm build                            # build/<mod name>/
uv run ppcm deploy --yes                     # copy it to the live mod folder
uv run pytest -q
```

The Prosper or Perish constructor (branch `cmf-compat`) runs `ppcm deploy` after every `ppc sync` when its
`constructor.local.toml` names this repository (`[cm_compat] repo`), so the merged interface files follow every change of
Prosper or Perish's. While EU5 runs, `--game-running` deploys interface and text only and leaves game-data changes for
the next deploy (a hot reload of game data breaks a running game).

Layout: `mod/` the patch's own files; `src/ppcm/gui_merge.py` the interface merges; `src/ppcm/rules.py` the generated
rule parts from Prosper or Perish's buildings (`ppcm.toml` holds the rules' numbers); `src/ppcm/cm_patch.py` the three
Construction Manager files that learn of the new rows.
