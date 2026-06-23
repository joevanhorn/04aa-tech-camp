#!/usr/bin/env bash
#
# setup-crm-resource.sh — O4AA Lab Module 2 helper (runs on the attendee Virtual Desktop).
#
# Pre-wires the participant's VantageCRM access END-TO-END after they register their agent in
# Module 2.3-2.7: it resolves their agent + the vantage-crm-as authorization server by name, then
# calls wire_adapter_resource.py to create the INCLUDE_ONLY managed connection in Okta and the
# CRM resource (`/crm/mcp`) in their MCP Adapter. The attendee then reviews the result (Module
# 2.9-2.10); they build the VantageDesk equivalent by hand in Module 4.
#
# Turnkey per attendee: it discovers the agent id (by name) and the auth-server id (by audience)
# at runtime, so nothing per-attendee is hard-coded except the org/adapter hosts and the tokens.
#
# Idempotent — safe to re-run (also the fix if the adapter is restarted; it re-syncs every run).

set -euo pipefail

# ──────────────────────────────────────────────────────────────────────────────
# Per-environment configuration (the lab provisions these per attendee org).
# ──────────────────────────────────────────────────────────────────────────────
AGENT_NAME="${AGENT_NAME:-TaskVantage Sales Agent}"   # must match the name used in Module 2.3
CRM_AUDIENCE="${CRM_AUDIENCE:-api://vantage-crm}"      # the vantage-crm-as audience (lab constant)
MCP_HOST="${MCP_HOST:-mcp.taskvantage-demo.com}"       # central shared MCP server (lab constant)

# Attendee-specific hosts. CALLOUT: provisioning should set these per environment.
ORG_DOMAIN="${ORG_DOMAIN:-}"        # e.g. attendee01.okta.com   (the attendee's Okta org)
ADAPTER_HOST="${ADAPTER_HOST:-}"    # e.g. https://adapter-attendee01.example.io  (their MCP Adapter)

# Where wire_adapter_resource.py lives on the VDI (shipped alongside this script).
WIRE="${WIRE:-$(dirname "$0")/wire_adapter_resource.py}"

# ┌─ LAB ENGINEERING CALLOUT: token delivery (NOT YET DECIDED) ──────────────────
# │ This helper needs TWO short-lived, admin-scoped tokens. How the VDI obtains
# │ them is a provisioning decision that is still open — pick one and wire it in
# │ where the two `: "${VAR:?...}"` guards are below:
# │
# │   OKTA_API_TOKEN       — Okta org API token (default scheme SSWS). Used to
# │                          resolve the agent/auth-server ids and to create the
# │                          agent's managed connection. Needs rights to read AI
# │                          agents + auth servers and manage agent connections.
# │
# │   ADAPTER_ADMIN_TOKEN  — bearer for the attendee's MCP Adapter admin API
# │                          (the same Okta login the adapter Admin UI uses).
# │                          Its principal needs Okta AI-Agent admin rights — the
# │                          adapter probes the AI Agents API on import/sync.
# │                          wire_adapter_resource.py also accepts --from-secret
# │                          <aws-secret-name> if you store it in Secrets Manager.
# │
# │ Options to consider: (a) pre-set as env vars in the VDI image/user profile,
# │ (b) pull from a secret store at run time, (c) inject from the provisioning
# │ component when the environment is spun up. Do NOT bake long-lived secrets
# │ into the VDI image. See deploy/README.md and
# │ 04aa-tech-camp/reference/crm-path-validation-runbook.md ("Admin API access").
# └──────────────────────────────────────────────────────────────────────────────
: "${OKTA_API_TOKEN:?set OKTA_API_TOKEN — see the lab-engineering callout above}"
: "${ADAPTER_ADMIN_TOKEN:?set ADAPTER_ADMIN_TOKEN — see the lab-engineering callout above}"
: "${ORG_DOMAIN:?set ORG_DOMAIN to the attendee Okta org, e.g. attendee01.okta.com}"
: "${ADAPTER_HOST:?set ADAPTER_HOST to the attendee MCP Adapter base URL}"

OKTA_BASE="https://${ORG_DOMAIN#https://}"

# ──────────────────────────────────────────────────────────────────────────────
# Resolve the agent id (by profile.name) and the auth-server id (by audience).
# Uses python3 (stdlib) so we don't depend on jq being on the VDI.
# ──────────────────────────────────────────────────────────────────────────────
echo "Resolving '${AGENT_NAME}' and ${CRM_AUDIENCE} in ${OKTA_BASE} …"

AGENT_ID="$(
  curl -fsS -H "Authorization: SSWS ${OKTA_API_TOKEN}" -H "Accept: application/json" \
    "${OKTA_BASE}/workload-principals/api/v1/ai-agents?limit=200" \
  | AGENT_NAME="${AGENT_NAME}" python3 -c '
import json, os, sys
want = os.environ["AGENT_NAME"]
data = json.load(sys.stdin)
agents = data.get("data", data) if isinstance(data, dict) else data
for a in agents or []:
    if (a.get("profile") or {}).get("name") == want or a.get("name") == want:
        print(a["id"]); break
'
)"
[ -n "${AGENT_ID}" ] || { echo "ERROR: no AI agent named '${AGENT_NAME}' in ${OKTA_BASE} — register it first (Module 2.3)."; exit 1; }

AS_ID="$(
  curl -fsS -H "Authorization: SSWS ${OKTA_API_TOKEN}" -H "Accept: application/json" \
    "${OKTA_BASE}/api/v1/authorizationServers?limit=200" \
  | CRM_AUDIENCE="${CRM_AUDIENCE}" python3 -c '
import json, os, sys
want = os.environ["CRM_AUDIENCE"]
for s in json.load(sys.stdin):
    if want in (s.get("audiences") or []):
        print(s["id"]); break
'
)"
[ -n "${AS_ID}" ] || { echo "ERROR: no authorization server with audience ${CRM_AUDIENCE} in ${OKTA_BASE}."; exit 1; }

echo "  agent id       = ${AGENT_ID}"
echo "  vantage-crm-as = ${AS_ID}"

# ──────────────────────────────────────────────────────────────────────────────
# Wire CRM end-to-end (managed connection in Okta + resource in the adapter).
# ──────────────────────────────────────────────────────────────────────────────
exec python3 "${WIRE}" \
  --preset crm \
  --adapter "${ADAPTER_HOST}" \
  --okta-agent-id "${AGENT_ID}" \
  --auth-server-id "${AS_ID}" \
  --mcp-host "${MCP_HOST}" \
  --org-domain "${ORG_DOMAIN#https://}" \
  --okta-token "${OKTA_API_TOKEN}" --okta-auth SSWS \
  --admin-token "${ADAPTER_ADMIN_TOKEN}"
