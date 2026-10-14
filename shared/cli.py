"""CLI entrypoint, usable both from repo and installed skill references."""
import argparse
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared.metadata import validate_listings, audit_listings
from shared.analysis import read_csv, keywords, compare_ranks, reviews, ads_report, campaign_plan, RANK_FIELDS, ADS_FIELDS


def write_json(value, path=None):
    text = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    if path:
        Path(path).write_text(text, encoding="utf-8")
    else:
        print(text, end="")


def protect_inputs(output, inputs):
    """An explicit report output must never destroy its own source artifacts."""
    if output is None:
        return
    target = Path(output)
    for source in inputs:
        path = Path(source)
        if target.resolve() == path.resolve() or target.exists() and path.exists() and os.path.samefile(target, path):
            raise ValueError("Output must differ from every input file, including symlinks and hard links")


def create_workspace(destination, package):
    import re
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z][A-Za-z0-9_]*)+", package):
        raise ValueError("--package: expected an Android application ID")
    destination = Path(destination)
    if os.path.lexists(destination):
        raise ValueError("Destination already exists; choose a new directory")
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".playkit-init-", dir=destination.parent))
    try:
        for name in ("research", "metadata", "screenshots", "reports"):
            (staging/name).mkdir()
        write_json({"package_name": package, "locales": [], "countries": [], "features": [],
                    "monetization": "", "note": "Fill product facts and scope before researching or publishing."}, staging/"project.json")
        if os.path.lexists(destination):
            raise ValueError("Destination appeared during initialization; it was left unchanged")
        staging.rename(destination)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    return destination


def main(argv=None):
    parser = argparse.ArgumentParser(description="Offline Google Play launch toolkit; no credentials needed.")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("validate", help="Validate a locale->Listing JSON file")
    p.add_argument("input")
    p = sub.add_parser("keywords", help="Normalize and prioritize a supplied keyword CSV")
    p.add_argument("input")
    p = sub.add_parser("ranks", help="Compare two normalized rank observations")
    p.add_argument("before")
    p.add_argument("after")
    p = sub.add_parser("reviews", help="Summarize normalized review CSV")
    p.add_argument("input")
    p = sub.add_parser("ads-report", help="Summarize normalized Google Ads campaign/day CSV")
    p.add_argument("input")
    p = sub.add_parser("ads-plan", help="Prepare a local campaign brief, without API mutations")
    p.add_argument("input")
    p = sub.add_parser("init", help="Create an empty application workspace")
    p.add_argument("directory")
    p.add_argument("--package", required=True)
    for name, child in sub.choices.items():
        if name != "init":
            child.add_argument("--output", help="Write JSON to this file rather than stdout")
    args = parser.parse_args(argv)
    try:
        if args.command == "init":
            dest = create_workspace(args.directory, args.package)
            write_json({"created": str(dest.resolve())})
            return 0
        protect_inputs(args.output, [getattr(args, name) for name in ("input", "before", "after") if hasattr(args, name)])
        if args.command in {"validate", "ads-plan"}:
            data = json.loads(Path(args.input).read_text(encoding="utf-8"))
        if args.command == "validate":
            errors = validate_listings(data)
            result = {"valid": not errors, "errors": errors, "audit": audit_listings(data) if not errors else []}
            write_json(result, args.output)
            return 1 if errors else 0
        elif args.command == "keywords":
            result = keywords(read_csv(args.input, ("query", "locale", "country", "source", "relevance")))
        elif args.command == "ranks":
            result = compare_ranks(read_csv(args.before, RANK_FIELDS), read_csv(args.after, RANK_FIELDS))
        elif args.command == "reviews":
            result = reviews(read_csv(args.input, ("review_id", "rating", "text")))
        elif args.command == "ads-report":
            result = ads_report(read_csv(args.input, ADS_FIELDS))
        else:
            result = campaign_plan(data)
        write_json(result, args.output)
        return 0
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
