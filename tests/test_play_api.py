"""Offline verification of Publisher edit lifecycle; never contacts Google."""

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from shared.play_api import (
    ADCTransport,
    APIError,
    PlayError,
    PlayPublisher,
    listing_map,
    main,
    plan_listings,
    write_json,
)


DESIRED = {
    "en-US": {
        "title": "Focus Timer",
        "shortDescription": "Plan focus sessions and follow your progress.",
        "fullDescription": "Start a focus session, take a break, and track your progress.",
    }
}
CURRENT = {"en-US": dict(DESIRED["en-US"], title="Old Timer", video="https://www.youtube.com/watch?v=abcdef12345")}


class FakeTransport:
    def __init__(self, current=None, failures=None):
        self.current = current if current is not None else CURRENT
        self.calls = []
        self.failures = failures or {}

    def request(self, method, url, *, payload=None, query=None):
        self.calls.append({"method": method, "url": url, "payload": payload, "query": query})
        for suffix, failure in self.failures.items():
            if url.endswith(suffix) and (not isinstance(failure, tuple) or failure[0] == method):
                raise failure[1] if isinstance(failure, tuple) else failure
        if method == "POST" and url.endswith("/edits"):
            return {"id": "edit-123"}
        if method == "GET":
            return {"listings": [dict(listing, language=language) for language, listing in self.current.items()]}
        if method == "POST":
            return {"id": "edit-123"}
        return {}


