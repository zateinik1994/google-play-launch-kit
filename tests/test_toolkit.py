import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from shared.analysis import ads_report, campaign_plan, compare_ranks, keywords, read_csv, reviews
from shared.metadata import validate_listing, validate_listings

ROOT = Path(__file__).resolve().parent.parent


class MetadataTests(unittest.TestCase):
    def setUp(self):
        self.listing = {"title": "Tracker", "shortDescription": "Daily routines", "fullDescription": "A daily checklist."}

    def test_limits_and_unicode(self):
        listing = {"title": "я" * 30, "shortDescription": "é" * 80, "fullDescription": "日" * 4000}
        self.assertEqual(validate_listing(listing), [])
        listing["title"] += "я"
        self.assertIn("exceeds 30", validate_listing(listing)[0])

    def test_apple_fields_and_invalid_locale_rejected(self):
        self.listing["keywords"] = "habits"
        self.assertTrue(validate_listings({"en_US": self.listing}))
        self.assertTrue(validate_listings({"en-US": self.listing}))

    def test_missing_text_and_video_validation(self):
        self.assertTrue(validate_listing({"title": ""}))
        self.listing["video"] = "https://youtube.com.attacker.example/watch?v=x"
        self.assertTrue(validate_listing(self.listing))
        self.listing["video"] = ""
        self.assertEqual(validate_listing(self.listing), [])


class AnalysisTests(unittest.TestCase):
    def test_missing_volume_stays_unknown_and_no_inferred_popularity(self):
        data = keywords([{"query": "habit", "locale": "en-US", "country": "US", "source": "brief", "relevance": "3"}])
        self.assertIsNone(data["keywords"][0]["volume"])
        rejected = keywords([{"query": "AI assistant", "locale": "en-US", "country": "US", "source": "brief", "relevance": "0"}])
        self.assertEqual(rejected["keywords"][0]["decision"], "excluded")
        with self.assertRaises(ValueError):
            keywords([{"query": "habit", "locale": "en-US", "country": "US", "source": "brief", "relevance": "3", "volume": "100"}])

    def rank(self, rank, date, **changes):
        return {"observed_at": date, "package_name": "com.example.app", "locale": "en-US", "country": "US",
                "query": "habit", "rank": rank, "depth": "50", "source": "manual", **changes}

    def test_censored_rank_is_not_zero_and_missing_is_not_censored(self):
        a = self.rank("", "2026-10-01T12:00:00Z")
        b = self.rank("10", "2026-10-02T12:00:00Z")
        result = compare_ranks([a], [b])[0]
        self.assertEqual(result["status"], "entered_observed_depth")
        self.assertIsNone(result["positions_gained"])
        self.assertEqual(compare_ranks([a], [])[0]["status"], "missing_observation")

    def test_observation_context_and_time(self):
        a = self.rank("18", "2026-10-01T12:00:00Z")
        b = self.rank("12", "2026-10-02T12:00:00Z")
        self.assertEqual(compare_ranks([a], [b])[0]["positions_gained"], 6)
        b["depth"] = "100"
        self.assertEqual(compare_ranks([a], [b])[0]["status"], "different_depth")
        b["observed_at"] = a["observed_at"]
        with self.assertRaises(ValueError):
            compare_ranks([a], [b])

    def ads(self, **changes):
        return {"date": "2026-10-01", "campaign_id": "1", "currency": "USD", "cost": "10.20",
                "impressions": "100", "clicks": "10", "conversions": "2.5", "conversion_action": "first_open", **changes}

    def test_fractional_conversions_and_zero_denominator(self):
        group = ads_report([self.ads()])["campaigns"][0]
        self.assertAlmostEqual(group["cost_per_selected_conversion"], 4.08)
        group = ads_report([self.ads(impressions="0", clicks="0", conversions="0")])["campaigns"][0]
        self.assertIsNone(group["ctr"])
        self.assertIsNone(group["cost_per_selected_conversion"])

    def test_duplicate_delivery_metrics_and_nan_rejected(self):
        with self.assertRaises(ValueError):
            ads_report([self.ads(), self.ads(conversion_action="purchase")])
        with self.assertRaises(ValueError):
            ads_report([self.ads(cost="NaN")])

    def test_review_id_dedup_and_topic_limits(self):
        result = reviews([{"review_id": "1", "rating": "2", "text": "Crash after payment"}])
        self.assertEqual(result["average_rating"], 2)
        self.assertEqual(result["topic_counts"], {"stability": 1, "billing": 1})
        with self.assertRaises(ValueError):
            reviews([{"review_id": "1", "rating": "0", "text": ""}])

    def test_campaign_plan_refuses_asa_fields(self):
        config = json.loads((ROOT/"examples/data/campaign.json").read_text())
        self.assertEqual(campaign_plan(config)["state"], "DRAFT_ONLY")
        config["keywords"] = ["habit"]
        with self.assertRaises(ValueError):
            campaign_plan(config)

    def test_campaign_text_counts_full_width_characters_twice(self):
        config = json.loads((ROOT/"examples/data/campaign.json").read_text())
        config["headlines"] = ["界" * 16]
        with self.assertRaises(ValueError):
            campaign_plan(config)


class CLITests(unittest.TestCase):
    def test_init_refuses_existing_directory(self):
        with tempfile.TemporaryDirectory() as temp:
            proc = subprocess.run([sys.executable, str(ROOT/"scripts/playkit.py"), "init", temp, "--package", "com.example.app"], capture_output=True)
            self.assertEqual(proc.returncode, 2)
            self.assertFalse((Path(temp)/"project.json").exists())

    def test_malformed_csv_does_not_silently_shift_columns(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/"input.csv"
            path.write_text("a,b\n1,2,3\n")
            with self.assertRaises(ValueError):
                read_csv(path, ("a", "b"))


if __name__ == "__main__":
    unittest.main()
