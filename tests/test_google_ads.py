"""No-network tests for the Ads REST schema, atomic creation, and CSV joins."""

import contextlib
import copy
import hashlib
import csv
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from shared.google_ads import (
    ADS_FIELDS, GOAL, INSTALL_GOAL, AdsADCTransport, AdsAPIError, AdsError, GoogleAds, campaign_request,
    customer_id, main, normalize_report, report_queries, dimension_queries, keyword_ideas_request, validate_config, write_report,
)


CUSTOMER = "1234567890"
ACTION = f"customers/{CUSTOMER}/conversionActions/987654321"
CONFIG = {
    "name": "Focus US", "package_name": "com.example.focus", "currency": "USD",
    "daily_budget_micros": 50000000, "target_cpa_micros": 5000000,
    "conversion_action": ACTION, "country_resources": ["geoTargetConstants/2840"],
    "language_resources": ["languageConstants/1000"],
    "headlines": ["Build a focus routine"], "descriptions": ["Start your next focus session."],
    "contains_eu_political_advertising": False,
}


class FakeAdsTransport:
    def __init__(self, *, currency="USD", target_type="Country", fail_validation=False, creation_error=None, malformed_create=False):
        self.calls = []
        self.currency = currency
        self.target_type = target_type
        self.fail_validation = fail_validation
        self.creation_error = creation_error
        self.malformed_create = malformed_create

    def request(self, method, url, *, payload):
        self.calls.append((method, url, copy.deepcopy(payload)))
        if url.endswith(":search"):
            if "FROM geo_target_constant" in payload["query"]:
                return {"results": [{"geoTargetConstant": {
                    "resourceName": "geoTargetConstants/2840", "targetType": self.target_type, "status": "ENABLED",
                }}]}
            return {"results": [{"customer": {"currencyCode": self.currency}}]}
        if payload["validateOnly"]:
            if self.fail_validation:
                raise AdsAPIError(400, "Invalid conversion action")
            return {}
        if self.creation_error:
            raise self.creation_error
        if self.malformed_create:
            return {}
        responses = []
        mapping = {
            "campaignBudgetOperation": ("campaignBudgetResult", "campaignBudgets"),
            "campaignOperation": ("campaignResult", "campaigns"),
            "campaignCriterionOperation": ("campaignCriterionResult", "campaignCriteria"),
            "adGroupOperation": ("adGroupResult", "adGroups"),
            "adGroupAdOperation": ("adGroupAdResult", "adGroupAds"),
        }
        for number, operation in enumerate(payload["mutateOperations"], 1):
            key = next(iter(operation))
            result, kind = mapping[key]
            identifier = f"2~{number}" if kind == "campaignCriteria" else f"{len(payload['mutateOperations']) - 1}~{number}" if kind == "adGroupAds" else str(number)
            responses.append({result: {"resourceName": f"customers/{CUSTOMER}/{kind}/{identifier}"}})
        return {"mutateOperationResponses": responses}


