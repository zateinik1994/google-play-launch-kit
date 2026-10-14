#!/usr/bin/env python3
"""Reconcile and update existing App campaigns from an explicit reviewed plan.

Snapshot/reconcile are reads. Plan and apply without --live never load credentials.
Live updates validate first, check the saved preconditions twice, and read back.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import secrets
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    from .google_ads import (AdsADCTransport, AdsAPIError, AdsError, GoogleAds, GOAL,
                             INSTALL_GOAL, api_version, campaign_filter, customer_id, package_name)
except ImportError:
    from google_ads import (AdsADCTransport, AdsAPIError, AdsError, GoogleAds, GOAL,
                            INSTALL_GOAL, api_version, campaign_filter, customer_id, package_name)


class AdsUpdateUnknown(AdsError):
    pass


class AdsReadbackError(AdsError):
    """Mutation was confirmed but a subsequent read did not verify its result."""


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(",", ":")).encode("utf-8")).hexdigest()


def positive_micros(value, field):
    if not isinstance(value, int) or isinstance(value, bool) or not 0 < value <= 2**63 - 1:
        raise ValueError(f"{field} must be a positive int64 integer in account currency micros.")
    return value


def resource(value, customer, kind, *, compound=False):
    pattern = rf"customers/{customer}/{kind}/[1-9][0-9]*" + (r"~[1-9][0-9]*" if compound else "")
    if not isinstance(value, str) or not re.fullmatch(pattern, value):
        raise ValueError(f"Use an actual {kind} resource belonging to customer {customer}.")
    return value


def validate_update_config(config):
    if not isinstance(config, dict) or set(config) != {"package_name", "currency", "changes"}:
        raise ValueError("Update config requires exactly package_name, currency and changes.")
    package_name(config["package_name"])
    if not isinstance(config["currency"], str) or not re.fullmatch(r"[A-Z]{3}", config["currency"]):
        raise ValueError("currency must be the account currency.")
    if not isinstance(config["changes"], list) or not config["changes"]:
        raise ValueError("changes must be a non-empty list.")
    seen = set()
    allowed = {"campaign_id", "daily_budget_micros", "target_cpa_micros", "target_cpi_micros",
               "status", "ad_group_resources", "ad_group_ad_resources"}
    for change in config["changes"]:
        if not isinstance(change, dict) or set(change) - allowed or "campaign_id" not in change:
            raise ValueError("Invalid change fields or missing campaign_id.")
        campaign = str(change["campaign_id"])
        if not re.fullmatch(r"[1-9][0-9]*", campaign) or campaign in seen:
            raise ValueError("Campaign IDs must be positive and unique.")
        seen.add(campaign)
        if not set(change) & {"daily_budget_micros", "target_cpa_micros", "target_cpi_micros", "status"}:
            raise ValueError("Change needs a budget, target cost or status.")
        for field in ("daily_budget_micros", "target_cpa_micros", "target_cpi_micros"):
            if field in change:
                positive_micros(change[field], field)
        if "target_cpa_micros" in change and "target_cpi_micros" in change:
            raise ValueError("Specify target CPA or target CPI, not both.")
        if "status" in change:
            if not isinstance(change["status"], str) or change["status"] not in {"ENABLED", "PAUSED"}:
                raise ValueError("Status updates support only ENABLED or PAUSED.")
            for key in ("ad_group_resources", "ad_group_ad_resources"):
                if not isinstance(change.get(key), list) or any(not isinstance(item, str) for item in change[key]):
                    raise ValueError(f"Status changes require an explicit {key} list (possibly empty for campaign-only pause).")
                if len(change[key]) != len(set(change[key])):
                    raise ValueError(f"Duplicate resources in {key}.")
            if change["status"] == "ENABLED" and (not change["ad_group_resources"] or not change["ad_group_ad_resources"]):
                raise ValueError("Activation must select ad groups and ads explicitly.")
        elif set(change) & {"ad_group_resources", "ad_group_ad_resources"}:
            raise ValueError("Serving resources require an explicit status.")
    return config


def snapshot(client, package):
    package_name(package)
    account = client.account()
    suffix = (" WHERE campaign.advertising_channel_type = 'MULTI_CHANNEL'"
              " AND campaign.advertising_channel_sub_type IN ('APP_CAMPAIGN', 'APP_CAMPAIGN_FOR_ENGAGEMENT', 'APP_CAMPAIGN_FOR_PRE_REGISTRATION')"
              " AND campaign.status IN ('ENABLED', 'PAUSED', 'REMOVED')"
              + campaign_filter(package))
    campaigns = client.search(
        "SELECT campaign.resource_name, campaign.id, campaign.name, campaign.status, "
        "campaign.advertising_channel_type, campaign.advertising_channel_sub_type, "
        "campaign.app_campaign_setting.app_id, campaign.app_campaign_setting.app_store, "
        "campaign.app_campaign_setting.bidding_strategy_goal_type, campaign.campaign_budget, "
        "campaign.bidding_strategy_type, campaign.target_cpa.target_cpa_micros, "
        "campaign.target_roas.target_roas, campaign.selective_optimization.conversion_actions, "
        "campaign_budget.resource_name, campaign_budget.amount_micros, "
        "campaign_budget.explicitly_shared, campaign_budget.reference_count FROM campaign" + suffix)
    groups = client.search("SELECT campaign.id, ad_group.resource_name, ad_group.id, ad_group.name, ad_group.status "
                           "FROM ad_group" + suffix + " AND ad_group.status IN ('ENABLED', 'PAUSED', 'REMOVED')")
    ads = client.search("SELECT campaign.id, ad_group.resource_name, ad_group_ad.resource_name, "
                        "ad_group_ad.status, ad_group_ad.ad.id, ad_group_ad.ad.type, "
                        "ad_group_ad.policy_summary.approval_status FROM ad_group_ad" + suffix + " AND ad_group_ad.status IN ('ENABLED', 'PAUSED', 'REMOVED')")
    result = {"customer": client.customer, "apiVersion": client.version, "package": package,
              "fetchedAt": datetime.now(timezone.utc).isoformat(), "source": "Google Ads API",
              "account": account, "campaigns": {}, "adGroups": {}, "adGroupAds": {}}
    for row in campaigns:
        campaign = row.get("campaign", {})
        if not isinstance(campaign, dict) or not re.fullmatch(r"[1-9][0-9]*", str(campaign.get("id", ""))):
            raise AdsError("Invalid campaign snapshot response.")
        key = str(campaign["id"])
        if key in result["campaigns"]:
            raise AdsError("Duplicate campaign in snapshot.")
        setting = campaign.get("appCampaignSetting")
        if not isinstance(setting, dict) or campaign.get("resourceName") != f"customers/{client.customer}/campaigns/{key}" or setting.get("appId") != package or setting.get("appStore") != "GOOGLE_APP_STORE":
            raise AdsError("Campaign snapshot resource/app identity differs from the requested scope.")
        if not isinstance(row.get("campaignBudget", {}), dict):
            raise AdsError("Campaign snapshot has an invalid budget object.")
        result["campaigns"][key] = row
    for rows, collection, field in ((groups, "adGroups", "adGroup"), (ads, "adGroupAds", "adGroupAd")):
        for row in rows:
            value, owner = row.get(field), row.get("campaign")
            if not isinstance(value, dict) or not isinstance(owner, dict):
                raise AdsError("Invalid serving resource/campaign object in snapshot.")
            name = value.get("resourceName")
            if not isinstance(name, str) or name in result[collection]:
                raise AdsError("Invalid or duplicate serving resource in snapshot.")
            campaign_id_value = str(owner.get("id", ""))
            if campaign_id_value not in result["campaigns"]:
                raise AdsError("Serving resource belongs to an unverified campaign in the app snapshot.")
            if field == "adGroup":
                group_id = str(row[field].get("id", ""))
                if not re.fullmatch(r"[1-9][0-9]*", group_id) or name != f"customers/{client.customer}/adGroups/{group_id}":
                    raise AdsError("Ad group snapshot did not confirm its customer/resource ID.")
            else:
                group_value, ad_value = row.get("adGroup"), value.get("ad")
                if not isinstance(group_value, dict) or not isinstance(ad_value, dict):
                    raise AdsError("Ad snapshot has an invalid parent/ad object.")
                group = group_value.get("resourceName")
                if not isinstance(group, str):
                    raise AdsError("Ad snapshot has an invalid parent resource name.")
                parent = result["adGroups"].get(group)
                ad_id = str(ad_value.get("id", ""))
                if not parent or str(parent.get("campaign", {}).get("id", "")) != campaign_id_value or not re.fullmatch(r"[1-9][0-9]*", ad_id) or name != f"{group.split('/adGroups/')[0]}/adGroupAds/{group.rsplit('/', 1)[-1]}~{ad_id}":
                    raise AdsError("Ad snapshot did not confirm its customer/parent/resource ID.")
            result[collection][name] = row
    return result


def plan_changes(config, current):
    validate_update_config(config)
    if not isinstance(current, dict):
        raise ValueError("Current snapshot must be a JSON object.")
    if current.get("status") == "reconciled" and isinstance(current.get("current"), dict):
        current = current["current"]
    customer, version = customer_id(current.get("customer")), api_version(current.get("apiVersion"))
    if current.get("package") != config["package_name"] or current.get("account", {}).get("currencyCode") != config["currency"]:
        raise ValueError("Snapshot package/currency differs from the requested change.")
    operations, diff, before, desired = [], [], {}, {}

    def operation(kind, name, path, old, new, body):
        key = name + ":" + path
        before[key], desired[key] = old, new
        if old != new:
            existing = next((item[kind] for item in operations if kind in item and item[kind]["update"]["resourceName"] == name), None)
            if existing is None:
                operations.append({kind: {"update": dict(resourceName=name, **body), "updateMask": path}})
            else:
                existing["update"].update(body)
                existing["updateMask"] += "," + path
            diff.append({"resource": name, "field": path, "from": old, "to": new})

    for change in config["changes"]:
        cid = str(change["campaign_id"])
        row = current.get("campaigns", {}).get(cid)
        if not isinstance(row, dict) or not isinstance(row.get("campaign"), dict):
            raise ValueError(f"Campaign {cid} is absent from the selected app snapshot.")
        campaign = row["campaign"]
        name = resource(campaign.get("resourceName"), customer, "campaigns")
        setting = campaign.get("appCampaignSetting", {})
        if setting.get("appId") != config["package_name"] or setting.get("appStore") != "GOOGLE_APP_STORE":
            raise ValueError("Campaign belongs to a different app/store.")
        if campaign.get("status") == "REMOVED":
            raise ValueError("Removed campaigns cannot be updated or reactivated.")
        # Identity, strategy and budget ownership are preconditions even when only
        # one selected field changes. A stale plan never overwrites unseen edits.
        before[name + ":identity"] = {key: campaign.get(key) for key in
                                     ("appCampaignSetting", "campaignBudget", "biddingStrategyType", "status",
                                      "targetCpa", "targetRoas", "selectiveOptimization")}
        before[name + ":budget"] = row.get("campaignBudget", {})
        if "daily_budget_micros" in change:
            budget = row.get("campaignBudget", {})
            budget_name = resource(budget.get("resourceName"), customer, "campaignBudgets")
            if campaign.get("campaignBudget") != budget_name or budget.get("explicitlyShared", False) is not False or str(budget.get("referenceCount")) != "1":
                raise ValueError("Refusing a shared/multi-campaign or unverified budget mutation.")
            before[budget_name + ":ownership"] = {"explicitlyShared": budget.get("explicitlyShared", False), "referenceCount": str(budget["referenceCount"])}
            old = str(budget.get("amountMicros", ""))
            if not re.fullmatch(r"[1-9][0-9]*", old):
                raise ValueError("Missing current budget amount.")
            amount = str(change["daily_budget_micros"])
            operation("campaignBudgetOperation", budget_name, "amount_micros", old, amount, {"amountMicros": amount})
        target_field = next((field for field in ("target_cpa_micros", "target_cpi_micros") if field in change), None)
        if target_field:
            expected_goal = INSTALL_GOAL if target_field == "target_cpi_micros" else GOAL
            if setting.get("biddingStrategyGoalType") != expected_goal or campaign.get("biddingStrategyType") != "TARGET_CPA":
                raise ValueError("Target CPI/CPA must match the existing goal and TARGET_CPA strategy; strategy switching is not implicit.")
            old = str(campaign.get("targetCpa", {}).get("targetCpaMicros", ""))
            if not re.fullmatch(r"[1-9][0-9]*", old):
                raise ValueError("Missing current target cost.")
            target = str(change[target_field])
            operation("campaignOperation", name, "target_cpa.target_cpa_micros", old, target, {"targetCpa": {"targetCpaMicros": target}})
        if "status" in change:
            status = change["status"]
            operation("campaignOperation", name, "status", campaign.get("status"), status, {"status": status})
            selected_groups = set(change["ad_group_resources"])
            groups_with_ads = set()
            for group in sorted(selected_groups):
                resource(group, customer, "adGroups")
                item = current.get("adGroups", {}).get(group)
                if not item or str(item.get("campaign", {}).get("id")) != cid:
                    raise ValueError("Selected ad group does not belong to the selected campaign.")
                group_status = item["adGroup"].get("status")
                if group_status == "REMOVED":
                    raise ValueError("Removed ad groups cannot be reactivated.")
                operation("adGroupOperation", group, "status", group_status, status, {"status": status})
            for ad in change["ad_group_ad_resources"]:
                resource(ad, customer, "adGroupAds", compound=True)
                item = current.get("adGroupAds", {}).get(ad)
                if not item or str(item.get("campaign", {}).get("id")) != cid or item.get("adGroup", {}).get("resourceName") not in selected_groups:
                    raise ValueError("Selected ad does not belong to a selected ad group/campaign.")
                groups_with_ads.add(item["adGroup"]["resourceName"])
                ad_status = item["adGroupAd"].get("status")
                if ad_status == "REMOVED":
                    raise ValueError("Removed ads cannot be reactivated.")
                before[ad + ":policy"] = item["adGroupAd"].get("policySummary", {})
                operation("adGroupAdOperation", ad, "status", ad_status, status, {"status": status})
            if status == "ENABLED" and selected_groups != groups_with_ads:
                raise ValueError("Activation requires at least one explicitly selected ad in each selected group.")
            if status == "ENABLED":
                # Enabling a parent can start already-enabled descendants even
                # without updating them. Require those ads in the reviewed scope.
                selected_ads = set(change["ad_group_ad_resources"])
                for ad_name, item in current.get("adGroupAds", {}).items():
                    if str(item.get("campaign", {}).get("id")) != cid:
                        continue
                    group_name = item.get("adGroup", {}).get("resourceName")
                    group_row = current.get("adGroups", {}).get(group_name, {})
                    group_enabled = group_name in selected_groups or group_row.get("adGroup", {}).get("status") == "ENABLED"
                    ad_enabled = ad_name in selected_ads or item.get("adGroupAd", {}).get("status") == "ENABLED"
                    if group_enabled and ad_enabled and (group_name not in selected_groups or ad_name not in selected_ads):
                        raise ValueError("Activation would serve an unselected enabled ad/group; include it in the plan or pause it first.")
    return {"status": "offline-plan", "customer": customer, "apiVersion": version,
            "config": config, "configSha256": digest(config), "before": before,
            "preconditionSha256": digest(before), "desired": desired, "changes": diff,
            "request": {"mutateOperations": operations, "partialFailure": False, "validateOnly": True,
                        "responseContentType": "RESOURCE_NAME_ONLY"},
            "warnings": ["ENABLED can start spend; target costs and average daily budgets are not experiment caps.",
                         "Live checks reduce stale-plan risk; Google Ads has no compare-and-swap transaction for these reads."]}


def check_saved_plan(plan):
    if not isinstance(plan, dict) or not isinstance(plan.get("config"), dict):
        raise ValueError("Use a plan produced by ads_manage plan.")
    validate_update_config(plan["config"])
    customer_id(plan.get("customer"))
    api_version(plan.get("apiVersion"))
    if plan.get("configSha256") != digest(plan["config"]) or plan.get("preconditionSha256") != digest(plan.get("before")):
        raise ValueError("Plan digest differs from config/preconditions; regenerate the plan.")


def fresh_plan(client, saved):
    check_saved_plan(saved)
    if client.customer != saved["customer"] or client.version != saved["apiVersion"]:
        raise ValueError("Client differs from reviewed plan account/version.")
    current = snapshot(client, saved["config"]["package_name"])
    fresh = plan_changes(saved["config"], current)
    if fresh["preconditionSha256"] != saved["preconditionSha256"]:
        raise AdsError("Account state changed since planning. Reconcile and review a new plan; no mutation sent.")
    if fresh["request"] != saved.get("request") or fresh["desired"] != saved.get("desired"):
        raise ValueError("Saved request differs from the rebuilt typed plan.")
    return fresh, current


def mutate_checked(client, request):
    response = client.transport.request("POST", client.root + ":mutate", payload=request)
    if response.get("partialFailureError"):
        raise AdsError("Unexpected partial failure in atomic mutate.")
    return response


def execute_plan(client, saved, *, live=False, receipt_writer=None):
    check_saved_plan(saved)
    if not live:
        return saved
    fresh, current = fresh_plan(client, saved)
    attempt = {"customer": client.customer, "apiVersion": client.version,
               "attemptedAt": datetime.now(timezone.utc).isoformat(), "requestedConfig": saved["config"],
               "configSha256": saved["configSha256"], "planSha256": digest(saved), "before": current}
    def record(status, **extra):
        result = dict(attempt, status=status, **extra)
        if receipt_writer:
            receipt_writer(result)
        return result
    if not fresh["request"]["mutateOperations"]:
        return record("unchanged", after=current)
    record("validation-pending")
    try:
        mutate_checked(client, fresh["request"])
        # validateOnly cannot prevent a human changing fields while it runs.
        fresh, _ = fresh_plan(client, saved)
    except (AdsError, ValueError):
        record("validation-failed")
        raise
    record("mutation-pending")  # Persist before any external write.
    request = dict(fresh["request"], validateOnly=False)
    try:
        response = mutate_checked(client, request)
        responses = response.get("mutateOperationResponses")
        if not isinstance(responses, list) or len(responses) != len(request["mutateOperations"]):
            raise AdsError("Mutation response did not confirm every operation.")
        for expected, actual in zip(request["mutateOperations"], responses):
            result_kind = {"campaignBudgetOperation": "campaignBudgetResult", "campaignOperation": "campaignResult",
                           "adGroupOperation": "adGroupResult", "adGroupAdOperation": "adGroupAdResult"}[next(iter(expected))]
            expected_name = next(iter(expected.values()))["update"]["resourceName"]
            detail = actual.get(result_kind) if isinstance(actual, dict) and len(actual) == 1 else None
            if not isinstance(detail, dict) or detail.get("resourceName") != expected_name:
                raise AdsError("Mutation result did not confirm the requested resource.")
    except AdsError as exc:
        unknown = not isinstance(exc, AdsAPIError) or exc.status == 408 or exc.status >= 500
        record("mutation-outcome-unknown" if unknown else "mutation-rejected")
        if unknown:
            raise AdsUpdateUnknown("Update outcome is unknown. Inspect Ads and receipt before retrying; no automatic retry.") from exc
        raise
    confirmed = record("mutated-readback-pending", resources=[item["resource"] for item in fresh["changes"]])
    try:
        after = snapshot(client, saved["config"]["package_name"])
        readback = plan_changes(saved["config"], after)
        if readback["request"]["mutateOperations"]:
            return record("mutated-readback-mismatch", after=after, remainingChanges=readback["changes"])
    except (AdsError, ValueError) as exc:
        record("mutated-readback-failed", confirmed=confirmed)
        raise AdsReadbackError("Mutation confirmed, but read-back failed. Inspect Ads; do not repeat the mutation blindly.") from exc
    return record("updated-verified", after=after)


def write_new(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("snapshot", "reconcile"):
        command = commands.add_parser(name)
        command.add_argument("--customer", required=True)
        command.add_argument("--api-version", required=True)
        command.add_argument("--package", required=True)
        command.add_argument("--output", required=True)
        if name == "reconcile":
            command.add_argument("--expected", required=True, help="Previously saved snapshot")
    plan = commands.add_parser("plan")
    plan.add_argument("--config", required=True)
    plan.add_argument("--current", required=True)
    plan.add_argument("--output", required=True)
    for name in ("validate", "apply"):
        command = commands.add_parser(name)
        command.add_argument("--plan", required=True)
        command.add_argument("--live", action="store_true")
        if name == "apply":
            command.add_argument("--receipt")
    args = parser.parse_args(argv)
    def read(path):
        return json.loads(Path(path).read_text(encoding="utf-8"))
    try:
        if args.command == "plan":
            result = plan_changes(read(args.config), read(args.current))
            write_new(args.output, result)
        elif args.command in ("snapshot", "reconcile"):
            customer_id(args.customer); api_version(args.api_version); package_name(args.package)
            expected = read(args.expected) if args.command == "reconcile" else None
            if Path(args.output).exists():
                raise FileExistsError(args.output)
            client = GoogleAds(args.customer, args.api_version, AdsADCTransport())
            actual = snapshot(client, args.package)
            if expected is not None:
                if expected.get("customer") != client.customer or expected.get("package") != args.package:
                    raise ValueError("Expected snapshot belongs to a different customer/package.")
                drift = []
                for kind in ("account", "campaigns", "adGroups", "adGroupAds"):
                    if expected.get(kind) != actual[kind]:
                        drift.append({"section": kind, "expected": expected.get(kind), "actual": actual[kind]})
                result = {"status": "reconciled", "drift": drift, "current": actual}
            else:
                result = actual
            write_new(args.output, result)
        else:
            saved = read(args.plan)
            check_saved_plan(saved)
            if not args.live:
                result = saved
            else:
                client = GoogleAds(saved["customer"], saved["apiVersion"], AdsADCTransport())
                if args.command == "validate":
                    fresh, current = fresh_plan(client, saved)
                    if fresh["request"]["mutateOperations"]:
                        mutate_checked(client, fresh["request"])
                    result = {"status": "validated-only", "current": current, "planSha256": digest(saved)}
                else:
                    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + secrets.token_hex(4)
                    receipt = Path(args.receipt or f"outputs/google-ads-updated-{stamp}.json")
                    write_new(receipt, {"status": "preflight-pending", "planSha256": digest(saved), "plan": saved})
                    def writer(value):
                        try:
                            receipt.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                        except OSError as exc:
                            print(json.dumps(dict(value, receiptSaved=False), ensure_ascii=False))
                            raise AdsError("Could not save receipt; inspect the reported stage before retrying.") from exc
                    result = execute_plan(client, saved, live=True, receipt_writer=writer)
                    result["receipt"] = str(receipt)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1 if result.get("status") == "mutated-readback-mismatch" else 0
    except (OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr); return 2
    except AdsError as exc:
        print(str(exc), file=sys.stderr); return 1


if __name__ == "__main__":
    raise SystemExit(main())