class PublisherTests(unittest.TestCase):
    def client(self, transport):
        return PlayPublisher("com.example.focus", transport)

    def test_read_discards_temporary_edit(self):
        transport = FakeTransport()
        self.assertEqual(self.client(transport).list_listings(), CURRENT)
        self.assertEqual([call["method"] for call in transport.calls], ["POST", "GET", "DELETE"])
        self.assertTrue(transport.calls[-1]["url"].endswith("/edits/edit-123"))

    def test_read_failure_discards_edit(self):
        transport = FakeTransport(failures={"/listings": APIError(403, "No access")})
        with self.assertRaisesRegex(APIError, "403"):
            self.client(transport).list_listings()
        self.assertEqual(transport.calls[-1]["method"], "DELETE")

    def test_apply_validates_then_commits_without_delete(self):
        transport = FakeTransport()
        result = self.client(transport).apply_listings(DESIRED)
        self.assertEqual(result["status"], "committed")
        self.assertEqual([call["method"] for call in transport.calls], ["POST", "GET", "PUT", "POST", "POST"])
        self.assertTrue(transport.calls[-2]["url"].endswith(":validate"))
        self.assertTrue(transport.calls[-1]["url"].endswith(":commit"))
        self.assertIsNone(transport.calls[-1]["payload"])
        self.assertEqual(transport.calls[-1]["query"], {"changesInReviewBehavior": "ERROR_IF_IN_REVIEW"})

    def test_optional_review_flag_is_explicit(self):
        transport = FakeTransport()
        self.client(transport).apply_listings(DESIRED, changes_not_sent_for_review=True)
        self.assertEqual(transport.calls[-1]["query"]["changesNotSentForReview"], "true")

    def test_preserves_existing_video_when_omitted_locally(self):
        transport = FakeTransport()
        self.client(transport).apply_listings(DESIRED)
        put = transport.calls[2]
        self.assertEqual(put["payload"]["video"], CURRENT["en-US"]["video"])
        self.assertEqual(put["payload"]["language"], "en-US")

    def test_explicit_empty_video_removes_it_in_payload(self):
        transport = FakeTransport()
        desired = {"en-US": dict(DESIRED["en-US"], video="")}
        self.client(transport).apply_listings(desired)
        self.assertEqual(transport.calls[2]["payload"]["video"], "")

    def test_new_locale_uses_put(self):
        transport = FakeTransport(current={})
        self.client(transport).apply_listings(DESIRED)
        self.assertEqual(transport.calls[2]["method"], "PUT")
        self.assertNotIn("video", transport.calls[2]["payload"])

    def test_no_change_discards_edit_without_validate_or_commit(self):
        transport = FakeTransport(current=DESIRED)
        result = self.client(transport).apply_listings(DESIRED)
        self.assertEqual(result["status"], "unchanged")
        self.assertEqual([call["method"] for call in transport.calls], ["POST", "GET", "DELETE"])

    def test_omitted_remote_locale_is_not_deleted(self):
        transport = FakeTransport(current=dict(CURRENT, de=DESIRED["en-US"]))
        self.client(transport).apply_listings(DESIRED)
        self.assertEqual(len([call for call in transport.calls if call["method"] == "PUT"]), 1)
        self.assertFalse(any(call["method"] == "DELETE" for call in transport.calls))

    def test_invalid_local_input_never_creates_edit(self):
        transport = FakeTransport()
        with self.assertRaises(ValueError):
            self.client(transport).apply_listings({"en-US": {"title": "x" * 31}})
        self.assertEqual(transport.calls, [])

    def test_backup_is_saved_before_put(self):
        transport = FakeTransport()
        saved = []

        def backup(snapshot):
            self.assertEqual([call["method"] for call in transport.calls], ["POST", "GET"])
            saved.append(snapshot)

        self.client(transport).apply_listings(DESIRED, save_backup=backup)
        self.assertEqual(saved, [CURRENT])

    def test_failed_backup_aborts_before_put_and_discards_edit(self):
        transport = FakeTransport()

        def backup(snapshot):
            raise OSError("Disk full")

        with self.assertRaisesRegex(OSError, "Disk full"):
            self.client(transport).apply_listings(DESIRED, save_backup=backup)
        self.assertEqual([call["method"] for call in transport.calls], ["POST", "GET", "DELETE"])

    def test_put_failure_aborts_and_discards_edit(self):
        transport = FakeTransport(failures={"/listings/en-US": APIError(400, "Invalid text")})
        with self.assertRaises(APIError):
            self.client(transport).apply_listings(DESIRED)
        self.assertEqual([call["method"] for call in transport.calls], ["POST", "GET", "PUT", "DELETE"])

    def test_validate_failure_never_commits_and_discards_edit(self):
        transport = FakeTransport(failures={":validate": APIError(400, "Validation failed")})
        with self.assertRaises(APIError):
            self.client(transport).apply_listings(DESIRED)
        self.assertFalse(any(call["url"].endswith(":commit") for call in transport.calls))
        self.assertEqual(transport.calls[-1]["method"], "DELETE")

    def test_rejected_commit_is_not_retried_and_discards_edit(self):
        transport = FakeTransport(failures={":commit": APIError(400, "Changes already in review")})
        with self.assertRaisesRegex(APIError, "already in review"):
            self.client(transport).apply_listings(DESIRED)
        self.assertEqual(len([call for call in transport.calls if call["url"].endswith(":commit")]), 1)
        self.assertEqual(transport.calls[-1]["method"], "DELETE")

    def test_uncertain_commit_reports_unknown_outcome(self):
        for failure in (PlayError("Timeout"), APIError(503, "Unavailable")):
            with self.subTest(failure=failure):
                transport = FakeTransport(failures={":commit": failure})
                with self.assertRaisesRegex(PlayError, "outcome is unknown.*edit-123"):
                    self.client(transport).apply_listings(DESIRED)
                self.assertEqual(len([call for call in transport.calls if call["url"].endswith(":commit")]), 1)

    def test_malformed_successful_commit_is_reported_as_unknown(self):
        transport = FakeTransport()
        original_request = transport.request

        def request(method, url, **kwargs):
            result = original_request(method, url, **kwargs)
            return {} if url.endswith(":commit") else result

        transport.request = request
        with self.assertRaisesRegex(PlayError, "outcome is unknown"):
            self.client(transport).apply_listings(DESIRED)
        self.assertEqual(transport.calls[-1]["method"], "DELETE")

    def test_cleanup_404_means_edit_is_already_absent(self):
        transport = FakeTransport(failures={"/edit-123": ("DELETE", APIError(404, "Not found"))})
        self.assertEqual(self.client(transport).list_listings(), CURRENT)

    def test_cleanup_error_does_not_hide_primary_failure(self):
        transport = FakeTransport(failures={
            ":validate": APIError(400, "Validation failed"),
            "/edit-123": ("DELETE", APIError(403, "Cleanup denied")),
        })
        with self.assertRaisesRegex(PlayError, "Validation failed\n.*") as raised:
            self.client(transport).apply_listings(DESIRED)
        self.assertIn("Could not delete temporary edit edit-123", str(raised.exception))
        self.assertIn("Cleanup denied", str(raised.exception))

    def test_cleanup_error_on_successful_read_is_reported(self):
        transport = FakeTransport(failures={"/edit-123": ("DELETE", APIError(403, "Cleanup denied"))})
        with self.assertRaisesRegex(PlayError, "Could not delete"):
            self.client(transport).list_listings()

    def test_missing_insert_id_never_uses_invalid_endpoint(self):
        transport = FakeTransport()
        transport.request = lambda *args, **kwargs: {}
        with self.assertRaisesRegex(PlayError, "An edit may have been created"):
            self.client(transport).list_listings()


