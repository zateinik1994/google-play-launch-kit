#!/usr/bin/env python3
"""Deterministic keyword discovery, listing coverage and experiment planning."""
import argparse
import json
import math
import re
import sys
from collections import Counter
from pathlib import Path
from statistics import NormalDist

STOP = set("a an and are as at be by for from in is it of on or the to with your you app apps this that can daily how our и в во на для от по с со к о об а но или это как что мы вы ваш ваша приложение приложения".split())


def tokens(text):
    # Numbers change meaning: 2FA/3FA and 7-day/30-day must not match.
    return re.findall(r"[^\W_]+", str(text).casefold(), re.UNICODE)


TEXT_FIELDS = ("title", "shortDescription", "fullDescription")


def checked_profiles(profiles, *, require_text=False):
    if not isinstance(profiles, list) or not profiles:
        raise ValueError("Provide non-empty normalized competitor profiles")
    packages = set()
    for profile in profiles:
        package = profile.get("package_name") if isinstance(profile, dict) else None
        if not isinstance(package, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z][A-Za-z0-9_]*)+", package) or package in packages:
            raise ValueError("Profiles need unique Android package_name")
        packages.add(package)
        if any(profile.get(field) is not None and not isinstance(profile[field], str) for field in TEXT_FIELDS):
            raise ValueError("Profile listing fields must be strings or null")
        if require_text and not any(profile.get(field, "") and profile[field].strip() for field in TEXT_FIELDS):
            raise ValueError("Discovery needs observed listing text, not an empty profile")
    return profiles


def checked_context(context):
    if not isinstance(context, dict) or not isinstance(context.get("locale"), str) or not re.fullmatch(r"[a-z]{2,3}(?:-[A-Za-z0-9]{2,8})*", context["locale"]) or not isinstance(context.get("country"), str) or not re.fullmatch(r"[A-Z]{2}", context["country"]):
        raise ValueError("Profiles must identify locale and country")
    return context


def discover(profiles, seeds=(), limit=50, context=None):
    if not isinstance(profiles, list) or not profiles or type(limit) is not int or not 1 <= limit <= 500:
        raise ValueError("Provide non-empty normalized profiles and limit 1..500")
    checked_profiles(profiles, require_text=True)
    if context is not None:
        checked_context(context)
    if not isinstance(seeds, (list, tuple)) or any(not isinstance(seed, str) for seed in seeds):
        raise ValueError("Seed phrases must be text")
    counts = Counter()
    for profile in profiles:
        phrases = set()
        # Field boundaries are not observed phrases: "Tracker" + "Cloud Sync"
        # must not produce a competitor occurrence of "tracker cloud".
        for field in TEXT_FIELDS:
            words = tokens(profile.get(field) or "")
            for size in (1, 2, 3):
                for i in range(len(words) - size + 1):
                    window = words[i:i+size]
                    if window[0] in STOP or window[-1] in STOP or all(w in STOP or len(w) <= 2 or w.isdigit() for w in window):
                        continue
                    phrases.add(" ".join(window))
        counts.update(phrases)
    seed_set = {" ".join(tokens(seed)) for seed in seeds if tokens(seed)}
    choices = sorted(set(counts) | seed_set, key=lambda q: (q not in seed_set, -counts[q], q))[:limit]
    return {"method": "document-frequency n-grams + supplied seed phrases; no query-volume or ranking inference",
            "profiles_observed": len(profiles), "metadata": context, "keywords": [{"query": q, "competitor_documents": counts[q],
            **({"locale": context["locale"], "country": context["country"]} if context is not None else {}),
            "seed": q in seed_set, "volume": None, "needs_product_fit_review": True,
            "source": "provided competitor listing texts" if counts[q] else "supplied seed phrase"} for q in choices]}


def contains(text, phrase):
    words, query = tokens(text), tokens(phrase)
    return bool(query) and any(words[i:i+len(query)] == query for i in range(len(words)-len(query)+1))


