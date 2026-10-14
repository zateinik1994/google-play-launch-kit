import contextlib
import csv
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from shared.appstorespy import AppStoreSpy, build_request, main as provider_main, validate
from shared.store_data import collect, rank_snapshot, normalize_reviews, CollectionError, context, main as collection_main
from shared.play_reports import normalize_csv, summarize, report_object, object_url, GCSReports


class ProviderTests(unittest.TestCase):
    def test_real_android_paths_and_typed_body(self):
        request = build_request("app", {"id":"com.example.app","country":"GB","language":"en_GB"})
        self.assertEqual(request["url"], "https://api.appstorespy.com/v1/play/apps/com.example.app")
        self.assertEqual(request["query"]["language"], "en_GB")
        with self.assertRaises(ValueError):
            build_request("reviews", {"id":"com.example.app"})
        with self.assertRaises(ValueError):
            build_request("search-job-create", body={"store":"ios","term":"habit","country":"GB","lang":"en_GB","limit":10})

    def test_invalid_query_cannot_consume_credits(self):
        calls=[]
        client = AppStoreSpy(transport=lambda request: calls.append(request))
        with self.assertRaises(ValueError):
            client.call("app", {"id":"x","unexpected":True})
        self.assertEqual(calls, [])

    def test_queued_country_missing_and_partial_are_explicit(self):
        for status, expected in ((202,"queued"),(204,"no_country_data"),(206,"partial")):
            client=AppStoreSpy(transport=lambda request: (status,None,{"X-Cost":"1"}))
            self.assertEqual(client.call("app",{"id":"com.example.app"})["status"], expected)

    def test_existing_output_blocks_paid_request(self):
        with tempfile.TemporaryDirectory() as temp:
            output=Path(temp)/"out.json";output.write_text("existing")
            with patch("shared.appstorespy.AppStoreSpy") as client, contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(provider_main(["countries","--execute","--output",str(output)]),2)
                client.assert_not_called()

    def test_plan_never_loads_key_or_calls_provider(self):
        with patch("shared.appstorespy.AppStoreSpy") as client, contextlib.redirect_stdout(io.StringIO()) as stdout:
            self.assertEqual(provider_main(["countries"]),0)
            self.assertEqual(json.loads(stdout.getvalue())["status"],"offline-plan")
            client.assert_not_called()


