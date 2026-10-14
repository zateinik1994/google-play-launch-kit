#!/usr/bin/env python3
"""Install portable skills as symlinks or dereferenced copies; never overwrite."""
import argparse
import importlib.util
import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def runtime_status():
    available = {}
    for module in ("google.auth", "requests", "google_play_scraper"):
        try:
            available[module] = importlib.util.find_spec(module) is not None
        except (ImportError, ModuleNotFoundError, ValueError):
            available[module] = False
    return {
        "interpreter": sys.executable,
        "version": ".".join(map(str, sys.version_info[:3])),
        "supported": sys.version_info[:2] >= (3, 11),
        "network_dependencies": available["google.auth"] and available["requests"],
        "collection_dependencies": available["google_play_scraper"],
    }


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--target", choices=("codex", "claude", "directory"), default="codex")
    p.add_argument("--directory", help="Installation directory; required for --target directory")
    p.add_argument("--copy", action="store_true", help="Dereference shared resources for portable copies")
    p.add_argument("--check", action="store_true", help="Check installation, interpreter and optional network dependencies without changing anything")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args(argv)
    if args.directory and args.target != "directory":
        p.error("--directory requires --target directory")
    if args.target == "directory" and not args.directory:
        p.error("--target directory requires --directory")
    if args.target == "directory":
        destination = Path(args.directory).expanduser().resolve()
    elif args.target == "codex":
        destination = Path(os.environ.get("CODEX_HOME", str(Path.home()/".codex")))/"skills"
    else:
        destination = Path.home()/".claude"/"skills"
    skills = sorted(path for path in (ROOT/"skills").iterdir() if (path/"SKILL.md").is_file())
    if args.check:
        runtime = runtime_status()
        print(f"Python: {runtime['interpreter']} ({runtime['version']}) — {'supported' if runtime['supported'] else 'requires 3.11+'}")
        print("Google API dependencies: " + ("available" if runtime["network_dependencies"] else "missing (optional for offline tools)"))
        if not runtime["network_dependencies"]:
            print("For Google API commands, install requirements.txt with this interpreter in your chosen environment.")
        print("Public collection dependency: " + ("available" if runtime["collection_dependencies"] else "missing (optional; install requirements-collection.txt)"))
        for skill in skills:
            target = destination/skill.name
            state = "not installed"
            if target.is_symlink():
                state = "linked to this repository" if target.resolve() == skill else f"other symlink: {os.readlink(target)}"
            elif target.exists():
                state = "copied or other installation"
            print(f"{skill.name}: {state}")
        return 0 if runtime["supported"] else 1
    conflicts = [destination/skill.name for skill in skills if os.path.lexists(destination/skill.name)]
    if conflicts:
        print("Existing skill paths will not be overwritten:\n" + "\n".join(map(str, conflicts)), file=sys.stderr)
        return 1
    for skill in skills:
        print(f"{'copy' if args.copy else 'link'} {skill.name} -> {destination/skill.name}")
    if args.dry_run:
        return 0
    destination.mkdir(parents=True, exist_ok=True)
    created = []
    try:
        with tempfile.TemporaryDirectory(prefix=".playkit-install-", dir=destination) as staging:
            for skill in skills:
                staged = Path(staging)/skill.name
                if args.copy:
                    shutil.copytree(skill, staged, symlinks=False, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
                else:
                    staged.symlink_to(skill, target_is_directory=True)
            for skill in skills:
                target = destination/skill.name
                if os.path.lexists(target):
                    raise FileExistsError(f"Installation target appeared during install: {target}")
                (Path(staging)/skill.name).rename(target)
                created.append(target)
    except OSError as exc:
        for target in reversed(created):
            if target.is_symlink():
                target.unlink()
            else:
                shutil.rmtree(target)
        print(f"Install failed; newly installed skills rolled back: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
