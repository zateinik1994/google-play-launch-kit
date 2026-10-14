#!/usr/bin/env python3
"""Bounded public Play collection, normalized profiles/reviews/rank snapshots."""
import argparse
import csv
import json
import re
import sys
from datetime import datetime, timezone
from importlib.metadata import version, PackageNotFoundError
from pathlib import Path

RANK_FIELDS = ("observed_at", "package_name", "locale", "country", "query", "rank", "depth", "source")


class CollectionError(RuntimeError):
    pass


class PublicPlay:
    source = "google-play-scraper/public-web"
    method = "unpersonalized public-web observation; not an official Play ranking API"
    def __init__(self):
        try:
            import google_play_scraper as scraper
        except ImportError as exc:
            raise CollectionError("Install optional dependency in this interpreter: python -m pip install 'google-play-scraper>=1.2.7,<2'") from exc
        self.scraper = scraper
        try:
            self.version = version("google-play-scraper")
        except PackageNotFoundError:
            self.version = "unknown"

    def app(self, package, lang, country):
        return self.scraper.app(package, lang=lang, country=country.lower())

    def search(self, query, lang, country, limit):
        return self.scraper.search(query, lang=lang, country=country.lower(), n_hits=limit)

    def reviews(self, package, lang, country, limit):
        rows, _ = self.scraper.reviews(package, lang=lang, country=country.lower(), count=limit, sort=self.scraper.Sort.NEWEST)
        return rows


def package_id(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z][A-Za-z0-9_]*)+", value):
        raise ValueError("Expected an Android package name")
    return value


def context(locale, country):
    if not re.fullmatch(r"[a-z]{2,3}(?:-[A-Za-z0-9]{2,8})*", locale) or not re.fullmatch(r"[A-Z]{2}", country):
        raise ValueError("Use explicit locale (en-GB) and country (GB)")
    # The scraper accepts language separately from the explicit country.
    return locale.replace("-", "_"), country


def normalize_profile(data, package):
    if not isinstance(data, dict) or not isinstance(data.get("title"), str):
        raise CollectionError("Unexpected public listing response; parser may need an update")
    return {"package_name": package, "title": data["title"], "shortDescription": data.get("summary"),
            "fullDescription": data.get("description"), "developer": data.get("developer"),
            "rating": data.get("score"), "rating_count": data.get("ratings"),
            "install_bucket": data.get("installs"), "min_installs": data.get("minInstalls"),
            "price": data.get("price"), "currency": data.get("currency"), "offers_iap": data.get("offersIAP"),
            "screenshots": data.get("screenshots", []), "url": data.get("url"), "updated": data.get("updated")}


def rank_snapshot(results, packages, query, locale, country, observed_at=None, source="provided search results"):
    if not isinstance(results, list) or not results:
        raise CollectionError("No observable search results; do not record an empty response as missing rankings")
    ids = []
    for row in results:
        if not isinstance(row, dict) or not isinstance(row.get("appId"), str):
            raise CollectionError("Malformed search result; snapshot not written")
        package_id(row["appId"])
        if row["appId"] in ids:
            raise CollectionError("Duplicate packages in search response; rank order is ambiguous")
        ids.append(row["appId"])
    stamp = observed_at or datetime.now(timezone.utc).isoformat()
    return [{"observed_at": stamp, "package_name": package_id(package), "locale": locale, "country": country,
             "query": query, "rank": ids.index(package) + 1 if package in ids else "", "depth": len(ids),
             "source": source} for package in packages]


def normalize_reviews(rows):
    output, seen = [], {}
    if not isinstance(rows, list):
        raise CollectionError("Unexpected reviews response")
    for row in rows:
        review_id = row.get("reviewId") if isinstance(row, dict) else None
        score = row.get("score") if isinstance(row, dict) else None
        if not isinstance(review_id, str) or not review_id or not isinstance(score, int) or isinstance(score, bool) or not 1 <= score <= 5 or not isinstance(row.get("content"), str):
            raise CollectionError("Malformed review response; output not written")
        at = row.get("at")
        normalized = {"review_id": review_id, "rating": score, "text": row["content"],
                      "created_at": at.isoformat() if isinstance(at, datetime) else at,
                      "app_version": row.get("appVersion") or row.get("reviewCreatedVersion")}
        if review_id in seen:
            if seen[review_id] != normalized:
                raise CollectionError("Conflicting versions of the same review ID; select a verified latest version before analysis")
            continue
        seen[review_id] = normalized
        output.append(normalized)
    return output