class CampaignTests(unittest.TestCase):
    def test_creation_response_rejects_wrong_customer_type_and_parent_as_unknown(self):
        transformations = (
            lambda responses: responses[0]["campaignBudgetResult"].update(resourceName="customers/9999999999/campaignBudgets/1"),
            lambda responses: responses[1].update(adGroupResult=responses[1].pop("campaignResult")),
            lambda responses: responses[-1]["adGroupAdResult"].update(resourceName=f"customers/{CUSTOMER}/adGroupAds/999~6"),
        )
        for transform in transformations:
            fake = FakeAdsTransport()
            original = fake.request
            def request(method, url, *, payload):
                result = original(method, url, payload=payload)
                if url.endswith(":mutate") and payload.get("validateOnly") is False:
                    transform(result["mutateOperationResponses"])
                return result
            fake.request = request
            from shared.google_ads import AdsCreationUnknown
            with self.subTest(transform=transform), self.assertRaises(AdsCreationUnknown):
                GoogleAds(CUSTOMER, "v25", fake).create_paused(CONFIG)
            self.assertEqual(sum(call[1].endswith(":mutate") and call[2].get("validateOnly") is False for call in fake.calls), 1)

    def test_authenticated_transport_rejects_redirect_without_forwarding_tokens(self):
        from types import SimpleNamespace
        calls = []
        def request(method, url, **kwargs):
            calls.append((method, url, kwargs))
            self.assertFalse(kwargs.get("allow_redirects", True))
            return SimpleNamespace(status_code=302, content=b"", headers={"Location": "https://outside.example/"})
        transport = AdsADCTransport.__new__(AdsADCTransport)
        transport.session = SimpleNamespace(request=request)
        transport.timeout = 1
        transport.headers = {"developer-token": "fixture-token", "login-customer-id": CUSTOMER}
        with self.assertRaises(AdsAPIError) as failure:
            transport.request("POST", "https://googleads.googleapis.com/v25/customers/1234567890/googleAds:mutate", payload={"validateOnly": True})
        self.assertEqual(failure.exception.status, 302)
        self.assertEqual(len(calls), 1)
        self.assertNotIn("fixture-token", str(failure.exception))

    def test_install_volume_is_a_distinct_explicit_goal(self):
        config = dict(CONFIG, goal="install-volume", target_cpi_micros=1500000)
        del config["target_cpa_micros"]
        del config["conversion_action"]
        campaign = campaign_request(CUSTOMER, config)["mutateOperations"][1]["campaignOperation"]["create"]
        self.assertEqual(campaign["appCampaignSetting"]["biddingStrategyGoalType"], INSTALL_GOAL)
        self.assertEqual(campaign["targetCpa"], {"targetCpaMicros": "1500000"})
        self.assertNotIn("selectiveOptimization", campaign)
        self.assertEqual(campaign["status"], "PAUSED")

    def test_goal_cost_fields_cannot_be_silently_reinterpreted(self):
        for goal in ("install-volume", "tROAS", [], None):
            with self.subTest(goal=goal):
                self.assertTrue(validate_config(dict(CONFIG, goal=goal)))

    def test_schema_uses_in_app_action_goal_and_real_ads_operations(self):
        request = campaign_request(CUSTOMER, CONFIG)
        self.assertTrue(request["validateOnly"])
        self.assertFalse(request["partialFailure"])
        operations = request["mutateOperations"]
        self.assertEqual(list(operations[0]), ["campaignBudgetOperation"])
        campaign = operations[1]["campaignOperation"]["create"]
        self.assertEqual(campaign["appCampaignSetting"]["biddingStrategyGoalType"], GOAL)
        self.assertEqual(campaign["advertisingChannelType"], "MULTI_CHANNEL")
        self.assertEqual(campaign["advertisingChannelSubType"], "APP_CAMPAIGN")
        self.assertEqual(campaign["selectiveOptimization"]["conversionActions"], [ACTION])
        self.assertEqual(campaign["targetCpa"]["targetCpaMicros"], "5000000")
        self.assertEqual(operations[-1]["adGroupAdOperation"]["create"]["ad"]["appAd"]["headlines"], [{"text": "Build a focus routine"}])

    def test_temporary_ids_are_unique_and_define_parents_first(self):
        operations = campaign_request(CUSTOMER, CONFIG)["mutateOperations"]
        budget = operations[0]["campaignBudgetOperation"]["create"]
        campaign = operations[1]["campaignOperation"]["create"]
        group = operations[-2]["adGroupOperation"]["create"]
        ad = operations[-1]["adGroupAdOperation"]["create"]
        self.assertTrue(budget["resourceName"].endswith("/-1"))
        self.assertTrue(campaign["resourceName"].endswith("/-2"))
        self.assertTrue(group["resourceName"].endswith("/-3"))
        self.assertEqual(campaign["campaignBudget"], budget["resourceName"])
        self.assertEqual(group["campaign"], campaign["resourceName"])
        self.assertEqual(ad["adGroup"], group["resourceName"])
        self.assertNotIn("type", group)
        self.assertNotIn("targetCpaMicros", group)
        self.assertFalse(budget["explicitlyShared"])

    def test_all_serving_resources_are_paused(self):
        for operation in campaign_request(CUSTOMER, CONFIG)["mutateOperations"]:
            resource = next(iter(operation.values()))["create"]
            if "status" in resource:
                self.assertEqual(resource["status"], "PAUSED")

    def test_targeting_uses_resource_names(self):
        operations = campaign_request(CUSTOMER, CONFIG)["mutateOperations"]
        self.assertEqual(operations[2]["campaignCriterionOperation"]["create"]["location"], {"geoTargetConstant": "geoTargetConstants/2840"})
        self.assertEqual(operations[3]["campaignCriterionOperation"]["create"]["language"], {"languageConstant": "languageConstants/1000"})

    def test_invalid_config_blocks_all_network_calls(self):
        fake = FakeAdsTransport()
        with self.assertRaises(ValueError):
            GoogleAds(CUSTOMER, "v25", fake).create_paused(dict(CONFIG, daily_budget_micros=True))
        self.assertEqual(fake.calls, [])

    def test_currency_is_verified_before_mutate(self):
        fake = FakeAdsTransport(currency="TRY")
        with self.assertRaisesRegex(AdsError, "currency"):
            GoogleAds(CUSTOMER, "v25", fake).create_paused(CONFIG)
        self.assertTrue(all(call[1].endswith(":search") for call in fake.calls))

    def test_city_id_is_not_silently_treated_as_country(self):
        fake = FakeAdsTransport(target_type="City")
        with self.assertRaisesRegex(AdsError, "Country"):
            GoogleAds(CUSTOMER, "v25", fake).create_paused(CONFIG)
        self.assertTrue(all(call[1].endswith(":search") for call in fake.calls))

    def test_validate_only_never_creates_resources(self):
        fake = FakeAdsTransport()
        result = GoogleAds(CUSTOMER, "v25", fake).validate(CONFIG)
        self.assertEqual(result["status"], "validated-only")
        mutations = [call for call in fake.calls if call[1].endswith(":mutate")]
        self.assertEqual(len(mutations), 1)
        self.assertTrue(mutations[0][2]["validateOnly"])

    def test_live_creation_validates_first_and_creates_atomically(self):
        fake = FakeAdsTransport()
        result = GoogleAds(CUSTOMER, "v25", fake).create_paused(CONFIG)
        mutations = [call for call in fake.calls if call[1].endswith(":mutate")]
        self.assertEqual([call[2]["validateOnly"] for call in mutations], [True, False])
        self.assertTrue(all(call[2]["partialFailure"] is False for call in mutations))
        self.assertEqual(result["status"], "created-paused")
        self.assertEqual(result["campaignStatus"], "PAUSED")
        self.assertEqual(len(result["resources"]), 6)

    def test_failed_validation_never_sends_creation(self):
        fake = FakeAdsTransport(fail_validation=True)
        with self.assertRaises(AdsAPIError):
            GoogleAds(CUSTOMER, "v25", fake).create_paused(CONFIG)
        mutations = [call for call in fake.calls if call[1].endswith(":mutate")]
        self.assertEqual(len(mutations), 1)
        self.assertTrue(mutations[0][2]["validateOnly"])

    def test_unknown_creation_outcome_does_not_retry(self):
        for failure in (AdsError("Timeout"), AdsAPIError(503, "Unavailable"), AdsAPIError(408, "Timeout")):
            with self.subTest(failure=failure):
                fake = FakeAdsTransport(creation_error=failure)
                with self.assertRaisesRegex(AdsError, "outcome is unknown.*duplicate"):
                    GoogleAds(CUSTOMER, "v25", fake).create_paused(CONFIG)
                self.assertEqual(len([call for call in fake.calls if call[1].endswith(":mutate")]), 2)

    def test_definitive_rejected_creation_is_not_called_unknown(self):
        fake = FakeAdsTransport(creation_error=AdsAPIError(400, "Rejected"))
        with self.assertRaises(AdsAPIError):
            GoogleAds(CUSTOMER, "v25", fake).create_paused(CONFIG)

    def test_malformed_creation_result_is_unknown(self):
        with self.assertRaisesRegex(AdsError, "outcome is unknown"):
            GoogleAds(CUSTOMER, "v25", FakeAdsTransport(malformed_create=True)).create_paused(CONFIG)

    def test_cjk_assets_use_double_width_count(self):
        self.assertTrue(validate_config(dict(CONFIG, headlines=["界" * 16])))
        self.assertEqual(validate_config(dict(CONFIG, headlines=["界" * 15])), [])

    def test_political_declaration_is_explicit(self):
        for value in (True, None, 0):
            self.assertTrue(validate_config(dict(CONFIG, contains_eu_political_advertising=value)))

    def test_no_other_status_or_unknown_fields_are_accepted(self):
        self.assertTrue(validate_config(dict(CONFIG, status="ENABLED")))


