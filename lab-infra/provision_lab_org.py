#!/usr/bin/env python3
"""Provision the O4AA lab pre-state into a fresh Okta org (idempotent, stdlib-only).

Stands up everything the lab guide assumes already exists *before* an attendee starts Module 1 —
so a dedicated/preview org goes from empty to lab-ready in one run, and `reset_lab.py` can wipe
the attendee-built artifacts between iterations.

Creates:
  • Groups: Sales Management, Sales Reps, IT Help Desk, CRM Read - Cross-Functional, Engineering.
  • Persona users (password-set, activated) mapped to those groups:
      susan.potter@atko.email  → Sales Management        (full CRM)
      alex.martinez@atko.email → Sales Reps               (full CRM — see binary-model note)
      kim.liu@atko.email       → IT Help Desk             (full CRM; full ITSM in Lab 4)
      frank.boone@atko.email   → Engineering              (no CRM/ITSM by default; OIG round-trip in Lab 5)
  • `vantage-crm-as` authorization server: audience api://vantage-crm, the 5 crm.* scopes, a
    `groups` claim, and the access policy with the 4 group-keyed rules that drive Module 3's
    per-user tool filtering (Sales mgmt / Sales reps / IT help desk / Cross-functional). The policy
    is assigned to ALL_CLIENTS so the attendee's (yet-to-be-registered) agent is governed by it; the
    rules allow the XAA grant types (token-exchange + jwt-bearer). Access is currently BINARY
    (group membership = full CRM tools / none) — graduated per-user filtering is a follow-up; see
    the CRM_RULES note below and lab-infra/README.md "Follow-ups".

Does NOT create: the attendee's agent, its sign-on OIDC app, or `vantage-desk-as` — those are built
during the lab (Modules 2 + 4). Tenant enrollment in the apps is separate (`enroll_tenant.py`).
OIG/Module-5 objects (access-request catalog, certification campaign) are a follow-on.

Usage:
  export OKTA_ORG=https://demo-o4aa-techcamp-testing.okta.com
  export OKTA_API_TOKEN=<SSWS super-admin token>
  export LAB_USER_PASSWORD='<password for persona logins>'      # or --password
  # NOTE: whatever LAB_USER_PASSWORD is set to becomes every persona's login password, and is the
  # value the lab guide surfaces as the {{persona_password}} placeholder (Module 1.3 / 5.3). The
  # lab platform must inject the SAME value into both this provisioner and the guide's placeholder,
  # or attendees can't log in as the personas.
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

# BINARY (0-or-all) ACCESS MODEL — see "Follow-ups" note below and lab-infra/README.md.
# Each rule grants either the FULL crm.* scope set or nothing (membership in a rule's group =
# full CRM tools; no membership = no CRM tools — validated as Alex/Susan=6 tools, Frank=0).
#
# Why binary and not graduated (e.g. Sales reps = read-only subset): the adapter requests the
# connection's FULL INCLUDE_ONLY scope set for EVERY user, and Okta DENIES the whole token
# (no_matching_policy) when the request isn't a subset of a matched rule. A per-group *subset*
# rule (e.g. 3 read scopes for Sales reps) therefore denies those users entirely rather than
# granting a narrower tool set — it's all-or-nothing at the token layer, not graduated.
# Graduated per-user filtering (Sales reps see only read tools) is a documented FOLLOW-UP:
# it needs adapter-side scope narrowing or an Okta intersection-grant. Until then every rule
# below grants the full set so group membership cleanly maps to "has CRM access / doesn't".
_ALL_CRM = ["crm.accounts.read", "crm.accounts.write", "crm.contacts.read",
            "crm.opportunities.read", "crm.opportunities.write"]

# (rule name, group name, granted scopes) — order is the policy priority (Module 3.2 table).
CRM_RULES = [
    ("Sales managers — full access", "Sales Management", _ALL_CRM),
    ("Sales reps — full access", "Sales Reps", _ALL_CRM),
    ("IT help desk — full access", "IT Help Desk", _ALL_CRM),
    ("Cross-functional readers — full access", "CRM Read - Cross-Functional", _ALL_CRM),
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


def _reconcile_policy(base, token, asid, pid):
    """Reassert the desired pre-state on an existing policy: clients=ALL_CLIENTS and ACTIVE.

    Why: deleting the attendee's agent (reset_lab.py) cascades to empty the policy's
    clients.include and can leave it INACTIVE, and a bare create-if-absent would never repair
    that. Re-running provisioning should restore a clean ALL_CLIENTS/active pre-state so the
    attendee can re-pin their own agent in Module 2.11.
    """
    req("PUT", base, f"/api/v1/authorizationServers/{asid}/policies/{pid}", token, {
        "type": "OAUTH_AUTHORIZATION_POLICY", "name": "VantageCRM access policy",
        "description": "Per-user CRM scope filtering (Module 3) + XAA grant",
        "conditions": {"clients": {"include": ["ALL_CLIENTS"]}},
    })
    req("POST", base, f"/api/v1/authorizationServers/{asid}/policies/{pid}/lifecycle/activate", token)


def ensure_policy(base, token, asid) -> str:
    code, pols = req("GET", base, f"/api/v1/authorizationServers/{asid}/policies", token)
    for p in (pols if isinstance(pols, list) else []):
        if p.get("name") == "VantageCRM access policy":
            _reconcile_policy(base, token, asid, p["id"])   # repair clients/active on re-runs
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


EXAMPLE_AGENT_NAME = "VantageCRM Example Agent"
CRM_AUDIENCE = "api://vantage-crm"


def ensure_example_agent(base, token, asid, name=EXAMPLE_AGENT_NAME) -> str:
    """Pre-load a dummy example AI agent + its CRM managed connection.

    Purpose: give attendees a reference agent in UD from lab launch, and let the CRM adapter
    resource materialize at launch (the adapter only surfaces a resource once an agent has a CRM
    managed connection it can sync). The agent stays STAGED — it's illustrative; the bridge won't
    serve live tool calls through it until someone activates it (which the lab doesn't require).
    The adapter-side step (import + enable the resource) is done by `wire_adapter_resource.py`.
    """
    code, body = req("GET", base, "/workload-principals/api/v1/ai-agents?limit=200", token)
    agents = (body.get("data", body) if isinstance(body, dict) else body) or []
    aid = next((a["id"] for a in agents if (a.get("profile") or {}).get("name") == name), None)
    if not aid:
        code, a = req("POST", base, "/workload-principals/api/v1/ai-agents", token,
                      {"profile": {"name": name,
                                   "description": "Reference/example agent for the O4AA lab (pre-loaded at launch; stays STAGED)."}})
        if code not in (200, 201, 202):  # create is async (202)
            raise SystemExit(f"create example agent failed ({code}): {a}")
        aid = (a or {}).get("id")
        if not aid:  # 202 may not return a body — re-fetch by name
            import time as _t; _t.sleep(2)
            _, body2 = req("GET", base, "/workload-principals/api/v1/ai-agents?limit=200", token)
            ag2 = (body2.get("data", body2) if isinstance(body2, dict) else body2) or []
            aid = next((x["id"] for x in ag2 if (x.get("profile") or {}).get("name") == name), None)
            if not aid:
                raise SystemExit("example agent created (202) but not found on re-fetch")
    if DRY:
        return aid
    code, conns = req("GET", base, f"/workload-principals/api/v1/ai-agents/{aid}/connections", token)
    have = any(c.get("resourceIndicator") == CRM_AUDIENCE
               for c in (conns.get("data", []) if isinstance(conns, dict) else []))
    if not have:
        code, org = req("GET", base, "/api/v1/org", token)
        orgid = org.get("id") if isinstance(org, dict) else None
        orn = f"orn:okta:idp:{orgid}:authorization_servers:{asid}"
        code, c = req("POST", base, f"/workload-principals/api/v1/ai-agents/{aid}/connections", token, {
            "connectionType": "IDENTITY_ASSERTION_CUSTOM_AS",
            "authorizationServer": {"orn": orn},
            "resourceIndicator": CRM_AUDIENCE, "scopeCondition": "INCLUDE_ONLY", "scopes": CRM_SCOPES,
        })
        if code not in (200, 201):
            print(f"  WARN example-agent CRM connection ({code}): {c}")
    return aid


# --- OIG: make CRM Read - Cross-Functional requestable (Module 5.3–5.5) -----------------------
# Mirrors the prod "Privileged AD Group Request" pattern: an OIN host app with the group assigned,
# plus an access request-condition. The certification campaign (Module 5.6) is intentionally NOT
# created here — build it in the Admin UI / lab platform (Governance > Access Certifications). The
# approval sequence is also not created (Okta pre-creates a "Requester's Manager Approval" sequence
# per org); we just reference it.
REQUEST_APP_OIN = "scim2testapp_basic"          # same OIN integration prod uses as the host app
REQUEST_APP_LABEL = "VantageCRM Access Requests"
XFUNC_GROUP = "CRM Read - Cross-Functional"
REQUEST_DURATION = "PT2H"                         # 2h for the lab (production would be 30+ days)
FRANK_LOGIN = "frank.boone@atko.email"           # the Module 5 requester whose manager must be set


def ensure_oig_request_access(base, token, gids, approver_login=None):
    """Option-C OIG setup: make the cross-functional group requestable via an OIN host app +
    request-condition, and set the requester's manager so Module 5.4 approval routes correctly."""
    xgid = gids[XFUNC_GROUP]
    # 1. Host app (idempotent by label).
    code, apps = req("GET", base, f"/api/v1/apps?q={urllib.parse.quote(REQUEST_APP_LABEL)}&limit=20", token)
    appid = next((a["id"] for a in (apps if isinstance(apps, list) else [])
                  if a.get("label") == REQUEST_APP_LABEL), None)
    if not appid:
        code, a = req("POST", base, "/api/v1/apps", token,
                      {"name": REQUEST_APP_OIN, "label": REQUEST_APP_LABEL, "signOnMode": "AUTO_LOGIN"})
        appid = a.get("id", "DRY") if isinstance(a, dict) else "DRY"
    # 2. Assign the requestable group to the host app.
    req("PUT", base, f"/api/v1/apps/{appid}/groups/{xgid}", token, {})
    # 3. Set the requester's manager (approval routing). Needs an approver login.
    if approver_login:
        code, u = req("GET", base, f"/api/v1/users/{urllib.parse.quote(approver_login)}", token)
        aid = u.get("id") if isinstance(u, dict) else None
        if aid:
            req("POST", base, f"/api/v1/users/{urllib.parse.quote(FRANK_LOGIN)}", token,
                {"profile": {"managerId": aid, "manager": approver_login}})
    else:
        print("  WARN no --approver-login: Frank has no manager set, so Module 5.4 manager-approval "
              "won't route. Pass --approver-login <admin> (the attendee admin who approves).")
    # 4. Reference the org's pre-created manager-approval request-sequence (prefer one naming a
    #    Manager and supporting GROUP; fall back to the first available).
    code, seqs = req("GET", base, f"/governance/api/v2/resources/{appid}/request-sequences", token)
    slist = seqs.get("data", seqs) if isinstance(seqs, dict) else seqs
    slist = slist if isinstance(slist, list) else []
    seq = next((s for s in slist if "Manager" in (s.get("name") or "")
                and "GROUP" in (s.get("compatibleResourceTypes") or [])), None) or (slist[0] if slist else None)
    seqid = seq.get("id") if seq else None
    # 5. Request-condition (idempotent by name — the list view omits accessScopeSettings.groups,
    #    so we can't match on the group; the name is unique to this condition), then activate.
    rc_name = "Request CRM cross-functional access"
    code, conds = req("GET", base, f"/governance/api/v2/resources/{appid}/request-conditions", token)
    clist = conds.get("data", conds) if isinstance(conds, dict) else conds
    clist = clist if isinstance(clist, list) else []
    rcid = next((c["id"] for c in clist if c.get("name") == rc_name), None)
    if not rcid and seqid:
        code, rc = req("POST", base, f"/governance/api/v2/resources/{appid}/request-conditions", token, {
            "name": rc_name,
            "requesterSettings": {"type": "EVERYONE"},
            "accessScopeSettings": {"type": "GROUPS", "groups": [{"id": xgid}]},
            "accessDurationSettings": {"type": "ADMIN_FIXED_DURATION", "duration": REQUEST_DURATION},
            "approvalSequenceId": seqid})
        rcid = rc.get("id") if isinstance(rc, dict) else None
    elif not seqid:
        print("  WARN no request-sequence found on the host app — cannot create the request-condition.")
    if rcid:
        req("POST", base, f"/governance/api/v2/resources/{appid}/request-conditions/{rcid}/activate", token)
    return appid, rcid, seqid


def main() -> int:
    global DRY
    p = argparse.ArgumentParser(description="Provision O4AA lab pre-state into a fresh Okta org.")
    p.add_argument("--org", default=os.environ.get("OKTA_ORG"), help="org base URL (env OKTA_ORG)")
    p.add_argument("--token", default=os.environ.get("OKTA_API_TOKEN"), help="SSWS token (env OKTA_API_TOKEN)")
    p.add_argument("--password", default=os.environ.get("LAB_USER_PASSWORD"), help="persona login password")
    p.add_argument("--no-example-agent", action="store_true",
                   help="skip pre-loading the example AI agent + its CRM connection")
    p.add_argument("--approver-login", default=os.environ.get("LAB_APPROVER_LOGIN"),
                   help="admin login set as Frank's manager for Module 5.4 approval routing "
                        "(env LAB_APPROVER_LOGIN); omit to skip the OIG request-access setup")
    p.add_argument("--no-oig", action="store_true",
                   help="skip the Module 5 OIG request-access setup (catalog entry + approver)")
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

    if not args.no_example_agent:
        print("Example agent (pre-loaded reference; STAGED) …")
        ex = ensure_example_agent(base, token, asid)
        print(f"  {EXAMPLE_AGENT_NAME} = {ex}  (+ CRM managed connection)")
        print(f"  → at launch, materialize its CRM resource with:\n"
              f"     wire_adapter_resource.py --preset crm --okta-agent-id {ex} "
              f"--auth-server-id {asid} --adapter <adapter-url> --mcp-host <mcp-host> "
              f"--org-domain <org>  (adapter token via ADAPTER_ADMIN_TOKEN)")

    if not args.no_oig:
        print("OIG request access (Module 5.3–5.5; certification campaign 5.6 is a manual/platform step) …")
        appid, rcid, seqid = ensure_oig_request_access(base, token, gids, args.approver_login)
        print(f"  request app = {appid}  | request-condition = {rcid}  | sequence = {seqid}")
        print(f"  '{XFUNC_GROUP}' is now requestable ({REQUEST_DURATION}, manager approval). "
              f"NOTE: create the certification campaign (5.6) in Governance > Access Certifications.")

    print("\nLab pre-state provisioned. Next: enroll the org in the apps (enroll_tenant.py); the example "
          "agent's CRM resource materializes once the adapter imports it (wire_adapter_resource.py). "
          "The attendee still registers their OWN agent in Module 2.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
