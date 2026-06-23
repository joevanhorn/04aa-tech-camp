# CRM Bridge Path — Validation Runbook & Session Log (2026-06-22/23)

Live record of wiring + validating the **VantageCRM** audience end-to-end through the bridge
(agent → adapter → XAA → MCP server → app), as the second audience alongside the already-validated
Desk path. Written so the work survives context loss. Companion to `xaa-bridge-wiring-lessons.md`
(the durable lessons) — this file is the blow-by-blow with concrete IDs.

## Goal

Both VantageCRM (`api://vantage-crm`) and VantageDesk (`api://vantage-desk`) reachable by the same
registered agent (`TechCamp-Opencode`) through **one** central MCP server, each tool minting its own
correct-audience XAA token. Robust + supportable for a live ~100-attendee lab.

> **Now codified.** The full validated sequence below is implemented as
> `taskvantage-apps/deploy/wire_adapter_resource.py` (idempotent, stdlib-only). With `--okta-token` it
> wires a resource **end-to-end** — creates the agent's INCLUDE_ONLY managed connection in Okta, then
> import → DCR-selectable → sync → resource at the path-scoped MCP URL. The lab uses `--preset crm` to
> **pre-wire CRM as the worked example** (Module 2); attendees hand-build the Desk path (Module 4). It's
> also the one-command fix for the post-restart `mcp:read` regression (it re-syncs every run).

## Design (confirmed by code, not guesswork)

The adapter binds **one resource = one managed connection = one audience**, and namespaces tools per
resource (`{resource}__{tool}`). There is **no two-connections-per-resource**. So two audiences ⇒
**two adapter resources**. Both apps share one MCP server, so the server exposes **path-scoped tool
subsets** and each resource points at its own path:

```
MCP server  mcp.taskvantage-demo.com
  /crm/mcp   → 6 crm.*  tools   ← adapter resource "vantage-crm"  (conn vantage-crm-as,  api://vantage-crm)
  /desk/mcp  → 6 itsm.* tools   ← adapter resource "vantage-tools"(conn vantage-desk-as, api://vantage-desk)
  /mcp       → all 12 (back-compat)
```

## Concrete IDs (taskvantage.okta.com)

| Thing | ID |
| --- | --- |
| Agent (principal / okta_ai_agent_id) | `wlp24fnititUIJG4o1d8` |
| Agent OIDC app (sign-on) | `0oa24foc90nytseaf1d8` |
| vantage-crm-as (AS) | `aus24g60q8aVYfJJp1d8` · audience `api://vantage-crm` |
| crm scopes | `crm.accounts.read/write`, `crm.contacts.read`, `crm.opportunities.read/write` (+`interclient_access`) |
| crm access policy / rule | `00p24g5zg3aeb9Zj41d8` / `0pr24g5xpxgs1nhRa1d8` (clients: agent wlp… + app 0oa…; grants token-exchange+jwt-bearer) |
| crm groups claim | `ocl24g7av88f0wBvh1d8` (RESOURCE, GROUPS, value `.*`, alwaysInclude) |
| crm managed connection (on agent) | `mcn24g62fj5feQhBf1d8` · INCLUDE_ONLY the 5 crm scopes |
| vantage-desk-as (AS) | `aus24fyc55jzybCmT1d8` · `api://vantage-desk` |
| desk managed connection | `mcn24g4rzm5TeqQGU1d8` · INCLUDE_ONLY 5 itsm scopes |
| adapter resource: vantage-crm | mcp_url `…/crm/mcp`, conn `mcn24g62…`, enabled |
| adapter resource: vantage-tools | mcp_url `…/desk/mcp`, conn `mcn24g4r…`, enabled |
| Sales Management group (created) | `00g24g7bngoKKkNaI1d8` |
| Bot user (Playwright login) | mcp-testbot@atko.email = `00u22znaqasB0kke81d8` |

## Steps performed (in order)

1. **MCP server path-split** — `taskvantage-apps` branch `feat/mcp-path-split`: three FastMCP mounts
   (`/crm/mcp`, `/desk/mcp`, `/mcp`) over the same tool fns. Deployed via
   `gh workflow run deploy.yml -f action=deploy-mcp --ref feat/mcp-path-split` (this action **builds
   from the checked-out ref**, so deploy from the branch, not main). Verified all three paths live.
2. **Okta CRM config** (all via SSWS API, `~/Taskvantage-prod-apiKey`): created `vantage-crm-as` +
   scopes + access policy/rule + managed connection (mirrors desk exactly). Managed-connection POST
   body uses `authorizationServer.orn` (NOT `issuerUrl`) at
   `/workload-principals/api/v1/ai-agents/{agent}/connections`.
