#!/usr/bin/env python3
"""Download official Play CSV reports from GCS and normalize explicit metric families."""
import argparse
import csv
import hashlib
import io
import json
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import quote

SCOPE = "https://www.googleapis.com/auth/devstorage.read_only"
PACKAGE = r"[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z][A-Za-z0-9_]*)+"
COUNTS = ("visitors", "acquisitions", "install_clicks", "open_clicks", "pre_registration_clicks")
DIMENSIONS = ("package_name", "country", "language", "store_listing", "install_state", "device_form_factor",
              "traffic_source", "search_term", "utm_source", "utm_campaign", "metric_family")
FIELDS = ("date", "package_name", "country", "language", "store_listing", "install_state", "device_form_factor", "traffic_source", "search_term", "utm_source", "utm_campaign",
          "metric_family", "visitors", "acquisitions", "install_clicks", "open_clicks", "pre_registration_clicks")


class ReportError(RuntimeError):
    pass


def report_object(package, month, breakdown):
    if not re.fullmatch(PACKAGE, package):
        raise ValueError("Expected Android package name")
    if not re.fullmatch(r"[0-9]{6}", month):
        raise ValueError("month must be YYYYMM")
    date(int(month[:4]), int(month[4:]), 1)
    if breakdown not in {"country", "traffic_source"}:
        raise ValueError("Supported legacy export breakdowns: country, traffic_source")
    return f"stats/store_performance/store_performance_{package}_{month}_{breakdown}.csv"


def object_url(bucket, name):
    if not re.fullmatch(r"[a-z0-9][a-z0-9._-]{1,220}[a-z0-9]", bucket) or not name or name.startswith("/") or ".." in name.split("/"):
        raise ValueError("Invalid bucket/object")
    return f"https://storage.googleapis.com/storage/v1/b/{quote(bucket, safe='')}/o/{quote(name, safe='')}?alt=media"


class GCSReports:
    def __init__(self):
        try:
            import google.auth
            from google.auth.transport.requests import AuthorizedSession
            credentials, _ = google.auth.default(scopes=[SCOPE])
            self.session = AuthorizedSession(credentials)
        except Exception as exc:
            raise ReportError("Configure ADC with storage read scope and Play report bucket permissions; install requirements.txt") from exc

    def download(self, bucket, name, max_bytes=64 * 1024 * 1024):
        try:
            with self.session.get(object_url(bucket, name), timeout=45, stream=True, allow_redirects=False) as response:
                if response.status_code != 200:
                    raise ReportError(f"Cloud Storage HTTP {response.status_code}; check bucket permissions and report availability")
                output = bytearray()
                for chunk in response.iter_content(64 * 1024):
                    output.extend(chunk)
                    if len(output) > max_bytes:
                        raise ReportError("Report exceeds the configured 64 MB limit")
                return bytes(output)
        except ReportError:
            raise
        except Exception as exc:
            raise ReportError(f"GCS read failed ({type(exc).__name__}); no automatic retry") from exc


ALIASES = {
    "date": ("Date", "date"), "package_name": ("Package name", "package_name"),
    "country": ("Country", "Country/region", "country"), "traffic_source": ("Traffic source", "traffic_source"),
    "language": ("Language", "language"), "store_listing": ("Store listing", "store_listing"),
    "install_state": ("App install state", "Install state", "install_state"),
    "device_form_factor": ("Device form factor", "Form factor", "device_form_factor"),
    "search_term": ("Search term", "search_term"), "utm_source": ("UTM source", "utm_source"), "utm_campaign": ("UTM campaign", "utm_campaign"),
    "visitors": ("Store listing visitors", "visitors"), "acquisitions": ("Store listing acquisitions", "acquisitions"),
    "install_clicks": ("Unique user install clicks", "install_clicks"), "open_clicks": ("Unique user open clicks", "open_clicks"),
    "pre_registration_clicks": ("Unique user pre-registration clicks", "pre_registration_clicks"),
}


