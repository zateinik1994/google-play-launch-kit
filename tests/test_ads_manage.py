"""No-network tests for planned Ads updates, reconciliation and read-back."""
import contextlib
import copy
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from shared.google_ads import AdsAPIError, AdsError, GoogleAds, GOAL, INSTALL_GOAL
from shared.ads_manage import (AdsReadbackError, AdsUpdateUnknown, execute_plan, main,
                               plan_changes, snapshot, validate_update_config)

CUSTOMER = "1234567890"
BASE = f"customers/{CUSTOMER}"
CAMPAIGN, BUDGET, GROUP, AD = (f"{BASE}/{kind}/{number}" for kind, number in
                              (("campaigns", "77"), ("campaignBudgets", "88"), ("adGroups", "99"), ("adGroupAds", "99~111")))
ACCOUNT = {"id": CUSTOMER, "currencyCode": "USD", "timeZone": "America/New_York",
           "conversionTrackingSetting": {"googleAdsConversionCustomer": f"customers/{CUSTOMER}"}}


def state():
    return {"customer": CUSTOMER, "apiVersion": "v25", "package": "com.example.focus", "account": copy.deepcopy(ACCOUNT),
            "campaigns": {"77": {"campaign": {
                "resourceName": CAMPAIGN, "id": "77", "name": "Focus US", "status": "PAUSED",
                "advertisingChannelType": "MULTI_CHANNEL", "advertisingChannelSubType": "APP_CAMPAIGN",
                "appCampaignSetting": {"appId": "com.example.focus", "appStore": "GOOGLE_APP_STORE", "biddingStrategyGoalType": GOAL},
                "campaignBudget": BUDGET, "biddingStrategyType": "TARGET_CPA",
                "targetCpa": {"targetCpaMicros": "5000000"},
                "selectiveOptimization": {"conversionActions": [f"{BASE}/conversionActions/123"]}},
                "campaignBudget": {"resourceName": BUDGET, "amountMicros": "50000000", "referenceCount": "1", "explicitlyShared": False}}},
            "adGroups": {GROUP: {"campaign": {"id": "77"}, "adGroup": {"resourceName": GROUP, "id": "99", "status": "PAUSED"}}},
            "adGroupAds": {AD: {"campaign": {"id": "77"}, "adGroup": {"resourceName": GROUP},
                                "adGroupAd": {"resourceName": AD, "status": "PAUSED", "ad": {"id": "111", "type": "APP_AD"},
                                              "policySummary": {"approvalStatus": "APPROVED"}}}}}


def config(**changes):
    return {"package_name": "com.example.focus", "currency": "USD", "changes": [dict(campaign_id="77", **changes)]}


class FakeManage:
    def __init__(self, current=None, *, validation_error=None, live_error=None, no_apply=False, on_validate=None, readback_error=False):
        self.current = copy.deepcopy(current or state())
        self.validation_error, self.live_error, self.on_validate = validation_error, live_error, on_validate
        self.no_apply, self.readback_error, self.did_mutate = no_apply, readback_error, False
        self.calls = []

    def request(self, method, url, *, payload):
        self.calls.append((method, url, copy.deepcopy(payload)))
        if url.endswith(":search"):
            if self.readback_error and self.did_mutate:
                raise AdsError("Read unavailable")
            query = payload["query"]
            if " FROM customer " in query:
                return {"results": [{"customer": self.current["account"]}]}
            for table, collection in (("ad_group_ad", "adGroupAds"), ("ad_group", "adGroups"), ("campaign", "campaigns")):
                if f" FROM {table} " in query:
                    return {"results": copy.deepcopy(list(self.current[collection].values()))}
            raise AssertionError(query)
        if payload["validateOnly"]:
            if self.validation_error:
                raise self.validation_error
            if self.on_validate:
                self.on_validate(self.current)
            return {}
        self.did_mutate = True
        if self.live_error:
            raise self.live_error
        responses = []
        for operation in payload["mutateOperations"]:
            kind, detail = next(iter(operation.items()))
            update = detail["update"]
            name = update["resourceName"]
            if kind == "campaignBudgetOperation":
                target = self.current["campaigns"]["77"]["campaignBudget"]
                result_kind = "campaignBudgetResult"
            elif kind == "campaignOperation":
                target = self.current["campaigns"]["77"]["campaign"]
                result_kind = "campaignResult"
            elif kind == "adGroupOperation":
                target = self.current["adGroups"][name]["adGroup"]
                result_kind = "adGroupResult"
            else:
                target = self.current["adGroupAds"][name]["adGroupAd"]
                result_kind = "adGroupAdResult"
            if not self.no_apply:
                target.update(update)
            responses.append({result_kind: {"resourceName": name}})
        return {"mutateOperationResponses": responses}


def client(fake):
    return GoogleAds(CUSTOMER, "v25", fake)


