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
      sally.field@atko.email   → (no functional group)    (executive; background persona, used only as narrative)
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
    # Executive — no functional group; interacts only via the agent. Background persona that
    # frames "the agent's access is the user's access" (Module 1.3 / lab-intro); not used in steps.
    ("Sally", "Field", "sally.field@atko.email", []),
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


# ---------------------------------------------------------------------------
# Lab Toolkit support: a read-only OIDC client + a no-MFA authentication policy
# so the on-VDI Lab Toolkit can mint per-persona app-audience tokens (and drive
# the adapter) via the no-browser auth-code flow without a second factor.
# ---------------------------------------------------------------------------
TOOLKIT_LABEL = "O4AA Lab Toolkit"   # display name in Okta; also the lookup key the VDI configurator resolves by
TOOLKIT_REDIRECT = "http://localhost:7777/callback"
TOOLKIT_READ_SCOPES = ["crm.accounts.read", "crm.contacts.read", "crm.opportunities.read"]
NOMFA_POLICY_NAME = "O4AA lab — password only (no MFA)"


def ensure_nomfa_policy(base, token) -> str:
    """An authentication (ACCESS_POLICY) policy that allows 1FA/password — mapped to the
    lab-toolkit and agent apps so the no-browser auth-code flow is never MFA-challenged."""
    code, pols = req("GET", base, "/api/v1/policies?type=ACCESS_POLICY&limit=200", token)
    for p in (pols if isinstance(pols, list) else []):
        if p.get("name") == NOMFA_POLICY_NAME:
            return p["id"]
    code, p = req("POST", base, "/api/v1/policies", token, {
        "type": "ACCESS_POLICY", "name": NOMFA_POLICY_NAME, "status": "ACTIVE",
        "description": "O4AA lab — single-factor (password) so the Lab Toolkit's no-browser flow isn't MFA-challenged."})
    if code not in (200, 201):
        raise SystemExit(f"create NOMFA policy failed ({code}): {p}")
    pid = p.get("id", "DRY")
    # a single allow rule: 1FA (password), any user, any network.
    # NB: omit people.groups — in an ACCESS_POLICY rule the literal "EVERYONE" matches
    # nobody (unlike authorization-server policies), which would silently fall through to
    # the default 2FA catch-all. `people.users.exclude=[]` matches all users.
    req("POST", base, f"/api/v1/policies/{pid}/rules", token, {
        "type": "ACCESS_POLICY", "name": "Password only", "priority": 0,
        "conditions": {"network": {"connection": "ANYWHERE"},
                       "people": {"users": {"exclude": []}}},
        "actions": {"appSignOn": {"access": "ALLOW",
            "verificationMethod": {"factorMode": "1FA", "type": "ASSURANCE", "reauthenticateIn": "PT43800H"}}}})
    return pid


def ensure_toolkit_client(base, token, nomfa_pid, gids) -> tuple[str, str]:
    """Create/reuse the lab-toolkit OIDC app, map it to the NOMFA policy, assign persona groups."""
    code, apps = req("GET", base, f"/api/v1/apps?q={urllib.parse.quote(TOOLKIT_LABEL)}&limit=20", token)
    app = next((a for a in (apps if isinstance(apps, list) else []) if a.get("label") == TOOLKIT_LABEL), None)
    if not app:
        code, app = req("POST", base, "/api/v1/apps", token, {
            "name": "oidc_client", "label": TOOLKIT_LABEL, "signOnMode": "OPENID_CONNECT",
            "credentials": {"oauthClient": {"token_endpoint_auth_method": "none"}},
            "settings": {"oauthClient": {
                "redirect_uris": [TOOLKIT_REDIRECT], "response_types": ["code"],
                "grant_types": ["authorization_code", "refresh_token"], "application_type": "native"}}})
        if code not in (200, 201):
            raise SystemExit(f"create lab-toolkit app failed ({code}): {app}")
    app_id = app.get("id", "DRY")
    client_id = (app.get("credentials", {}).get("oauthClient", {}).get("client_id", "DRY"))
    if nomfa_pid and not DRY:
        req("PUT", base, f"/api/v1/apps/{app_id}/policies/{nomfa_pid}", token)
    for gname in ["Sales Management", "Sales Reps", "IT Help Desk", "CRM Read - Cross-Functional"]:
        if gids.get(gname):
            req("PUT", base, f"/api/v1/apps/{app_id}/groups/{gids[gname]}", token)
    return app_id, client_id


