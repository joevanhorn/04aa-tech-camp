#!/usr/bin/env python3
"""Reset an O4AA lab org between iterations — wipe the attendee-built artifacts, keep the pre-state.

Removes exactly what a run of Modules 2-5 creates, so the next run starts from the same lab-ready
baseline `provision_lab_org.py` established. It does NOT touch the pre-state (groups, persona users,
`vantage-crm-as` + its policy) or the central apps' enrollment.

Wipes (idempotent — silent if already gone):
  • the attendee's AI agent (default name "TaskVantage Sales Agent") — deactivate + delete; this also
    drops its managed connections (CRM + any Desk connection).
  • its user-sign-on OIDC app (default "TaskVantage Agent UI") — deactivate + delete.
  • `vantage-desk-as` (built in Module 4) — deactivate + delete.
  • Module-5 OIG residue: remove members from "CRM Read - Cross-Functional" (Frank's temporary grant).

The attendee's MCP Adapter is reset on the adapter side when you pass --adapter + --adapter-token:
it deletes the agent's adapter **resources** (so no orphaned resource survives with a dead
connection_id → silent 0 tools next run) and then the adapter agent. Otherwise do it via the Admin UI.

Usage:
  export OKTA_ORG=https://demo-o4aa-techcamp-testing.okta.com
  export OKTA_API_TOKEN=<SSWS super-admin token>
  python deploy/reset_lab.py --dry-run
  python deploy/reset_lab.py
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

DRY = False


def req(method, base, path, token, body=None, scheme="SSWS"):
    url = base.rstrip("/") + path
    if DRY and method in ("POST", "PUT", "DELETE"):
        print(f"  DRY {method} {path}")
        return 200, {}
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(url, data=data, method=method)
    r.add_header("Authorization", f"{scheme} {token}")
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


def delete_agent(base, token, name):
    code, body = req("GET", base, "/workload-principals/api/v1/ai-agents?limit=200", token)
    agents = (body.get("data", body) if isinstance(body, dict) else body) or []
    hit = [a for a in agents if (a.get("profile") or {}).get("name") == name or a.get("name") == name]
    if not hit:
        print(f"  agent '{name}': none found"); return
    for a in hit:
        aid = a["id"]
        req("POST", base, f"/workload-principals/api/v1/ai-agents/{aid}/lifecycle/deactivate", token)
        # Deactivation is async; DELETE 400s until the status settles to INACTIVE. Wait for it.
        if not DRY:
            for _ in range(10):
                c, cur = req("GET", base, f"/workload-principals/api/v1/ai-agents/{aid}", token)
                if c == 404 or (isinstance(cur, dict) and cur.get("status") == "INACTIVE"):
                    break
                time.sleep(2)
        code = 0
        for _ in range(1 if DRY else 6):
            code, _ = req("DELETE", base, f"/workload-principals/api/v1/ai-agents/{aid}", token)
            if DRY or code in (200, 202, 204, 404):
                break
            time.sleep(2)
        # DELETE is async too — poll until the agent is actually gone (404).
        if not DRY:
            for _ in range(10):
                c, _ = req("GET", base, f"/workload-principals/api/v1/ai-agents/{aid}", token)
                if c == 404:
                    break
                time.sleep(2)
        print(f"  agent '{name}' ({aid}) deleted (HTTP {code})")


def delete_app(base, token, label):
    code, apps = req("GET", base, f"/api/v1/apps?q={urllib.parse.quote(label)}&limit=50", token)
    hit = [a for a in (apps if isinstance(apps, list) else []) if a.get("label") == label]
    if not hit:
        print(f"  app '{label}': none found"); return
    for a in hit:
        aid = a["id"]
        req("POST", base, f"/api/v1/apps/{aid}/lifecycle/deactivate", token)
        code, _ = req("DELETE", base, f"/api/v1/apps/{aid}", token)
        print(f"  app '{label}' ({aid}) deleted (HTTP {code})")


def delete_auth_server(base, token, name):
    code, servers = req("GET", base, "/api/v1/authorizationServers?limit=200", token)
    hit = [s for s in (servers if isinstance(servers, list) else []) if s.get("name") == name]
    if not hit:
        print(f"  auth server '{name}': none found"); return
    for s in hit:
        sid = s["id"]
        req("POST", base, f"/api/v1/authorizationServers/{sid}/lifecycle/deactivate", token)
        code, _ = req("DELETE", base, f"/api/v1/authorizationServers/{sid}", token)
        print(f"  auth server '{name}' ({sid}) deleted (HTTP {code})")


def empty_group(base, token, name):
    code, groups = req("GET", base, f"/api/v1/groups?q={urllib.parse.quote(name)}", token)
    hit = [g for g in (groups if isinstance(groups, list) else []) if g.get("profile", {}).get("name") == name]
    if not hit:
        print(f"  group '{name}': none found"); return
    gid = hit[0]["id"]
    code, members = req("GET", base, f"/api/v1/groups/{gid}/users?limit=200", token)
    members = members if isinstance(members, list) else []
    for u in members:
        req("DELETE", base, f"/api/v1/groups/{gid}/users/{u['id']}", token)
    print(f"  group '{name}': removed {len(members)} member(s)")


def delete_adapter_agent(adapter, token, okta_agent_name):
    """Adapter-side reset: delete the agent's RESOURCES first, then the agent.

    Deleting the resources is the important part. An orphaned resource survives a reset and, on
    the next import, gets its agent_id reassigned while keeping the OLD (now-deleted)
    connection_id — XAA then fails with "could not create auth headers" and the agent silently
    returns 0 tools. Removing the resources forces a clean re-materialize on the next sync.
    """
    code, body = req("GET", adapter, "/api/admin/agents", token, scheme="Bearer")
    if code != 200:
        print(f"  adapter agents list ({code}) — skipping adapter reset"); return
    agents = body if isinstance(body, list) else body.get("agents", body.get("data", []))
    want = okta_agent_name.lower().replace(" ", "-")  # adapter stores the slug lowercased
    for a in agents or []:
        slug = a.get("agent_id", "")
        if slug.lower() in (want, okta_agent_name.lower()) or a.get("name") == okta_agent_name:
            rc, rbody = req("GET", adapter, "/api/admin/resources", token, scheme="Bearer")
            resources = (rbody.get("resources", rbody) if isinstance(rbody, dict) else rbody) or []
            for r in (resources if isinstance(resources, list) else []):
                if r.get("agent_id") == slug:
                    rn = r.get("name")
                    drc, _ = req("DELETE", adapter, f"/api/admin/resources/{rn}", token, scheme="Bearer")
                    print(f"    adapter resource '{rn}' deleted (HTTP {drc})")
            code, _ = req("DELETE", adapter, f"/api/admin/agents/{slug}", token, scheme="Bearer")
            print(f"  adapter agent '{slug}' deleted (HTTP {code})")


def main() -> int:
    global DRY
    p = argparse.ArgumentParser(description="Reset an O4AA lab org between iterations.")
    p.add_argument("--org", default=os.environ.get("OKTA_ORG"))
    p.add_argument("--token", default=os.environ.get("OKTA_API_TOKEN"))
    p.add_argument("--agent-name", default="TaskVantage Sales Agent")
    p.add_argument("--app-label", default="TaskVantage Agent UI")
    p.add_argument("--adapter", help="adapter base URL (also reset the adapter-side agent)")
    p.add_argument("--adapter-token", default=os.environ.get("ADAPTER_ADMIN_TOKEN"))
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    if not args.org or not args.token:
        raise SystemExit("need --org/OKTA_ORG and --token/OKTA_API_TOKEN")
    DRY = args.dry_run
    base, token = args.org, args.token

    print("Resetting attendee-built artifacts (pre-state preserved)…")
    delete_agent(base, token, args.agent_name)
    delete_app(base, token, args.app_label)
    delete_auth_server(base, token, "vantage-desk-as")
    empty_group(base, token, "CRM Read - Cross-Functional")
    if args.adapter and args.adapter_token:
        delete_adapter_agent(args.adapter, args.adapter_token, args.agent_name)
    elif args.adapter:
        print("  (adapter given but no --adapter-token/ADAPTER_ADMIN_TOKEN — skipped adapter reset)")
    print("Reset complete. Re-run the lab from Module 1.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
