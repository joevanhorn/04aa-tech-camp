#!/usr/bin/env python3
"""Enroll (or list / remove) Okta orgs as tenants of the VantageCRM/VantageDesk apps.

Enrollment trusts an Okta org by its base URL; once enrolled, the apps accept tokens
from any custom auth server under that org (resolved by issuer + JWKS). The registry is
Redis-backed and shared by both apps, so a single enroll is consistent across every
replica and across both apps — but this utility posts to all configured hosts anyway so
it stays correct even if the registry is ever split per app.

Idempotent and dependency-free (Python stdlib only).

Usage:
  # admin key from env (ADMIN_API_KEY) or --admin-key or --from-secret <name>
  export ADMIN_API_KEY="$(aws secretsmanager get-secret-value \
      --secret-id labapps-admin-api-key --region us-east-2 --query SecretString --output text)"

  python deploy/enroll_tenant.py enroll https://attendee01.okta.com
  python deploy/enroll_tenant.py enroll --file roster.txt          # one org base URL per line
  python deploy/enroll_tenant.py list
  python deploy/enroll_tenant.py remove attendee01                 # tenant_id or org URL

Exit code is non-zero if any enroll/remove fails to verify.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request

DEFAULT_HOSTS = [
    "https://vantagecrm.taskvantage-demo.com",
    "https://vantagedesk.taskvantage-demo.com",
]


def _slug(org_base: str) -> str:
    host = re.sub(r"^https?://", "", org_base.strip().rstrip("/").lower())
    sub = host.split(".", 1)[0]
    return re.sub(r"[^a-z0-9-]", "-", sub).strip("-")


def _req(method: str, url: str, admin_key: str, body: dict | None = None) -> tuple[int, object]:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("X-Admin-Api-Key", admin_key)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read().decode()
            return resp.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def _admin_key(args) -> str:
    if args.admin_key:
        return args.admin_key
    if args.from_secret:
        import subprocess  # only if explicitly requested

        return subprocess.check_output(
            ["aws", "secretsmanager", "get-secret-value", "--secret-id", args.from_secret,
             "--region", args.region, "--query", "SecretString", "--output", "text"],
            text=True,
        ).strip()
    key = os.environ.get("ADMIN_API_KEY")
    if not key:
        sys.exit("No admin key: set ADMIN_API_KEY, or pass --admin-key / --from-secret <name>")
    return key


def cmd_enroll(args, key: str) -> int:
    orgs = list(args.orgs)
    if args.file:
        orgs += [ln.strip() for ln in open(args.file) if ln.strip() and not ln.startswith("#")]
    if not orgs:
        sys.exit("enroll: provide one or more org URLs or --file")
    rc = 0
    for org in orgs:
        tid = _slug(org)
        for host in args.hosts:
            st, _ = _req("POST", f"{host}/admin/tenants", key, {"org_base_url": org})
            ok = st in (200, 201)
            # verify the slug shows up
            vst, vbody = _req("GET", f"{host}/admin/tenants", key)
            present = isinstance(vbody, list) and any(t.get("tenant_id") == tid for t in vbody)
            mark = "OK" if (ok and present) else "FAIL"
            if mark == "FAIL":
                rc = 1
            print(f"[{mark}] enroll {org} ({tid}) -> {host}  (POST {st}, verified={present})")
    return rc


def cmd_list(args, key: str) -> int:
    for host in args.hosts:
        st, body = _req("GET", f"{host}/admin/tenants", key)
        print(f"{host}: {st} {json.dumps(body)}")
    return 0


def cmd_remove(args, key: str) -> int:
    tid = _slug(args.org) if "://" in args.org or "." in args.org else args.org
    rc = 0
    for host in args.hosts:
        st, body = _req("DELETE", f"{host}/admin/tenants/{tid}", key)
        ok = st == 200
        rc = rc or (0 if ok else 1)
        print(f"[{'OK' if ok else 'FAIL'}] remove {tid} -> {host} ({st} {json.dumps(body)})")
    return rc


def main() -> int:
    p = argparse.ArgumentParser(description="Enroll/list/remove Okta org tenants for the lab apps.")
    p.add_argument("--hosts", nargs="+", default=DEFAULT_HOSTS, help="App base URLs (default: both apps)")
    p.add_argument("--admin-key", help="Operator admin key (else $ADMIN_API_KEY or --from-secret)")
    p.add_argument("--from-secret", help="AWS Secrets Manager secret id to read the admin key from")
    p.add_argument("--region", default="us-east-2")
    sub = p.add_subparsers(dest="cmd", required=True)

    pe = sub.add_parser("enroll", help="Enroll one or more org base URLs")
    pe.add_argument("orgs", nargs="*", help="Org base URLs, e.g. https://attendee01.okta.com")
    pe.add_argument("--file", help="File with one org base URL per line")

    sub.add_parser("list", help="List enrolled tenants")

    pr = sub.add_parser("remove", help="Remove a tenant by id or org URL")
    pr.add_argument("org", help="tenant_id or org base URL")

    args = p.parse_args()
    key = _admin_key(args)
    return {"enroll": cmd_enroll, "list": cmd_list, "remove": cmd_remove}[args.cmd](args, key)


if __name__ == "__main__":
    raise SystemExit(main())