def ensure_toolkit_read_rule(base, token, asid, pid, gids):
    """Add an authorization_code read rule to vantage-crm-as so the lab-toolkit client can mint
    per-persona api://vantage-crm read tokens (the XAA rules only allow token-exchange/jwt-bearer)."""
    name = "Lab toolkit — read (auth code)"
    code, existing = req("GET", base, f"/api/v1/authorizationServers/{asid}/policies/{pid}/rules", token)
    if isinstance(existing, list) and any(r.get("name") == name for r in existing):
        return
    groups = [gids[g] for g in ["Sales Management", "Sales Reps", "IT Help Desk", "CRM Read - Cross-Functional"] if gids.get(g)]
    req("POST", base, f"/api/v1/authorizationServers/{asid}/policies/{pid}/rules", token, {
        "type": "RESOURCE_ACCESS", "name": name, "priority": 1,
        "conditions": {
            "grantTypes": {"include": ["authorization_code"]},
            "scopes": {"include": TOOLKIT_READ_SCOPES},
            "people": {"users": {"exclude": []}, "groups": {"include": groups}}}})


# ---------------------------------------------------------------------------
# Adapter Admin-UI client: the OIDC SPA the MCP-adapter bridge's Admin UI signs
# into (its ADMIN_UI_OKTA_CLIENT_ID) AND the one the VDI's setup-crm-resource
# helper mints an admin token against (the no-browser brokered flow) to wire the
# CRM resource. One client serves both the browser GUI and the headless VDI flow.
#
# NB: a headless *service* app (client_credentials + private_key_jwt, for the
# bridge's ADMIN_API_SERVICE_CLIENT_IDS allowlist) is intentionally NOT created
# here. The adapter admin API accepts any org-issuer *user* token as admin (no
# scope gate — okta_agent_proxy/admin/auth.py), and the lab's wiring runs under
# the attendee's own admin sign-in, so the service-app path isn't needed for the
# end-to-end flow. (It also needs an RSA keypair/JWK, which the stdlib-only
# provisioner can't mint — defer to the bridge automation if a no-user path is
# ever required.)
# ---------------------------------------------------------------------------
ADMIN_UI_LABEL = "O4AA Adapter Admin UI"   # display name in Okta; also the lookup key bind-to-org.sh resolves by
ADMIN_UI_REDIRECTS = ["http://localhost:3001/callback",
                      "http://adapter.taskvantage.lab:3001/callback",
                      # Friendly bridge-GUI hostname the VDI configurator writes to the hosts file
                      # (Configure-OpenCodeAgent.ps1 -BridgeGuiHost); Admin-UI sign-in via this name
                      # needs its callback registered or the OIDC redirect is rejected.
                      "http://bridge.taskvantage.lab:3001/callback"]
ADMIN_UI_API_SCOPES = ["okta.aiAgents.manage", "okta.aiAgents.read", "okta.apps.read",
                       "okta.authorizationServers.read"]


def _everyone_group_id(base, token) -> str | None:
    code, body = req("GET", base, "/api/v1/groups?q=Everyone&limit=20", token)
    for g in (body if isinstance(body, list) else []):
        if g.get("type") == "BUILT_IN" and g.get("profile", {}).get("name") == "Everyone":
            return g["id"]
    return None


def _ensure_admin_ui_redirects(base, token, app_id):
    """Union ADMIN_UI_REDIRECTS into an existing admin-ui app's redirect_uris (idempotent).

    Create sets redirect_uris once; a plain create-if-absent would never add newly-needed callbacks
    (e.g. the friendly bridge-GUI hostname) to orgs provisioned before it existed. Okta has no PATCH
    for oauthClient settings, so re-PUT the full app resource with the field merged."""
    code, full = req("GET", base, f"/api/v1/apps/{app_id}", token)
    if not isinstance(full, dict):
        return
    oc = full.get("settings", {}).get("oauthClient", {})
    have = oc.get("redirect_uris", []) or []
    missing = [u for u in ADMIN_UI_REDIRECTS if u not in have]
    if not missing:
        return
    oc["redirect_uris"] = have + missing
    full.setdefault("settings", {})["oauthClient"] = oc
    code, body = req("PUT", base, f"/api/v1/apps/{app_id}", token, full)
    if code not in (200, 201):
        print(f"  WARN could not update admin-ui redirect_uris ({code}): {body}")
    else:
        print(f"  admin-ui redirect_uris updated (+{len(missing)}): {missing}")


