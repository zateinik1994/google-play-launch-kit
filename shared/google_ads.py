#!/usr/bin/env python3
"""Optional Google Ads REST client: selected-action reports and paused App campaigns."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import secrets
import sys
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Callable, Mapping, Protocol
import unicodedata

ADS_FIELDS = ("date", "campaign_id", "currency", "cost", "impressions", "clicks", "conversions", "conversion_action")
ADS_SCOPE = "https://www.googleapis.com/auth/adwords"
CONVERSION_RESOURCE = re.compile(r"^customers/[0-9]{10}/conversionActions/[1-9][0-9]*$")
GOAL = "OPTIMIZE_IN_APP_CONVERSIONS_TARGET_CONVERSION_COST"


class AdsError(RuntimeError):
    pass


class AdsAPIError(AdsError):
    def __init__(self, status: int, message: str):
        self.status = status
        super().__init__(f"Google Ads API HTTP {status}: {message}")


class AdsCreationUnknown(AdsError):
    """The server may have created resources without returning confirmation."""


class AdsTransport(Protocol):
    def request(self, method: str, url: str, *, payload: Mapping[str, Any]) -> Mapping[str, Any]: ...


def customer_id(value: str) -> str:
    normalized = value.replace("-", "") if isinstance(value, str) else ""
    if not re.fullmatch(r"[0-9]{10}", normalized):
        raise ValueError("Customer ID must contain 10 digits, with optional hyphens.")
    return normalized


def api_version(value: str) -> str:
    if not re.fullmatch(r"v[1-9][0-9]*", value or ""):
        raise ValueError("Pass an explicit API version, e.g. v25; check Google's supported versions.")
    return value


def conversion_resource(value: str) -> str:
    if not isinstance(value, str) or not CONVERSION_RESOURCE.fullmatch(value):
        raise ValueError("Use an actual customers/<10-digit-id>/conversionActions/<id> resource.")
    return value


class AdsADCTransport:
    """ADC with the Ads OAuth scope; credentials and developer token stay in memory."""

    def __init__(self, timeout: float = 60.0):
        token = os.environ.get("GOOGLE_ADS_DEVELOPER_TOKEN")
        if not token:
            raise AdsError("Set GOOGLE_ADS_DEVELOPER_TOKEN for network commands.")
        login = os.environ.get("GOOGLE_ADS_LOGIN_CUSTOMER_ID")
        self.headers = {"developer-token": token}
        if login:
            self.headers["login-customer-id"] = customer_id(login)
        try:
            import google.auth
            from google.auth.transport.requests import AuthorizedSession
        except ImportError as exc:
            raise AdsError('Install optional dependency: python3 -m pip install "google-auth[requests]>=2"') from exc
        try:
            credentials, _ = google.auth.default(scopes=[ADS_SCOPE])
            self.session = AuthorizedSession(credentials, max_refresh_attempts=1)
        except Exception as exc:
            raise AdsError("Configure ADC with the adwords scope and access to the Google Ads account.") from exc
        self.timeout = timeout

    def request(self, method, url, *, payload):
        try:
            response = self.session.request(
                method, url, json=payload, headers=self.headers, timeout=self.timeout
            )
        except Exception as exc:
            raise AdsError(f"{type(exc).__name__} contacting Google Ads; no automatic retry.") from exc
        try:
            result = response.json() if response.content else {}
        except ValueError as exc:
            raise AdsError("Google Ads returned non-JSON data; no automatic retry.") from exc
        if not 200 <= response.status_code < 300:
            error = result.get("error", {}) if isinstance(result, dict) else {}
            message = error.get("message", "Request failed") if isinstance(error, dict) else "Request failed"
            # Only API message and request ID are reported, never headers/tokens.
            request_id = response.headers.get("request-id")
            if request_id:
                message = f"{message} (request-id: {request_id})"
            raise AdsAPIError(response.status_code, str(message))
        if not isinstance(result, dict):
            raise AdsError("Google Ads returned a non-object response.")
        return result


def text_length(value: str) -> int:
    """Conservative Google Ads count: full/wide CJK characters count twice."""
    return sum(2 if unicodedata.east_asian_width(char) in {"W", "F"} else 1 for char in value)


def validate_config(config: Any) -> list[str]:
    if not isinstance(config, dict):
        return ["Campaign config must be a JSON object."]
    required = {
        "name", "package_name", "currency", "daily_budget_micros", "target_cpa_micros",
        "conversion_action", "country_resources", "language_resources", "headlines", "descriptions",
        "contains_eu_political_advertising",
    }
    errors = [f"Missing field: {key}" for key in sorted(required - config.keys())]
    errors += [f"Unsupported field: {key}" for key in sorted(config.keys() - required)]
    if not isinstance(config.get("name"), str) or not config["name"].strip():
        errors.append("name must be non-empty text.")
    if not isinstance(config.get("package_name"), str) or not re.fullmatch(
        r"[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z][A-Za-z0-9_]*)+", config["package_name"]
    ):
        errors.append("package_name must be an Android application ID.")
    if not re.fullmatch(r"[A-Z]{3}", str(config.get("currency", ""))):
        errors.append("currency must be the Ads account currency, e.g. USD.")
    for key in ("daily_budget_micros", "target_cpa_micros"):
        value = config.get(key)
        if not isinstance(value, int) or isinstance(value, bool) or not 0 < value <= 2**63 - 1:
            errors.append(f"{key} must be a positive int64 integer in account currency micros.")
    try:
        conversion_resource(config.get("conversion_action"))
    except ValueError as exc:
        errors.append(str(exc))
    for key, prefix in (("country_resources", "geoTargetConstants"), ("language_resources", "languageConstants")):
        values = config.get(key)
        if not isinstance(values, list) or not values or any(
            not isinstance(value, str) or not re.fullmatch(rf"{prefix}/[1-9][0-9]*", value)
            for value in values
        ):
            errors.append(f"{key} must contain actual {prefix}/<id> resources.")
        elif len(set(values)) != len(values):
            errors.append(f"{key} contains duplicates.")
    for key, maximum in (("headlines", 30), ("descriptions", 90)):
        values = config.get(key)
        if not isinstance(values, list) or not 1 <= len(values) <= 5:
            errors.append(f"{key} must contain 1–5 text assets.")
        else:
            for index, value in enumerate(values):
                if not isinstance(value, str) or not value.strip():
                    errors.append(f"{key}[{index}] must be non-empty text.")
                elif text_length(value) > maximum or any(ord(char) < 32 for char in value):
                    errors.append(f"{key}[{index}] exceeds {maximum} ad characters or contains control characters.")
    if config.get("contains_eu_political_advertising") is not False:
        errors.append("This tool supports only explicitly declared non-political campaigns: contains_eu_political_advertising=false.")
    return errors


def campaign_request(customer: str, config: Mapping[str, Any], *, validate_only: bool = True) -> dict[str, Any]:
    """Prepare real REST operations, ordered to resolve temporary parent IDs."""
    customer = customer_id(customer)
    errors = validate_config(config)
    if errors:
        raise ValueError("Invalid campaign config:\n" + "\n".join(errors))
    base = f"customers/{customer}"
    budget, campaign, ad_group = (f"{base}/{kind}/{number}" for kind, number in (
        ("campaignBudgets", -1), ("campaigns", -2), ("adGroups", -3)
    ))
    operations = [
        {"campaignBudgetOperation": {"create": {
            "resourceName": budget,
            "name": config["name"] + " budget",
            "amountMicros": str(config["daily_budget_micros"]),
            "deliveryMethod": "STANDARD",
            "explicitlyShared": False,
        }}},
        {"campaignOperation": {"create": {
            "resourceName": campaign,
            "name": config["name"],
            "status": "PAUSED",
            "advertisingChannelType": "MULTI_CHANNEL",
            "advertisingChannelSubType": "APP_CAMPAIGN",
            "campaignBudget": budget,
            "targetCpa": {"targetCpaMicros": str(config["target_cpa_micros"])},
            "appCampaignSetting": {
                "appId": config["package_name"], "appStore": "GOOGLE_APP_STORE",
                "biddingStrategyGoalType": GOAL,
            },
            "selectiveOptimization": {"conversionActions": [config["conversion_action"]]},
            "containsEuPoliticalAdvertising": "DOES_NOT_CONTAIN_EU_POLITICAL_ADVERTISING",
        }}},
    ]
    for resource in config["country_resources"]:
        operations.append({"campaignCriterionOperation": {"create": {
            "campaign": campaign, "location": {"geoTargetConstant": resource}, "negative": False,
        }}})
    for resource in config["language_resources"]:
        operations.append({"campaignCriterionOperation": {"create": {
            "campaign": campaign, "language": {"languageConstant": resource}, "negative": False,
        }}})
    operations.extend([
        {"adGroupOperation": {"create": {
            "resourceName": ad_group, "name": config["name"] + " ad group", "campaign": campaign,
            "status": "PAUSED",
        }}},
        {"adGroupAdOperation": {"create": {
            "adGroup": ad_group, "status": "PAUSED",
            "ad": {"appAd": {
                "headlines": [{"text": text} for text in config["headlines"]],
                "descriptions": [{"text": text} for text in config["descriptions"]],
            }},
        }}},
    ])
    return {
        "mutateOperations": operations, "partialFailure": False,
        "validateOnly": validate_only, "responseContentType": "RESOURCE_NAME_ONLY",
    }


def date_range(start: str, end: str) -> tuple[str, str]:
    for value in (start, end):
        try:
            parsed = date.fromisoformat(value)
        except (ValueError, TypeError) as exc:
            raise ValueError("Report dates must use YYYY-MM-DD.") from exc
        if value != parsed.isoformat():
            raise ValueError("Report dates must use YYYY-MM-DD.")
    if start > end:
        raise ValueError("Report start date must not follow end date.")
    return start, end


def report_queries(start: str, end: str, conversion_action: str) -> tuple[str, str]:
    start, end = date_range(start, end)
    conversion_resource(conversion_action)
    where = (
        " FROM campaign WHERE campaign.advertising_channel_type = 'MULTI_CHANNEL'"
        " AND campaign.advertising_channel_sub_type IN "
        "('APP_CAMPAIGN', 'APP_CAMPAIGN_FOR_ENGAGEMENT', 'APP_CAMPAIGN_FOR_PRE_REGISTRATION')"
        " AND campaign.status IN ('ENABLED', 'PAUSED', 'REMOVED')"
        f" AND segments.date BETWEEN '{start}' AND '{end}'"
    )
    cost = (
        "SELECT segments.date, campaign.id, customer.currency_code, metrics.cost_micros, "
        "metrics.impressions, metrics.clicks" + where + " ORDER BY segments.date, campaign.id"
    )
    conversions = (
        "SELECT segments.date, campaign.id, customer.currency_code, segments.conversion_action, "
        "metrics.conversions" + where + f" AND segments.conversion_action = '{conversion_action}'"
        " ORDER BY segments.date, campaign.id"
    )
    return cost, conversions


def _number(value: Any, name: str, *, integer=False) -> Decimal:
    try:
        number = Decimal(str(value))
    except InvalidOperation as exc:
        raise AdsError(f"Invalid report metric: {name}.") from exc
    if not number.is_finite() or number < 0 or (integer and number != number.to_integral_value()):
        raise AdsError(f"Invalid report metric: {name}.")
    return number


def normalize_report(cost_rows, conversion_rows, conversion_action: str) -> list[dict[str, str]]:
    conversion_resource(conversion_action)
    merged = {}

    def get_key(row):
        try:
            day = row["segments"]["date"]
            campaign = str(row["campaign"]["id"])
            currency = row["customer"]["currencyCode"]
            date_range(day, day)
            if not re.fullmatch(r"[1-9][0-9]*", campaign) or not re.fullmatch(r"[A-Z]{3}", currency):
                raise ValueError("Invalid report key")
            return day, campaign, currency
        except (KeyError, TypeError, ValueError) as exc:
            raise AdsError("Invalid date, campaign ID, or currency in report response.") from exc

    def base(key):
        return dict(zip(ADS_FIELDS, (key[0], key[1], key[2], "0", "0", "0", "0", conversion_action)))

    def metrics_for(row):
        # Google may omit zero-valued metrics, but a non-object is a protocol
        # error, not evidence that spend or conversions are zero.
        metrics = row.get("metrics", {})
        if not isinstance(metrics, dict):
            raise AdsError("Invalid metrics object in report response.")
        return metrics

    seen = set()
    for row in cost_rows:
        key = get_key(row)
        if key in seen:
            raise AdsError("Duplicate campaign/day cost row; refusing to double-count spend.")
        seen.add(key)
        metrics = metrics_for(row)
        item = base(key)
        item["cost"] = format(_number(metrics.get("costMicros", 0), "costMicros", integer=True) / Decimal(1_000_000), "f")
        for field in ("impressions", "clicks"):
            item[field] = format(_number(metrics.get(field, 0), field, integer=True), "f")
        merged[key] = item
    seen = set()
    for row in conversion_rows:
        key = get_key(row)
        if row["segments"].get("conversionAction") != conversion_action:
            raise AdsError("Report returned a different conversion action than requested.")
        if key in seen:
            raise AdsError("Duplicate campaign/day conversion row; refusing to double-count conversions.")
        seen.add(key)
        item = merged.setdefault(key, base(key))
        item["conversions"] = format(_number(metrics_for(row).get("conversions", 0), "conversions"), "f")
    return [merged[key] for key in sorted(merged)]


class GoogleAds:
    def __init__(self, customer: str, version: str, transport: AdsTransport):
        self.customer = customer_id(customer)
        self.version = api_version(version)
        self.transport = transport
        self.root = f"https://googleads.googleapis.com/{self.version}/customers/{self.customer}/googleAds"

    def search(self, query: str) -> list[dict[str, Any]]:
        result, token, seen = [], None, set()
        while True:
            payload = {"query": query}
            if token:
                payload["pageToken"] = token
            response = self.transport.request("POST", self.root + ":search", payload=payload)
            rows = response.get("results", [])
            if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
                raise AdsError("Invalid Google Ads search response.")
            result.extend(rows)
            token = response.get("nextPageToken")
            if not token:
                return result
            if not isinstance(token, str) or token in seen:
                raise AdsError("Invalid or repeated pagination token.")
            seen.add(token)

    def _validate(self, config: Mapping[str, Any], request: Mapping[str, Any]) -> None:
        rows = self.search("SELECT customer.currency_code FROM customer LIMIT 1")
        if len(rows) != 1 or rows[0].get("customer", {}).get("currencyCode") != config["currency"]:
            raise AdsError("Configured currency differs from the Ads account or could not be verified.")
        countries = ", ".join(f"'{resource}'" for resource in config["country_resources"])
        rows = self.search(
            "SELECT geo_target_constant.resource_name, geo_target_constant.target_type, "
            "geo_target_constant.status FROM geo_target_constant "
            f"WHERE geo_target_constant.resource_name IN ({countries})"
        )
        verified = set()
        for row in rows:
            criterion = row.get("geoTargetConstant", {})
            if criterion.get("targetType") != "Country" or criterion.get("status") != "ENABLED":
                raise AdsError("Country targeting requires enabled Country geoTargetConstants.")
            verified.add(criterion.get("resourceName"))
        if verified != set(config["country_resources"]):
            raise AdsError("Could not verify every country targeting resource.")
        response = self.transport.request("POST", self.root + ":mutate", payload=request)
        if response.get("partialFailureError"):
            raise AdsError("Google Ads returned validation errors despite atomic request settings.")

    def validate(self, config: Mapping[str, Any]) -> dict[str, Any]:
        request = campaign_request(self.customer, config)
        self._validate(config, request)
        return {"status": "validated-only", "customer": self.customer, "apiVersion": self.version}

    def create_paused(
        self, config: Mapping[str, Any], *, on_validated: Callable[[], None] | None = None,
    ) -> dict[str, Any]:
        request = campaign_request(self.customer, config)
        self._validate(config, request)
        if on_validated:
            on_validated()
        request = dict(request, validateOnly=False)
        try:
            response = self.transport.request("POST", self.root + ":mutate", payload=request)
            resources = response.get("mutateOperationResponses")
            if response.get("partialFailureError") or not isinstance(resources, list) or len(resources) != len(request["mutateOperations"]):
                raise AdsError("Creation response did not confirm all operations.")
            names = []
            for resource in resources:
                if not isinstance(resource, dict) or len(resource) != 1:
                    raise AdsError("Creation response contained an invalid operation result.")
                detail = next(iter(resource.values()))
                if not isinstance(detail, dict) or not isinstance(detail.get("resourceName"), str) or not detail["resourceName"]:
                    raise AdsError("Creation response contained a missing resource name.")
                names.append(detail["resourceName"])
        except AdsError as exc:
            if not isinstance(exc, AdsAPIError) or exc.status == 408 or exc.status >= 500:
                raise AdsCreationUnknown(
                    f"Creation outcome is unknown: {exc}. Check Google Ads and change history before "
                    "retrying; another live request may create a duplicate paused campaign. No automatic retry."
                ) from exc
            raise
        return {
            "status": "created-paused", "customer": self.customer, "apiVersion": self.version,
            "campaignStatus": "PAUSED", "resources": names,
        }

    def report(self, start: str, end: str, conversion_action: str) -> list[dict[str, str]]:
        cost, conversions = report_queries(start, end, conversion_action)
        return normalize_report(self.search(cost), self.search(conversions), conversion_action)


def read_config(path: str | Path):
    with Path(path).open(encoding="utf-8") as handle:
        return json.load(handle)


def write_report(path: Path, rows) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=ADS_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def _parser():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("plan", "validate", "create", "report"):
        command = commands.add_parser(name)
        command.add_argument("--customer", required=True)
        command.add_argument("--api-version", required=True, help="Explicit supported version, e.g. v25")
        if name == "report":
            command.add_argument("--start-date", required=True)
            command.add_argument("--end-date", required=True)
            command.add_argument("--conversion-action", required=True)
            command.add_argument("--output", help="New CSV file; defaults to outputs/<unique>.csv")
        else:
            command.add_argument("--config", required=True)
        if name in ("validate", "create"):
            command.add_argument("--live", action="store_true", help="Contact Ads; create remains PAUSED")
        if name == "create":
            command.add_argument("--receipt", help="New receipt JSON; defaults to outputs/<unique>.json")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        customer, version = customer_id(args.customer), api_version(args.api_version)
        config = None
        if args.command == "report":
            report_queries(args.start_date, args.end_date, args.conversion_action)
        else:
            config = read_config(args.config)
            request = campaign_request(customer, config)
            if args.command == "plan" or not args.live:
                print(json.dumps({
                    "status": "offline-plan", "customer": customer, "apiVersion": version,
                    "currency": config["currency"], "request": request,
                }, ensure_ascii=False, indent=2))
                return 0
        client = GoogleAds(customer, version, AdsADCTransport())
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + secrets.token_hex(4)
        if args.command == "report":
            rows = client.report(args.start_date, args.end_date, args.conversion_action)
            output = Path(args.output) if args.output else Path("outputs") / f"google-ads-report-{stamp}.csv"
            write_report(output, rows)
            result = {"status": "exported", "output": str(output), "rows": len(rows)}
        elif args.command == "validate":
            result = client.validate(config)
        else:
            receipt = Path(args.receipt) if args.receipt else Path("outputs") / f"google-ads-created-{stamp}.json"
            # Check receipt destination before creating remote resources.
            receipt.parent.mkdir(parents=True, exist_ok=True)
            serialized_config = json.dumps(config, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            attempt = {
                "customer": customer, "apiVersion": version, "name": config["name"],
                "attemptedAt": datetime.now(timezone.utc).isoformat(),
                "configSha256": hashlib.sha256(serialized_config.encode("utf-8")).hexdigest(),
                "requestedConfig": config,
            }
            with receipt.open("x", encoding="utf-8") as handle:
                json.dump(dict(attempt, status="validation-pending"), handle)
            phase = "validation"

            def validated():
                nonlocal phase
                receipt.write_text(json.dumps(dict(attempt, status="creation-pending")) + "\n", encoding="utf-8")
                phase = "creation"

            try:
                result = client.create_paused(config, on_validated=validated)
            except AdsError as exc:
                status = "creation-outcome-unknown" if isinstance(exc, AdsCreationUnknown) else (
                    "creation-rejected" if phase == "creation" else "validation-failed"
                )
                try:
                    receipt.write_text(json.dumps(dict(attempt, status=status)) + "\n", encoding="utf-8")
                except OSError as receipt_error:
                    raise AdsError(f"{exc}\nCould not update failure receipt: {receipt_error}") from exc
                raise
            # Retain the actual reviewed request even if the config file is
            # edited later. This is reconciliation evidence, not an idempotency key.
            result = dict(attempt, **result)
            try:
                receipt.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            except OSError as exc:
                # Preserve confirmed resource IDs even if the local disk fails.
                print(json.dumps(dict(result, receipt=str(receipt), receiptSaved=False), ensure_ascii=False, indent=2))
                raise AdsError("Created paused resources, but could not save receipt. Inspect Google Ads before retrying.") from exc
            result["receipt"] = str(receipt)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (ValueError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except AdsError as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