3. **Adapter admin API** — see "Admin API access" below. The **deployed adapter is an older build**:
   new managed connections do **not** auto-materialize as resources (newer 0.15.x does). Instead a
   connection resolves to a `resource_id` (= the AS id) and is "unresolved" until a Resource with that
   id exists. So: `POST /api/admin/resources` to **create** `vantage-crm` with
   `resource_id = aus24g60q8aVYfJJp1d8`, `mcp_url = …/crm/mcp`, `auth_method = okta-cross-app`; then
   `POST /api/admin/connections/sync` links the connection (fills scopes/conn_id). Also
   `PUT /api/admin/resources/vantage-tools` to repoint desk → `…/desk/mcp`.
4. **groups claim gap** — `ctx.groups = token["groups"]` in the apps, but neither vantage AS emitted a
   `groups` claim. Desk hid this (tickets aren't group-gated); CRM exposed it (accounts are
   owner/Sales-Management gated). Added the groups claim to `vantage-crm-as`. **TODO: add the same to
   `vantage-desk-as` for lab parity** (Module 3/4/5 visibility).
5. **Sales Management group** — referenced by the app (`filters.SALES_MANAGEMENT = "Sales Management"`)
   but didn't exist. Created it + added the bot so the bot sees all CRM accounts for the proof.

## Admin API access (how I drove the adapter without the UI)

The adapter admin API accepts an **Okta org-AS service-app token** (private_key_jwt client_credentials;
audience not pinned). Steps:
- Temp API Services app (private_key_jwt, JWKS = a generated RSA key, kid `techcamp-admin-1`).
- Granted scopes `okta.users.read`, `okta.aiAgents.read`, `okta.aiAgents.manage`, `okta.apps.read`.
- **Scope is necessary but not sufficient**: the AI Agents API (`/workload-principals/api/v1/ai-agents`)
  returned 403 until the app was also given an **admin role** — assigned via
  `POST /oauth2/v1/clients/{cid}/roles {"type":"SUPER_ADMIN"}`. Re-mint after assigning (role applies
  to new tokens). Token at `/tmp/orgtoken.txt`, app id at `/tmp/adminapp.txt`, key at `/tmp/adminkey.pem`.
- **CLEANUP TODO:** delete the temp app (`/oauth2/v1/clients/{cid}/roles/{rid}` then deactivate+delete
  the app) once validation is locked; the SUPER_ADMIN service app must not linger.

## Adapter token cache gotcha

`CACHE_PROVIDER=memory`, resource-token cache TTL 1h, key `{user_id}:{resource}`. A groups-empty CRM
token gets cached on first call; the older build has **no** force-logout route to evict it. To pick up
new groups/scopes during testing: `aws ecs update-service --cluster supersafe-ai --service mcp-adapter
--force-new-deployment` (memory cache ⇒ restart clears it). For the live lab this is a non-issue
(attendees mint fresh, and config is set before first call).

## Validation status — ✅ BOTH AUDIENCES PROVEN END-TO-END

Single `bridge_login.py` run, one agent, one adapter, two path-scoped resources:
- `vantage-tools__itsm.lookup_ticket TKT-1734` → real VantageDesk ticket (`api://vantage-desk`).
- `vantage-crm__crm.lookup_account ACC-1001` → **"Northwind Trading Co."** (`api://vantage-crm`).

35 tools consolidated (12 vantage = 6 crm + 6 itsm, 14 SuperSafe, 9 governance), each minting its
own correct-audience XAA token. Groups claim + Sales-Management membership gave the caller CRM
visibility (Module 3's "Susan sees all accounts" mechanic).

### Durability finding (gotcha-5 redux — important for lab-day)

After an adapter **restart**, both vantage exchanges failed with
`[ID-JAG] STEP 1+2 FAILED: invalid_scope: scopes not allowed: [mcp:read]`. Cause: the DB-hydrated
resources came back with `scope_condition` defaulted to **ALLOW_ALL**, so the adapter requested its
fallback scope `mcp:read` — which the vantage AS doesn't define. (Same failure mode as gotcha 5; here
triggered by hydration, not config.) On this **older deployed adapter**, a resource created via the
manual `POST /api/admin/resources` workaround + sync persists the granular scopes to the in-memory
resolved set and the admin cache, but not durably to the DB `scope_condition` column — so a restart
loses them. **Fix: re-run sync after any adapter restart** (`POST /api/admin/okta/sync/all` then
`/api/admin/connections/sync`) to rebuild the in-memory resolved resources with `INCLUDE_ONLY` +
granular scopes. For a real lab on a **current adapter (0.15.x)**, resources auto-materialize from
connections on sync (no manual POST), where sync-owned scope fields persist — so this is largely an
artifact of the old-adapter workaround. Still: the modules' adapter-setup step should say *sync* (and
re-sync after Lab 4), and proctor notes should mention "re-sync if the adapter restarts."

## Test harness

`/tmp/bridge_login.py` — bot authn → DCR+PKCE → Playwright Okta login (TOTP via pyotp) → token →
MCP `initialize`/`tools/list`/`tools/call` against adapter root `/`. Calls both
`itsm.lookup_ticket TKT-1734` and `crm.lookup_account ACC-1001`. Env from
`/home/ubuntu/lab-screenshot/enablement-drift/.env`.
