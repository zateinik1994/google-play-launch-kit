#!/usr/bin/env python3
"""Check canonical resource links and skill frontmatter without third-party modules."""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def check(root=ROOT):
    errors = []
    skills = sorted((root/"skills").glob("*/SKILL.md"))
    if not skills:
        return ["No skills found"]
    for entry in skills:
        text = entry.read_text(encoding="utf-8")
        match = re.match(r"\A---\n(.*?)\n---\n", text, re.S)
        if not match:
            errors.append(f"{entry}: missing frontmatter")
            continue
        name = re.search(r"^name:\s*(.+)$", match[1], re.M)
        description = re.search(r"^description:\s*(.+)$", match[1], re.M)
        if not name or name[1].strip() != entry.parent.name:
            errors.append(f"{entry}: name differs from directory")
        if not description or not description[1].strip():
            errors.append(f"{entry}: description required")
        for link in (entry.parent/"references").iterdir() if (entry.parent/"references").exists() else ():
            if link.is_symlink() and not link.exists():
                errors.append(f"{link}: broken canonical resource link")
            if link.name in {"knowledge", "shared", "docs", "examples"}:
                canonical = root/link.name
                if not link.is_symlink() or link.resolve() != canonical.resolve():
                    errors.append(f"{link}: should link to canonical {canonical}")
        for target in re.findall(r"\[[^\]]*\]\(([^)]+)\)", text):
            if re.match(r"^[a-zA-Z][\w+.-]*:", target) or target.startswith("#"):
                continue
            path = target.split("#", 1)[0]
            if path and not (entry.parent/path).exists():
                errors.append(f"{entry}: missing reference {path}")
    return errors


if __name__ == "__main__":
    errors = check()
    for error in errors:
        print(error, file=sys.stderr)
    if not errors:
        print("Skills and canonical references OK")
    raise SystemExit(bool(errors))