def gaps(bank, listings, profiles=None):
    try:
        from .metadata import validate_listings
    except ImportError:
        from metadata import validate_listings
    errors = validate_listings(listings)
    if errors:
        raise ValueError("Invalid listings: " + "; ".join(errors))
    rows = bank.get("keywords") if isinstance(bank, dict) else bank
    if not isinstance(rows, list):
        raise ValueError("Keyword bank must contain keywords array")
    keyword_metadata = bank.get("metadata") if isinstance(bank, dict) else None
    if keyword_metadata is not None and not isinstance(keyword_metadata, dict):
        raise ValueError("Keyword metadata must be an object or null")
    competitor_context = None
    competitors = []
    if profiles is not None:
        if not isinstance(profiles, dict) or not isinstance(profiles.get("metadata"), dict):
            raise ValueError("Competitor comparison needs normalized profiles with metadata.locale/country")
        competitor_context = checked_context(profiles["metadata"])
        competitors = checked_profiles(profiles.get("data"))
    output = []
    for locale, listing in listings.items():
        grouped = {}
        for row in rows:
            if not isinstance(row, dict) or not isinstance(row.get("query"), str) or not tokens(row["query"]):
                raise ValueError("Each keyword requires query text")
            if row.get("locale") and row["locale"] != locale:
                continue
            if "relevance" in row and (type(row["relevance"]) is not int or not 0 <= row["relevance"] <= 3):
                raise ValueError("relevance must be 0..3 when provided")
            if row.get("country") is not None and (not isinstance(row["country"], str) or not re.fullmatch(r"[A-Z]{2}", row["country"])):
                raise ValueError("Keyword country must be a two-letter code when provided")
            query = " ".join(tokens(row["query"]))
            grouped.setdefault((query, row.get("country")), []).append(row)
        for (query, country), observations in grouped.items():
            coverage = {field: contains(listing[field], query) for field in TEXT_FIELDS}
            exclusions = {row.get("relevance") == 0 or row.get("decision") == "excluded" for row in observations}
            conflict = len(exclusions) > 1
            result = {"locale": locale, "country": country, "query": observations[0]["query"], "coverage": coverage,
                      "status": "decision_conflict" if conflict else "excluded" if True in exclusions else "present" if any(coverage.values()) else "text_gap",
                      "needs_product_fit_review": conflict or any(row.get("needs_product_fit_review", False) for row in observations),
                      "observations": [{key: row[key] for key in ("source", "country", "relevance", "decision") if key in row} for row in observations]}
            if competitor_context is not None:
                applies = locale == competitor_context["locale"] and (country is None or country == competitor_context["country"])
                matches = []
                if applies:
                    for profile in competitors:
                        fields = {field: contains(profile[field], query) if profile.get(field) is not None else None for field in TEXT_FIELDS}
                        matches.append({"package_name": profile["package_name"], "coverage": fields,
                                        "contains_phrase": True if any(v is True for v in fields.values()) else False if all(v is False for v in fields.values()) else None})
                result["competitors"] = {"context_applies": applies, "context": competitor_context,
                    "documents_observed": len(matches) if applies else None,
                    "documents_with_phrase": sum(m["contains_phrase"] is True for m in matches) if applies else None,
                    "documents_without_phrase": sum(m["contains_phrase"] is False for m in matches) if applies else None,
                    "documents_unverified": sum(m["contains_phrase"] is None for m in matches) if applies else None,
                    "profiles": matches}
            output.append(result)
    return {"method": "casefolded token phrase coverage, no stemming or official ASO score; a text gap is not a search-rank gap",
            "keyword_metadata": keyword_metadata, "rows": output}


