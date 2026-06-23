#!/usr/bin/env python3
"""Provision the O4AA lab pre-state into a fresh Okta org (idempotent, stdlib-only).

Stands up everything the lab guide assumes already exists *before* an attendee starts Module 1 —
so a dedicated/preview org goes from empty to lab-ready in one run, and `reset_lab.py` can wipe
the attendee-built artifacts between iterations.

Creates:
  • Groups: Sales Management, Sales Reps, IT Help Desk, CRM Read - Cross-Functional, Engineering.
  • Persona users (password-set, activated) mapped to those groups:
      susan.potter@atko.email  → Sales Management        (full CRM)
      alex.martinez@atko.email → Sales Reps               (read-only CRM)
      kim.liu@atko.email       → IT Help Desk             (limited CRM read; full ITSM in Lab 4)
      frank.boone@atko.email   → Engineering              (no CRM/ITSM by default; OIG round-trip in Lab 5)
  • `vantage-crm-as` authorization server: audience api://vantage-crm, the 5 crm.* scopes, a
    `groups` claim, and the access policy with the 4 group-keyed rules that drive Module 3's
    per-user tool filtering (Sales mgmt / Sales reps / IT help desk / Cross-functional). The policy
    is assigned to ALL_CLIENTS so the attendee's (yet-to-be-registered) agent is governed by it; the
    rules allow the XAA grant types (token-exchange + jwt-bearer).

Does NOT create: the attendee's agent, its sign-on OIDC app, or `vantage-desk-as` — those are built
during the lab (Modules 2 + 4). Tenant enrollment in the apps is separate (`enroll_tenant.py`).
OIG/Module-5 objects (access-request catalog, certification campaign) are a follow-on.

Usage:
  export OKTA_ORG=https://demo-o4aa-techcamp-testing.okta.com
  export OKTA_API_TOKEN=<SSWS super-admin token>
  export LAB_USER_PASSWORD='<password for persona logins>'      # or --password
  python deploy/provision_lab_org.py
  python deploy/provision_lab_org.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

GROUPS = [
    ("Sales Management", "O4AA lab — Sales managers (full CRM)"),
    ("Sales Reps", "O4AA lab — Sales reps (read-only CRM)"),
    ("IT Help Desk", "O4AA lab — IT help desk (full ITSM; limited CRM read)"),
    ("CRM Read - Cross-Functional", "O4AA lab — empty until OIG grants in Lab 5"),
    ("Engineering", "O4AA lab — no CRM/ITSM by default (Frank)"),
]

USERS = [
    # (first, last, login/email, [group names])
    ("Susan", "Potter", "susan.potter@atko.email", ["Sales Management"]),
    ("Alex", "Martinez", "alex.martinez@atko.email", ["Sales Reps"]),
    ("Kim", "Liu", "kim.liu@atko.email", ["IT Help Desk"]),
    ("Frank", "Boone", "frank.boone@atko.email", ["Engineering"]),
]

CRM_SCOPES = ["crm.accounts.read", "crm.accounts.write", "crm.contacts.read",
              "crm.opportunities.read", "crm.opportunities.write"]

# (rule name, group name, granted scopes) — order is the policy priority (Module 3.2 table).
CRM_RULES = [
    ("Sales managers — full access", "Sales Management",
     ["crm.accounts.read", "crm.accounts.write", "crm.contacts.read",
      "crm.opportunities.read", "crm.opportunities.write"]),
    ("Sales reps — read access", "Sales Reps",
     ["crm.accounts.read", "crm.contacts.read", "crm.opportunities.read"]),
    ("IT help desk — limited read", "IT Help Desk",
     ["crm.accounts.read", "crm.contacts.read"]),
    ("Cross-functional readers — read access", "CRM Read - Cross-Functional",
     ["crm.accounts.read", "crm.contacts.read", "crm.opportunities.read"]),
]

XAA_GRANTS = ["urn:ietf:params:oauth:grant-type:token-exchange",
              "urn:ietf:params:oauth:grant-type:jwt-bearer"]

DRY = False


def req(method: str, base: str, path: str, token: str, body: dict | None = None) -> tuple[int, object]:
    url = base.rstrip("/") + path
    if DRY and method != "GET":
        print(f"      DRY {method} {path}  {json.dumps(body) if body else ''}")
        return 200, {}
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(url, data=data, method=method)
    r.add_header("Authorization", f"SSWS {token}")
    r.add_header("Accept", "application/json")
    if data is not None:
        r.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(r, timeout=30) as resp:
            raw = resp.read().decode()
            return resp.status, (json.loads(raw) if raw.strip() else {})
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            return e.code, json.loads(raw)
        except ValueError:
            return e.code, raw


def ensure_group(base, token, name, desc) -> str:
    code, body = req("GET", base, f"/api/v1/groups?q={urllib.parse.quote(name)}", token)
    for g in (body if isinstance(body, list) else []):
        if g.get("profile", {}).get("name") == name:
            return g["id"]
    code, g = req("POST", base, "/api/v1/groups", token, {"profile": {"name": name, "description": desc}})
    if code not in (200, 201):
        raise SystemExit(f"create group {name} failed ({code}): {g}")
    return g.get("id", "DRY")


def ensure_user(base, token, first, last, login, password) -> str:
    code, body = req("GET", base, f"/api/v1/users/{urllib.parse.quote(login)}", token)
    if code == 200 and isinstance(body, dict) and body.get("id"):
        return body["id"]
    code, u = req("POST", base, "/api/v1/users?activate=true", token, {
        "profile": {"firstName": first, "lastName": last, "email": login, "login": login},
        "credentials": {"password": {"value": password}},
    })
    if code not in (200, 201):
        raise SystemExit(f"create user {login} failed ({code}): {u}")
    return u.get("id", "DRY")


def add_to_group(base, token, gid, uid):
    req("PUT", base, f"/api/v1/groups/{gid}/users/{uid}", token)


def ensure_auth_server(base, token) -> str:
    code, body = req("GET", base, "/api/v1/authorizationServers?limit=200", token)
    for a in (body if isinstance(body, list) else []):
        if a.get("name") == "vantage-crm-as":
            return a["id"]
    code, a = req("POST", base, "/api/v1/authorizationServers", token, {
        "name": "vantage-crm-as", "description": "O4AA lab — VantageCRM resource AS",
        "audiences": ["api://vantage-crm"],
    })
    if code not in (200, 201):
        raise SystemExit(f"create vantage-crm-as failed ({code}): {a}")
    return a.get("id", "DRY")


def ensure_scopes(base, token, asid):
    code, existing = req("GET", base, f"/api/v1/authorizationServers/{asid}/scopes?limit=200", token)
    have = {s["name"] for s in existing} if isinstance(existing, list) else set()
    for s in CRM_SCOPES:
        if s in have:
            continue
        req("POST", base, f"/api/v1/authorizationServers/{asid}/scopes", token,
            {"name": s, "consent": "IMPLICIT", "metadataPublish": "ALL_CLIENTS"})


def ensure_groups_claim(base, token, asid):
    code, existing = req("GET", base, f"/api/v1/authorizationServers/{asid}/claims?limit=200", token)
    if isinstance(existing, list) and any(c.get("name") == "groups" for c in existing):
        return
    req("POST", base, f"/api/v1/authorizationServers/{asid}/claims", token, {
        "name": "groups", "status": "ACTIVE", "claimType": "RESOURCE", "valueType": "GROUPS",
        "value": ".*", "group_filter_type": "REGEX", "alwaysIncludeInToken": True,
        "conditions": {"scopes": []},
    })


def ensure_policy(base, token, asid) -> str:
    code, pols = req("GET", base, f"/api/v1/authorizationServers/{asid}/policies", token)
    for p in (pols if isinstance(pols, list) else []):
        if p.get("name") == "VantageCRM access policy":
            return p["id"]
    code, p = req("POST", base, f"/api/v1/authorizationServers/{asid}/policies", token, {
        "type": "OAUTH_AUTHORIZATION_POLICY", "name": "VantageCRM access policy",
        "description": "Per-user CRM scope filtering (Module 3) + XAA grant",
        "conditions": {"clients": {"include": ["ALL_CLIENTS"]}},
    })
    if code not in (200, 201):
        raise SystemExit(f"create CRM policy failed ({code}): {p}")
    return p.get("id", "DRY")


def ensure_rules(base, token, asid, pid, gids):
    code, existing = req("GET", base, f"/api/v1/authorizationServers/{asid}/policies/{pid}/rules", token)
    have = {r.get("name") for r in existing} if isinstance(existing, list) else set()
    for prio, (name, group, scopes) in enumerate(CRM_RULES, start=1):
        if name in have:
            continue
        req("POST", base, f"/api/v1/authorizationServers/{asid}/policies/{pid}/rules", token, {
            "type": "RESOURCE_ACCESS", "name": name, "priority": prio,
            "conditions": {
                "grantTypes": {"include": XAA_GRANTS},
                "scopes": {"include": scopes},
                "people": {"users": {"exclude": []}, "groups": {"include": [gids[group]]}},
            },
        })


def main() -> int:
    global DRY
    p = argparse.ArgumentParser(description="Provision O4AA lab pre-state into a fresh Okta org.")
    p.add_argument("--org", default=os.environ.get("OKTA_ORG"), help="org base URL (env OKTA_ORG)")
    p.add_argument("--token", default=os.environ.get("OKTA_API_TOKEN"), help="SSWS token (env OKTA_API_TOKEN)")
    p.add_argument("--password", default=os.environ.get("LAB_USER_PASSWORD"), help="persona login password")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    if not args.org or not args.token:
        raise SystemExit("need --org/OKTA_ORG and --token/OKTA_API_TOKEN")
    if not args.password and not args.dry_run:
        raise SystemExit("need --password/LAB_USER_PASSWORD (persona logins)")
    DRY = args.dry_run
    base, token = args.org, args.token

    print("Groups …")
    gids = {name: ensure_group(base, token, name, desc) for name, desc in GROUPS}
    for name, gid in gids.items():
        print(f"  {name} = {gid}")

    print("Persona users …")
    for first, last, login, groups in USERS:
        uid = ensure_user(base, token, first, last, login, args.password or "x")
        for gname in groups:
            add_to_group(base, token, gids[gname], uid)
        print(f"  {login} = {uid}  → {', '.join(groups)}")

    print("vantage-crm-as …")
    asid = ensure_auth_server(base, token)
    print(f"  AS = {asid}")
    ensure_scopes(base, token, asid)
    ensure_groups_claim(base, token, asid)
    pid = ensure_policy(base, token, asid)
    print(f"  policy = {pid}")
    ensure_rules(base, token, asid, pid, gids)
    print(f"  rules = {[r[0] for r in CRM_RULES]}")

    print("\nLab pre-state provisioned. Next: enroll the org in the apps (enroll_tenant.py), then the "
          "attendee runs Modules 1-2 (register agent + setup-crm-resource.sh).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
