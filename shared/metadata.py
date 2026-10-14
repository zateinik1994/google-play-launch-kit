"""Validate the Google Play Listing JSON contract without credentials."""
import re
from urllib.parse import urlparse

LIMITS = {"title": 30, "shortDescription": 80, "fullDescription": 4000}
LANGUAGE_TAG = re.compile(r"^[a-z]{2,3}(?:-[A-Za-z0-9]{2,8})*$")


def validate_listing(listing):
    errors = []
    if not isinstance(listing, dict):
        return ["listing must be an object"]
    allowed = set(LIMITS) | {"video", "language"}
    for key in sorted(set(listing) - allowed):
        errors.append(f"unsupported listing field: {key}")
    for field, maximum in LIMITS.items():
        value = listing.get(field)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{field}: non-empty text required")
        elif len(value) > maximum:
            errors.append(f"{field}: {len(value)} characters exceeds {maximum}")
        elif any(ord(c) < 32 and c not in "\n\r\t" for c in value):
            errors.append(f"{field}: contains control characters")
    if "video" in listing:
        value = listing["video"]
        if not isinstance(value, str):
            errors.append("video: must be a string (empty string removes a video)")
        elif value:
            url = urlparse(value)
            if url.scheme != "https" or url.hostname not in {"www.youtube.com", "youtube.com", "youtu.be"}:
                errors.append("video: use an HTTPS YouTube URL")
    return errors


def validate_listings(listings):
    if not isinstance(listings, dict) or not listings:
        return ["listings must be a non-empty object keyed by locale"]
    errors = []
    for locale, listing in listings.items():
        if not isinstance(locale, str) or not LANGUAGE_TAG.fullmatch(locale):
            errors.append(f"{locale}: expected a BCP-47 language tag, e.g. en-US")
        errors.extend(f"{locale}: {e}" for e in validate_listing(listing))
        if isinstance(listing, dict) and "language" in listing and listing["language"] != locale:
            errors.append(f"{locale}: language field differs from locale key")
    return errors


def audit_listings(listings):
    """Editorial suggestions, not a prediction or automatic policy verdict."""
    report = []
    for locale, listing in listings.items():
        warnings = []
        title = listing["title"]
        if re.search(r"(?i)(#\s*1|\b(best|free|top|sale)\b|№\s*1)", title):
            warnings.append("Review title for price, ranking or promotional claims; context matters.")
        if listing["shortDescription"].strip().casefold() == title.strip().casefold():
            warnings.append("Short description repeats the title; explain a benefit.")
        words = re.findall(r"[^\W\d_]+", listing["fullDescription"].casefold())
        from collections import Counter
        counts = Counter(words)
        repeated = [w for w, n in counts.items() if len(w) > 3 and n >= 8]
        if repeated:
            warnings.append("Check repetition in context: " + ", ".join(sorted(repeated)))
        report.append({"locale": locale, "characters": {k: len(listing[k]) for k in LIMITS},
                       "warnings": warnings})
    return report
