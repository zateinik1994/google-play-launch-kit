#!/usr/bin/env python3
"""Offline locale inventory and evidence checklist; never a Play approval verdict."""
import argparse
import json
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

try:
    from .metadata import LANGUAGE_TAG, validate_listing, validate_listings
except ImportError:
    from metadata import LANGUAGE_TAG, validate_listing, validate_listings

PACKAGE = r"[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z][A-Za-z0-9_]*)+"
CHECKS = {
    "product_truth": "Current Android functions and monetization match the listing promises",
    "privacy_data_safety": "Privacy policy, Data safety and actual app/SDK data flows agree",
    "permissions_sdks": "Permissions, SDK versions and applicable declarations were reviewed",
    "build_signing_target_api": "Selected build, signing, versionCode and current target requirements were verified",
    "testing_release_eligibility": "Account/testing gates and intended release track are confirmed",
    "reviewer_access": "Reviewer instructions work from a clean install for the intended build",
    "billing": "Applicable purchases, offers and subscription terms were verified",
    "account_deletion": "Applicable account/data deletion paths were verified",
    "visual_localization": "Selected assets, real UI language, device coverage and translations were reviewed",
}


def identity(package, release=None):
    if not isinstance(package, str) or not re.fullmatch(PACKAGE, package):
        raise ValueError("Expected an Android package_name")
    if release is not None and (not isinstance(release, str) or not release.strip()):
        raise ValueError("release_reference must identify the intended build/release")


def template(package, release):
    identity(package, release)
    if release is None:
        raise ValueError("Template requires an explicit release_reference")
    return {"package_name": package, "release_reference": release,
            "checks": {key: {"status": "pending", "reference": "", "checked_at": None, "note": ""} for key in CHECKS}}


def evidence_rows(evidence, package, release):
    if evidence is None:
        records = {}
    else:
        if not isinstance(evidence, dict) or set(evidence) != {"package_name", "release_reference", "checks"}:
            raise ValueError("Evidence requires package_name, release_reference and checks")
        if not release or evidence["package_name"] != package or evidence["release_reference"] != release:
            raise ValueError("Evidence must match the selected package and explicit release_reference")
        records = evidence["checks"]
        if not isinstance(records, dict) or set(records) - set(CHECKS):
            raise ValueError("Unknown evidence check ID")
    output = []
    for key, description in CHECKS.items():
        entry = records.get(key, {"status": "pending", "reference": "", "checked_at": None, "note": ""})
        if not isinstance(entry, dict) or set(entry) - {"status", "reference", "checked_at", "note"}:
            raise ValueError(f"{key}: invalid evidence record")
        status = entry.get("status")
        if status not in ("pending", "passed", "failed", "not-applicable"):
            raise ValueError(f"{key}: use pending/passed/failed/not-applicable")
        reference, note, checked = entry.get("reference", ""), entry.get("note", ""), entry.get("checked_at")
        if not isinstance(reference, str) or not isinstance(note, str):
            raise ValueError(f"{key}: reference and note must be strings")
        if checked is not None:
            if not isinstance(checked, str):
                raise ValueError(f"{key}: checked_at must be a timestamp or null")
            stamp = datetime.fromisoformat(checked)
            if stamp.tzinfo is None or stamp.utcoffset() is None:
                raise ValueError(f"{key}: checked_at needs a timezone")
        if status == "passed":
            if not reference.strip() or not isinstance(checked, str):
                raise ValueError(f"{key}: passed requires evidence reference and timestamp")
        if status in {"failed", "not-applicable"} and not note.strip():
            raise ValueError(f"{key}: explain the failure or non-applicability")
        output.append({"id": key, "description": description, **entry, "source": "provided-evidence" if key in records else "not-provided"})
    return output


