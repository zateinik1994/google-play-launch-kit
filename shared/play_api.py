#!/usr/bin/env python3
"""Small Android Publisher v3 client for localized listing text.

Offline validation and planning need only the standard library. Network commands
use Application Default Credentials and the optional google-auth[requests] extra.
"""

from __future__ import annotations

import argparse
import json
import secrets
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Protocol
from urllib.parse import quote, urlencode

try:
    from .metadata import validate_listings
except ImportError:  # Also support running the file from an installed skill.
    from metadata import validate_listings


API_ROOT = "https://androidpublisher.googleapis.com/androidpublisher/v3"
OAUTH_SCOPE = "https://www.googleapis.com/auth/androidpublisher"
LISTING_FIELDS = ("title", "shortDescription", "fullDescription", "video")


class PlayError(RuntimeError):
    """An actionable API, authentication, or protocol failure."""


class APIError(PlayError):
    def __init__(self, status: int, message: str):
        self.status = status
        super().__init__(f"Google Play API HTTP {status}: {message}")


class Transport(Protocol):
    def request(
        self,
        method: str,
        url: str,
        *,
        payload: Mapping[str, Any] | None = None,
        query: Mapping[str, Any] | None = None,
    ) -> Mapping[str, Any]: ...


class ADCTransport:
    """Authorized HTTPS transport; no retries after network or server errors."""

    def __init__(self, timeout: float = 60.0):
        try:
            import google.auth
            from google.auth.transport.requests import AuthorizedSession
        except ImportError as exc:
            raise PlayError(
                'Network commands require: python3 -m pip install "google-auth[requests]>=2"'
            ) from exc
        try:
            credentials, _ = google.auth.default(scopes=[OAUTH_SCOPE])
            self.session = AuthorizedSession(credentials, max_refresh_attempts=1)
        except Exception as exc:
            raise PlayError(
                "Application Default Credentials are unavailable. Configure ADC or "
                "GOOGLE_APPLICATION_CREDENTIALS for an account authorized in Play Console."
            ) from exc
        self.timeout = timeout

    def request(self, method, url, *, payload=None, query=None):
        if query:
            url += "?" + urlencode(query)
        try:
            response = self.session.request(
                method, url, json=payload, timeout=self.timeout
            )
        except Exception as exc:
            # Do not print an exception that could contain credential material.
            raise PlayError(
                f"{type(exc).__name__} while contacting Google Play; no automatic retry."
            ) from exc
        if not 200 <= response.status_code < 300:
            try:
                message = response.json().get("error", {}).get("message", "Request failed")
            except (ValueError, AttributeError):
                message = "Request failed (non-JSON response)"
            raise APIError(response.status_code, str(message))
        if not response.content:
            return {}
        try:
            result = response.json()
        except ValueError as exc:
            raise PlayError("Google Play returned invalid JSON; no automatic retry.") from exc
        if not isinstance(result, dict):
            raise PlayError("Google Play returned a non-object JSON response.")
        return result


def listing_map(response: Mapping[str, Any]) -> dict[str, dict[str, str]]:
    """Convert list API output to the round-trippable, local JSON format."""
    listings = response.get("listings", [])
    if not isinstance(listings, list):
        raise PlayError("Google Play returned invalid listings.")
    result: dict[str, dict[str, str]] = {}
    for listing in listings:
        if not isinstance(listing, dict):
            raise PlayError("Google Play returned an invalid listing.")
        language = listing.get("language")
        if not isinstance(language, str) or not language or language in result:
            raise PlayError("Google Play returned a missing or duplicate listing language.")
        fields = {key: listing[key] for key in LISTING_FIELDS if key in listing}
        if any(not isinstance(value, str) for value in fields.values()):
            raise PlayError(f"Google Play returned invalid text fields for {language}.")
        result[language] = fields
    return result


def desired_listing(
    language: str,
    desired: Mapping[str, str],
    current: Mapping[str, str] | None,
) -> dict[str, str]:
    """Preserve an existing video when local metadata does not specify it."""
    body = {key: value for key, value in (current or {}).items() if key in LISTING_FIELDS}
    body.update({key: value for key, value in desired.items() if key in LISTING_FIELDS})
    body["language"] = language
    return body


