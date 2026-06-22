# ADR-0001: Central, multi-tenant, API-only hosting for the lab apps

**Status:** Accepted — June 2026
**Supersedes:** the per-attendee hosting model in the original `../lab-apps-build-spec.md`
**Amended by:** `0002-central-shared-mcp-server.md` — the "Unchanged" clause below wrongly lumped the MCP server with the adapter; the MCP server is now **central/shared** (the adapter stays per-attendee).
**Related:** `../notes/central-multitenant-hosting.md` (the parked exploration this resolves)

## Context

The original build spec hosted VantageCRM and VantageDesk once per attendee. For labs of up to ~100 attendees that is 100 deployments to provision, monitor, debug, and secret-inject — the weakest part of the design. We were asked to pursue hosting the apps as a multi-tenant pseudo-SaaS that each attendee's Okta org connects to.

"Multiple IdPs" was raised and then narrowed: it means **multiple Okta orgs**, not heterogeneous IdP vendors. That keeps token and claim shapes uniform (`scp`, `groups`, controllable audience) and avoids a per-tenant claim-normalization layer — the single biggest simplification relative to a truly generic multi-IdP design.

## Decision

1. **One central, multi-tenant deployment** of VantageCRM + VantageDesk, supporting up to ~100 attendee orgs, instead of per-attendee hosting.
2. **Tenant keyed by token issuer.** Audience is a constant lab value shared by all tenants; `iss` is the discriminator. Enrollment is **by org** (`https://{org}.okta.com`), trusting any custom auth server under it via that issuer's JWKS — so the attendee-built `vantage-desk-as` (created mid-lab in Module 4) is trusted automatically with no re-enrollment step.
3. **API-only.** The apps are resource servers only — no browser login, no human SSO, no UI. Every interaction is an agentic API call. The browser-tour moments in Modules 1.5/1.6 are delivered out-of-band (rendered screenshots, or read scripts) rather than as a live UI. This removes the per-tenant OIDC client enrollment that would otherwise be the central model's hardest part.
4. **Redis-backed, per-tenant-partitioned state**, enabling horizontal scaling / HA across replicas, with a per-tenant reset action.

## Consequences

**Positive.** One deployment to operate instead of 100. Scales to the target room size. More faithful to how real SaaS is consumed (a central app your IdP connects to). API-only removes per-tenant OIDC client setup entirely. Redis plus stateless app replicas give HA and let one attendee reset without affecting others.

**Negative / risks.** Trades 100 small failure domains for one larger one (mitigated by Redis + multiple replicas). **Tenant isolation becomes a correctness-critical property on every data path** — a bug that lets org A's token read org B's data is the principal risk, and must be covered by tests before the lab runs at scale. Loses the tactile browser-login demo (accepted; faked with screenshots).

**Partly changed — see ADR-0002.** The **Okta MCP Adapter** stays **per-attendee** — it holds per-org agent secrets and performs per-org XAA token exchange, and does not centralize cleanly (see `../notes/central-multitenant-hosting.md` for the shared-Adapter analysis, which remains tabled). The **MCP server**, however, is a stateless secret-less proxy and was subsequently **centralized** (ADR-0002): one shared MCP server serves every attendee's adapter. Each adapter calls the central MCP server with the attendee's Bearer token; the MCP server forwards it to the central apps, which resolve tenant by issuer.

## Module impact

Three module steps assume a live UI and must be reworked for API-only: Module 1.5 (tour accounts as Susan vs Alex), Module 1.6 (Kim portal vs Alex self-service), Module 4.10 (find TKT-1734's access log in an admin page). Each becomes a script or a screenshot. Tracked in the build spec's Part 4 open items.
