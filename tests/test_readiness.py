import contextlib
import copy
import io
import json
import tempfile
import unittest
from pathlib import Path

from shared.readiness import CHECKS, main, report, template

PROJECT = {"package_name": "com.example.app", "locales": ["en-GB", "ar"], "countries": ["GB"], "features": ["Daily checklist"], "monetization": "Free core; subscription for reports"}
LISTING = {"title": "Habits", "shortDescription": "Build a daily routine", "fullDescription": "Track your daily checklist."}


class ReadinessTests(unittest.TestCase):
    def test_metadata_pass_cannot_imply_release_readiness_or_fill_missing_locale(self):
        result = report(PROJECT, {"en-GB": LISTING})
        self.assertEqual(result["state"], "INCOMPLETE")
        self.assertEqual(result["locale_matrix"][1]["listing"], "missing")
        self.assertEqual(result["evidence_status_counts"]["pending"], len(CHECKS))
        self.assertNotIn("is_compliant", result)

    def test_alternative_asset_profiles_are_separate_and_fallback_is_preserved(self):
        rows = [{"file": f"en-GB/{profile}/{index}.png", "locale": "en-GB", "kind": "screenshot", "profileId": profile, "device_type": "phone", "source_fallback": True} for profile in ("phone-portrait", "phone-landscape") for index in (1, 2)]
        result = report(PROJECT, {"en-GB": LISTING}, {"assets": rows})
        self.assertEqual([row["count"] for row in result["locale_matrix"][0]["screenshot_sets"]], [2, 2])
        self.assertEqual(result["locale_matrix"][0]["default_ui_sources"], 4)
        with self.assertRaises(ValueError): report(PROJECT, assets={"assets": rows+rows[:1]})

    def test_evidence_for_another_app_or_build_and_unverifiable_pass_are_rejected(self):
        evidence = template(PROJECT["package_name"], "versionCode 42")
        for field, value in (("package_name", "com.example.other"), ("release_reference", "versionCode 41")):
            bad = dict(evidence, **{field: value})
            with self.subTest(field=field), self.assertRaises(ValueError): report(PROJECT, evidence=bad, release="versionCode 42")
        evidence["checks"]["product_truth"]["status"] = "passed"
        with self.assertRaises(ValueError): report(PROJECT, evidence=evidence, release="versionCode 42")
        evidence["checks"]["product_truth"].update(reference="QA log", checked_at="2026-10-14T12:00:00")
        with self.assertRaises(ValueError): report(PROJECT, evidence=evidence, release="versionCode 42")

    def test_recorded_completion_is_distinct_from_platform_approval(self):
        evidence = template(PROJECT["package_name"], "versionCode 42")
        for entry in evidence["checks"].values(): entry.update(status="passed", reference="fictional QA log", checked_at="2026-10-14T12:00:00Z")
        result = report(PROJECT, {code: LISTING for code in PROJECT["locales"]}, evidence=evidence, release="versionCode 42")
        self.assertEqual(result["state"], "CHECKLIST_RECORDED")
        self.assertEqual(result["evidence_status_counts"]["passed"], len(CHECKS))
        self.assertTrue(any("not policy compliance" in note for note in result["limitations"]))

    def test_malformed_pending_evidence_does_not_leave_partial_json(self):
        with tempfile.TemporaryDirectory() as temp, contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            folder = Path(temp); project = folder/"project.json"; project.write_text(json.dumps(PROJECT))
            path = folder/"evidence.json"
            for index, invalid in enumerate((float("nan"), False, [], "2026-10-14T12:00:00")):
                evidence = template(PROJECT["package_name"], "versionCode 42")
                evidence["checks"]["visual_localization"]["checked_at"] = invalid
                path.write_text(json.dumps(evidence)); output = folder/f"report-{index}.json"
                self.assertEqual(main(["report", "--project", str(project), "--evidence", str(path), "--release-reference", "versionCode 42", "--output", str(output)]), 2)
                self.assertFalse(output.exists())

    def test_template_report_and_optional_completeness_exit_work_without_accounts(self):
        with tempfile.TemporaryDirectory() as temp, contextlib.redirect_stdout(io.StringIO()):
            folder = Path(temp); project = folder/"project.json"; project.write_text(json.dumps(PROJECT))
            output = folder/"evidence.json"
            self.assertEqual(main(["template", "--package", PROJECT["package_name"], "--release-reference", "versionCode 42", "--output", str(output)]), 0)
            self.assertEqual(main(["report", "--project", str(project), "--output", str(folder/"report.json"), "--require-complete"]), 1)
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(main(["template", "--package", PROJECT["package_name"], "--release-reference", "versionCode 42", "--output", str(output)]), 2)
            self.assertTrue(all(row["status"] == "pending" for row in json.loads(output.read_text())["checks"].values()))


if __name__ == "__main__": unittest.main()
