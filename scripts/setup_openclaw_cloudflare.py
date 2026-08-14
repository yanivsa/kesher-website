#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request

API = "https://api.cloudflare.com/client/v4"
ACCOUNT = os.environ["CLOUDFLARE_ACCOUNT_ID"]
TOKEN = os.environ["CLOUDFLARE_API_TOKEN"]
HOSTNAME = os.environ.get("OPENCLAW_HOSTNAME", "openclaw.the-israeli-lawyer.com")
ALLOWED_EMAIL = os.environ.get("OPENCLAW_ALLOWED_EMAIL", "yanivsa@gmail.com")
TUNNEL_NAME = os.environ.get("OPENCLAW_TUNNEL_NAME", "openclaw-dashboard")
APP_NAME = os.environ.get("OPENCLAW_ACCESS_APP_NAME", "OpenClaw Dashboard")
POLICY_NAME = os.environ.get("OPENCLAW_ACCESS_POLICY_NAME", "Yaniv only")


def request(method: str, path: str, payload=None):
    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json",
    }
    data = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(API + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=45) as r:
            body = json.load(r)
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace")
        try:
            body = json.loads(raw)
        except Exception:
            body = {"errors": [{"message": raw[:1000]}]}
        raise RuntimeError(f"Cloudflare {method} {path} failed HTTP {e.code}: {json.dumps(body.get('errors') or body)[:1200]}") from e
    if isinstance(body, dict) and body.get("success") is False:
        raise RuntimeError(f"Cloudflare {method} {path} failed: {json.dumps(body.get('errors') or body)[:1200]}")
    return body.get("result") if isinstance(body, dict) and "result" in body else body


def paged(path: str):
    sep = "&" if "?" in path else "?"
    page = 1
    out = []
    while True:
        result = request("GET", f"{path}{sep}page={page}&per_page=50")
        if not isinstance(result, list):
            return result or []
        out.extend(result)
        if len(result) < 50:
            return out
        page += 1


def main():
    zones = paged("/zones?status=active")
    zone_name = HOSTNAME.split(".", 1)[1]
    zone = next((z for z in zones if z.get("name") == zone_name), None)
    if not zone:
        raise RuntimeError(f"Active Cloudflare zone not visible for {zone_name}")
    zone_id = zone["id"]

    # Use the narrower zone-scoped Access API. The existing token can see this
    # zone but is intentionally not an account-wide Access administrator.
    access_base = f"/zones/{zone_id}/access"
    apps = paged(f"{access_base}/apps")
    app = next((a for a in apps if a.get("domain") == HOSTNAME), None)
    if not app:
        app = request("POST", f"{access_base}/apps", {
            "name": APP_NAME,
            "domain": HOSTNAME,
            "type": "self_hosted",
            "session_duration": "24h",
            "app_launcher_visible": False,
        })
        print("CF_ACCESS_APP_CREATED=true")
    else:
        print("CF_ACCESS_APP_CREATED=false")
    app_id = app["id"]

    policies = paged(f"{access_base}/apps/{app_id}/policies")
    policy = next((p for p in policies if p.get("name") == POLICY_NAME), None)
    desired_policy = {
        "name": POLICY_NAME,
        "decision": "allow",
        "precedence": 1,
        "include": [{"email": {"email": ALLOWED_EMAIL}}],
    }
    if not policy:
        policy = request("POST", f"{access_base}/apps/{app_id}/policies", desired_policy)
        print("CF_ACCESS_POLICY_CREATED=true")
    else:
        request("PUT", f"{access_base}/apps/{app_id}/policies/{policy['id']}", desired_policy)
        print("CF_ACCESS_POLICY_CREATED=false")

    tunnels = paged(f"/accounts/{ACCOUNT}/cfd_tunnel?is_deleted=false")
    tunnel = next((t for t in tunnels if t.get("name") == TUNNEL_NAME), None)
    if not tunnel:
        tunnel = request("POST", f"/accounts/{ACCOUNT}/cfd_tunnel", {
            "name": TUNNEL_NAME,
            "config_src": "cloudflare",
        })
        print("CF_TUNNEL_CREATED=true")
    else:
        print("CF_TUNNEL_CREATED=false")
    tunnel_id = tunnel["id"]

    request("PUT", f"/accounts/{ACCOUNT}/cfd_tunnel/{tunnel_id}/configurations", {
        "config": {
            "ingress": [
                {
                    "hostname": HOSTNAME,
                    "service": "http://127.0.0.1:18789",
                    "originRequest": {},
                },
                {"service": "http_status:404"},
            ]
        }
    })
    print("CF_TUNNEL_CONFIGURED=true")

    records = paged(f"/zones/{zone_id}/dns_records?type=CNAME&name={urllib.parse.quote(HOSTNAME)}")
    desired_dns = {
        "type": "CNAME",
        "name": HOSTNAME,
        "content": f"{tunnel_id}.cfargotunnel.com",
        "ttl": 1,
        "proxied": True,
    }
    if records:
        request("PUT", f"/zones/{zone_id}/dns_records/{records[0]['id']}", desired_dns)
        print("CF_DNS_CREATED=false")
    else:
        request("POST", f"/zones/{zone_id}/dns_records", desired_dns)
        print("CF_DNS_CREATED=true")

    tunnel_token = request("GET", f"/accounts/{ACCOUNT}/cfd_tunnel/{tunnel_id}/token")
    if not isinstance(tunnel_token, str) or len(tunnel_token) < 50:
        raise RuntimeError("INVALID_TUNNEL_TOKEN_RESPONSE")

    print("OPENCLAW_HOSTNAME=" + HOSTNAME)
    print("CF_ACCESS_APP_ID=" + app_id)
    print("CF_TUNNEL_ID=" + tunnel_id)
    print("CF_SETUP_OK=true")


if __name__ == "__main__":
    main()
