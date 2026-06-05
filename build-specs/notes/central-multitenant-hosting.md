# Open design question: central multi-tenant app hosting

**Status: RESOLVED (June 2026) — see [`../adr/0001-central-multitenant-api-only.md`](../adr/0001-central-multitenant-api-only.md).** Decision: central, API-only, Redis-backed, issuer-keyed multi-tenant. The build spec has been updated accordingly. Original exploration retained below for context. The shared-Adapter question further down remains tabled.

## The question

The current build spec (`../lab-apps-build-spec.md`) assumes each attendee hosts their own copy of VantageCRM and VantageDesk. For labs up to ~100 users that's 100 deployments to provision, monitor, and debug, plus 100 sets of injected secrets. Alternative: host the two apps **once, centrally, multi-tenant**, and have each attendee connect their own Okta org to it — closer to how real SaaS works, and the lab narrative arguably improves.

## What changes under the central model

- **Tenant key is the attendee's Okta org (the issuer), not the app instance.** The audience stays constant across all tenants (`api://vantage-crm` / `api://vantage-desk` are fixed lab values), so audience is *not* the discriminator — `iss` is.
- **Enroll by org, not by auth server.** `vantage-crm-as` is pre-provisioned (issuer known up front) but `vantage-desk-as` is created *by the attendee* in Module 4, so its issuer doesn't exist until mid-lab. Enroll the org once (`https://{org}.okta.com` base) and trust any custom auth server under it, proven by JWKS signature. One enrollment covers both the prebuilt CRM auth server and the attendee-built Desk one — avoids a re-enrollment step in Module 4.
- **Token validation:** decode unverified to read `iss` → match org prefix against tenant registry (401 if not enrolled) → fetch/cache that issuer's JWKS → verify signature + `aud` + `exp` → scope all data access to that tenant.
- **Per-tenant data partitioning.** Every attendee's org has the same `alex.martinez@atko.email`; only the issuer distinguishes attendee 42's Alex from attendee 77's. Each tenant gets a logically isolated dataset, seeded identically, with a **per-tenant reset** action (new requirement — in the per-attendee model "reset" was just a container restart).

## The two unresolved forks

1. **Browser tour vs API-only.**
   - *Keep the Module 1.5/1.6 browser login tour* ("log in as Susan, see 8 accounts; as Alex, see 2") → the app's OIDC Relying Party role must federate to *each attendee's* org, i.e. per-tenant OIDC client ID/secret stored in the registry and captured at enrollment. This is the main friction point of the whole central model.
   - *Make the central app API-only* → drop the RP role entirely; attendees see row-level filtering only through the agent/script output in Module 3. Much simpler to multi-tenant (issuer-based token validation and nothing else), at the cost of the tactile login demo.
   - Current lean: API-only if optimizing for 100-user robustness, but depends how much the Module 1 login moment is valued. Deliberate call needed.

2. **State model.**
   - *In-memory, single replica* — restart resets everyone's data; minimum moving parts; failure domain is "all 100 blocked."
   - *Redis-backed (keyed by tenant), multi-replica* — survives restarts, allows HA. The one place worth spending complexity, because it's the difference between "one attendee has a problem" and "all 100 are blocked."
   - Current lean: Redis-backed if the lab runs repeatedly and a mid-session crash is unacceptable; in-memory single-replica for minimum moving parts.

## What stays per-attendee regardless

The **MCP server and Okta MCP Adapter** don't centralize cleanly — they hold per-org agent secrets and do per-org XAA token exchange. Natural seam: **apps central** (dumb resource-server + data layer), **MCP server + Adapter per-attendee** (baked into the VDI/Heropa env), pointing at the central app URLs. Each attendee's MCP server calls the central app with the attendee's Bearer token; the central app resolves tenant by issuer.

## Honest downsides of centralizing

- Trades 100 small failure domains for one big one.
- Introduces tenant isolation as a correctness risk: a bug leaking tenant A's data to tenant B is the thing to fear. Issuer scoping must be airtight on **every** data path.

## Related parked question: shared Adapter backend, distinct per-user GUIs

**Status: parked** (shares the tenant-isolation spine with the above, so kept here).

The idea: instead of a per-attendee Okta MCP Adapter, run a **single shared Adapter backend** with a distinct front-end (GUI) per attendee. The GUIs being separate is the easy part — those multi-tenant trivially, just per-attendee front-ends pointed at one endpoint. The real question is **key custody**, because the Adapter is not a dumb proxy: it performs the XAA token exchange, which means it acts as each attendee's registered agent (a distinct identity, in a distinct org, with a distinct private key) and presents that agent's client assertion to that attendee's org.

The feasibility fork:

- **Keys travel with the request** (the per-user GUI/agent runtime holds the attendee's agent private key, request carries the assertion material) → a shared Adapter backend works and stays stateless per-tenant: each call says "I'm attendee N's agent against org-N, here's my assertion," and the backend routes the XAA exchange to the right org. Secret custody stays at the edge. This is the only clean version.
- **Adapter holds the keys** (the more typical design, Adapter is the confidential client storing agent private keys server-side) → the shared backend becomes a vault of up to 100 agents' private keys with tenant-selection on every path. A cross-tenant bug here does not leak fake CRM data (as it would for the central app) — it leaks the **ability to act as another attendee's agent**. Worst blast radius of any centralization option discussed.

Extra wrinkle for the lab: the Adapter also does **scope-based tool filtering**, so a shared Adapter fans out to up to 100 different org authorization servers (per-tenant JWKS + policy caching) — fine at lab-pace traffic, but more moving parts in the component that is hardest to debug live, in front of customers.

**Decision (June 2026): tabled.** Joe agreed the impersonation blast radius makes this a different risk class from the shared *app* backend, which holds no secrets. Revisit only if the design demonstrably keeps agent keys at the edge, and even then the tenant-selection path wants test coverage before it goes near a 100-person room. The default remains: MCP server + Adapter per-attendee, baked into the VDI/Heropa env.

## To resume

- **Central app:** RESOLVED — API-only, Redis-backed, issuer-keyed multi-tenant. See `../adr/0001-central-multitenant-api-only.md`; build spec updated accordingly.
- **Shared Adapter:** only reconsider if agent key custody can stay with the per-user GUI/runtime (the "keys travel with the request" branch). Otherwise leave per-attendee.