def normalize_csv(raw, *, family="auto", mapping=None, package=None, encoding=None):
    if not isinstance(raw, (bytes, str)):
        raise ValueError("Report must be bytes or CSV text")
    original = raw if isinstance(raw, bytes) else raw.encode("utf-8")
    codec = "unicode-text"
    if isinstance(raw, bytes):
        codec = encoding or ("utf-16" if raw.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8-sig")
        raw = raw.decode(codec)
    reader = csv.DictReader(io.StringIO(raw, newline=""))
    headers = reader.fieldnames or []
    if not headers or len(headers) != len(set(headers)):
        raise ValueError("Report needs unique column headers")
    if mapping is not None and (not isinstance(mapping, dict) or any(not isinstance(value, str) for value in mapping.values())):
        raise ValueError("Mapping must be a JSON object of normalized fields to source column names")
    explicit = mapping or {}
    if set(explicit) - set(ALIASES):
        raise ValueError("Mapping contains unsupported normalized fields")
    columns = {}
    for name, aliases in ALIASES.items():
        matches = [explicit[name]] if name in explicit else [h for h in headers if h.strip().casefold() in {a.casefold() for a in aliases}]
        if len(matches) > 1 or matches and matches[0] not in headers:
            raise ValueError(f"Ambiguous/missing column mapping for {name}")
        if matches:
            columns[name] = matches[0]
    if len(set(columns.values())) != len(columns):
        raise ValueError("Each source column must map to one normalized field; refusing to duplicate metrics or dimensions")
    if "date" not in columns or "visitors" not in columns:
        raise ValueError("Date and visitor columns are required; provide --mapping for translated exports")
    acquisitions = "acquisitions" in columns
    clicks = any(k in columns for k in ("install_clicks", "open_clicks", "pre_registration_clicks"))
    if family == "auto":
        if acquisitions == clicks:
            raise ValueError("Cannot infer one metric family; select legacy-acquisitions or click-intent explicitly")
        family = "legacy-acquisitions" if acquisitions else "click-intent"
    if family not in {"legacy-acquisitions", "click-intent"} or family == "legacy-acquisitions" and not acquisitions or family == "click-intent" and not clicks:
        raise ValueError("Metric family does not match present columns")
    output = []
    for index, row in enumerate(reader, 2):
        if None in row or any(v is None for v in row.values()):
            raise ValueError(f"Malformed CSV row {index}")
        normalized = {key: row[column] for key, column in columns.items()}
        if date.fromisoformat(normalized["date"]).isoformat() != normalized["date"]:
            raise ValueError("Dates must be YYYY-MM-DD")
        value = normalized.get("package_name") or package
        if not isinstance(value, str) or not re.fullmatch(PACKAGE, value) or package and value != package:
            raise ValueError("Missing or unexpected package in report")
        normalized["package_name"] = value
        for field in COUNTS:
            text = normalized.get(field, "").strip()
            if text and not re.fullmatch(r"[0-9]+", text):
                raise ValueError(f"{field}: expected integer or blank; suppressed counts stay unknown")
            normalized[field] = int(text) if text else None
            if normalized[field] is not None and normalized[field] > 2**63 - 1:
                raise ValueError(f"{field}: expected a nonnegative 64-bit integer or blank")
        normalized["metric_family"] = family
        if family == "legacy-acquisitions":
            for field in ("install_clicks", "open_clicks", "pre_registration_clicks"):
                normalized[field] = None
        else:
            normalized["acquisitions"] = None
        output.append({key: normalized.get(key) for key in FIELDS})
    return {"metadata": {"metric_family": family, "rows": len(output), "input_sha256": hashlib.sha256(original).hexdigest(),
                         "input_encoding": codec, "source_columns": headers, "column_mapping": columns,
                         "note": "Daily visitors are not deduplicated weekly/monthly users. Search-term visits are your app's traffic, not total query volume."}, "data": output}


def summarize(rows, action="install_clicks"):
    if action not in {"install_clicks", "open_clicks", "pre_registration_clicks"}:
        raise ValueError("Select one click metric")
    if not isinstance(rows, list):
        raise ValueError("Expected a normalized report array")
    groups = {}
    seen = set()
    for row in rows:
        if not isinstance(row, dict) or row.get("metric_family") not in {"legacy-acquisitions", "click-intent"}:
            raise ValueError("Expected normalized report rows with a supported metric family")
        stamp = row.get("date")
        if not isinstance(stamp, str) or date.fromisoformat(stamp).isoformat() != stamp:
            raise ValueError("Dates must be YYYY-MM-DD")
        package = row.get("package_name")
        if not isinstance(package, str) or not re.fullmatch(PACKAGE, package):
            raise ValueError("Expected an Android package name in each report row")
        if any(row.get(key) is not None and not isinstance(row[key], str) for key in DIMENSIONS):
            raise ValueError("Report dimensions must be strings or null")
        for field in COUNTS:
            value = row.get(field)
            if value is not None and (type(value) is not int or not 0 <= value <= 2**63 - 1):
                raise ValueError(f"{field}: expected a nonnegative 64-bit integer or null")
        signature = tuple(row.get(k) for k in ("date",) + DIMENSIONS)
        if signature in seen:
            raise ValueError("Duplicate report row; refusing to double-count")
        seen.add(signature)
        key = signature[1:]
        group = groups.setdefault(key, {"dates": [], "visitor_days": 0, "action_days": 0, "complete": True})
        group["dates"].append(row["date"])
        visitor = row.get("visitors")
        selected = row.get("acquisitions") if row["metric_family"] == "legacy-acquisitions" else row.get(action)
        group["complete"] &= visitor is not None and selected is not None
        group["visitor_days"] += visitor or 0
        group["action_days"] += selected or 0
    output = []
    keys = DIMENSIONS
    for key, values in groups.items():
        output.append({**dict(zip(keys, key)), "from": min(values["dates"]), "to": max(values["dates"]),
                       "days_observed": len(values["dates"]), "visitor_days": values["visitor_days"] if values["complete"] else None,
                       "action_days": values["action_days"] if values["complete"] else None,
                       "action_metric": "acquisitions" if key[-1] == "legacy-acquisitions" else action,
                       "daily_weighted_rate": values["action_days"] / values["visitor_days"] if values["complete"] and values["visitor_days"] else None})
    return output


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)
    d = sub.add_parser("download")
    d.add_argument("--bucket", required=True)
    d.add_argument("--object", help="Exact report object path")
    d.add_argument("--package")
    d.add_argument("--month")
    d.add_argument("--breakdown", choices=("country", "traffic_source"), default="traffic_source")
    d.add_argument("--execute", action="store_true")
    n = sub.add_parser("normalize")
    n.add_argument("--input", required=True)
    n.add_argument("--package")
    n.add_argument("--family", choices=("auto", "legacy-acquisitions", "click-intent"), default="auto")
    n.add_argument("--mapping")
    n.add_argument("--encoding")
    s = sub.add_parser("summary")
    s.add_argument("--input", required=True)
    s.add_argument("--action", choices=("install_clicks", "open_clicks", "pre_registration_clicks"), default="install_clicks")
    for child in sub.choices.values():
        child.add_argument("--output", required=True, help="New file; never overwritten")
    args = p.parse_args(argv)
    try:
        output = Path(args.output)
        sidecar = output.with_suffix(output.suffix + ".meta.json")
        if output.exists() or output.is_symlink() or sidecar.exists() or sidecar.is_symlink():
            raise ValueError("Output already exists")
        if args.command == "download":
            name = args.object or report_object(args.package or "", args.month or "", args.breakdown)
            url = object_url(args.bucket, name)
            meta = {"status": "offline-plan", "source": "Google Play report bucket", "bucket": args.bucket, "object": name, "url": url}
            if args.execute:
                raw = GCSReports().download(args.bucket, name)
                output.parent.mkdir(parents=True, exist_ok=True)
                with output.open("xb") as handle:
                    handle.write(raw)
                meta.update(status="downloaded", observed_at=datetime.now(timezone.utc).isoformat())
                with output.with_suffix(output.suffix + ".meta.json").open("x", encoding="utf-8") as handle:
                    json.dump(meta, handle, indent=2)
                print(json.dumps(meta))
                return 0
            result = meta
        elif args.command == "normalize":
            mapping = json.loads(Path(args.mapping).read_text()) if args.mapping else None
            result = normalize_csv(Path(args.input).read_bytes(), family=args.family, mapping=mapping, package=args.package, encoding=args.encoding)
            result["metadata"].update(input_file=str(Path(args.input).resolve()), normalized_at=datetime.now(timezone.utc).isoformat())
        else:
            result = summarize(json.loads(Path(args.input).read_text())["data"], args.action)
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("x", encoding="utf-8") as handle:
            json.dump(result, handle, ensure_ascii=False, indent=2, allow_nan=False)
            handle.write("\n")
        print(json.dumps({"output": str(output)}))
        return 0
    except (OSError, ValueError, TypeError, KeyError, UnicodeError, LookupError) as exc:
        print(f"Input/output error: {exc}", file=sys.stderr)
        return 2
    except ReportError as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