def plan_listings(
    desired: Mapping[str, Mapping[str, str]],
    current: Mapping[str, Mapping[str, str]] | None = None,
) -> dict[str, Any]:
    """Build a plan without API access; omitted locales are never deleted."""
    errors = validate_listings(desired)
    if errors:
        raise ValueError("Invalid metadata:\n" + "\n".join(errors))
    if current is not None:
        if not isinstance(current, dict) or any(
            not isinstance(language, str)
            or not language
            or not isinstance(listing, dict)
            or any(key not in LISTING_FIELDS or not isinstance(value, str) for key, value in listing.items())
            for language, listing in current.items()
        ):
            raise ValueError("Baseline must map language tags to listing text fields.")
    baseline = current or {}
    changes = []
    for language in sorted(desired):
        before = baseline.get(language, {})
        after = desired_listing(language, desired[language], before)
        fields = {
            key: {"from": before.get(key), "to": after.get(key)}
            for key in LISTING_FIELDS
            if before.get(key) != after.get(key)
        }
        if fields:
            changes.append({"language": language, "operation": "update", "fields": fields})
    return {
        "baselineProvided": current is not None,
        "changedLocales": len(changes),
        "changes": changes,
    }


class _Edit:
    def __init__(self, client: "PlayPublisher", edit_id: str):
        self.client = client
        self.id = edit_id
        self.committed = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        if not self.committed:
            try:
                self.client.delete_edit(self.id)
            except APIError as cleanup:
                if cleanup.status == 404:  # Expired, invalidated, or already committed.
                    return False
                self._cleanup_error(exc, cleanup)
            except Exception as cleanup:
                self._cleanup_error(exc, cleanup)
        return False

    def _cleanup_error(self, primary, cleanup):
        message = f"Could not delete temporary edit {self.id}: {cleanup}"
        if primary is not None:
            raise PlayError(f"{primary}\n{message}") from primary
        raise PlayError(message) from cleanup


class PlayPublisher:
    def __init__(self, package_name: str, transport: Transport):
        if not package_name or any(char.isspace() for char in package_name):
            raise ValueError("A non-empty Android package name is required.")
        self.package_name = package_name
        self.transport = transport
        self.root = f"{API_ROOT}/applications/{quote(package_name, safe='')}/edits"

    def _edit_url(self, edit_id: str) -> str:
        return f"{self.root}/{quote(edit_id, safe='')}"

    def new_edit(self) -> _Edit:
        result = self.transport.request("POST", self.root, payload={})
        edit_id = result.get("id")
        if not isinstance(edit_id, str) or not edit_id:
            raise PlayError(
                "Insert returned no edit ID. An edit may have been created; "
                "inspect Play Console before retrying."
            )
        return _Edit(self, edit_id)

    def delete_edit(self, edit_id: str):
        return self.transport.request("DELETE", self._edit_url(edit_id))

    def list_listings(self) -> dict[str, dict[str, str]]:
        # Listing API requires an edit; even this read invalidates an earlier
        # edit owned by the same account. Keep the edit short and discard it.
        with self.new_edit() as edit:
            response = self.transport.request("GET", f"{self._edit_url(edit.id)}/listings")
            return listing_map(response)

    def apply_listings(
        self,
        desired: Mapping[str, Mapping[str, str]],
        *,
        save_backup: Callable[[dict[str, dict[str, str]]], None] | None = None,
        changes_not_sent_for_review: bool = False,
    ) -> dict[str, Any]:
        # Local validation must happen before insert or credential-dependent IO.
        plan_listings(desired)
        with self.new_edit() as edit:
            base_url = self._edit_url(edit.id)
            current = listing_map(self.transport.request("GET", f"{base_url}/listings"))
            plan = plan_listings(desired, current)
            if not plan["changes"]:
                return {"status": "unchanged", "editId": edit.id, "plan": plan}
            # The CLI saves this snapshot before any listing PUT or commit.
            if save_backup is not None:
                save_backup(current)
            for change in plan["changes"]:
                language = change["language"]
                self.transport.request(
                    "PUT",
                    f"{base_url}/listings/{quote(language, safe='')}",
                    payload=desired_listing(language, desired[language], current.get(language)),
                )
            self.transport.request("POST", f"{base_url}:validate")
            query: dict[str, str] = {"changesInReviewBehavior": "ERROR_IF_IN_REVIEW"}
            if changes_not_sent_for_review:
                query["changesNotSentForReview"] = "true"
            try:
                response = self.transport.request("POST", f"{base_url}:commit", query=query)
                if not isinstance(response.get("id"), str) or not response["id"]:
                    raise PlayError("Commit response did not contain an edit ID.")
            except PlayError as exc:
                uncertain = not isinstance(exc, APIError) or exc.status == 408 or exc.status >= 500
                if uncertain:
                    raise PlayError(
                        f"Commit outcome is unknown for edit {edit.id}: {exc}. "
                        "Check Play Console before retrying. Deleting an edit cannot "
                        "undo a successful commit."
                    ) from exc
                raise
            edit.committed = True
            return {"status": "committed", "editId": edit.id, "plan": plan}