def collect(provider, operation, *, locale, country, packages=(), query=None, limit=30):
    lang, country = context(locale, country)
    for package in packages:
        package_id(package)
    if not 1 <= limit <= (1000 if operation == "reviews" else 30):
        raise ValueError("Bounded limit: search/ranks 1–30; reviews 1–1000")
    if operation in {"search", "ranks"} and (not isinstance(query, str) or not query.strip()):
        raise ValueError("Non-empty query required")
    if operation in {"profiles", "ranks", "reviews"} and not packages:
        raise ValueError("At least one package required")
    if len(packages) > 30 or len(packages) != len(set(packages)):
        raise ValueError("Use up to 30 distinct packages")
    stamp = datetime.now(timezone.utc).isoformat()
    dependency_version = getattr(provider, "version", "unknown")
    source = getattr(provider, "source", "provided-adapter") + "@" + dependency_version
    meta = {"source": source, "dependency_version": dependency_version, "is_fixture": getattr(provider, "is_fixture", False),
            "observed_at": stamp, "locale": locale, "country": country, "language_requested": lang,
            "method": getattr(provider, "method", "provided adapter observation"),
            "volume": None, "packages": list(packages)}
    if operation == "profiles":
        data = [normalize_profile(provider.app(p, lang, country), p) for p in packages]
    elif operation in {"search", "ranks"}:
        rows = provider.search(query, lang, country, limit)
        if not isinstance(rows, list) or len(rows) > limit:
            raise CollectionError("Unexpected search response size")
        snapshot = rank_snapshot(rows, packages, query, locale, country, stamp, source)
        data = snapshot if operation == "ranks" else rows
        meta.update(query=query, requested_depth=limit, observed_depth=len(rows))
    else:
        if len(packages) != 1:
            raise ValueError("Review collection requires exactly one package")
        reviews = provider.reviews(packages[0], lang, country, limit)
        if not isinstance(reviews, list) or len(reviews) > limit:
            raise CollectionError("Unexpected review response size")
        data = normalize_reviews(reviews)
    return {"metadata": meta, "data": data}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("profiles", "search", "ranks", "reviews"))
    parser.add_argument("--package", action="append", default=[])
    parser.add_argument("--query")
    parser.add_argument("--locale", required=True)
    parser.add_argument("--country", required=True)
    parser.add_argument("--limit", type=int, default=30)
    parser.add_argument("--output", required=True, help="New JSON, or CSV for ranks/reviews with .meta.json sidecar")
    parser.add_argument("--fixture", help="Offline JSON {apps:{package:profile},search:[],reviews:[]}")
    args = parser.parse_args(argv)
    try:
        output = Path(args.output)
        sidecar = output.with_suffix(output.suffix + ".meta.json")
        if output.exists() or sidecar.exists():
            raise ValueError("Output or metadata sidecar already exists")
        if output.suffix == ".csv" and args.operation not in {"ranks", "reviews"}:
            raise ValueError("CSV output is supported for ranks/reviews")
        if args.fixture:
            fixture = json.loads(Path(args.fixture).read_text())
            class Fixture:
                version = "fixture"
                source = "fixture/offline"
                is_fixture = True
                method = "offline fictional fixture; timestamps describe this fixture run, not a live observation"
                def app(self, package, lang, country): return fixture["apps"][package]
                def search(self, query, lang, country, limit): return fixture["search"][:limit]
                def reviews(self, package, lang, country, limit): return fixture["reviews"][:limit]
            provider = Fixture()
        else:
            provider = PublicPlay()
        result = collect(provider, args.operation, locale=args.locale, country=args.country,
                         packages=args.package, query=args.query, limit=args.limit)
        output.parent.mkdir(parents=True, exist_ok=True)
        if output.suffix == ".csv":
            if args.operation not in {"ranks", "reviews"}:
                raise ValueError("CSV output is supported for ranks/reviews")
            fields = RANK_FIELDS if args.operation == "ranks" else ("review_id", "rating", "text", "created_at", "app_version")
            with output.open("x", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=fields)
                writer.writeheader()
                writer.writerows(result["data"])
            with sidecar.open("x", encoding="utf-8") as handle:
                handle.write(json.dumps(result["metadata"], ensure_ascii=False, indent=2) + "\n")
        else:
            with output.open("x", encoding="utf-8") as handle:
                json.dump(result, handle, ensure_ascii=False, indent=2, allow_nan=False)
                handle.write("\n")
        print(json.dumps({"output": str(output), "rows": len(result["data"])}))
        return 0
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print(f"Input/output error: {exc}", file=sys.stderr)
        return 2
    except CollectionError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Public collection failed ({type(exc).__name__}); parser/service unavailable, no automatic retry", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
