# Agent "Client registration" — GUI + API mapping

**Date:** 2026-08-19
**Context:** The migrated Okta AI Agents admin console (preview) adds a **Client registration** section on the agent detail page (left nav: Profile / Owners / **Client registration** / User access / Machine access / Resource connections). It lets an admin choose how the agent authenticates to Okta, with one method active at a time and the others staged. This maps that GUI to the underlying API, verified live against `demo-o4aa-techcamp-xaa2` on a throwaway agent (created and deleted during the probe).

## The three methods = the app's `token_endpoint_auth_method`

The agent's sign-on app (`signOnProvider.appInstanceId`) carries the authoritative "active method" in `credentials.oauthClient.token_endpoint_auth_method`, editable via `PUT /api/v1/apps/{appId}`:

| GUI card | token_endpoint_auth_method | Credential material | Notes |
|---|---|---|---|
| **Client ID only** | `none` | none | Public client; identity is just the `wlp...` client_id. "Least secure," for local coding agents (the CIMD/DCR public path). |
| **Client secret** | `client_secret_basic` / `client_secret_post` | agent `credentials/secrets` | "Confidential, server-side agents." |
| **Public/private key** | `private_key_jwt` | agent `credentials/jwks` | "Builder-managed key pair. Most secure." This is the lab's path (the bridge holds the key). |

Auto-created apps (`signOnProvider: NEW_OIDC_APP`) default to `private_key_jwt`. Switching methods = `PUT` the app with a new `token_endpoint_auth_method` (this is what the GUI "Activate" / Step 3 button does). The client_id is always the `wlp...` workload principal ID.

## Credential sub-resources (both are agent-scoped, undocumented in the public spec as of 2026-08-19)

**Client secret** — `.../workload-principals/api/v1/ai-agents/{agentId}/credentials/secrets`
- `GET` list (returns `[]` when none)
- `POST {}` generate → returns `{id: "ocs...", client_secret: "<one-time>", secret_hash, status: "ACTIVE", _links.{activate,deactivate,delete}}`. **The `client_secret` value is shown only once, at creation.**
- `.../secrets/{id}` GET / DELETE, `.../secrets/{id}/lifecycle/{activate,deactivate}`

**Public/private key** — `.../ai-agents/{agentId}/credentials/jwks` (was already in the public spec)
- `GET` list, `POST <public JWK>` → `{id: "wpc...", kid, status: "ACTIVE"}`, `.../jwks/{keyId}` GET/DELETE, lifecycle activate/deactivate

"Staged methods are saved" = these credential resources persist independent of which method is active, so an admin can switch `token_endpoint_auth_method` without regenerating. Multiple credentials can be ACTIVE at the API level simultaneously; the GUI enforces one active *method*.

## This resolves finding #2 (the `jwks` app-edit error)

Confirmed on the throwaway agent: a `PUT /api/v1/apps/{appId}` (e.g. adding a redirect URI) **fails `Api validation failed: jwks` only when the app is `private_key_jwt` and the agent has no registered JWK.** Once a key exists on `credentials/jwks`, the identical edit succeeds, and flipping the method to `client_secret_basic` also succeeds. So it is not a general "edit lock" — it is Okta validating that a `private_key_jwt` client has key material. Correct ordering: register/activate the client-registration method (or at least a key) **before** editing the app. (Still worth confirming whether the GUI's targeted edit behaves the same, per Joe's GUI test.)

## Adapter reconciliation

- The adapter reads `token_endpoint_auth_method` from the app (migration 017) — that IS the authoritative active method, so detection is correct for all three states as long as it reads the app's current value.
- **Client-secret caveat:** the secret value is only returned at `POST` creation. An adapter "auto-fetch client secret on import" cannot read an existing secret — it would have to generate a new one (`POST credentials/secrets`) or have the admin paste it. Not lab-relevant today (the lab uses `private_key_jwt`, bridge-held key), but it matters for any `client_secret_*` agent path.

## Lab impact

- This **Client registration** section is the new "getting a badge" surface. The old Module flow (Credentials tab → Add public key → activate) is replaced by: pick a method card → generate secret / add key → Activate. Module text + screenshots for that module change.
- New left-nav items to account for: **User access** ("who can access this agent" — likely the assignment surface relevant to finding #1) and **Machine access** ("what can call this agent" — A2A, not covered by the lab today).
- The lab should standardize on **Public/private key** (`private_key_jwt`), matching the bridge-held-key model already validated.
