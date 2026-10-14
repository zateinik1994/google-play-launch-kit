"""Analysis of user-supplied normalized CSV exports. No scraping or invented data."""
import csv
import math
import re
from collections import Counter, defaultdict
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
import unicodedata


def read_csv(path, required):
    with Path(path).open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or len(reader.fieldnames) != len(set(reader.fieldnames)):
            raise ValueError("CSV needs unique column names")
        missing = set(required) - set(reader.fieldnames)
        if missing:
            raise ValueError("CSV missing columns: " + ", ".join(sorted(missing)))
        rows = list(reader)
        if any(None in row or any(value is None for value in row.values()) for row in rows):
            raise ValueError("CSV row length differs from header")
        return rows


def finite_float(value, field):
    result = float(value)
    if not math.isfinite(result) or value != 0 and result == 0:
        raise ValueError(f"{field}: outside the finite JSON number range")
    return result


def number(value, field, integer=False):
    try:
        result = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError(f"{field}: expected a number") from exc
    if not result.is_finite() or result < 0 or (integer and result != result.to_integral_value()):
        raise ValueError(f"{field}: expected a finite non-negative {'integer' if integer else 'number'}")
    if integer and result > 2**63 - 1:
        raise ValueError(f"{field}: expected a nonnegative 64-bit integer")
    if not integer:
        finite_float(result, field)
    return int(result) if integer else result


def keywords(rows):
    output, seen = [], set()
    for row in rows:
        query, locale, country = (row[k].strip() for k in ("query", "locale", "country"))
        source = row["source"].strip()
        if not all((query, locale, country, source)):
            raise ValueError("Keyword query, locale, country and source must be non-empty")
        key = (locale, country, query.casefold(), source)
        if key in seen:
            raise ValueError(f"Duplicate keyword observation: {key}")
        seen.add(key)
        volume = None if not row.get("volume", "").strip() else finite_float(number(row["volume"], "volume"), "volume")
        relevance = number(row.get("relevance", ""), "relevance", integer=True)
        if relevance > 3:
            raise ValueError("relevance: use 0 (unrelated) to 3 (core feature)")
        if volume is not None and not row.get("volume_source", "").strip():
            raise ValueError("volume_source required for measured volume")
        output.append({"query": query, "locale": locale, "country": country, "source": source,
                       "relevance": relevance, "decision": "excluded" if relevance == 0 else "candidate", "volume": volume,
                       "volume_source": row.get("volume_source", "") or None,
                       "note": row.get("note", "")})
    # Do not compare unlike volume providers or turn missing volumes into zero.
    return {"method": "Sort by user-assigned feature relevance, then alphabetically; relevance 0 is retained for audit as excluded; volume is not a Play popularity score.",
            "keywords": sorted(output, key=lambda r: (-r["relevance"], r["locale"], r["country"], r["query"].casefold()))}


RANK_FIELDS = ("observed_at", "package_name", "locale", "country", "query", "rank", "depth", "source")