def row(day="2026-10-01", campaign="77", *, cost="1234567", impressions="100", clicks="7", conversions=None):
    result = {"segments": {"date": day}, "campaign": {"id": campaign}, "customer": {"currencyCode": "USD"}}
    if conversions is None:
        result["metrics"] = {"costMicros": cost, "impressions": impressions, "clicks": clicks}
    else:
        result["segments"]["conversionAction"] = ACTION
        result["metrics"] = {"conversions": conversions}
    return result


class ReportTests(unittest.TestCase):
    def test_app_and_campaign_filters_apply_to_both_queries(self):
        queries = report_queries("2026-10-01", "2026-10-10", ACTION, package="com.example.focus", campaign_ids=["77"])
        for query in queries:
            self.assertIn("campaign.app_campaign_setting.app_id = 'com.example.focus'", query)
            self.assertIn("campaign.id IN (77)", query)
            self.assertIn("GOOGLE_APP_STORE", query)
        for package, ids in (("x' OR 1=1", None), (None, ["7) OR 1=1"]), (None, [])):
            with self.assertRaises(ValueError):
                report_queries("2026-10-01", "2026-10-10", ACTION, package=package, campaign_ids=ids)

    def test_geo_and_asset_use_separate_delivery_and_action_queries(self):
        for dimension, source in (("geo", "geographic_view"), ("asset", "ad_group_ad_asset_view")):
            delivery, conversions = dimension_queries(dimension, "2026-10-01", "2026-10-10", ACTION, package="com.example.focus")
            self.assertIn(" FROM " + source, delivery)
            self.assertNotIn("segments.conversion_action", delivery)
            self.assertNotIn("metrics.cost_micros", conversions)
            self.assertIn("segments.conversion_action", conversions)
            self.assertIn("com.example.focus", conversions)
        self.assertIn("geographic_view.location_type", dimension_queries("geo", "2026-10-01", "2026-10-10", ACTION)[0])

    def test_spend_and_conversions_are_queried_separately(self):
        cost, conversions = report_queries("2026-10-01", "2026-10-10", ACTION)
        self.assertNotIn("conversion_action", cost)
        self.assertNotIn("cost_micros", conversions)
        self.assertNotIn("metrics.clicks", conversions)
        self.assertIn(f"segments.conversion_action = '{ACTION}'", conversions)
        self.assertIn("APP_CAMPAIGN", cost)

    def test_invalid_dates_or_action_cannot_inject_gaql(self):
        for start, end, action in (("2026-10-10", "2026-10-01", ACTION), ("20261001", "2026-10-10", ACTION), ("2026-10-01", "2026-10-10", "x' OR 1=1")):
            with self.assertRaises(ValueError):
                report_queries(start, end, action)

    def test_csv_metrics_keep_micros_precision_and_fractional_conversions(self):
        result = normalize_report([row()], [row(conversions=2.5)], ACTION)
        self.assertEqual(result[0]["cost"], "1.234567")
        self.assertEqual(result[0]["conversions"], "2.5")
        self.assertEqual(tuple(result[0]), ADS_FIELDS)

    def test_missing_conversion_row_retains_spend_and_zero_conversions(self):
        self.assertEqual(normalize_report([row()], [], ACTION)[0]["conversions"], "0")

    def test_conversion_only_day_is_not_dropped(self):
        item = normalize_report([], [row(conversions=1.5)], ACTION)[0]
        self.assertEqual(item["cost"], "0")
        self.assertEqual(item["conversions"], "1.5")

    def test_duplicate_metrics_do_not_double_count(self):
        for costs, conversions in (([row(), row()], []), ([], [row(conversions=2), row(conversions=2)])):
            with self.assertRaisesRegex(AdsError, "Duplicate"):
                normalize_report(costs, conversions, ACTION)

    def test_wrong_conversion_action_is_rejected(self):
        conversion = row(conversions=2)
        conversion["segments"]["conversionAction"] = "customers/1234567890/conversionActions/5"
        with self.assertRaisesRegex(AdsError, "different conversion"):
            normalize_report([row()], [conversion], ACTION)

    def test_non_finite_or_fractional_count_is_rejected(self):
        for data in (row(cost="NaN"), row(impressions="1.5"), row(clicks="-1")):
            with self.assertRaises(AdsError):
                normalize_report([data], [], ACTION)

    def test_malformed_metrics_are_protocol_errors_not_zero_results(self):
        for value in (None, [], "unexpected"):
            for conversion in (False, True):
                with self.subTest(value=value, conversion=conversion):
                    item = row(conversions=2) if conversion else row()
                    item["metrics"] = value
                    with self.assertRaisesRegex(AdsError, "metrics object"):
                        normalize_report([] if conversion else [item], [item] if conversion else [], ACTION)

    def test_omitted_zero_metrics_still_normalize(self):
        item = row()
        del item["metrics"]
        result = normalize_report([item], [], ACTION)[0]
        self.assertEqual((result["cost"], result["impressions"], result["clicks"]), ("0", "0", "0"))

    def test_pagination_fetches_every_page(self):
        class Pages:
            def __init__(self):
                self.calls = []

            def request(self, method, url, *, payload):
                self.calls.append(copy.deepcopy(payload))
                return {"results": [{"part": 2}]} if payload.get("pageToken") else {"results": [{"part": 1}], "nextPageToken": "second"}

        pages = Pages()
        result = GoogleAds(CUSTOMER, "v25", pages).search("SELECT campaign.id FROM campaign")
        self.assertEqual(result, [{"part": 1}, {"part": 2}])
        self.assertEqual(pages.calls[1]["pageToken"], "second")
        self.assertNotIn("pageSize", pages.calls[0])

    def test_repeated_pagination_token_aborts(self):
        class Pages:
            def request(self, *args, **kwargs):
                return {"nextPageToken": "same"}

        with self.assertRaisesRegex(AdsError, "repeated"):
            GoogleAds(CUSTOMER, "v25", Pages()).search("query")

    def test_csv_is_compatible_and_not_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "report.csv"
            write_report(path, normalize_report([row()], [row(conversions=2)], ACTION))
            with path.open() as handle:
                reader = csv.DictReader(handle)
                self.assertEqual(tuple(reader.fieldnames), ADS_FIELDS)
                self.assertEqual(next(reader)["cost"], "1.234567")
            with self.assertRaises(FileExistsError):
                write_report(path, [])


