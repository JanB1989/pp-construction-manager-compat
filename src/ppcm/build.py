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


def deploy(ctx: Context, built: Path) -> None:
    if ctx.deploy_target is None:
        raise SystemExit("no [deploy] target in ppcm.local.toml")
    target = ctx.deploy_target
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(built, target)
    print(f"deployed to {target}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="ppcm")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("build", help="write build/<mod name>/")
    dep = sub.add_parser("deploy", help="build and copy to the live mod folder")
    dep.add_argument("--yes", action="store_true", help="really copy")
    args = parser.parse_args(argv)
    ctx = Context.load()
    built = build(ctx)
    print(f"built {built}")
    if args.command == "deploy":
        if not args.yes:
            raise SystemExit("dry run: add --yes to copy to the live mod folder")
        deploy(ctx, built)


if __name__ == "__main__":
    main()