class LocalTests(unittest.TestCase):
    def test_transport_rejects_redirected_write_without_following_location(self):
        calls = []
        def request(method, url, **kwargs):
            calls.append((method, url, kwargs))
            return SimpleNamespace(
                status_code=302, content=b"redirect", headers={"Location": "https://other.example/write"},
                json=lambda: {"error": {"message": "Redirect response"}},
            )
        transport = ADCTransport.__new__(ADCTransport)
        transport.timeout = 1
        transport.session = SimpleNamespace(request=request)
        with self.assertRaises(APIError) as raised:
            transport.request("POST", "https://androidpublisher.googleapis.com/androidpublisher/v3/applications/com.example.focus/dataSafety",
                              payload={"safetyLabels": "synthetic CSV"})
        self.assertEqual(raised.exception.status, 302)
        self.assertEqual(len(calls), 1)
        self.assertFalse(calls[0][2]["allow_redirects"])
        self.assertNotIn("other.example", calls[0][1])

    def test_local_plan_lists_only_changed_fields(self):
        plan = plan_listings(DESIRED, CURRENT)
        self.assertTrue(plan["baselineProvided"])
        self.assertEqual(plan["changedLocales"], 1)
        self.assertEqual(set(plan["changes"][0]["fields"]), {"title"})

    def test_plan_without_baseline_says_so(self):
        self.assertFalse(plan_listings(DESIRED)["baselineProvided"])

    def test_invalid_baseline_is_actionable(self):
        with self.assertRaisesRegex(ValueError, "Baseline"):
            plan_listings(DESIRED, {"en-US": "unexpected"})

    def test_listing_response_rejects_duplicate_languages(self):
        with self.assertRaisesRegex(PlayError, "duplicate"):
            listing_map({"listings": [{"language": "en-US"}, {"language": "en-US"}]})

    def test_export_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "listing.json"
            write_json(output, DESIRED)
            with self.assertRaises(FileExistsError):
                write_json(output, CURRENT)
            self.assertEqual(json.loads(output.read_text()), DESIRED)

    def test_default_apply_cli_is_offline(self):
        with tempfile.TemporaryDirectory() as directory:
            input_path = Path(directory) / "listing.json"
            write_json(input_path, DESIRED)
            with patch("shared.play_api.ADCTransport", side_effect=AssertionError("Must stay offline")):
                with contextlib.redirect_stdout(io.StringIO()) as stdout:
                    code = main(["apply", "--input", str(input_path), "--package", "com.example.focus"])
            self.assertEqual(code, 0)
            self.assertEqual(json.loads(stdout.getvalue())["status"], "dry-run")

    def test_invalid_input_live_cli_never_loads_credentials(self):
        with tempfile.TemporaryDirectory() as directory:
            input_path = Path(directory) / "listing.json"
            write_json(input_path, {"en-US": {"title": "x" * 31}})
            with patch("shared.play_api.ADCTransport", side_effect=AssertionError("Must stay offline")):
                with contextlib.redirect_stderr(io.StringIO()):
                    code = main(["apply", "--input", str(input_path), "--package", "com.example.focus", "--live"])
            self.assertEqual(code, 2)

    def test_live_cli_creates_backup_and_reports_committed(self):
        transport = FakeTransport()
        with tempfile.TemporaryDirectory() as directory:
            input_path = Path(directory) / "listing.json"
            backup = Path(directory) / "before.json"
            write_json(input_path, DESIRED)
            with patch("shared.play_api.ADCTransport", return_value=transport):
                with contextlib.redirect_stdout(io.StringIO()) as stdout:
                    code = main([
                        "apply", "--input", str(input_path), "--package", "com.example.focus",
                        "--live", "--backup", str(backup),
                    ])
            self.assertEqual(code, 0)
            self.assertEqual(json.loads(stdout.getvalue())["status"], "committed")
            self.assertEqual(json.loads(backup.read_text()), CURRENT)


if __name__ == "__main__":
    unittest.main()