class Plans(unittest.TestCase):
    def test_exact_field_masks_and_all_selected_serving_resources(self):
        plan = plan_changes(config(daily_budget_micros=60000000, target_cpa_micros=6000000,
                                   status="ENABLED", ad_group_resources=[GROUP], ad_group_ad_resources=[AD]), state())
        operations = plan["request"]["mutateOperations"]
        self.assertEqual(len(operations), 4)
        self.assertEqual(operations[0]["campaignBudgetOperation"]["updateMask"], "amount_micros")
        self.assertEqual(operations[1]["campaignOperation"]["updateMask"], "target_cpa.target_cpa_micros,status")
        self.assertEqual(operations[1]["campaignOperation"]["update"]["targetCpa"], {"targetCpaMicros": "6000000"})
        for operation in operations[1:]:
            self.assertEqual(next(iter(operation.values()))["update"]["status"], "ENABLED")
        self.assertTrue(plan["request"]["validateOnly"])
        self.assertFalse(plan["request"]["partialFailure"])

    def test_shared_and_unverified_budgets_refused(self):
        for overrides in ({"explicitlyShared": True}, {"referenceCount": "2"}, {"referenceCount": None}):
            current = state()
            current["campaigns"]["77"]["campaignBudget"].update(overrides)
            with self.assertRaisesRegex(ValueError, "shared/multi-campaign"):
                plan_changes(config(daily_budget_micros=60000000), current)

    def test_target_cpi_only_matches_install_goal(self):
        with self.assertRaisesRegex(ValueError, "match the existing goal"):
            plan_changes(config(target_cpi_micros=2000000), state())
        current = state()
        current["campaigns"]["77"]["campaign"]["appCampaignSetting"]["biddingStrategyGoalType"] = INSTALL_GOAL
        self.assertEqual(plan_changes(config(target_cpi_micros=2000000), current)["changes"][0]["to"], "2000000")
        with self.assertRaises(ValueError):
            plan_changes(config(target_cpa_micros=2000000), current)

    def test_activation_needs_explicit_children_and_membership(self):
        for change in (dict(status="ENABLED"), dict(status="ENABLED", ad_group_resources=[], ad_group_ad_resources=[]),
                       dict(status="ENABLED", ad_group_resources=[GROUP], ad_group_ad_resources=[f"{BASE}/adGroupAds/1~2"])):
            with self.subTest(change=change), self.assertRaises(ValueError):
                plan_changes(config(**change), state())

    def test_status_pause_can_select_campaign_only_without_enabling_anything(self):
        current = state()
        current["campaigns"]["77"]["campaign"]["status"] = "ENABLED"
        plan = plan_changes(config(status="PAUSED", ad_group_resources=[], ad_group_ad_resources=[]), current)
        self.assertEqual(len(plan["request"]["mutateOperations"]), 1)

    def test_activation_cannot_wake_an_unselected_already_enabled_ad(self):
        current = state()
        other_ad = f"{BASE}/adGroupAds/99~222"
        current["adGroupAds"][other_ad] = copy.deepcopy(current["adGroupAds"][AD])
        current["adGroupAds"][other_ad]["adGroupAd"].update(resourceName=other_ad, status="ENABLED")
        with self.assertRaisesRegex(ValueError, "unselected enabled"):
            plan_changes(config(status="ENABLED", ad_group_resources=[GROUP], ad_group_ad_resources=[AD]), current)
        self.assertTrue(plan_changes(config(status="ENABLED", ad_group_resources=[GROUP], ad_group_ad_resources=[AD, other_ad]), current))

    def test_other_app_removed_resource_and_wrong_currency_refused(self):
        cases = []
        current = state(); current["campaigns"]["77"]["campaign"]["status"] = "REMOVED"; cases.append(current)
        current = state(); current["campaigns"]["77"]["campaign"]["appCampaignSetting"]["appId"] = "com.other.app"; cases.append(current)
        current = state(); current["account"]["currencyCode"] = "TRY"; cases.append(current)
        for current in cases:
            with self.assertRaises(ValueError):
                plan_changes(config(daily_budget_micros=60000000), current)

    def test_malformed_unknown_and_boolean_fields_block_before_io(self):
        for value in (config(daily_budget_micros=True), config(status=[]), config(keywords=["focus"]),
                      config(target_cpa_micros=4, target_cpi_micros=3), {}, None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_update_config(value)

    def test_noop_plan_has_no_mutation_operations(self):
        self.assertEqual(plan_changes(config(daily_budget_micros=50000000), state())["request"]["mutateOperations"], [])


class LiveExecution(unittest.TestCase):
    def test_snapshot_has_package_bids_budget_and_child_statuses(self):
        fake = FakeManage()
        result = snapshot(client(fake), "com.example.focus")
        self.assertEqual(result["account"]["timeZone"], "America/New_York")
        self.assertEqual(result["campaigns"]["77"]["campaign"]["targetCpa"]["targetCpaMicros"], "5000000")
        self.assertEqual(result["adGroupAds"][AD]["adGroupAd"]["status"], "PAUSED")
        for _, _, payload in fake.calls[1:]:
            self.assertIn("com.example.focus", payload["query"])

    def test_validate_atomic_mutate_and_verified_readback(self):
        fake, records = FakeManage(), []
        saved = plan_changes(config(daily_budget_micros=60000000, target_cpa_micros=6000000), state())
        result = execute_plan(client(fake), saved, live=True, receipt_writer=lambda value: records.append(copy.deepcopy(value)))
        self.assertEqual(result["status"], "updated-verified")
        mutates = [item[2] for item in fake.calls if item[1].endswith(":mutate")]
        self.assertEqual([item["validateOnly"] for item in mutates], [True, False])
        self.assertTrue(all(item["partialFailure"] is False for item in mutates))
        self.assertEqual([item["status"] for item in records], ["validation-pending", "mutation-pending", "mutated-readback-pending", "updated-verified"])
        self.assertEqual(result["before"]["campaigns"]["77"]["campaignBudget"]["amountMicros"], "50000000")
        self.assertEqual(result["after"]["campaigns"]["77"]["campaignBudget"]["amountMicros"], "60000000")

    def test_drift_before_or_during_validation_never_mutates(self):
        saved = plan_changes(config(daily_budget_micros=60000000), state())
        current = state(); current["campaigns"]["77"]["campaign"]["targetCpa"]["targetCpaMicros"] = "9000000"
        fake = FakeManage(current)
        with self.assertRaisesRegex(AdsError, "state changed"):
            execute_plan(client(fake), saved, live=True)
        self.assertFalse(any(item[1].endswith(":mutate") for item in fake.calls))
        fake = FakeManage(on_validate=lambda data: data["campaigns"]["77"]["campaignBudget"].update(amountMicros="70000000"))
        with self.assertRaisesRegex(AdsError, "state changed"):
            execute_plan(client(fake), saved, live=True)
        self.assertFalse(fake.did_mutate)

    def test_validation_failure_never_updates(self):
        fake = FakeManage(validation_error=AdsAPIError(400, "Invalid target"))
        with self.assertRaises(AdsAPIError):
            execute_plan(client(fake), plan_changes(config(target_cpa_micros=6000000), state()), live=True)
        self.assertFalse(fake.did_mutate)

    def test_unknown_update_is_not_retried_and_receipt_is_explicit(self):
        for error in (AdsError("Timeout"), AdsAPIError(503, "Unavailable"), AdsAPIError(408, "Timeout")):
            fake, records = FakeManage(live_error=error), []
            with self.assertRaises(AdsUpdateUnknown):
                execute_plan(client(fake), plan_changes(config(target_cpa_micros=6000000), state()), live=True,
                             receipt_writer=records.append)
            self.assertEqual(records[-1]["status"], "mutation-outcome-unknown")
            self.assertEqual(len([item for item in fake.calls if item[1].endswith(":mutate")]), 2)

    def test_readback_failure_keeps_confirmed_mutation_stage(self):
        fake, records = FakeManage(readback_error=True), []
        with self.assertRaises(AdsReadbackError):
            execute_plan(client(fake), plan_changes(config(target_cpa_micros=6000000), state()), live=True,
                         receipt_writer=records.append)
        self.assertEqual(records[-1]["status"], "mutated-readback-failed")
        self.assertEqual(fake.current["campaigns"]["77"]["campaign"]["targetCpa"]["targetCpaMicros"], "6000000")

    def test_readback_mismatch_is_not_success(self):
        fake = FakeManage(no_apply=True)
        result = execute_plan(client(fake), plan_changes(config(target_cpa_micros=6000000), state()), live=True)
        self.assertEqual(result["status"], "mutated-readback-mismatch")

    def test_noop_receipt_records_completion_without_mutation(self):
        fake, records = FakeManage(), []
        result = execute_plan(client(fake), plan_changes(config(target_cpa_micros=5000000), state()),
                              live=True, receipt_writer=records.append)
        self.assertEqual(result["status"], "unchanged")
        self.assertEqual(records[-1]["status"], "unchanged")
        self.assertFalse(any(call[1].endswith(":mutate") for call in fake.calls))

    def test_receipt_failure_before_mutate_blocks_external_write(self):
        fake = FakeManage()
        def writer(value):
            if value["status"] == "mutation-pending":
                raise OSError("Disk full")
        with self.assertRaises(OSError):
            execute_plan(client(fake), plan_changes(config(target_cpa_micros=6000000), state()), live=True, receipt_writer=writer)
        self.assertFalse(fake.did_mutate)

    def test_tampered_payload_cannot_expand_typed_scope(self):
        saved = plan_changes(config(target_cpa_micros=6000000), state())
        saved["request"]["mutateOperations"][0]["campaignOperation"]["update"]["name"] = "Unexpected"
        with self.assertRaisesRegex(ValueError, "rebuilt typed plan"):
            execute_plan(client(FakeManage()), saved, live=True)

    def test_apply_default_is_offline_and_keeps_credentials_unloaded(self):
        with tempfile.TemporaryDirectory() as directory:
            saved = Path(directory) / "plan.json"
            saved.write_text(json.dumps(plan_changes(config(target_cpa_micros=6000000), state())))
            with patch("shared.ads_manage.AdsADCTransport", side_effect=AssertionError("Offline")):
                with contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(main(["apply", "--plan", str(saved)]), 0)


if __name__ == "__main__":
    unittest.main()
