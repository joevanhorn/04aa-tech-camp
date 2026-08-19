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

## Bundle/compose fixes already upstream

PR #4 on `joevanhorn/okta-agent-mcp-adapter` carries the DCR private_key_jwt gate fixes and the compose admin-env passthrough fix; both were required to bring this environment up.