def report(project, listings=None, assets=None, evidence=None, release=None):
    if not isinstance(project, dict):
        raise ValueError("Project brief must be an object")
    package = project.get("package_name")
    release = release if release is not None else project.get("release_reference")
    identity(package, release)
    codes, countries, features = (project.get(key, []) for key in ("locales", "countries", "features"))
    for values, pattern, name in ((codes, LANGUAGE_TAG, "locales"), (countries, re.compile("[A-Z]{2}"), "countries")):
        if not isinstance(values, list) or any(not isinstance(v, str) or not pattern.fullmatch(v) for v in values) or len(set(values)) != len(values):
            raise ValueError(f"{name}: use distinct valid codes")
    if not isinstance(features, list) or any(not isinstance(v, str) or not v.strip() for v in features):
        raise ValueError("features must contain non-empty text")
    monetization = project.get("monetization", "")
    if not isinstance(monetization, str):
        raise ValueError("monetization must be text")
    if listings is not None and not isinstance(listings, dict):
        raise ValueError("Listings must be a locale map")
    listing_errors = validate_listings(listings) if listings is not None else []
    asset_rows, seen_files = [], set()
    if assets is not None:
        if not isinstance(assets, dict) or not isinstance(assets.get("assets"), list):
            raise ValueError("Assets require the studio JSON manifest with an assets array")
        for row in assets["assets"]:
            if not isinstance(row, dict) or row.get("kind") not in ("screenshot", "feature-graphic"):
                raise ValueError("Invalid asset kind")
            code, filename = row.get("locale"), row.get("file")
            if not isinstance(code, str) or not LANGUAGE_TAG.fullmatch(code) or not isinstance(filename, str) or not filename.strip() or filename in seen_files:
                raise ValueError("Assets need valid locales and distinct filenames")
            if not isinstance(row.get("profileId"), str) or not row["profileId"].strip() or row.get("device_type") not in ("phone", "tablet-7", "tablet-10", "all"):
                raise ValueError("Assets need device_type and profileId")
            if row["kind"] == "feature-graphic" and (row["device_type"] != "all" or row["profileId"] != "feature-graphic") or row["kind"] == "screenshot" and (row["device_type"] == "all" or row["profileId"] == "feature-graphic"):
                raise ValueError("Asset kind must match its device/profile")
            if row.get("alt_text") is not None and not isinstance(row["alt_text"], str):
                raise ValueError("alt_text must be text or null")
            if "source_fallback" in row and type(row["source_fallback"]) is not bool:
                raise ValueError("source_fallback must be boolean")
            seen_files.add(filename); asset_rows.append(row)
    matrix = []
    for code in codes:
        entry = listings.get(code) if listings is not None else None
        rows = [row for row in asset_rows if row["locale"] == code]
        sets = Counter((row["device_type"], row["profileId"]) for row in rows if row["kind"] == "screenshot")
        matrix.append({"locale": code, "listing": "missing" if entry is None else "invalid" if validate_listing(entry) else "validated-structure",
                       "screenshot_sets": [{"device": device, "profile": profile, "count": count} for (device, profile), count in sorted(sets.items())],
                       "feature_graphics": sum(row["kind"] == "feature-graphic" for row in rows),
                       "default_ui_sources": sum(row.get("source_fallback") is True for row in rows),
                       "alt_text_missing": sum(not str(row.get("alt_text") or "").strip() for row in rows),
                       "visual_review": "not-verified-by-tool"})
    manual = evidence_rows(evidence, package, release)
    local = [{"id": "market_scope", "status": "passed" if codes and countries else "pending"},
             {"id": "product_facts_present", "status": "passed" if features and monetization.strip() else "pending"},
             {"id": "release_scope", "status": "passed" if release else "pending"},
             {"id": "listing_structure", "status": "pending" if listings is None else "failed" if listing_errors else "passed", "errors": listing_errors},
             {"id": "target_locale_coverage", "status": "pending" if listings is None else "failed" if any(row["listing"] == "missing" for row in matrix) else "passed" if codes else "pending"}]
    counts = Counter(row["status"] for row in manual)
    complete = all(row["status"] == "passed" for row in local) and all(row["status"] in {"passed", "not-applicable"} for row in manual)
    return {"state": "CHECKLIST_RECORDED" if complete else "INCOMPLETE", "package_name": package, "release_reference": release,
            "countries": countries, "locale_matrix": matrix, "extra_listing_locales": sorted(set(listings or {}) - set(codes)),
            "extra_asset_locales": sorted({row["locale"] for row in asset_rows} - set(codes)),
            "local_checks": local, "evidence_checks": manual, "evidence_status_counts": dict(counts),
            "limitations": ["Evidence statuses are provided records; the tool does not verify the cited documents or account state.",
                            "Locale/country syntax does not prove Play support, market eligibility or translation quality.",
                            "Asset profiles are alternative sets; counts are not summed as one upload sequence. Image bytes are not validated here.",
                            "CHECKLIST_RECORDED is not policy compliance, submission, approval or permission to publish."]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    t = sub.add_parser("template"); t.add_argument("--package", required=True); t.add_argument("--release-reference", required=True)
    r = sub.add_parser("report"); r.add_argument("--project", required=True)
    for name in ("listings", "assets", "evidence", "release-reference"):
        r.add_argument("--" + name)
    r.add_argument("--require-complete", action="store_true", help="Exit 1 for an incomplete recorded checklist")
    for child in sub.choices.values(): child.add_argument("--output", required=True, help="New JSON file; never overwritten")
    args = parser.parse_args(argv)
    try:
        output = Path(args.output)
        if output.exists() or output.is_symlink(): raise ValueError("Output already exists")
        def read(path): return json.loads(Path(path).read_text(encoding="utf-8")) if path else None
        result = template(args.package, args.release_reference) if args.command == "template" else report(read(args.project), read(args.listings), read(args.assets), read(args.evidence), args.release_reference)
        serialized = json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("x", encoding="utf-8") as handle:
            handle.write(serialized)
        print(json.dumps({"output": str(output), "state": result.get("state", "EVIDENCE_TEMPLATE")}))
        return 1 if args.command == "report" and args.require_complete and result["state"] != "CHECKLIST_RECORDED" else 0
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print(f"Input/output error: {exc}", file=sys.stderr); return 2


if __name__ == "__main__":
    raise SystemExit(main())
