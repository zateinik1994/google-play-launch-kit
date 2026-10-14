import unittest
from shared.aso_tools import discover, gaps, experiment


class ASOToolsTests(unittest.TestCase):
    def test_discovery_counts_documents_not_stuffing_or_volume(self):
        profiles=[{"package_name":"com.example.a","title":"Habit tracker", "fullDescription":"Habit tracker habit tracker"},
                  {"package_name":"com.example.b","title":"Habit tracker"}]
        result=discover(profiles,seeds=["offline planner"])
        by_query={row["query"]:row for row in result["keywords"]}
        self.assertEqual(by_query["habit tracker"]["competitor_documents"],2)
        self.assertIsNone(by_query["habit tracker"]["volume"])
        self.assertTrue(by_query["offline planner"]["needs_product_fit_review"])

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
