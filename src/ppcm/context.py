"""Paths and file helpers shared by the build steps."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
MOD_SOURCE = REPO / "mod"  # hand-written files of the patch (ours, committed)
BUILD = REPO / "build"
MOD_NAME = "Prosper or Perish - Construction Manager Compatibility"


@dataclass(frozen=True)
class Context:
    pp_mod: Path  # Prosper or Perish, the built mod folder
    pp_repo: Path  # the constructor checkout (data the rules are generated from)
    cm: Path  # Construction Manager
    cmf: Path  # Community Mod Framework
    vanilla: Path  # the game: in_game, main_menu, dlc
    deploy_target: Path | None = None

    @classmethod
    def load(cls, path: Path | None = None) -> "Context":
        path = path or REPO / "ppcm.local.toml"
        if not path.is_file():
            raise SystemExit(f"{path} is missing: copy ppcm.local.toml.example and fix the paths")
        data = tomllib.loads(path.read_text(encoding="utf-8"))
        paths = {key: Path(value) for key, value in data["paths"].items()}
        target = data.get("deploy", {}).get("target")
        return cls(deploy_target=Path(target) if target else None, **paths)


def read(path: Path) -> str:
    """A game text file: UTF-8 with or without BOM, LF line ends."""
    return path.read_text(encoding="utf-8-sig").replace("\r\n", "\n")


def bom(text: str) -> str:
    return text if text.startswith("\ufeff") else "\ufeff" + text
