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
    return re.findall(r"[^\W\d_]+", str(text).casefold(), re.UNICODE)


def discover(profiles, seeds=(), limit=50):
    if not isinstance(profiles, list) or not profiles or not 1 <= limit <= 500:
        raise ValueError("Provide non-empty normalized profiles and limit 1..500")
    counts, packages = Counter(), set()
    for profile in profiles:
        if not isinstance(profile, dict) or not profile.get("package_name") or profile["package_name"] in packages:
            raise ValueError("Profiles need unique package_name")
        packages.add(profile["package_name"])
        words = tokens(" ".join(str(profile.get(k) or "") for k in ("title", "shortDescription", "fullDescription")))
        phrases = set()
        for size in (1, 2, 3):
            for i in range(len(words) - size + 1):
                window = words[i:i+size]
                if window[0] in STOP or window[-1] in STOP or all(w in STOP or len(w) <= 2 for w in window):
                    continue
                phrases.add(" ".join(window))
        counts.update(phrases)
    seed_set = {" ".join(tokens(seed)) for seed in seeds if tokens(seed)}
    choices = sorted(set(counts) | seed_set, key=lambda q: (q not in seed_set, -counts[q], q))[:limit]
    return {"method": "document-frequency n-grams + supplied seed phrases; no query-volume or ranking inference",
            "profiles_observed": len(packages), "keywords": [{"query": q, "competitor_documents": counts[q],
            "seed": q in seed_set, "volume": None, "needs_product_fit_review": True,
            "source": "provided competitor listing texts"} for q in choices]}


def contains(text, phrase):
    words, query = tokens(text), tokens(phrase)
    return bool(query) and any(words[i:i+len(query)] == query for i in range(len(words)-len(query)+1))


def gaps(bank, listings):
    from shared.metadata import validate_listings
    errors = validate_listings(listings)
    if errors:
        raise ValueError("Invalid listings: " + "; ".join(errors))
    rows = bank.get("keywords") if isinstance(bank, dict) else bank
    if not isinstance(rows, list):
        raise ValueError("Keyword bank must contain keywords array")
    output = []
    for locale, listing in listings.items():
        seen = set()
        for row in rows:
            if not isinstance(row, dict) or not isinstance(row.get("query"), str) or not tokens(row["query"]):
                raise ValueError("Each keyword requires query text")
            if row.get("locale") and row["locale"] != locale:
                continue
            query = " ".join(tokens(row["query"]))
            if query in seen:
                continue
            seen.add(query)
            coverage = {field: contains(listing[field], query) for field in ("title", "shortDescription", "fullDescription")}
            excluded = row.get("relevance") == 0 or row.get("decision") == "excluded"
            output.append({"locale": locale, "query": row["query"], "coverage": coverage,
                           "status": "excluded" if excluded else "present" if any(coverage.values()) else "text_gap",
                           "needs_product_fit_review": row.get("needs_product_fit_review", False)})
    return {"method": "casefolded token phrase coverage, no stemming or official ASO score; a text gap is not a search-rank gap", "rows": output}


def experiment(baseline_rate, mde_relative, confidence, power, daily_visitors, variants=1, min_days=7, traffic_fraction=1):
    values = (baseline_rate, mde_relative, confidence, power, daily_visitors, traffic_fraction)
    if not all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) for v in values):
        raise ValueError("Experiment inputs must be finite numbers")
    if not 0 < baseline_rate < 1 or not 0 < mde_relative or not .5 < confidence < 1 or not .5 < power < 1 or daily_visitors <= 0 or not 0 < traffic_fraction <= 1:
        raise ValueError("Invalid rate/MDE/confidence/power/traffic")
    if variants not in {1, 2} or not isinstance(min_days, int) or min_days < 1:
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
        if output.exists():
            raise ValueError("Output already exists")
        if args.command == "discover":
            profiles = json.loads(Path(args.profiles).read_text())
            result = discover(profiles["data"] if isinstance(profiles, dict) else profiles, args.seed, args.limit)
        elif args.command == "gaps":
            result = gaps(json.loads(Path(args.keywords).read_text()), json.loads(Path(args.listings).read_text()))
        else:
            result = experiment(args.baseline_rate,args.mde_relative,args.confidence,args.power,args.daily_visitors,args.variants,args.min_days,args.traffic_fraction)
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("x", encoding="utf-8") as handle:
            json.dump(result, handle, ensure_ascii=False, indent=2, allow_nan=False)
            handle.write("\n")
        print(json.dumps({"output": str(output)}))
        return 0
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print(f"Input/output error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