def read_json(path: str | Path) -> dict[str, Any]:
    with Path(path).open(encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError("Metadata JSON must be an object mapping language tags to listings.")
    return data


def write_json(path: Path, data: Mapping[str, Any]) -> None:
    """Save an export without silently overwriting another backup."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    validate = commands.add_parser("validate", help="Validate local metadata without network access")
    validate.add_argument("--input", required=True)
    plan = commands.add_parser("plan", help="Plan local changes without network access")
    plan.add_argument("--input", required=True)
    plan.add_argument("--current", help="Optional previously exported listing JSON")
    list_command = commands.add_parser("list", help="Read listings using a temporary API edit")
    list_command.add_argument("--package", required=True)
    export = commands.add_parser("export", help="Read listings into a new JSON file")
    export.add_argument("--package", required=True)
    export.add_argument("--output", required=True)
    apply = commands.add_parser("apply", help="Offline dry run unless --live is supplied")
    apply.add_argument("--input", required=True)
    apply.add_argument("--package", required=True)
    apply.add_argument("--current", help="Local baseline for the offline dry run")
    apply.add_argument("--live", action="store_true", help="Update, validate, and commit listings")
    apply.add_argument("--backup", help="New snapshot file; default outputs/play-backups/<unique>.json")
    apply.add_argument("--changes-not-sent-for-review", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "validate":
            errors = validate_listings(read_json(args.input))
            result = {"valid": not errors, "errors": errors}
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 2 if errors else 0
        if args.command == "plan" or (args.command == "apply" and not args.live):
            baseline = read_json(args.current) if args.current else None
            result = {
                "status": "dry-run",
                "plan": plan_listings(read_json(args.input), baseline),
            }
        else:
            desired = None
            if args.command == "apply":
                desired = read_json(args.input)
                plan_listings(desired)
                if args.current:
                    raise ValueError("--current applies to offline planning; live uses a fresh API snapshot.")
            client = PlayPublisher(args.package, ADCTransport())
            if args.command in ("list", "export"):
                result = client.list_listings()
                if args.command == "export":
                    write_json(Path(args.output), result)
                    result = {"status": "exported", "output": str(Path(args.output)), "locales": len(result)}
            else:
                timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
                backup = Path(args.backup) if args.backup else Path("outputs/play-backups") / (
                    f"{quote(args.package, safe='')}-{timestamp}-{secrets.token_hex(4)}.json"
                )
                result = client.apply_listings(
                    desired,
                    save_backup=lambda snapshot: write_json(backup, snapshot),
                    changes_not_sent_for_review=args.changes_not_sent_for_review,
                )
                if result["status"] == "committed":
                    result["backup"] = str(backup)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (ValueError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except PlayError as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
