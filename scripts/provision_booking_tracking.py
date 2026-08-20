#!/usr/bin/env python3
"""Provision Kesher booking reconciliation resources without exposing secrets.

Modes:
  cloudflare       Ensure D1 exists, apply schema, and bind BOOKING_DB to Pages.
  calendly-status  Check whether the target Calendly webhook already exists.
  calendly-create  Create a user-scoped Calendly webhook using a supplied signing key.

The script emits GitHub Actions outputs when GITHUB_OUTPUT is available. It never
prints tokens or webhook signing keys.
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

PROJECT_NAME = "kesher-website"
DATABASE_NAME = "kesher-booking-attribution"
BOOKING_BINDING = "BOOKING_DB"
WEBHOOK_URL = "https://kesher.saharoni.com/api/calendly/webhook"
CALENDLY_API = "https://api.calendly.com"
CLOUDFLARE_API = "https://api.cloudflare.com/client/v4"
MIGRATION_FILE = pathlib.Path("migrations/0001_booking_attribution.sql")


class ProvisioningError(RuntimeError):
    pass


def emit_output(name: str, value: str) -> None:
    output_path = os.environ.get("GITHUB_OUTPUT")
    if output_path:
        with open(output_path, "a", encoding="utf-8") as handle:
            handle.write(f"{name}={value}\n")
    else:
        print(f"{name}={value}")


def request_json(
    url: str,
    *,
    method: str = "GET",
    token: str,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "User-Agent": "kesher-booking-provisioner/1",
    }
    if body is not None:
        headers["Content-Type"] = "application/json"

    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")[:2000]
        raise ProvisioningError(
            f"{method} {urllib.parse.urlsplit(url).path} failed with HTTP {exc.code}: {error_body}"
        ) from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise ProvisioningError(
            f"{method} {urllib.parse.urlsplit(url).path} failed: {exc}"
        ) from exc


def require_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise ProvisioningError(f"Required environment variable {name} is not configured")
    return value


def cloudflare_result(response: dict[str, Any]) -> Any:
    if response.get("success") is not True:
        errors = response.get("errors") or []
        raise ProvisioningError(f"Cloudflare API returned failure: {errors}")
    return response.get("result")


def ensure_d1(account_id: str, token: str) -> tuple[str, bool]:
    query = urllib.parse.urlencode({"name": DATABASE_NAME, "per_page": "100"})
    listed = cloudflare_result(
        request_json(
            f"{CLOUDFLARE_API}/accounts/{account_id}/d1/database?{query}",
            token=token,
        )
    ) or []

    matches = [item for item in listed if item.get("name") == DATABASE_NAME]
    if len(matches) > 1:
        raise ProvisioningError(f"Multiple D1 databases named {DATABASE_NAME} exist")
    if matches:
        database_id = str(matches[0].get("uuid") or matches[0].get("id") or "")
        if not database_id:
            raise ProvisioningError("Existing D1 database response did not contain an ID")
        return database_id, False

    created = cloudflare_result(
        request_json(
            f"{CLOUDFLARE_API}/accounts/{account_id}/d1/database",
            method="POST",
            token=token,
            payload={"name": DATABASE_NAME},
        )
    ) or {}
    database_id = str(created.get("uuid") or created.get("id") or "")
    if not database_id:
        raise ProvisioningError("Created D1 database response did not contain an ID")
    return database_id, True


def apply_schema(account_id: str, token: str, database_id: str) -> None:
    if not MIGRATION_FILE.exists():
        raise ProvisioningError(f"Migration file is missing: {MIGRATION_FILE}")
    sql = MIGRATION_FILE.read_text(encoding="utf-8").strip()
    if not sql:
        raise ProvisioningError("Booking attribution migration is empty")

    result = cloudflare_result(
        request_json(
            f"{CLOUDFLARE_API}/accounts/{account_id}/d1/database/{database_id}/query",
            method="POST",
            token=token,
            payload={"sql": sql},
        )
    ) or []
    if any(item.get("success") is False for item in result if isinstance(item, dict)):
        raise ProvisioningError("D1 schema query returned an unsuccessful statement")


def ensure_pages_binding(account_id: str, token: str, database_id: str) -> bool:
    project_response = request_json(
        f"{CLOUDFLARE_API}/accounts/{account_id}/pages/projects/{PROJECT_NAME}",
        token=token,
    )
    project = cloudflare_result(project_response) or {}
    configs = project.get("deployment_configs") or {}

    production = configs.get("production") or {}
    preview = configs.get("preview") or {}
    production_d1 = dict(production.get("d1_databases") or {})
    preview_d1 = dict(preview.get("d1_databases") or {})

    desired = {"id": database_id}
    changed = (
        production_d1.get(BOOKING_BINDING) != desired
        or preview_d1.get(BOOKING_BINDING) != desired
    )
    if not changed:
        return False

    production_d1[BOOKING_BINDING] = desired
    preview_d1[BOOKING_BINDING] = desired

    patch = {
        "deployment_configs": {
            "production": {"d1_databases": production_d1},
            "preview": {"d1_databases": preview_d1},
        }
    }
    cloudflare_result(
        request_json(
            f"{CLOUDFLARE_API}/accounts/{account_id}/pages/projects/{PROJECT_NAME}",
            method="PATCH",
            token=token,
            payload=patch,
        )
    )
    return True


def cloudflare_mode() -> None:
    account_id = require_env("CLOUDFLARE_ACCOUNT_ID")
    token = require_env("CLOUDFLARE_API_TOKEN")

    database_id, created = ensure_d1(account_id, token)
    apply_schema(account_id, token, database_id)
    binding_changed = ensure_pages_binding(account_id, token, database_id)

    emit_output("database_id", database_id)
    emit_output("database_created", "true" if created else "false")
    emit_output("binding_changed", "true" if binding_changed else "false")
    print(
        f"Cloudflare booking reconciliation ready: database={'created' if created else 'existing'}, "
        f"binding={'updated' if binding_changed else 'already-current'}"
    )


def calendly_headers_token() -> str:
    return require_env("CALENDLY_API_TOKEN")


def calendly_current_user(token: str) -> tuple[str, str]:
    response = request_json(f"{CALENDLY_API}/users/me", token=token)
    resource = response.get("resource") or {}
    user_uri = str(resource.get("uri") or "")
    organization_uri = str(resource.get("current_organization") or "")
    if not user_uri or not organization_uri:
        raise ProvisioningError("Calendly /users/me did not return user and organization URIs")
    return user_uri, organization_uri


def list_calendly_webhooks(token: str, user_uri: str, organization_uri: str) -> list[dict[str, Any]]:
    query = urllib.parse.urlencode(
        {"organization": organization_uri, "scope": "user", "user": user_uri}
    )
    response = request_json(f"{CALENDLY_API}/webhook_subscriptions?{query}", token=token)
    collection = response.get("collection") or []
    return [item for item in collection if isinstance(item, dict)]


def webhook_matches(item: dict[str, Any]) -> bool:
    callback = str(item.get("callback_url") or item.get("url") or "")
    state = str(item.get("state") or "")
    events = set(item.get("events") or [])
    return (
        callback == WEBHOOK_URL
        and state in {"active", ""}
        and {"invitee.created", "invitee.canceled"}.issubset(events)
    )


def calendly_status_mode() -> None:
    token = calendly_headers_token()
    user_uri, organization_uri = calendly_current_user(token)
    subscriptions = list_calendly_webhooks(token, user_uri, organization_uri)
    matches = [item for item in subscriptions if webhook_matches(item)]
    if len(matches) > 1:
        raise ProvisioningError("Multiple active Kesher Calendly webhook subscriptions exist")
    emit_output("webhook_exists", "true" if matches else "false")
    print("Calendly webhook status: " + ("already-active" if matches else "missing"))


def calendly_create_mode() -> None:
    token = calendly_headers_token()
    signing_key = require_env("CALENDLY_WEBHOOK_SIGNING_KEY")
    if len(signing_key) < 32:
        raise ProvisioningError("Calendly webhook signing key must contain at least 32 characters")

    user_uri, organization_uri = calendly_current_user(token)
    subscriptions = list_calendly_webhooks(token, user_uri, organization_uri)
    matches = [item for item in subscriptions if webhook_matches(item)]
    if matches:
        print("Calendly webhook already exists; creation skipped")
        return

    request_json(
        f"{CALENDLY_API}/webhook_subscriptions",
        method="POST",
        token=token,
        payload={
            "url": WEBHOOK_URL,
            "events": ["invitee.created", "invitee.canceled"],
            "organization": organization_uri,
            "user": user_uri,
            "scope": "user",
            "signing_key": signing_key,
        },
    )
    print("Calendly booking webhook created successfully")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("cloudflare", "calendly-status", "calendly-create"))
    args = parser.parse_args()

    try:
        if args.mode == "cloudflare":
            cloudflare_mode()
        elif args.mode == "calendly-status":
            calendly_status_mode()
        else:
            calendly_create_mode()
    except ProvisioningError as exc:
        print(f"Provisioning failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