class CLITests(unittest.TestCase):
    def test_existing_report_destination_blocks_before_credentials_or_api(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "existing.json"
            output.write_text("existing")
            for command in ("report", "geo-report", "asset-report"):
                args = [command, "--customer", CUSTOMER, "--api-version", "v25",
                        "--start-date", "2026-10-01", "--end-date", "2026-10-10",
                        "--conversion-action", ACTION, "--output", str(output)]
                with self.subTest(command=command), patch("shared.google_ads.AdsADCTransport", side_effect=AssertionError("No ADC or API before preflight")), contextlib.redirect_stderr(io.StringIO()):
                    self.assertEqual(main(args), 2)
            csv_output = Path(directory) / "new.csv"
            csv_output.with_suffix(".csv.metadata.json").write_text("existing")
            with patch("shared.google_ads.AdsADCTransport", side_effect=AssertionError("No ADC")), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(main(["report", "--customer", CUSTOMER, "--api-version", "v25",
                                       "--start-date", "2026-10-01", "--end-date", "2026-10-10",
                                       "--conversion-action", ACTION, "--output", str(csv_output)]), 2)

    def test_keyword_ideas_preserve_search_source_and_pagination(self):
        config = {"seeds": ["focus timer"], "language_resource": "languageConstants/1000", "country_resources": ["geoTargetConstants/2840"]}
        class Planner:
            def __init__(self):
                self.calls = []
            def request(self, method, url, *, payload):
                self.calls.append((url, copy.deepcopy(payload)))
                if url.endswith(":search"):
                    if "FROM geo_target_constant" in payload["query"]:
                        return {"results": [{"geoTargetConstant": {"resourceName": "geoTargetConstants/2840", "status": "ENABLED", "targetType": "Country"}}]}
                    if "FROM language_constant" in payload["query"]:
                        return {"results": [{"languageConstant": {"resourceName": "languageConstants/1000"}}]}
                    return {"results": [{"customer": {"currencyCode": "USD", "timeZone": "UTC"}}]}
                if not url.endswith(f"customers/{CUSTOMER}:generateKeywordIdeas"):
                    raise AssertionError(url)
                if payload.get("pageToken"):
                    return {"results": [{"text": "pomodoro timer", "keywordIdeaMetrics": {"avgMonthlySearches": "1000"}}]}
                return {"results": [{"text": "focus timer"}], "nextPageToken": "next"}
        planner = Planner()
        result = GoogleAds(CUSTOMER, "v25", planner).keyword_ideas(config)
        self.assertFalse(result["isGooglePlayPopularity"])
        self.assertEqual(result["surface"], "GOOGLE_SEARCH")
        self.assertEqual(len(result["results"]), 2)
        calls = [payload for url, payload in planner.calls if url.endswith(":generateKeywordIdeas")]
        self.assertEqual(calls[0]["keywordSeed"], {"keywords": ["focus timer"]})
        self.assertEqual(calls[0]["keywordPlanNetwork"], "GOOGLE_SEARCH")
        self.assertFalse(calls[0]["includeAdultKeywords"])
        self.assertEqual(calls[1]["pageToken"], "next")
        self.assertNotIn("avgMonthlySearches", result["results"][0])

    def test_invalid_keyword_ideas_cannot_default_to_unscoped_worldwide_query(self):
        for data in ({"seeds": [], "language_resource": "languageConstants/1000", "country_resources": ["geoTargetConstants/2840"]},
                     {"seeds": ["focus"], "language_resource": "en", "country_resources": []},
                     {"seeds": ["x"] * 21, "language_resource": "languageConstants/1000", "country_resources": ["geoTargetConstants/2840"]}):
            with self.assertRaises(ValueError):
                keyword_ideas_request(data)

    def test_report_writes_timezone_action_metadata_and_applies_filters(self):
        class Reports:
            def __init__(self):
                self.calls = []
            def request(self, method, url, *, payload):
                self.calls.append(copy.deepcopy(payload))
                query = payload["query"]
                if " FROM customer " in query:
                    return {"results": [{"customer": {"id": CUSTOMER, "currencyCode": "USD", "timeZone": "America/New_York"}}]}
                if "FROM conversion_action" in query:
                    return {"results": [{"conversionAction": {"resourceName": ACTION, "name": "Purchase", "primaryForGoal": True, "countingType": "MANY_PER_CLICK", "clickThroughLookbackWindowDays": "30"}}]}
                return {"results": [row(conversions=2)] if "segments.conversion_action" in query else [row()]}
        fake = Reports()
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "report.csv"
            with patch("shared.google_ads.AdsADCTransport", return_value=fake), contextlib.redirect_stdout(io.StringIO()):
                code = main(["report", "--customer", CUSTOMER, "--api-version", "v25", "--package", "com.example.focus",
                             "--campaign-id", "77", "--start-date", "2026-10-01", "--end-date", "2026-10-10",
                             "--conversion-action", ACTION, "--output", str(output)])
            self.assertEqual(code, 0)
            metadata = json.loads(output.with_suffix(".csv.metadata.json").read_text())
            self.assertEqual(metadata["account"]["timeZone"], "America/New_York")
            self.assertEqual(metadata["conversionSettings"][0]["conversionAction"]["name"], "Purchase")
            self.assertTrue(metadata["conversionSettingsVerified"])
            self.assertEqual(metadata["metric"], "metrics.conversions")
            for payload in fake.calls[:2]:
                self.assertIn("campaign.id IN (77)", payload["query"])

    def test_geo_and_asset_commands_export_raw_views_without_writes(self):
        class Reports:
            def request(self, method, url, *, payload):
                if not url.endswith(":search"):
                    raise AssertionError("Reports must not mutate")
                if " FROM customer " in payload["query"]:
                    return {"results": [{"customer": {"currencyCode": "USD", "timeZone": "UTC"}}]}
                return {"results": []}
        for command in ("geo-report", "asset-report"):
            with self.subTest(command=command), tempfile.TemporaryDirectory() as directory:
                output = Path(directory) / "report.json"
                with patch("shared.google_ads.AdsADCTransport", return_value=Reports()), contextlib.redirect_stdout(io.StringIO()):
                    code = main([command, "--customer", CUSTOMER, "--api-version", "v25", "--package", "com.example.focus",
                                 "--start-date", "2026-10-01", "--end-date", "2026-10-10", "--conversion-action", ACTION,
                                 "--output", str(output)])
                self.assertEqual(code, 0)
                report = json.loads(output.read_text())
                self.assertEqual(report["dimension"], command.split("-", 1)[0])
                self.assertEqual(report["deliveryRows"], [])
                self.assertFalse(report["metadata"]["conversionSettingsVerified"])

    def test_customer_id_accepts_display_hyphens(self):
        self.assertEqual(customer_id("123-456-7890"), CUSTOMER)

    def test_create_without_live_never_loads_credentials(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            path.write_text(json.dumps(CONFIG))
            with patch("shared.google_ads.AdsADCTransport", side_effect=AssertionError("Offline")):
                with contextlib.redirect_stdout(io.StringIO()) as stdout:
                    code = main(["create", "--customer", CUSTOMER, "--api-version", "v25", "--config", str(path)])
            self.assertEqual(code, 0)
            self.assertEqual(json.loads(stdout.getvalue())["status"], "offline-plan")

    def test_api_version_is_explicit_not_defaulted(self):
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                main(["plan", "--customer", CUSTOMER, "--config", "irrelevant.json"])

    def test_live_create_records_paused_resources(self):
        with tempfile.TemporaryDirectory() as directory:
            path, receipt = Path(directory) / "config.json", Path(directory) / "receipt.json"
            path.write_text(json.dumps(CONFIG))
            with patch("shared.google_ads.AdsADCTransport", return_value=FakeAdsTransport()):
                with contextlib.redirect_stdout(io.StringIO()) as stdout:
                    code = main([
                        "create", "--customer", CUSTOMER, "--api-version", "v25", "--config", str(path),
                        "--live", "--receipt", str(receipt),
                    ])
            self.assertEqual(code, 0)
            self.assertEqual(json.loads(receipt.read_text())["status"], "created-paused")
            self.assertEqual(json.loads(stdout.getvalue())["campaignStatus"], "PAUSED")

    def test_receipt_retains_config_evidence_for_reconciliation(self):
        for transport in (FakeAdsTransport(), FakeAdsTransport(creation_error=AdsError("Timeout"))):
            with self.subTest(transport=transport), tempfile.TemporaryDirectory() as directory:
                path, receipt = Path(directory) / "config.json", Path(directory) / "receipt.json"
                path.write_text(json.dumps(CONFIG))
                with patch("shared.google_ads.AdsADCTransport", return_value=transport):
                    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                        main([
                            "create", "--customer", CUSTOMER, "--api-version", "v25", "--config", str(path),
                            "--live", "--receipt", str(receipt),
                        ])
                result = json.loads(receipt.read_text())
                serialized = json.dumps(CONFIG, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
                self.assertEqual(result["requestedConfig"], CONFIG)
                self.assertEqual(result["configSha256"], hashlib.sha256(serialized.encode("utf-8")).hexdigest())
                self.assertTrue(result["attemptedAt"].endswith("+00:00"))
                # Changing the source file must not change the saved attempt.
                path.write_text(json.dumps(dict(CONFIG, target_cpa_micros=9000000)))
                self.assertEqual(json.loads(receipt.read_text())["requestedConfig"]["target_cpa_micros"], 5000000)

    def test_failed_attempt_receipts_record_the_actual_stage(self):
        cases = (
            (FakeAdsTransport(fail_validation=True), "validation-failed"),
            (FakeAdsTransport(creation_error=AdsAPIError(400, "Rejected")), "creation-rejected"),
            (FakeAdsTransport(creation_error=AdsError("Timeout")), "creation-outcome-unknown"),
        )
        for transport, expected in cases:
            with self.subTest(expected=expected), tempfile.TemporaryDirectory() as directory:
                path, receipt = Path(directory) / "config.json", Path(directory) / "receipt.json"
                path.write_text(json.dumps(CONFIG))
                with patch("shared.google_ads.AdsADCTransport", return_value=transport):
                    with contextlib.redirect_stderr(io.StringIO()):
                        code = main([
                            "create", "--customer", CUSTOMER, "--api-version", "v25", "--config", str(path),
                            "--live", "--receipt", str(receipt),
                        ])
                self.assertEqual(code, 1)
                self.assertEqual(json.loads(receipt.read_text())["status"], expected)

    def test_successful_creation_ids_survive_failed_receipt_write(self):
        with tempfile.TemporaryDirectory() as directory:
            path, receipt = Path(directory) / "config.json", Path(directory) / "receipt.json"
            path.write_text(json.dumps(CONFIG))
            original = Path.write_text

            def write(target, data, *args, **kwargs):
                if target == receipt and '"created-paused"' in data:
                    raise OSError("Disk full")
                return original(target, data, *args, **kwargs)

            with patch("shared.google_ads.AdsADCTransport", return_value=FakeAdsTransport()), patch.object(Path, "write_text", write):
                with contextlib.redirect_stdout(io.StringIO()) as stdout, contextlib.redirect_stderr(io.StringIO()):
                    code = main([
                        "create", "--customer", CUSTOMER, "--api-version", "v25", "--config", str(path),
                        "--live", "--receipt", str(receipt),
                    ])
            self.assertEqual(code, 1)
            result = json.loads(stdout.getvalue())
            self.assertEqual(result["status"], "created-paused")
            self.assertFalse(result["receiptSaved"])
            self.assertEqual(len(result["resources"]), 6)


if __name__ == "__main__":
    unittest.main()
