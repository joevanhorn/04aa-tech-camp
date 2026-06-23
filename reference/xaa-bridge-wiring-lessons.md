# XAA Bridge Wiring — Lessons Learned

**What this is:** every place the full agent → adapter → XAA → MCP → app path broke while we wired
it end-to-end against the live environment (2026-06-22), with the known-good fix for each. It exists
so the lab modules and per-attendee setup don't have to rediscover these. Several of these are
**required lab configuration that the modules currently get wrong or omit** — flagged inline.

We proved it by calling `itsm.lookup_ticket TKT-1734` through the bridge as a registered AI agent
(`TechCamp-Opencode`) and getting the real VantageDesk record back. Related: `okta-xaa-id-jag-analysis.md`.

## The chain (one line per hop)

1. **Agent → adapter `/oauth/authorize`** — brokered OAuth (Dynamic Client Registration on a loopback
   redirect + PKCE); the user signs into Okta and the adapter gets the user's tokens.
2. **Adapter resolves the agent** (DCR-linked / `X-MCP-Agent`) and the user.
3. **Per tool call — XAA / Cross-App Access (two exchanges):**
   a. **ID-JAG** minted at the **org** authorization server — the adapter signs a JWT bearer with the
      **agent's** key (`principal_id` as `iss`/`sub`), carrying the user's identity + requested scopes.
   b. The ID-JAG is exchanged at the **resource** AS (`vantage-desk-as`) for an `api://vantage-desk`
      access token carrying the user's **granted** scopes.
4. **Adapter → MCP server** — forwards that token (`bearer-passthrough` resource) to the MCP server.
5. **MCP server → VantageDesk** — forwards the token; the app validates `aud=api://vantage-desk`, the
   **granular scope** (`itsm.tickets.read`), and resolves the tenant by issuer → returns data.

## What broke, in order

Each item: **symptom → root cause → fix → lab impact**. The "evidence" is where to look if it
recurs.

### 1. MCP server returns `421 Invalid Host header`
- **Symptom:** `POST /mcp` → 421 behind the ALB; `GET /health` works.
- **Cause:** the MCP SDK's streamable-HTTP transport enforces **DNS-rebinding protection**, which
  allow-lists the `Host` header (loopback by default) and rejects the public host.
- **Fix:** `FastMCP(..., transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False))`.
- **Lab impact:** **infra** (the MCP server image). Done in `taskvantage-apps/mcp-server`. Any MCP
  server fronted by a proxy/ALB needs this.

### 2. Intermittent 401 / "issuer not from an enrolled org"
- **Symptom:** the same token is accepted on some requests and 401s on others.
- **Cause:** the apps' tenant registry was an **in-memory dict per replica**, so a runtime
  enrollment only reached one task behind the load balancer.
- **Fix:** Redis-back the registry (shared across replicas). Done in `taskvantage-apps/common/tenants.py`.
- **Lab impact:** **infra/apps**. Also: the attendee org must be **enrolled** in the apps — see
  `taskvantage-apps/docs/TENANT-ENROLLMENT.md`.

### 3. `client_assertion_invalid_kid` at the token grant
- **Symptom:** XAA fails; Okta System Log shows `app.oauth2.token.grant FAILURE client_assertion_invalid_kid`.
- **Cause:** the private key the adapter signs the agent assertion with does **not** match the
  agent's **active credential** registered in Okta (a stale/old key was synced to the adapter).
- **Fix:** make the adapter hold the private key whose `kid` matches Okta's **active** agent
  credential — generate the credential in the AI Agents registry, then sync **that exact key** to the
  adapter. Verify by comparing the adapter's signing kid to the app's registered JWKS kid.
- **Lab impact:** **Module 2.5** (agent credential). The key you generate **and activate** in Okta
  must be the one the agent runtime/adapter uses. Regenerating the credential without re-syncing
  breaks XAA.

### 4. `temporarily_unavailable` — "No agents available for linking" at `/oauth/authorize`
- **Symptom:** adapter `/oauth/authorize` returns 503 with that message.
- **Cause:** the DCR flow links the dynamically-registered client to an agent flagged
  **DCR-selectable**; no agent was marked selectable.
- **Fix:** mark the agent **DCR-selectable** in the adapter Admin UI.
- **Lab impact:** **adapter setup** (per-attendee infra). Belongs in the platform-team provisioning,
  not an attendee module.

### 5. `no_matching_scope` at the resource AS  ← **required module change**
- **Symptom:** the ID-JAG mints fine, but the exchange at `vantage-desk-as` fails `no_matching_scope`;
  the System Log shows `requestedScopes: mcp:read`.
