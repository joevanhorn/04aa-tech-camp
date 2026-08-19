# XAA2 Lab Validation Findings (Heropa env, migrated org)

**Date:** 2026-08-19
**Environment:** Heropa pair: VDI 100.28.210.105 + bridge VM (10.0.0.5, bundle 0.16.2-xaa2.1 from adapter main + PR #4) + org `demo-o4aa-techcamp-xaa2` (migrated model). Baseline provisioned with `archive/provision_lab_org.py`; org enrolled in the central lab apps.
**Result:** Full lab chain validated green: Alex persona login through the relay (private_key_jwt), XAA to `vantage-crm-as`, six real CRM tools from the central VantageCRM backend, live data returned. Frank correctly denied at `tools/call` by the access policy.

Numbered findings below with the decision recorded for each.

## 1. Auto-created agent app has no user assignments (DECISION: manual lab step)

On a migrated org, registering an agent auto-creates its sign-on app with no assignments. Persona sign-in through the relay fails with `access_denied: User is not assigned to the client application` until a group is assigned. The old flow's "Allow everyone in your organization to access" checkbox existed only in the manual Create App Integration wizard, which is gone.

Decision (Joe, 2026-08-19): make this a **manual step** in the v2 module 03: after registering the agent, open its sign-on app and assign the Everyone group (exact UI wording to be captured during the module rewrite). Do not automate.

## 2. App edits rejected until the agent has a signing key (FLAGGED, fix TBD)

`PUT /api/v1/apps/{appId}` on a migrated agent's auto-created app fails with `Api validation failed: jwks` while the agent has zero registered signing keys. Once at least one key exists on the agent (for example, after the bridge's generate-keypair), the same PUT succeeds. Verified both directions on 2026-08-19: the same payload failed pre-key and succeeded post-key, and an idempotent PUT on an agent app that has keys succeeds.

Practical consequence: the redirect-URI step (adding `<GATEWAY_BASE_URL>/oauth/callback`) must be sequenced AFTER key registration. Current state: the validated working order is register agent, import into bridge + generate keypair, then edit the app's redirect URIs. Any doc or automation that edits the app first will hit the error. Root cause is Okta-side validation (a `private_key_jwt` client must have key material; agent-held keys satisfy it, but only once they exist). Candidate fixes to evaluate: (a) sequence the steps in docs/automation (zero-cost, works today); (b) have provisioning register a throwaway key first (ugly); (c) raise with the O4AA product team whether app edits should validate against the agent's key store presence at all.

## 3. `wire_adapter_resource.py` breaks on the 0.16 admin API (fix design)

Confirmed live: after a successful import/DCR-selectable/sync, the script's resource fallback `POST /api/admin/resources` includes `auth_method` and 0.16 rejects it: `'auth_method' is connection-level — set it via PUT /api/admin/agents/{id}/connections/{cid}/resource`. The script also masks auth failures (a 401 on import is reported as "agent not found in adapter after import").

The right fix, matching the 0.16 contract (validated by hand on 2026-08-19):
1. `POST /api/admin/resources` with `{name, url, description, enabled}` only. No `auth_method`, no `config.metadata` (connection metadata is sync-owned now).
2. Look up the agent's connection id (`GET /api/admin/agents/{slug}/connections`, match on `connection_resource_id` == auth server id or `resource_indicator`).
3. `PUT /api/admin/agents/{slug}/connections/{cid}/resource` with `{"resource_name": "<name>"}`. The response echoes the derived `auth_method` (`okta-cross-app`) and scopes; assert on those instead of writing them.
4. Error handling: raise on any non-2xx from import (print body); handle `selection_required: true` + `candidates` by failing with a clear message (or accepting a `--selected-delegation-app-id` flag).
5. Drop the `mcp_url`/`url` dual-write and the "older adapter path" fallback once the fleet is on 0.16.

## 4. Bootstrap wrote an unreachable opencode.json (root cause: image drift, not a prod bug)

On this env the CDN bootstrap wrote `url: https://adapter.taskvantage.lab:8000`, but the VDI's boot-time Discover-Bridge task pins the name `bridge.taskvantage.lab`, and the replaced bridge bundle served plain HTTP. Production ran fine last week because prod images are internally consistent: the prod bridge image serves HTTPS with the `adapter.taskvantage.lab` cert and the prod VDI pins that same name. This environment is an older/divergent image build (VDI pins `bridge.`, cert/bootstrap expect `adapter.`), and replacing the bridge bundle removed the old image's TLS front. Resolution on this env: TLS front restored with a cert covering BOTH names, both names pinned on the VDI, canonical name aligned to `adapter.taskvantage.lab` to match the CDN bootstrap.

