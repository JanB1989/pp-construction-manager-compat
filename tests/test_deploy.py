"""Deploying the patch never hot-reloads game data into a running game (Prosper or Perish's rule since 2026-10-18)."""

from __future__ import annotations

from pathlib import Path

from ppcm import build
from ppcm.context import Context


def _tree(root: Path, files: dict[str, str]) -> None:
    for rel, text in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")


def _ctx(target: Path) -> Context:
    here = Path(".")
    return Context(pp_mod=here, pp_repo=here, cm=here, cmf=here, vanilla=here, deploy_target=target)


def test_changed_files(tmp_path: Path) -> None:
    built, target = tmp_path / "b", tmp_path / "t"
    _tree(built, {"in_game/gui/a.gui": "1", "in_game/common/x.txt": "2"})
    _tree(target, {"in_game/gui/a.gui": "1", "gone.txt": "3"})
    assert build.changed_files(built, target) == ["gone.txt", "in_game/common/x.txt"]


def test_running_game_gets_interface_only(tmp_path: Path) -> None:
    built, target = tmp_path / "b", tmp_path / "t"
    _tree(built, {"in_game/gui/a.gui": "new", "in_game/common/scripted_effects/x.txt": "new"})
    _tree(target, {"in_game/gui/a.gui": "old", "in_game/common/scripted_effects/x.txt": "old"})
    assert build.deploy(_ctx(target), built, game_running=True) == 3
    assert (target / "in_game/gui/a.gui").read_text() == "old"
    # interface and text alone deploy while the game runs
    (built / "in_game/common/scripted_effects/x.txt").write_text("old")
    assert build.deploy(_ctx(target), built, game_running=True) == 0
    assert (target / "in_game/gui/a.gui").read_text() == "new"
    # with the game closed everything deploys
    (built / "in_game/common/scripted_effects/x.txt").write_text("newer")
    assert build.deploy(_ctx(target), built) == 0
    assert (target / "in_game/common/scripted_effects/x.txt").read_text() == "newer"
