#!/usr/bin/env python3
"""Typed Android AppStoreSpy requests, with explicit paid execution and provenance."""
import argparse
import json
import math
import os
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, build_opener, HTTPRedirectHandler

SCHEMA = json.loads(Path(__file__).with_name("appstorespy_schema.json").read_text())
BASE = "https://api.appstorespy.com/v1"


class ProviderError(RuntimeError):
    pass


def validate(value, schema, path="value"):
    if "$ref" in schema:
        return validate(value, SCHEMA["schemas"][schema["$ref"].rsplit("/", 1)[-1]], path)
    if "allOf" in schema:
        for part in schema["allOf"]:
            validate(value, part, path)
    if "anyOf" in schema:
        for part in schema["anyOf"]:
            try:
                validate(value, part, path)
                return
            except ValueError:
                pass
        raise ValueError(f"{path}: invalid value")
    kind = schema.get("type")
    valid = {"string": isinstance(value, str), "integer": isinstance(value, int) and not isinstance(value, bool),
             "number": (isinstance(value, int) and not isinstance(value, bool)) or isinstance(value, float) and math.isfinite(value),
             "boolean": isinstance(value, bool), "object": isinstance(value, dict),
             "array": isinstance(value, list), "null": value is None}
    if kind in valid and not valid[kind]:
        raise ValueError(f"{path}: expected {kind}")
    if "enum" in schema and value not in schema["enum"]:
        raise ValueError(f"{path}: unsupported enum value")
    if kind in {"integer", "number"}:
        if "minimum" in schema and value < schema["minimum"] or "maximum" in schema and value > schema["maximum"]:
            raise ValueError(f"{path}: outside allowed bounds")
    if kind == "string":
        if not value.strip():
            raise ValueError(f"{path}: empty string")
        if schema.get("format") == "date":
            try:
                if date.fromisoformat(value).isoformat() != value:
                    raise ValueError()
            except ValueError as exc:
                raise ValueError(f"{path}: expected YYYY-MM-DD") from exc
    if kind == "array":
        if len(value) > schema.get("maxItems", 1000) or len(value) < schema.get("minItems", 0):
            raise ValueError(f"{path}: invalid item count")
        for i, item in enumerate(value):
            validate(item, schema.get("items", {}), f"{path}[{i}]")
    if kind == "object":
        props = schema.get("properties", {})
        unknown = set(value) - set(props)
        missing = set(schema.get("required", [])) - set(value)
        if unknown or missing:
            raise ValueError(f"{path}: unknown fields {sorted(unknown)}, missing fields {sorted(missing)}")
        for key, item in value.items():
            validate(item, props[key], f"{path}.{key}")


def build_request(operation, params=None, body=None):
    if operation not in SCHEMA["operations"]:
        raise ValueError("Unknown Android AppStoreSpy operation")
    spec = SCHEMA["operations"][operation]
    params = dict(params or {})
    unknown = set(params) - set(spec["parameters"])
    if unknown:
        raise ValueError(f"Unsupported parameters: {sorted(unknown)}")
    for name, field in spec["parameters"].items():
        if name not in params:
            if field["required"]:
                raise ValueError(f"Required parameter: {name}")
        else:
            validate(params[name], field["schema"], name)
    if spec["method"] == "POST":
        if body is None:
            raise ValueError("This operation requires --body JSON")
        validate(body, spec["body"], "body")
        if operation == "search-job-create" and body.get("store") != "play":
            raise ValueError("Android search jobs require store=play")
    elif body is not None:
        raise ValueError("GET operation cannot have a body")
    if operation == "search-jobs":
        if params.get("store", "play") != "play":
            raise ValueError("Android search jobs require store=play")
        params["store"] = "play"
    path, query = spec["path"], {}
    for key, value in params.items():
        if spec["parameters"][key]["in"] == "path":
            path = path.replace("{" + key + "}", quote(str(value), safe=""))
        else:
            query[key] = ",".join(map(str, value)) if isinstance(value, list) else str(value).lower() if isinstance(value, bool) else value
    if "{" in path:
        raise ValueError("Missing path parameter")
    if params.get("start") and params.get("end") and params["start"] > params["end"]:
        raise ValueError("start must not follow end")
    if params.get("date_start") and params.get("date_end") and params["date_start"] > params["date_end"]:
        raise ValueError("date_start must not follow date_end")
    return {"operation": operation, "method": spec["method"], "url": BASE + path,
            "query": query, "body": body, "credit_estimate": spec["credit_estimate"],
            "schema_checked_at": SCHEMA["checked_at"]}


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


