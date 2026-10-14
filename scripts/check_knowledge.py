#!/usr/bin/env python3
"""Check skill metadata, canonical resources and local Markdown links."""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def check_markdown_links(entry):
    errors = []
    fenced = None
    for line in entry.read_text(encoding="utf-8").splitlines():
        marker = re.match(r"^\s*(`{3,}|~{3,})(.*)$", line)
        if marker:
            if fenced is None:
                fenced = marker[1]
            elif marker[1][0] == fenced[0] and len(marker[1]) >= len(fenced) and not marker[2].strip():
                fenced = None
            continue
        if fenced is not None:
            continue
        for target in re.findall(r"\[[^\]]*\]\(([^)]+)\)", line):
            if re.match(r"^[a-zA-Z][\w+.-]*:", target) or target.startswith("#"):
                continue
            path = target.split("#", 1)[0]
            if path and not (entry.parent/path).exists():
                errors.append(f"{entry}: missing reference {path}")
    return errors


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
    documents = set(skills) | set(root.glob("*.md"))
    for directory in ("knowledge", "docs", "examples"):
        documents.update((root/directory).rglob("*.md"))
    for document in sorted(documents):
        errors.extend(check_markdown_links(document))
    return errors


if __name__ == "__main__":
    errors = check()
    for error in errors:
        print(error, file=sys.stderr)
    if not errors:
        print("Skills, canonical references and local documentation links OK")
    raise SystemExit(bool(errors))