def ensure_admin_ui_client(base, token, nomfa_pid) -> tuple[str, str]:
    """Create/reuse the okta-mcp-admin-ui OIDC SPA: grant the Okta API scopes the adapter admin
    path needs, map it to NOMFA (so the VDI's no-browser admin sign-in isn't MFA-challenged), and
    assign it to Everyone (so the attendee's admin account — whoever the platform provisions — can
    sign in). Returns (app_id, client_id); the client_id is the bridge's ADMIN_UI_OKTA_CLIENT_ID."""
    code, apps = req("GET", base, f"/api/v1/apps?q={urllib.parse.quote(ADMIN_UI_LABEL)}&limit=20", token)
    app = next((a for a in (apps if isinstance(apps, list) else []) if a.get("label") == ADMIN_UI_LABEL), None)
    if not app:
        code, app = req("POST", base, "/api/v1/apps", token, {
            "name": "oidc_client", "label": ADMIN_UI_LABEL, "signOnMode": "OPENID_CONNECT",
            "credentials": {"oauthClient": {"token_endpoint_auth_method": "none"}},
            "settings": {"oauthClient": {
                "redirect_uris": ADMIN_UI_REDIRECTS, "response_types": ["code"],
                "grant_types": ["authorization_code", "refresh_token"], "application_type": "browser"}}})
        if code not in (200, 201):
            raise SystemExit(f"create okta-mcp-admin-ui app failed ({code}): {app}")
    app_id = app.get("id", "DRY")
    client_id = app.get("credentials", {}).get("oauthClient", {}).get("client_id", "DRY")
    if DRY:
        return app_id, client_id
    _ensure_admin_ui_redirects(base, token, app_id)   # add newly-needed callbacks on re-runs
    # Grant the Okta API scopes the adapter admin path requires (idempotent).
    code, grants = req("GET", base, f"/api/v1/apps/{app_id}/grants?limit=200", token)
    granted = {g.get("scopeId") for g in (grants if isinstance(grants, list) else [])}
    for scope in ADMIN_UI_API_SCOPES:
        if scope not in granted:
            req("POST", base, f"/api/v1/apps/{app_id}/grants", token,
                {"scopeId": scope, "issuer": base.rstrip("/")})
    if nomfa_pid:
        req("PUT", base, f"/api/v1/apps/{app_id}/policies/{nomfa_pid}", token)
    eid = _everyone_group_id(base, token)
    if eid:
        req("PUT", base, f"/api/v1/apps/{app_id}/groups/{eid}", token)
    return app_id, client_id


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
# created here — the attendee builds it by hand in Module 5.6 (the lab's review-then-build pattern). The
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
    p.add_argument("--emit-json", nargs="?", const="-", default=None,
                   help="emit the created per-org ids as JSON to the given path (or stdout if '-'/no value) — "
                        "machine-readable hand-off for the bridge automation + the Demo-Platform status callback")
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

    print("Lab Toolkit support (read client + no-MFA policy) …")
    nomfa_pid = ensure_nomfa_policy(base, token)
    print(f"  NOMFA policy = {nomfa_pid}")
    tk_app, tk_client = ensure_toolkit_client(base, token, nomfa_pid, gids)
    print(f"  lab-toolkit app = {tk_app}  client_id = {tk_client}")
    ensure_toolkit_read_rule(base, token, asid, pid, gids)
    print(f"  crm-as auth-code read rule ensured  (toolkit_client_id for toolkit.config.json = {tk_client})")

    print("Adapter Admin-UI client (bridge ADMIN_UI_OKTA_CLIENT_ID + VDI admin sign-in) …")
    au_app, au_client = ensure_admin_ui_client(base, token, nomfa_pid)
    print(f"  okta-mcp-admin-ui app = {au_app}  client_id = {au_client}")

    result = {
        "org_url": base.rstrip("/"),
        "crm_as_id": asid,
        "crm_policy_id": pid,
        "nomfa_policy_id": nomfa_pid,
        "toolkit_client_id": tk_client,
        "admin_ui_client_id": au_client,
        "crm_audience": CRM_AUDIENCE,
        "agent_name": "TaskVantage Sales Agent",
    }

    if not args.no_example_agent:
        print("Example agent (pre-loaded reference; STAGED) …")
        ex = ensure_example_agent(base, token, asid)
        print(f"  {EXAMPLE_AGENT_NAME} = {ex}  (+ CRM managed connection)")
        print(f"  → at launch, materialize its CRM resource with:\n"
              f"     wire_adapter_resource.py --preset crm --okta-agent-id {ex} "
              f"--auth-server-id {asid} --adapter <adapter-url> --mcp-host <mcp-host> "
              f"--org-domain <org>  (adapter token via ADAPTER_ADMIN_TOKEN)")

    if not args.no_oig:
        print("OIG request access (Module 5.3–5.5; the attendee builds the cert campaign in 5.6) …")
        appid, rcid, seqid = ensure_oig_request_access(base, token, gids, args.approver_login)
        print(f"  request app = {appid}  | request-condition = {rcid}  | sequence = {seqid}")
        print(f"  '{XFUNC_GROUP}' is now requestable ({REQUEST_DURATION}, manager approval). "
              f"The certification campaign (5.6) is built by the attendee in the lab, not provisioned.")

    print("\nLab pre-state provisioned. Next: enroll the org in the apps (enroll_tenant.py); the example "
          "agent's CRM resource materializes once the adapter imports it (wire_adapter_resource.py). "
          "The attendee still registers their OWN agent in Module 2.")

    if args.emit_json is not None:
        blob = json.dumps(result, indent=2)
        if args.emit_json in ("-", ""):
            print("\n--- provisioned-ids (json) ---")
            print(blob)
        else:
            with open(args.emit_json, "w") as f:
                f.write(blob + "\n")
            print(f"\nWrote provisioned ids -> {args.emit_json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