- **Cause:** the agent's **managed connection** was set to **"Allow all" (`ALL_SCOPES`)**. With that,
  the adapter's `apply_scope_condition` (`auth/cross_app_access.py`) **defaults to `["mcp:read"]`** —
  a scope the lab's custom AS doesn't define. (And even if it did, a `mcp:read` token wouldn't satisfy
  VantageDesk, which requires `itsm.*`.)
- **Fix:** set the managed connection to **"Only allow" (`INCLUDE_ONLY`)** the **granular** scopes
  (`itsm.tickets.read`, `itsm.tickets.write`, `itsm.incidents.read`, `itsm.incidents.write`,
  `itsm.kb.read`). Then the adapter requests exactly those, the AS grants them, and VantageDesk
  accepts the token.
- **Lab impact:** **Module 2.9 must change.** It currently says select **"Allow all"** (with a *NOTE*
  that "Only allow" is a production nicety). That is backwards for this adapter: **"Allow all" breaks
  the bridge** (defaults to `mcp:read`). "Only allow" the granular scopes is **required**, and it's
  also what makes Module 3's per-tool scope-gating story actually work.

### 6. `no_matching_policy` at the resource AS  ← **required module change**
- **Symptom:** exchange at `vantage-desk-as` fails `no_matching_policy`; the System Log shows the
  client is the **agent** (`wlp…`, `clientAuthType: private_key_jwt`).
- **Cause:** the AS access-policy `client_whitelist` contained only the agent's **OIDC app** (`0oa…`),
  but the XAA exchange authenticates as the **agent principal** (`wlp…`).
- **Fix:** assign the access policy to the **agent** (include the `wlp…` principal). Keeping the app
  id too is harmless.
- **Lab impact:** **Module 4.5** (build `vantage-desk-as`'s access policy). The "Assign to clients"
  step must select the **agent** (it appears as an assignable client), not just the sign-on app.
  Confirm the UI wording matches.

### 7. App sign-on enforces Okta Verify MFA
- **Symptom:** the brokered login presents Okta Verify ("Enter a code").
- **Cause:** the agent's linked sign-on app auth policy requires MFA.
- **Lab impact:** **expected** — attendees do a real MFA login. Only relevant if you automate the
  login (supply a TOTP factor).

### Bonus (test-harness note, not lab content)
The adapter's **unified** endpoint returns **plain JSON-RPC**, not SSE; the backend MCP server
(FastMCP) returns **SSE**. A client must handle both, or it will silently see zero tools.

## Known-good configuration (the recipe, in order)

Per attendee org, to bring a registered agent fully through the bridge to VantageDesk:

1. **Custom AS** `vantage-desk-as`, audience `api://vantage-desk`, with the 5 `itsm.*` scopes.
2. **Access policy** on `vantage-desk-as` **assigned to the agent principal**, with a rule allowing
   grant types `token-exchange` + `jwt-bearer`, the `itsm.*` scopes, group `EVERYONE` (or the lab's
   target group).
3. **AI Agent** registered + active; **credential generated**, and the **same private key synced to
   the adapter** (kids must match); agent marked **DCR-selectable** in the adapter.
4. **Managed connection** agent → `vantage-desk-as`, set to **"Only allow" the `itsm.*` scopes**
   (`INCLUDE_ONLY`) — not "Allow all".
5. **Adapter resource** (one per backend AS — sync materializes it from the managed connection):
   `auth_method = okta-cross-app`, URL = the **path-scoped** MCP mount for that audience
   (`…/desk/mcp` for the desk connection, `…/crm/mcp` for the crm connection).
6. **MCP server** = central, shared, with DNS-rebinding protection disabled (infra).
7. **Org enrolled** in the apps (Redis-backed registry).

## The participant configures their own adapter

The Okta MCP Adapter is **provisioned per attendee but starts empty** — the participant wires it as
part of the lab. So the adapter-side steps are **attendee module content**, not just platform-team
infra. A new **Module 2 "Wire your agent into the MCP Adapter"** section is needed (before Module 3's
filtering demo), covering, in the adapter Admin UI:

1. **Import the agent** (Agents → *Okta Import* → the registered agent) — or confirm it auto-imported
   if the lab provisions the Okta event hook for sync.
2. **Mark the agent DCR-selectable** (gotcha 4) — required for the brokered OAuth to link.
3. **Confirm the agent's signing credential** matches Okta's active key (gotcha 3).
4. **Sync managed connections** — each Okta managed connection materializes as one adapter resource
   (resource = one `(agent, connection)` pair). After Lab 2 this surfaces the `vantage-crm-as`
   connection; **re-sync after Lab 4** to surface `vantage-desk-as`.
5. **Set each resource's URL to its path-scoped MCP mount** (sync owns the connection/scopes; the admin
   owns routing): the CRM resource → `https://{{mcp_host}}/crm/mcp`, the Desk resource →
   `https://{{mcp_host}}/desk/mcp`. (`auth_method` is auto-derived as `okta-cross-app` from the
   connection type.) Each resource then mints its own audience token for its 6 tools.
