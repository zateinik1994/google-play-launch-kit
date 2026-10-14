"""CLI entrypoint, usable both from repo and installed skill references."""
import argparse
import json
import sys
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
            import re
            if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z][A-Za-z0-9_]*)+", args.package):
                raise ValueError("--package: expected an Android application ID")
            dest = Path(args.directory)
            if dest.exists():
                raise ValueError("Destination already exists; choose a new directory")
            dest.mkdir(parents=True)
            for name in ("research", "metadata", "screenshots", "reports"):
                (dest/name).mkdir()
            write_json({"package_name": args.package, "locales": [], "countries": [], "features": [],
                        "monetization": "", "note": "Fill product facts and scope before researching or publishing."}, dest/"project.json")
            write_json({"created": str(dest.resolve())})
            return 0
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
