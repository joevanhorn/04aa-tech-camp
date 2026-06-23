#!/usr/bin/env python3
"""Wire one VantageCRM/VantageDesk tool resource into an attendee's Okta MCP Adapter.

This is the environment-setup automation behind the O4AA lab's "review-then-build" pattern:
it **pre-wires the CRM resource as the worked example** so each attendee starts Module 3 with a
live CRM tool path, then hand-builds the Desk resource in Module 4. It codifies the exact
adapter-admin sequence validated end-to-end on 2026-06-23 (see
`04aa-tech-camp/reference/crm-path-validation-runbook.md`).

What it does (all idempotent):
  0. (Optional, with --okta-token) Ensure the agent's **Okta managed connection** for this auth
     server exists, set INCLUDE_ONLY with the granular scopes — the Okta half of pre-wiring CRM
     end-to-end. Omit --okta-token if the attendee already built the connection by hand (Module 2.9).
  1. Import the Okta AI agent into the adapter (skips if already imported).
  2. Mark the agent DCR-selectable (required for the agent's brokered OAuth to link).
  3. Sync managed connections (materializes/refreshes the agent's resources from Okta).
  4. Ensure ONE resource for the given authorization server exists, points at the path-scoped
     MCP URL (`…/crm/mcp` or `…/desk/mcp`), and is enabled.
  5. Verify the resource carries INCLUDE_ONLY granular scopes (not the `mcp:read` fallback).

With --okta-token (Okta org API token, default scheme SSWS) the script wires CRM **end-to-end**
onto the attendee's freshly-registered agent — managed connection + adapter resource — so Module 2
becomes "register your agent, then review the pre-wired CRM example." Without it, the script only
does the adapter half (the attendee built the connection in Okta themselves).

Why path-scoped resources: the adapter binds one resource = one managed connection = one
audience, and tools are namespaced per resource. Both apps sit behind one shared MCP server,
so each app's tools are published at their own path and each resource points at the path whose
audience its token is valid for.

Auth: the adapter admin API accepts an Okta **org-AS** bearer token from a principal with admin
rights (the same login the adapter Admin UI uses). Supply it via --admin-token, env
ADAPTER_ADMIN_TOKEN, or --from-secret <aws-secret-name>.

Dependency-free (Python stdlib only). Idempotent: safe to re-run (also the fix if the adapter is
restarted and a hydrated resource falls back to `mcp:read`).

Usage:
  export ADAPTER_ADMIN_TOKEN="<okta org-AS admin bearer>"

  # Pre-wire the CRM example (Module 2):
  python deploy/wire_adapter_resource.py --preset crm \
      --adapter https://adapter.example.io \
      --okta-agent-id wlp24fnititUIJG4o1d8 \
      --auth-server-id aus24g60q8aVYfJJp1d8 \
      --mcp-host mcp.taskvantage-demo.com

  # The Desk equivalent (what Module 4.7 does by hand):
  python deploy/wire_adapter_resource.py --preset desk \
      --adapter https://adapter.example.io \
      --okta-agent-id wlp24fnititUIJG4o1d8 \
      --auth-server-id aus24fyc55jzybCmT1d8 \
      --mcp-host mcp.taskvantage-demo.com

  # Fully explicit (no preset):
  python deploy/wire_adapter_resource.py \
      --adapter ... --okta-agent-id ... --auth-server-id ... \
      --resource-name vantage-crm --audience api://vantage-crm \
      --mcp-url https://mcp.taskvantage-demo.com/crm/mcp

Exit code is non-zero if the resource cannot be verified enabled with granular scopes.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request

PRESETS = {
    "crm": {
        "resource_name": "vantage-crm",
        "audience": "api://vantage-crm",
        "path": "/crm/mcp",
        "scopes": [
            "crm.accounts.read", "crm.accounts.write", "crm.contacts.read",
            "crm.opportunities.read", "crm.opportunities.write",
        ],
    },
    "desk": {
        "resource_name": "vantage-tools",
        "audience": "api://vantage-desk",
        "path": "/desk/mcp",
        "scopes": [
            "itsm.tickets.read", "itsm.tickets.write", "itsm.incidents.read",
            "itsm.incidents.write", "itsm.kb.read",
        ],
    },
}


def _req(method: str, url: str, token: str, body: dict | None = None) -> tuple[int, object]:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", "application/json")
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode()
            return resp.status, (json.loads(raw) if raw.strip() else {})
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            return e.code, json.loads(raw)
        except ValueError:
            return e.code, raw
    except urllib.error.URLError as e:
        return 0, str(e)


def _resources(adapter: str, token: str) -> list[dict]:
    code, body = _req("GET", f"{adapter}/api/admin/resources", token)
    if code != 200:
        raise SystemExit(f"list resources failed ({code}): {body}")
    return body.get("resources", body) if isinstance(body, dict) else body


def _find_resource(adapter: str, token: str, auth_server_id: str, audience: str,
                   agent_slug: str | None = None, connection_id: str | None = None) -> dict | None:
    """Match THIS agent's synced resource for the given auth server.

    Multiple agents can connect to the same auth server, so the adapter creates one resource per
    (agent, connection) — naming them after the AS id with a `-N` suffix on collision. Scope the
    match to this agent (agent_id / connection_id) first, then fall back to AS-id/audience matching.
    """
    asl = (auth_server_id or "").lower()
    candidates = []
    for r in _resources(adapter, token):
        cfg = r.get("config", {}) or {}
        meta = cfg.get("metadata", {}) or {}
        name_l = (r.get("name") or "").lower()
        as_match = (r.get("resource_id") == auth_server_id
                    or name_l == asl or name_l.startswith(asl + "-")
                    or (r.get("connection_resource_id") or "").lower() == asl
                    or cfg.get("resource_indicator") == audience
                    or meta.get("resource_indicator") == audience)
        if not as_match:
            continue
        if connection_id and r.get("connection_id") == connection_id:
            return r
        if agent_slug and r.get("agent_id") == agent_slug:
            return r
        candidates.append(r)
    # no agent-scoped hit; return a single AS match only if unambiguous
    if not agent_slug and not connection_id and len(candidates) == 1:
        return candidates[0]
    return None


def _agent_slug(adapter: str, token: str, okta_agent_id: str) -> str | None:
    code, body = _req("GET", f"{adapter}/api/admin/agents", token)
    if code != 200:
        return None
    agents = body if isinstance(body, list) else body.get("agents", body.get("data", []))
    for a in agents or []:
        if a.get("okta_ai_agent_id") == okta_agent_id or a.get("principal_id") == okta_agent_id:
            return a.get("agent_id")
    return None


def _okta_req(method: str, url: str, token: str, scheme: str, body: dict | None = None) -> tuple[int, object]:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"{scheme} {token}")
    req.add_header("Accept", "application/json")
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode()
            return resp.status, (json.loads(raw) if raw.strip() else {})
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            return e.code, json.loads(raw)
        except ValueError:
            return e.code, raw
    except urllib.error.URLError as e:
        return 0, str(e)


def ensure_managed_connection(okta_domain: str, token: str, scheme: str, okta_agent_id: str,
                              auth_server_id: str, audience: str, scopes: list[str]) -> None:
    """Idempotently create the agent's INCLUDE_ONLY managed connection in Okta.

    This is the Okta half of pre-wiring the CRM example: the adapter resource (below) can only
    carry granular scopes if the underlying managed connection is INCLUDE_ONLY with those scopes.
    """
    base = f"https://{okta_domain.replace('https://', '').rstrip('/')}"
    conns_url = f"{base}/workload-principals/api/v1/ai-agents/{okta_agent_id}/connections"
    code, body = _okta_req("GET", conns_url, token, scheme)
    if code != 200:
        raise SystemExit(f"list Okta connections failed ({code}): {body}")
    for c in (body.get("data") or []):
        if c.get("resourceIndicator") == audience:
            print(f"      Okta managed connection for {audience} already exists ({c.get('id')})")
            return
    # Need the org id for the authorization-server ORN.
    code, org = _okta_req("GET", f"{base}/api/v1/org", token, scheme)
    if code != 200 or not isinstance(org, dict) or not org.get("id"):
        raise SystemExit(f"could not read org id for ORN ({code}): {org}")
    orn = f"orn:okta:idp:{org['id']}:authorization_servers:{auth_server_id}"
    code, created = _okta_req("POST", conns_url, token, scheme, {
        "connectionType": "IDENTITY_ASSERTION_CUSTOM_AS",
        "authorizationServer": {"orn": orn},
        "resourceIndicator": audience,
        "scopeCondition": "INCLUDE_ONLY",
        "scopes": scopes,
    })
    if code not in (200, 201) or not isinstance(created, dict) or not created.get("id"):
        raise SystemExit(f"create Okta managed connection failed ({code}): {created}")
    print(f"      created Okta managed connection {created['id']} "
          f"(INCLUDE_ONLY, {len(scopes)} scopes)")


def wire(adapter: str, token: str, okta_agent_id: str, auth_server_id: str,
         resource_name: str, audience: str, mcp_url: str, org_domain: str,
         scopes: list[str], okta_token: str | None = None, okta_scheme: str = "SSWS") -> int:
    adapter = adapter.rstrip("/")

    # 0. (Optional) Ensure the Okta managed connection exists, so CRM is end-to-end pre-wired.
    if okta_token:
        if not org_domain:
            raise SystemExit("--okta-token needs --org-domain (the attendee's Okta org)")
        print(f"[0] ensuring Okta managed connection for {audience} …")
        ensure_managed_connection(org_domain, okta_token, okta_scheme, okta_agent_id,
                                  auth_server_id, audience, scopes)

    # 1. Import the agent (idempotent — import is a no-op/refresh if already present).
    print(f"[1/5] importing agent {okta_agent_id} …")
    code, body = _req("POST", f"{adapter}/api/admin/okta/agents/{okta_agent_id}/import", token, {})
    if code not in (200, 400) or (isinstance(body, dict) and body.get("error") == "insufficient_scopes"):
        print(f"      import response ({code}): {body}")
        if isinstance(body, dict) and body.get("error") == "insufficient_scopes":
            raise SystemExit("admin token lacks Okta AI-Agent scopes/role — see runbook 'Admin API access'")
    slug = _agent_slug(adapter, token, okta_agent_id)
    if not slug:
        raise SystemExit("agent not found in adapter after import — check the okta-agent-id")
    print(f"      adapter agent id = {slug}")

    # 2. DCR-selectable.
    print("[2/5] marking agent DCR-selectable …")
    code, body = _req("PUT", f"{adapter}/api/admin/agents/{slug}/dcr-selectable", token,
                      {"dcr_selectable": True})
    if code not in (200, 204):
        print(f"      WARN dcr-selectable ({code}): {body}")

    # 3. Sync managed connections (materialize/refresh resources from Okta).
    print("[3/5] syncing managed connections …")
    _req("POST", f"{adapter}/api/admin/okta/agents/{okta_agent_id}/sync", token, {})
    _req("POST", f"{adapter}/api/admin/connections/sync", token, {})

    # 4. Ensure the resource exists, points at the path-scoped MCP URL, and is enabled.
    print(f"[4/5] ensuring resource '{resource_name}' → {mcp_url} …")
    existing = _find_resource(adapter, token, auth_server_id, audience, agent_slug=slug)
    issuer = f"https://{org_domain}/oauth2/{auth_server_id}" if org_domain else None
    orn_metadata = {
        "resource_indicator": audience,
        "authorization_server_orn": f"authorization_servers:{auth_server_id}",
    }
    if issuer:
        orn_metadata["issuer_url"] = issuer
    if existing is None:
        # Newer adapter auto-materializes the resource on sync; give it a moment + re-sync,
        # then look again. Only fall back to POST-create on older adapters that need it.
        print("      resource not found yet — re-syncing for auto-materialize")
        _req("POST", f"{adapter}/api/admin/connections/sync", token, {})
        time.sleep(2)
        existing = _find_resource(adapter, token, auth_server_id, audience, agent_slug=slug)
    if existing is None:
        print("      still none — POST-creating (older adapter path)")
        code, body = _req("POST", f"{adapter}/api/admin/resources", token, {
            "name": resource_name, "resource_id": auth_server_id, "url": mcp_url, "mcp_url": mcp_url,
            "protocol": "mcp", "auth_method": "okta-cross-app", "enabled": True,
            "config": {"metadata": orn_metadata, "resource_indicator": audience},
        })
        if code not in (200, 201):
            raise SystemExit(f"create resource failed ({code}): {body}")
        name = body.get("name", resource_name)
    else:
        name = existing.get("name", resource_name)
        cur_url = existing.get("url") or existing.get("mcp_url")
        if cur_url != mcp_url or not existing.get("enabled", False):
            print(f"      updating existing resource '{name}' (url/enabled)")
            # send both field names so it works across adapter versions
            code, body = _req("PUT", f"{adapter}/api/admin/resources/{name}", token,
                              {"url": mcp_url, "mcp_url": mcp_url, "enabled": True})
            if code not in (200, 204):
                raise SystemExit(f"update resource failed ({code}): {body}")
        else:
            print(f"      resource '{name}' already correct")

    # 5. Verify: enabled, right URL, INCLUDE_ONLY granular scopes (not the mcp:read fallback).
    print("[5/5] verifying …")
    code, r = _req("GET", f"{adapter}/api/admin/resources/{name}", token)
    if code != 200:
        raise SystemExit(f"verify GET failed ({code}): {r}")
    got_url = r.get("url") or r.get("mcp_url")
    ok = (r.get("enabled") and got_url == mcp_url
          and r.get("scope_condition") == "INCLUDE_ONLY" and r.get("scopes"))
    print(f"      enabled={r.get('enabled')} url={got_url} "
          f"scope_condition={r.get('scope_condition')} scopes={r.get('scopes')}")
    if not ok:
        print("ERROR: resource is not fully wired. If scope_condition is ALLOW_ALL / scopes are "
              "empty (→ adapter requests `mcp:read`), confirm the Okta managed connection is "
              "INCLUDE_ONLY with granular scopes, then re-run this script (it re-syncs).")
        return 1
    print(f"OK: '{name}' wired → {mcp_url} (audience {audience}, {len(r['scopes'])} scopes).")
    return 0


def _admin_token(args) -> str:
    if args.admin_token:
        return args.admin_token
    if os.environ.get("ADAPTER_ADMIN_TOKEN"):
        return os.environ["ADAPTER_ADMIN_TOKEN"]
    if args.from_secret:
        import subprocess
        out = subprocess.check_output(
            ["aws", "secretsmanager", "get-secret-value", "--secret-id", args.from_secret,
             "--region", args.region, "--query", "SecretString", "--output", "text"])
        return out.decode().strip()
    raise SystemExit("no admin token: pass --admin-token, set ADAPTER_ADMIN_TOKEN, or --from-secret")


def main() -> int:
    p = argparse.ArgumentParser(description="Wire a VantageCRM/Desk resource into the Okta MCP Adapter.")
    p.add_argument("--adapter", required=True, help="adapter base URL, e.g. https://adapter.example.io")
    p.add_argument("--okta-agent-id", required=True, help="the agent's Okta AI-Agent id (wlp…)")
    p.add_argument("--auth-server-id", required=True, help="the resource auth server id (aus…)")
    p.add_argument("--preset", choices=sorted(PRESETS), help="crm or desk (fills name/audience/path/scopes)")
    p.add_argument("--mcp-host", help="MCP server host (with --preset), e.g. mcp.taskvantage-demo.com")
    p.add_argument("--resource-name", help="adapter resource name (no preset)")
    p.add_argument("--audience", help="token audience, e.g. api://vantage-crm (no preset)")
    p.add_argument("--mcp-url", help="full path-scoped MCP URL (no preset)")
    p.add_argument("--org-domain", default="", help="Okta org domain for issuer metadata, e.g. attendee01.okta.com")
    p.add_argument("--admin-token", help="adapter admin bearer (or env ADAPTER_ADMIN_TOKEN / --from-secret)")
    p.add_argument("--from-secret", help="AWS Secrets Manager secret name holding the admin token")
    p.add_argument("--region", default="us-east-2")
    p.add_argument("--scopes", help="comma-separated granular scopes (no preset; needed for --okta-token)")
    p.add_argument("--okta-token", help="Okta org API token — when set, also creates the agent's "
                                        "INCLUDE_ONLY managed connection (env OKTA_API_TOKEN)")
    p.add_argument("--okta-auth", default="SSWS", choices=["SSWS", "Bearer"],
                   help="Okta token scheme (default SSWS)")
    args = p.parse_args()

    if args.preset:
        pr = PRESETS[args.preset]
        resource_name = args.resource_name or pr["resource_name"]
        audience = args.audience or pr["audience"]
        scopes = args.scopes.split(",") if args.scopes else pr["scopes"]
        if args.mcp_url:
            mcp_url = args.mcp_url
        elif args.mcp_host:
            mcp_url = f"https://{args.mcp_host.rstrip('/')}{pr['path']}"
        else:
            raise SystemExit("--preset needs --mcp-host (or pass --mcp-url)")
    else:
        if not (args.resource_name and args.audience and args.mcp_url):
            raise SystemExit("without --preset, pass --resource-name, --audience, and --mcp-url")
        resource_name, audience, mcp_url = args.resource_name, args.audience, args.mcp_url
        scopes = args.scopes.split(",") if args.scopes else []

    okta_token = args.okta_token or os.environ.get("OKTA_API_TOKEN")
    if okta_token and not scopes:
        raise SystemExit("--okta-token (managed-connection creation) requires --preset or --scopes")

    return wire(args.adapter, _admin_token(args), args.okta_agent_id, args.auth_server_id,
                resource_name, audience, mcp_url, args.org_domain, scopes,
                okta_token=okta_token, okta_scheme=args.okta_auth)


if __name__ == "__main__":
    sys.exit(main())