6. The agent's access to each resource is **implicit** (the resource *is* the agent's connection); no
   separate grant/link step.

### Design (resolved): two adapter resources, one per backend AS, on path-scoped MCP mounts

Two apps (`api://vantage-crm`, `api://vantage-desk`) sit behind **one** central MCP server, and a token
minted for one audience is rejected by the other app. The constraint that drives the design: in the
adapter, **a "resource" is exactly one `(agent, managed-connection)` pair → one audience**, and
`tools/list` namespaces every tool by its resource (`{resource}__{tool}`). The syncer materializes one
resource row per connection (`resources/syncer.py`); there is **no way to bind two connections to one
resource**. So a single `vantage-tools` resource (bound to the desk connection) can only ever mint
`api://vantage-desk` tokens — and a `crm.*` call through it gets a desk-audience token, which VantageCRM
rejects with `401 "Audience doesn't match"` (observed 2026-06-22).

This is also how the working **`claude-code`** agent is wired — **two** resources, one per backend AS,
each `INCLUDE_ONLY` its granular scopes — it just looks seamless there because Salesforce and ServiceNow
are **different MCP server URLs**:

```
XAA - Salesforce  → audience https://…salesforce.com   INCLUDE_ONLY [accounts.read, contacts.read]
XAA - ServiceNow  → audience https://…service-now.com  INCLUDE_ONLY [incidents.read, enhancements.read]
```

The vantage twist is that **both apps share one MCP server**. To keep tool catalogs clean (no duplicate,
half-erroring tools), the MCP server exposes **path-scoped tool subsets** and each adapter resource points
at its own path:

```
MCP server (one ECS service, mcp.taskvantage-demo.com)
  /crm/mcp   → 6 crm.*  tools        adapter resource "vantage-crm"  (conn vantage-crm-as,  api://vantage-crm)
  /desk/mcp  → 6 itsm.* tools        adapter resource "vantage-desk" (conn vantage-desk-as, api://vantage-desk)
  /mcp       → all 12 (back-compat)
```

Each resource mints the right-audience token for its 6 tools and forwards to the matching app. Both
managed connections are `INCLUDE_ONLY` the backend's granular scopes (confirming gotcha 5 again —
`claude-code` never uses "Allow all"). This matches the modules' two-AS structure (`vantage-crm-as`
in Lab 2, `vantage-desk-as` in Lab 4); the adapter-side addition is registering **two** resources, each
pointing at its `/crm/mcp` or `/desk/mcp` path.

**Status:** ✅ **both audiences validated end-to-end in one run (2026-06-23)** — `itsm.lookup_ticket
TKT-1734` (`api://vantage-desk`) **and** `crm.lookup_account ACC-1001` → "Northwind Trading Co."
(`api://vantage-crm`), same agent, one adapter, two path-scoped resources (`vantage-tools`→`/desk/mcp`,
`vantage-crm`→`/crm/mcp`). Full play-by-play + IDs in `crm-path-validation-runbook.md`. Two lab gaps
surfaced and fixed: (1) **groups claim** missing on both vantage AS — the apps read `token["groups"]`
for row-level visibility (Module 3); added to both. (2) the **"Sales Management" group** referenced by
the app code didn't exist; created it. Durability note: on the older deployed adapter, re-run sync after
any restart (see runbook).

## Module impact summary (drives the doc/module update pass)

| Lesson | Module / artifact | Change | Status |
| --- | --- | --- | --- |
| 5 — managed connection scope | **Module 2.9 / 4.6** | "Allow all" → **"Only allow" the granular scopes** | ✅ applied |
| 6 — policy client = agent | **Module 4.5** | Assign the AS policy to the **agent principal** | ✅ applied (NOTE) |
| 3 — credential key match | **Module 2.5** | Key generated+activated must be the one the runtime/adapter uses | ✅ applied (NOTE) |
| 4 + resource registration | **NEW Module 2 adapter-config section** | Import agent, DCR-selectable, register the per-AS resource (okta-cross-app) at its `/crm/mcp`/`/desk/mcp` path, sync | ⏳ pending |
| 1, 2 — infra | platform-team / apps | MCP server transport-security; Redis registry | ✅ done in taskvantage-apps |
| dual-audience routing | architecture / Module 2+4 | **two** adapter resources (one per AS), MCP server path-scoped (`/crm/mcp`, `/desk/mcp`) | ✅ validated E2E (both audiences, one run) |
| groups claim for visibility | **Module 1 (AS build) / 2.x** | add a `groups` claim to each vantage AS; create the **Sales Management** group | ✅ added to both AS + group created |