def rank_index(rows):
    output = {}
    for row in rows:
        if not all(row.get(k, "").strip() for k in RANK_FIELDS if k != "rank"):
            raise ValueError("Rank snapshot needs timestamp, package, locale, country, query, depth and source")
        try:
            observed = datetime.fromisoformat(row["observed_at"].replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("observed_at: expected an ISO-8601 timestamp with timezone") from exc
        if observed.tzinfo is None:
            raise ValueError("observed_at: include timezone")
        depth = number(row["depth"], "depth", integer=True)
        rank = None if not row["rank"].strip() else number(row["rank"], "rank", integer=True)
        if depth < 1 or (rank is not None and not 1 <= rank <= depth):
            raise ValueError("rank must be within 1..depth; blank means not found within depth")
        # Source is part of measurement context; unlike observations cannot be compared.
        key = tuple(row[k].strip() for k in ("package_name", "locale", "country", "query", "source"))
        if key in output:
            raise ValueError(f"Duplicate rank snapshot context: {key}")
        output[key] = {"rank": rank, "depth": depth, "observed_at": row["observed_at"], "timestamp": observed}
    return output


def compare_ranks(before, after):
    old, new = rank_index(before), rank_index(after)
    result = []
    for key in sorted(old.keys() | new.keys()):
        a, b = old.get(key), new.get(key)
        movement = None
        if not a or not b:
            status = "missing_observation"
        elif b["timestamp"] <= a["timestamp"]:
            raise ValueError(f"After timestamp must be later than before: {key}")
        elif a["depth"] != b["depth"]:
            status = "different_depth"
        elif a["rank"] is None and b["rank"] is None:
            status = "outside_observed_depth"
        elif a["rank"] is None:
            status = "entered_observed_depth"
        elif b["rank"] is None:
            status = "left_observed_depth"
        else:
            movement = a["rank"] - b["rank"]
            status = "up" if movement > 0 else "down" if movement < 0 else "unchanged"
        result.append({**dict(zip(("package_name", "locale", "country", "query", "source"), key)),
                       "before": {k: v for k, v in a.items() if k != "timestamp"} if a else None,
                       "after": {k: v for k, v in b.items() if k != "timestamp"} if b else None,
                       "status": status, "positions_gained": movement})
    return result


TOPICS = {
    "stability": ("crash", "freeze", "bug", "вылет", "завис", "ошибк"),
    "billing": ("payment", "charged", "refund", "subscription", "оплат", "подписк", "списал"),
    "usability": ("confusing", "interface", "navigation", "неудоб", "интерфейс"),
    "performance": ("slow", "battery", "lag", "медлен", "батаре"),
}
FEATURE_REQUEST_CUES = ("please add", "wish", "would be nice", "feature request", "missing",
                        "добавьте", "хотелось бы", "не хватает", "пожалуйста добавьте")
REVIEW_STOP = set("a an and are as at be by for from in is it of on or the to with your you app apps this that can и в во на для от по с со к о об а но или это как что мы вы ваш ваша приложение приложения".split())


def reviews(rows):
    ratings, topics, low = Counter(), Counter(), []
    phrases, issue_evidence, feature_requests = defaultdict(list), [], []
    seen = set()
    for row in rows:
        review_id = row["review_id"].strip()
        if not review_id or review_id in seen:
            raise ValueError("Review IDs must be non-empty and unique")
        seen.add(review_id)
        rating = number(row["rating"], "rating", integer=True)
        if not 1 <= rating <= 5:
            raise ValueError("rating must be 1..5")
        text = row["text"].casefold()
        labels = [name for name, stems in TOPICS.items() if any(stem in text for stem in stems)]
        words = re.findall(r"[^\W_]+", text, re.UNICODE)
        observed_phrases = set()
        for size in (2, 3):
            for i in range(len(words) - size + 1):
                window = words[i:i+size]
                if window[0] not in REVIEW_STOP and window[-1] not in REVIEW_STOP:
                    observed_phrases.add(" ".join(window))
        for phrase in observed_phrases:
            phrases[phrase].append(review_id)
        # Exact token phrases produce inspectable cues, not confirmed intent.
        cues = []
        for cue in FEATURE_REQUEST_CUES:
            parts = cue.split()
            if any(words[i:i+len(parts)] == parts for i in range(len(words)-len(parts)+1)):
                cues.append(cue)
        evidence = {"review_id": review_id, "rating": rating, "topics": labels, "text": row["text"],
                    "created_at": row.get("created_at") or None, "app_version": row.get("app_version") or None}
        if labels:
            issue_evidence.append(evidence)
        if cues:
            feature_requests.append({**evidence, "matched_cues": cues, "needs_human_review": True})
        ratings[rating] += 1
        topics.update(labels)
        if rating <= 2:
            low.append(evidence)
    n = len(rows)
    return {"count": n, "average_rating": round(sum(k*v for k, v in ratings.items())/n, 3) if n else None,
            "ratings": {str(k): ratings[k] for k in range(1, 6)}, "topic_counts": dict(topics),
            "low_rating_reviews": low,
            "topic_evidence": issue_evidence, "feature_request_cues": feature_requests,
            "recurring_phrases": [{"phrase": phrase, "review_documents": len(ids), "review_ids": ids}
                                  for phrase, ids in sorted(phrases.items(), key=lambda item: (-len(item[1]), item[0])) if len(ids) >= 2][:30],
            "method": "English/Russian topic substring dictionary and feature-request token cues need human review; recurring 2–3 token phrases count distinct reviews in this sample without joining across removed words; no sentiment, severity or population inference."}


ADS_FIELDS = ("date", "campaign_id", "currency", "cost", "impressions", "clicks", "conversions", "conversion_action")


def ads_report(rows):
    groups, seen = defaultdict(lambda: {"cost": Decimal(0), "impressions": 0, "clicks": 0, "conversions": Decimal(0), "dates": []}), set()
    for row in rows:
        # Require campaign/day export with one explicitly selected conversion action.
        key = tuple(row[k].strip() for k in ("campaign_id", "currency", "conversion_action"))
        if not all(key):
            raise ValueError("campaign_id, currency and conversion_action required")
        try:
            date = datetime.strptime(row["date"], "%Y-%m-%d").date()
            if row["date"] != date.isoformat():
                raise ValueError("Non-canonical date")
        except ValueError as exc:
            raise ValueError("date: expected YYYY-MM-DD") from exc
        unique = (key[0], row["date"])
        if unique in seen:
            raise ValueError("Use one campaign/day row and one selected conversion action; duplicate delivery metrics cannot be summed")
        seen.add(unique)
        if not re.fullmatch(r"[A-Z]{3}", key[1]):
            raise ValueError("currency: use a three-letter currency code")
        values = {k: number(row[k], k, integer=k in {"impressions", "clicks"}) for k in ("cost", "impressions", "clicks", "conversions")}
        if values["clicks"] > values["impressions"]:
            raise ValueError("clicks cannot exceed impressions")
        group = groups[key]
        for field, value in values.items():
            group[field] += value
        group["dates"].append(date.isoformat())
    result = []
    for (campaign, currency, action), group in sorted(groups.items()):
        cost, clicks, impressions, conversions = (group[k] for k in ("cost", "clicks", "impressions", "conversions"))
        result.append({"campaign_id": campaign, "currency": currency, "conversion_action": action,
                       "from": min(group["dates"]), "to": max(group["dates"]), "days_observed": len(group["dates"]),
                       "cost": finite_float(cost, "total cost"), "impressions": number(impressions, "total impressions", integer=True), "clicks": number(clicks, "total clicks", integer=True), "conversions": finite_float(conversions, "total conversions"),
                       "ctr": round(clicks/impressions, 6) if impressions else None,
                       "cpc": round(finite_float(cost/clicks, "cpc"), 4) if clicks else None,
                       "cost_per_selected_conversion": round(finite_float(cost/conversions, "cost per selected conversion"), 4) if conversions else None})
    return {"campaigns": result, "note": "Conversions can be fractional. Costs are in account currency, not micros. Attribution lag and conversion definitions need review; this tool never changes bids."}


def campaign_plan(config):
    if not isinstance(config, dict):
        raise ValueError("Campaign config must be a JSON object")
    required = {"package_name", "countries", "languages", "currency", "daily_budget", "target_cpa", "conversion_action", "headlines", "descriptions"}
    missing = required - config.keys()
    if missing:
        raise ValueError("Campaign config missing: " + ", ".join(sorted(missing)))
    if not isinstance(config["package_name"], str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z][A-Za-z0-9_]*)+", config["package_name"]):
        raise ValueError("package_name: expected an Android application ID")
    for field in ("countries", "languages", "headlines", "descriptions"):
        if not isinstance(config[field], list) or not config[field] or not all(isinstance(v, str) and v.strip() for v in config[field]):
            raise ValueError(f"{field}: non-empty list of strings required")
    if any(not re.fullmatch(r"[A-Z]{2}", v) for v in config["countries"]):
        raise ValueError("countries: use two-letter country codes")
    if not isinstance(config["currency"], str) or not re.fullmatch(r"[A-Z]{3}", config["currency"]):
        raise ValueError("currency: use a three-letter account currency code")
    for field, maximum in (("headlines", 30), ("descriptions", 90)):
        if len(config[field]) > 5 or any(sum(2 if unicodedata.east_asian_width(c) in {"W", "F"} else 1 for c in v) > maximum for v in config[field]):
            raise ValueError(f"{field}: at most 5 assets of at most {maximum} characters")
    if not isinstance(config["conversion_action"], str) or not config["conversion_action"].strip():
        raise ValueError("conversion_action: specify the one event to optimize for")
    budget, target = (number(config[k], k) for k in ("daily_budget", "target_cpa"))
    if budget <= 0 or target <= 0:
        raise ValueError("daily_budget and target_cpa must be positive")
    unsupported = {"keywords", "keyword_bids", "match_type", "search_popularity"} & config.keys()
    if unsupported:
        raise ValueError("App campaigns are not ASA keyword campaigns: unsupported " + ", ".join(sorted(unsupported)))
    warnings = ["Check conversion tracking, account eligibility, asset rights, geo/language IDs and current bidding requirements before implementation."]
    if budget < 10 * target:
        warnings.append("Budget is below 10x target CPA; review Google's current guidance and expected event volume. This is a recommendation, not an API validity rule.")
    return {"state": "DRAFT_ONLY", "campaign_type": "App campaign for in-app actions (target CPA)",
            "proposed_status": "PAUSED", "config": config, "warnings": warnings,
            "execution": "This brief does not call an API. Convert it to google_ads.py config with resource IDs and micros, then plan/validate. Authorized API creation keeps all serving resources PAUSED."}
