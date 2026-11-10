"""Build the patch: our files (mod/) plus what is generated from the three mods and the game.

    uv run ppcm build            # writes build/<mod name>/
    uv run ppcm deploy --yes     # copies it to the live mod folder ([deploy] target)

Steps (each returns {relative path: text}):
- gui_merge: the GUI files and types Prosper or Perish and Construction Manager both change, merged.
- rules: Prosper or Perish's food, Granary and improvement rules as Construction Manager features.
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from ppcm.context import BUILD, MOD_NAME, MOD_SOURCE, Context


def generated(ctx: Context) -> dict[str, str]:
    from ppcm import gui_merge, rules

    out: dict[str, str] = {}
    for step in (gui_merge, rules):
        for rel, text in step.build(ctx).items():
            if rel in out:
                raise SystemExit(f"{rel} is written by two steps")
            out[rel] = text
    return out


def build(ctx: Context, out: Path | None = None) -> Path:
    out = out or BUILD / MOD_NAME
    if out.exists():
        shutil.rmtree(out)
    shutil.copytree(MOD_SOURCE, out)
    for rel, text in generated(ctx).items():
        if (MOD_SOURCE / rel).exists():
            raise SystemExit(f"{rel} is both hand-written (mod/) and generated")
        path = out / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")
    return out


# Files the running game may reload safely (Prosper or Perish's rule since 2026-10-18: a hot reload of game data broke
# a running game's constructions and its saves).
LIVE_SAFE = ("in_game/gui/", "main_menu/gui/", "main_menu/localization/", "in_game/gfx/", "main_menu/gfx/", ".metadata/")


def changed_files(built: Path, target: Path) -> list[str]:
    """Relative paths that differ between the build and the deployed copy (new, changed or gone)."""
    def files(root: Path) -> dict[str, bytes]:
        return {str(p.relative_to(root)): p.read_bytes() for p in root.rglob("*") if p.is_file()} if root.is_dir() else {}

    new, old = files(built), files(target)
    return sorted(rel for rel in new.keys() | old.keys() if new.get(rel) != old.get(rel))


def deploy(ctx: Context, built: Path, *, game_running: bool = False) -> int:
    if ctx.deploy_target is None:
        raise SystemExit("no [deploy] target in ppcm.local.toml")
    target = ctx.deploy_target
    changed = changed_files(built, target)
    if not changed:
        print(f"{target} is up to date")
        return 0
    unsafe = [rel for rel in changed if not rel.replace("\\", "/").startswith(LIVE_SAFE)]
    if game_running and unsafe:
        print(f"EU5 is running and the patch would hot-reload {len(unsafe)} game-data file(s): "
              + ", ".join(unsafe[:8]) + ("..." if len(unsafe) > 8 else "")
              + "\nNOT deployed; it deploys with the next sync after the game is closed.")
        return 3
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(built, target)
    print(f"deployed to {target} ({len(changed)} file(s) changed)")
    return 0


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="ppcm")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("build", help="write build/<mod name>/")
    dep = sub.add_parser("deploy", help="build and copy to the live mod folder")
    dep.add_argument("--yes", action="store_true", help="really copy")
    dep.add_argument("--game-running", action="store_true",
                     help="EU5 is running: deploy only interface and text changes (no game-data hot reload)")
    args = parser.parse_args(argv)
    ctx = Context.load()
    built = build(ctx)
    print(f"built {built}")
    if args.command == "deploy":
        if not args.yes:
            raise SystemExit("dry run: add --yes to copy to the live mod folder")
        raise SystemExit(deploy(ctx, built, game_running=args.game_running))


if __name__ == "__main__":
    main()