class PublicTests(unittest.TestCase):
    def test_fixture_rank_csv_cannot_be_mistaken_for_live_observations(self):
        with tempfile.TemporaryDirectory() as temp, contextlib.redirect_stdout(io.StringIO()):
            output = Path(temp)/"ranks.csv"
            fixture = Path(__file__).resolve().parents[1]/"examples/data/public-play-fixture.json"
            self.assertEqual(collection_main(["ranks", "--package", "com.example.habits", "--query", "habit", "--locale", "en-GB", "--country", "GB", "--fixture", str(fixture), "--output", str(output)]), 0)
            with output.open(newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(rows[0]["source"], "fixture/offline@fixture")
            metadata = json.loads(output.with_suffix(".csv.meta.json").read_text())
            self.assertTrue(metadata["is_fixture"])
            self.assertEqual(metadata["packages"], ["com.example.habits"])

    def test_invalid_search_and_unbounded_reviews_are_rejected(self):
        class Provider:
            def search(self, *args): return []
            def reviews(self, *args): return [{"reviewId":"a", "score":2, "content":"Crash"}] * 3
        with self.assertRaises(CollectionError):
            collect(Provider(), "search", locale="en-GB", country="GB", query="habit")
        with self.assertRaises(CollectionError):
            collect(Provider(), "reviews", locale="en-GB", country="GB", packages=["com.example.app"], limit=2)

    def test_rank_actual_depth_missing_is_censored(self):
        rows=rank_snapshot([{"appId":"com.example.a"},{"appId":"com.example.b"}], ["com.example.b","com.example.c"], "habit", "en-GB", "GB", "2026-10-01T12:00:00Z")
        self.assertEqual(rows[0]["rank"],2)
        self.assertEqual(rows[1]["rank"],"")
        self.assertEqual(rows[1]["depth"],2)
        with self.assertRaises(CollectionError):rank_snapshot([], ["com.example.b"],"habit","en-GB","GB")

    def test_locale_variant_is_preserved(self):
        self.assertEqual(context("zh-TW","TW"),("zh_TW","TW"))

    def test_dedup_reviews_and_invalid_response(self):
        row={"reviewId":"a","score":2,"content":"Crash"}
        self.assertEqual(len(normalize_reviews([row,row])),1)
        with self.assertRaises(CollectionError):normalize_reviews([dict(row,score=None)])
        with self.assertRaises(CollectionError):normalize_reviews([row,dict(row,score=5)])

    def test_limit_rejected_before_provider_calls(self):
        class Provider:
            def search(self,*args):raise AssertionError("No call expected")
        with self.assertRaises(ValueError):collect(Provider(),"search",locale="en-GB",country="GB",query="habit",limit=100)


class ReportTests(unittest.TestCase):
    def test_download_does_not_forward_credentials_via_redirects(self):
        class Response:
            status_code = 200
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def iter_content(self, size): yield b"report"
        class Session:
            def get(self, url, **kwargs):
                self.kwargs = kwargs
                return Response()
        client = GCSReports.__new__(GCSReports)
        client.session = Session()
        self.assertEqual(client.download("pubsite_prod_123", "stats/report.csv"), b"report")
        self.assertIs(client.session.kwargs["allow_redirects"], False)

    def test_summary_rejects_invalid_counts_and_context(self):
        base = normalize_csv("Date,Package name,visitors,install_clicks\n2026-10-01,com.example.app,100,8\n")["data"][0]
        for field, value in (("install_clicks", -3), ("visitors", True), ("visitors", float("nan")), ("visitors", 10**100), ("date", "2026-99-01"), ("date", None), ("package_name", "wrong"), ("language", [])):
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                summarize([dict(base, **{field: value})])

    def test_utf16_legacy_export_and_known_daily_aggregation(self):
        raw="Date,Package name,Store listing visitors,Store listing acquisitions\n2026-10-01,com.example.app,100,8\n2026-10-02,com.example.app,120,10\n"
        result=normalize_csv(raw.encode("utf-16"))
        self.assertEqual(result["metadata"]["metric_family"],"legacy-acquisitions")
        summary=summarize(result["data"])[0]
        self.assertEqual(summary["visitor_days"],220)
        self.assertEqual(summary["action_days"],18)

    def test_clicks_and_suppression_are_not_acquisitions_or_zero(self):
        raw="Date,Package name,Store listing visitors,Unique user install clicks\n2026-10-01,com.example.app,100,\n"
        result=normalize_csv(raw)
        self.assertEqual(result["metadata"]["metric_family"],"click-intent")
        self.assertIsNone(result["data"][0]["acquisitions"])
        self.assertIsNone(summarize(result["data"])[0]["action_days"])

    def test_mixed_family_requires_explicit_choice_and_duplicates_fail(self):
        raw="Date,Package name,visitors,acquisitions,install_clicks\n2026-10-01,com.example.app,100,8,9\n"
        with self.assertRaises(ValueError):normalize_csv(raw)
        data=normalize_csv(raw,family="legacy-acquisitions")["data"]
        with self.assertRaises(ValueError):summarize(data+data)

    def test_gcs_object_path_and_no_traversal(self):
        name=report_object("com.example.app","202610","traffic_source")
        self.assertIn("202610_traffic_source.csv",name)
        self.assertIn("%2F",object_url("pubsite_prod_123",name))
        with self.assertRaises(ValueError):object_url("pubsite_prod_123","../private")

    def test_different_listing_language_and_install_state_are_not_merged(self):
        raw="Date,Package name,Language,Store listing,App install state,visitors,install_clicks\n2026-10-01,com.example.app,en-GB,main,new,100,8\n2026-10-01,com.example.app,en-GB,custom,new,100,9\n2026-10-02,com.example.app,ru-RU,main,installed,200,20\n"
        result=normalize_csv(raw)
        groups=summarize(result["data"])
        self.assertEqual(len(groups),3)
        self.assertEqual(groups[0]["store_listing"],"main")
        self.assertEqual(groups[1]["store_listing"],"custom")
        self.assertEqual(groups[2]["language"],"ru-RU")


if __name__ == "__main__":unittest.main()