def experiment(baseline_rate, mde_relative, confidence, power, daily_visitors, variants=1, min_days=7, traffic_fraction=1):
    values = (baseline_rate, mde_relative, confidence, power, daily_visitors, traffic_fraction)
    if not all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) for v in values):
        raise ValueError("Experiment inputs must be finite numbers")
    if not 0 < baseline_rate < 1 or not 0 < mde_relative or not .5 < confidence < 1 or not .5 < power < 1 or daily_visitors <= 0 or not 0 < traffic_fraction <= 1:
        raise ValueError("Invalid rate/MDE/confidence/power/traffic")
    if type(variants) is not int or variants not in {1, 2} or type(min_days) is not int or min_days < 1:
        raise ValueError("Use 1–2 variants and positive minimum days")
    p0, p1 = baseline_rate, baseline_rate * (1 + mde_relative)
    if p1 >= 1:
        raise ValueError("Baseline plus detectable uplift must remain below 1")
    average = (p0 + p1)/2
    normal = NormalDist()
    # Bonferroni-adjusted two-sided comparisons against the common control.
    za = normal.inv_cdf(1 - (1-confidence)/(2*variants))
    zb = normal.inv_cdf(power)
    delta_squared = (p1-p0)**2
    effective_traffic = daily_visitors * traffic_fraction
    if delta_squared <= 0 or not math.isfinite(delta_squared) or effective_traffic <= 0 or not math.isfinite(effective_traffic):
        raise ValueError("Effect size or effective traffic is outside numeric precision")
    sample = (za*math.sqrt(2*average*(1-average)) + zb*math.sqrt(p0*(1-p0)+p1*(1-p1)))**2 / delta_squared
    if not math.isfinite(sample) or not math.isfinite(sample*(variants+1)):
        raise ValueError("Derived sample size exceeds finite numeric bounds")
    per_arm = math.ceil(sample)
    total = per_arm * (variants + 1)
    duration = total/effective_traffic
    if not math.isfinite(duration):
        raise ValueError("Derived duration exceeds finite numeric bounds")
    days = max(min_days, math.ceil(duration))
    return {"state": "PLANNING_ESTIMATE", "baseline_rate": p0, "alternative_rate": p1,
            "confidence": confidence, "power": power, "variants": variants, "visitors_per_arm": per_arm,
            "total_visitors": total, "estimated_days": days, "minimum_days": min_days,
            "method": "normal approximation for independent two-proportion comparison; equal allocation; Bonferroni across variants",
            "assumptions": ["Use a compatible metric and eligible unique visitors, not impressions or acquisitions of a different report.",
                            "No repeated peeking decision; choose hypothesis/readout before launch.",
                            "This estimates traffic need; Play Console uses its own engine and actual settings, no experiment is created."]}


def main(argv=None):
    if __package__ in (None, ""):
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    d = sub.add_parser("discover")
    d.add_argument("--profiles", required=True)
    d.add_argument("--seed", action="append", default=[])
    d.add_argument("--limit", type=int, default=50)
    g = sub.add_parser("gaps")
    g.add_argument("--keywords", required=True)
    g.add_argument("--listings", required=True)
    g.add_argument("--profiles", help="Optional normalized competitor envelope with locale/country metadata")
    e = sub.add_parser("experiment")
    e.add_argument("--baseline-rate", type=float, required=True)
    e.add_argument("--mde-relative", type=float, required=True)
    e.add_argument("--confidence", type=float, default=.95)
    e.add_argument("--power", type=float, default=.8)
    e.add_argument("--daily-visitors", type=float, required=True)
    e.add_argument("--variants", type=int, default=1)
    e.add_argument("--min-days", type=int, default=7)
    e.add_argument("--traffic-fraction", type=float, default=1)
    for child in sub.choices.values():
        child.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    try:
        output = Path(args.output)
        if output.exists() or output.is_symlink():
            raise ValueError("Output already exists")
        if args.command == "discover":
            profiles = json.loads(Path(args.profiles).read_text())
            result = discover(profiles["data"] if isinstance(profiles, dict) else profiles, args.seed, args.limit,
                              profiles.get("metadata") if isinstance(profiles, dict) else None)
        elif args.command == "gaps":
            result = gaps(json.loads(Path(args.keywords).read_text()), json.loads(Path(args.listings).read_text()),
                          json.loads(Path(args.profiles).read_text()) if args.profiles else None)
        else:
            result = experiment(args.baseline_rate,args.mde_relative,args.confidence,args.power,args.daily_visitors,args.variants,args.min_days,args.traffic_fraction)
        serialized = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("x", encoding="utf-8") as handle:
            handle.write(serialized)
        print(json.dumps({"output": str(output)}))
        return 0
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print(f"Input/output error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