class AppStoreSpy:
    def __init__(self, api_key=None, transport=None):
        self.key = api_key or os.environ.get("APPSTORESPY_API_KEY")
        self.transport = transport or self._send

    def _send(self, request):
        if not self.key:
            raise ProviderError("APPSTORESPY_API_KEY is required for executed requests")
        url = request["url"] + ("?" + urlencode(request["query"]) if request["query"] else "")
        data = json.dumps(request["body"], allow_nan=False).encode() if request["body"] is not None else None
        req = Request(url, data=data, method=request["method"], headers={"API-KEY": self.key, "Accept": "application/json", "Content-Type": "application/json"})
        try:
            with build_opener(NoRedirect()).open(req, timeout=45) as response:
                raw = response.read(32 * 1024 * 1024 + 1)
                if len(raw) > 32 * 1024 * 1024:
                    raise ProviderError("Provider response exceeds 32 MB")
                status = response.status
                credits = {name: response.headers.get(name) for name in ("X-Cost", "X-Remaining-Credits", "X-Receipt")}
                payload = json.loads(raw) if raw.strip() else None
                return status, payload, credits
        except HTTPError as exc:
            messages = {401: "Missing or invalid key", 402: "Insufficient credits", 403: "Access denied; check key and plan", 429: "Rate limit; no automatic retry"}
            raise ProviderError(f"AppStoreSpy HTTP {exc.code}: {messages.get(exc.code, 'Request failed; no automatic retry')}") from exc
        except (URLError, TimeoutError, ValueError) as exc:
            raise ProviderError("AppStoreSpy transport/JSON failure; no automatic retry") from exc

    def call(self, operation, params=None, body=None):
        request = build_request(operation, params, body)
        status, payload, credits = self.transport(request)
        if status not in {200, 202, 204, 206}:
            raise ProviderError(f"Unexpected provider status: {status}")
        state = {200: "returned", 202: "queued", 204: "no_country_data", 206: "partial"}[status]
        return {"status": state, "observed_at": datetime.now(timezone.utc).isoformat(),
                "source": "AppStoreSpy Android", "request": request, "billing": credits,
                "estimates_are_modeled": True, "data": payload}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=sorted(SCHEMA["operations"]))
    parser.add_argument("--params", help="JSON file with endpoint query/path parameters")
    parser.add_argument("--body", help="JSON file with typed POST body")
    parser.add_argument("--execute", action="store_true", help="Call provider; uses account credits and may queue a crawl")
    parser.add_argument("--output", help="New result JSON; never overwritten")
    args = parser.parse_args(argv)
    try:
        if args.output:
            output = Path(args.output)
            if output.exists():
                raise ValueError("Output already exists; no provider request made")
            output.parent.mkdir(parents=True, exist_ok=True)
        params = json.loads(Path(args.params).read_text()) if args.params else {}
        body = json.loads(Path(args.body).read_text()) if args.body else None
        request = build_request(args.operation, params, body)
        result = AppStoreSpy().call(args.operation, params, body) if args.execute else {"status": "offline-plan", "request": request}
        text = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
        if args.output:
            with Path(args.output).open("x", encoding="utf-8") as handle:
                handle.write(text)
        else:
            print(text, end="")
        return 0
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print(f"Input error: {exc}", file=sys.stderr)
        return 2
    except ProviderError as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
