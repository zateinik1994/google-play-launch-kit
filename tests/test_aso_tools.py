import unittest
from shared.aso_tools import contains, discover, gaps, experiment


class ASOToolsTests(unittest.TestCase):
    def test_gap_keeps_fixture_provenance_separate_from_listing_locale(self):
        context = {"locale": "en-GB", "country": "GB", "is_fixture": True, "source": "fixture/offline", "observed_at": "2026-10-14T12:00:00Z"}
        bank = discover([{"package_name": "com.example.app", "title": "Daily habits"}], context=context)
        listings = {"en-GB": {"title": "Habits", "shortDescription": "Track daily habits", "fullDescription": "A daily checklist."}}
        result = gaps(bank, listings)
        self.assertEqual(result["keyword_metadata"], context)
        self.assertTrue(result["keyword_metadata"]["is_fixture"])
        self.assertIsNone(gaps(bank["keywords"], listings)["keyword_metadata"])
    def test_numeric_product_facts_are_not_erased_in_phrase_coverage(self):
        self.assertFalse(contains("7-day trial", "30 day trial"))
        self.assertFalse(contains("2FA authenticator", "3FA"))
        self.assertTrue(contains("Use a 7-day trial", "7 day trial"))
        self.assertTrue(contains("2FA authenticator", "2fa"))

    def test_discovery_never_invents_phrases_between_listing_fields(self):
        profiles=[{"package_name":"com.example.a","title":"Habit Tracker", "shortDescription":"Cloud Sync", "fullDescription":"Offline Reminders and 2FA protection"}]
        rows={row["query"]:row for row in discover(profiles,seeds=["7 day trial"],limit=100)["keywords"]}
        self.assertNotIn("tracker cloud",rows)
        self.assertIn("cloud sync",rows)
        self.assertIn("2fa protection",rows)
        self.assertEqual(rows["7 day trial"]["competitor_documents"],0)
        self.assertEqual(rows["7 day trial"]["source"],"supplied seed phrase")

    def test_gap_keeps_conflicting_decisions_and_different_markets(self):
        listings={"en-US":{"title":"Habits","shortDescription":"Track routines.","fullDescription":"Check progress."}}
        bank={"keywords":[{"query":"cloud sync","locale":"en-US","country":"US","source":"one","relevance":3},
                          {"query":"cloud sync","locale":"en-US","country":"US","source":"two","relevance":0},
                          {"query":"cloud sync","locale":"en-US","country":"GB","source":"three","relevance":2}]}
        rows=gaps(bank,listings)["rows"]
        self.assertEqual(len(rows),2)
        self.assertEqual(rows[0]["status"],"decision_conflict")
        self.assertTrue(rows[0]["needs_product_fit_review"])
        self.assertEqual(len(rows[0]["observations"]),2)
        self.assertEqual(rows[1]["country"],"GB")

    def test_competitor_gap_counts_selected_documents_with_unknowns_and_scope(self):
        listings={"en-US":{"title":"Habits","shortDescription":"Track routines.","fullDescription":"Check progress."},
                  "ru-RU":{"title":"Привычки","shortDescription":"Отмечайте привычки.","fullDescription":"Проверяйте прогресс."}}
        profiles={"metadata":{"locale":"en-US","country":"US","source":"fixture/offline","is_fixture":True},
                  "data":[{"package_name":"com.example.a","title":"Cloud Sync","shortDescription":"Sync routines.","fullDescription":"Work offline."},
                          {"package_name":"com.example.b","title":"Checklist","shortDescription":None,"fullDescription":None}]}
        bank={"keywords":[{"query":"cloud sync","country":"US"},{"query":"cloud sync","country":"GB"}]}
        rows=gaps(bank,listings,profiles)["rows"]
        comparison=rows[0]["competitors"]
        self.assertEqual(comparison["documents_observed"],2)
        self.assertEqual(comparison["documents_with_phrase"],1)
        self.assertEqual(comparison["documents_unverified"],1)
        self.assertEqual(comparison["documents_without_phrase"],0)
        self.assertIsNone(rows[1]["competitors"]["documents_with_phrase"])
        self.assertFalse(rows[2]["competitors"]["context_applies"])
        self.assertTrue(comparison["context"]["is_fixture"])

    def test_competitor_comparison_requires_declared_locale_country_and_typed_text(self):
        listings={"en-US":{"title":"Habits","shortDescription":"Track routines.","fullDescription":"Check progress."}}
        with self.assertRaises(ValueError):gaps([{"query":"habit"}],listings,[{"package_name":"com.example.a","title":"Habits"}])
        with self.assertRaises(ValueError):discover([{"package_name":"com.example.a","title":{"word":"Habits"}}])
        with self.assertRaises(ValueError):discover([{"package_name":"com.example.a","title":""}])

    def test_discovery_counts_documents_not_stuffing_or_volume(self):
        profiles=[{"package_name":"com.example.a","title":"Habit tracker", "fullDescription":"Habit tracker habit tracker"},
                  {"package_name":"com.example.b","title":"Habit tracker"}]
        result=discover(profiles,seeds=["offline planner"])
        by_query={row["query"]:row for row in result["keywords"]}
        self.assertEqual(by_query["habit tracker"]["competitor_documents"],2)
        self.assertIsNone(by_query["habit tracker"]["volume"])
        self.assertTrue(by_query["offline planner"]["needs_product_fit_review"])

    def test_discovery_preserves_scope_and_fixture_provenance(self):
        profile = {"package_name": "com.example.a", "title": "Habit tracker"}
        context = {"locale": "en-GB", "country": "GB", "source": "fixture/offline@fixture", "is_fixture": True}
        result = discover([profile], context=context)
        self.assertEqual(result["metadata"], context)
        self.assertTrue(all(row["locale"] == "en-GB" and row["country"] == "GB" for row in result["keywords"]))
        with self.assertRaises(ValueError):
            discover([profile], context={"source": "unknown scope"})
        self.assertIsNone(discover([profile])["metadata"])

    def test_gap_is_phrase_and_locale_aware(self):
        listings={"en-GB":{"title":"Habit tracker", "shortDescription":"Daily routines", "fullDescription":"Check your weekly progress."}}
        result=gaps({"keywords":[{"query":"habit tracker","locale":"en-GB"},{"query":"cloud sync","relevance":0},{"query":"процесс","locale":"ru-RU"}]},listings)
        self.assertEqual(len(result["rows"]),2)
        self.assertEqual(result["rows"][0]["status"],"present")
        self.assertEqual(result["rows"][1]["status"],"excluded")

    def test_smaller_effect_more_variants_and_lower_traffic_require_more_data(self):
        base=experiment(.08,.2,.95,.8,1000)
        small=experiment(.08,.1,.95,.8,1000)
        multi=experiment(.08,.2,.95,.8,1000,variants=2)
        self.assertGreater(small["visitors_per_arm"],base["visitors_per_arm"])
        self.assertGreater(multi["total_visitors"],base["total_visitors"])
        self.assertGreaterEqual(experiment(.08,.2,.95,.8,1000,traffic_fraction=.2)["estimated_days"],base["estimated_days"])

    def test_impossible_inputs_do_not_produce_a_plan(self):
        for rate, mde in ((0,.2),(.9,.2),(.08,float('nan'))):
            with self.assertRaises(ValueError):experiment(rate,mde,.95,.8,1000)
        with self.assertRaises(ValueError):experiment(.08,1e-30,.95,.8,1000)
        with self.assertRaises(ValueError):experiment(.08,.2,.95,.8,1000,traffic_fraction=1e-320)


if __name__ == "__main__":unittest.main()