## 5. Adapter requires https or loopback GATEWAY_BASE_URL (image responsibility)

The 0.16 adapter refuses to start with a non-loopback `http://` GATEWAY_BASE_URL. The bundle's standalone profile has no TLS termination, so the Heropa bridge image must provide the TLS front (this was true of the old image; it was lost when the bundle was swapped). On this env: host nginx terminates TLS on 443 and on `<private-ip>:8000` (so the CDN bootstrap's `:8000` URL works verbatim), proxying to the adapter on loopback. The image build should bake this in (or the bundle's `edge-proxy` profile should be evaluated as the supported path).

## 6. Kill switch (Module 5 / conclusion): works, with a cached-token nuance

Verified on the migrated model 2026-08-19. Deactivating the agent (Actions > Deactivate, or `POST .../ai-agents/{id}/lifecycle/deactivate`) flips the agent's auto-created sign-on app to INACTIVE. A **new** user sign-in through the agent is then blocked at Okta's `/authorize` (HTTP 400, app inactive) before any token is brokered — this is exactly the "no user can broker a token through it" claim, and it holds. Reactivating flips the app back to ACTIVE and a fresh sign-in fully recovers (after the bridge re-syncs the agent's enabled state).

Nuance worth a sentence in the module (do not over-claim "instantly, every call stops"): an **already-issued** resource token stays usable from the adapter's token cache until its TTL. In testing, replaying a gateway token minted just before deactivation still returned cached CRM data, because the resource token was already brokered and cached (default cache TTL 3600s). The kill switch stops *new* brokering immediately; in-flight cached tokens age out. For the lab this is fine (the demo deactivates, then starts a fresh session to show the block), but the text should say "no new token can be brokered" rather than implying instant revocation of live sessions. Bridge-side note: the bridge only learns of the deactivation on its next agent sync (the lab's Toolkit/last step triggers this; the periodic syncer also picks it up).

## Bundle/compose fixes already upstream

PR #4 on `joevanhorn/okta-agent-mcp-adapter` carries the DCR private_key_jwt gate fixes and the compose admin-env passthrough fix; both were required to bring this environment up.

## 7. Toolkit + OpenCode capstone (Modules 2/3/7) validated

**Toolkit DCR endpoint break (fixed).** The Lab Toolkit posted DCR to the pre-0.16 path `/.well-known/oauth/registration`, which on 0.16 falls through to the MCP proxy and 401s ("Authorization header required"). Every Toolkit action that brokers a persona token (list-tools, invoke, side-by-side) failed. Fix: read `registration_endpoint` from `/.well-known/oauth-authorization-server` (falls back to `/oauth/register`). Landed in three places, all on XAA2-Updates branches: `o4aa-lab-toolkit` backend/app/auth.py; `techcamp-o4aa-v2` PS `Lab-Toolkit.ps1` + `invoke-agent-write.ps1` (and the embedded copy in bootstrap.ps1).

**Toolkit end-to-end (validated live on migrated xaa2, patched backend from source).** check-env green (CRM, Desk, Bridge all HTTP 200). Persona matrix is exactly the lab's teaching point:
- alex / susan / kim: catalog 6, authorized 6, denied 0, flow agent>adapter>xaa>app all ok
- frank: catalog 6, authorized 0, denied 6, flow app:denied
Invoke succeeds for an entitled persona and is denied for Frank. Tokens show the real chain (sub=persona, act.sub=wlp agent, cid=wlp).

**OpenCode capstone (Module 7).** OpenCode 1.18.4 installed, OpenAI via OPENAI_API_KEY env, MCP block points at the bridge with X-MCP-Agent=taskvantage-sales-agent. `opencode run "List the Northwind account from VantageCRM"` connects to the bridge (bridge log: `10.0.0.6 POST / 401`) and the agent reports "You're not authorized" — the bridge correctly rejects the unauthenticated MCP session. The one step that cannot be driven headlessly is OpenCode's interactive MCP OAuth (browser loopback) to establish the persona session; that is inherent to the capstone (the attendee logs in as a persona in the browser) and uses the same DCR->authorize->token flow already validated end-to-end via the Toolkit and the raw e2e harness. Automatable portion: PASS. Interactive persona-login step: not headlessly testable, deferred to a live human run.
