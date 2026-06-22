# ADR-0002: Central, shared MCP server (adapter stays per-attendee)

**Status:** Accepted — June 2026
**Amends:** ADR-0001's "Unchanged" clause, which lumped the MCP server in with the Okta MCP Adapter as per-attendee.
**Related:** `../notes/central-multitenant-hosting.md`; implemented in `joevanhorn/taskvantage-apps` (`deploy/terraform/mcp.tf`, PR #2).

## Context

ADR-0001 centralized the VantageCRM/VantageDesk apps but kept **both** the MCP server and the Okta MCP Adapter per-attendee, reasoning they "hold per-org agent secrets and perform per-org XAA token exchange." That rationale is true for the **adapter** — but not for the **MCP server** as actually built.

The lab's MCP server (`taskvantage-apps/mcp-server/`) is a **stateless, secret-less bearer-forwarding proxy**: it reads only `VANTAGECRM_URL`/`VANTAGEDESK_URL`, forwards the user's Okta Bearer token to the apps, stores nothing, and holds no per-org configuration or keys. The XAA / ID-JAG token exchange and the agent's private key live entirely in the **adapter**. So the per-attendee constraint never applied to the MCP server — it was an over-generalization in ADR-0001.

The lab platform team already auto-deploys the per-attendee **adapter** to ECS. The only remaining question was how to deploy the MCP server it connects to. Heropa does not run Terraform, so a per-attendee Terraform stack for the MCP server was awkward; and 100 copies of a stateless proxy is needless operational surface.

## Decision

1. **Deploy ONE central, shared MCP server** that every attendee's adapter connects to, at `https://mcp.taskvantage-demo.com/mcp` — not one per attendee.
2. **The Okta MCP Adapter stays per-attendee** (unchanged from ADR-0001): it holds the attendee's agent credentials and performs that org's XAA token exchange. The shared-Adapter analysis in `../notes/central-multitenant-hosting.md` remains **tabled** for the reasons recorded there (agent-key impersonation blast radius).
3. **Deploy it like the apps**, in the existing `taskvantage-apps/deploy/terraform/` + `deploy.yml` pipeline (ECS Fargate behind the shared ALB, `desired_count` ≥ 2, CPU target-tracking autoscaling, multi-AZ private subnets). Not a per-attendee Terraform stack and not a bespoke CLI script.

## Why a shared MCP server is safe

Tenant isolation does **not** depend on per-attendee MCP servers. The security boundary is the **apps**, which validate each request's token signature against the issuing org's JWKS, enforce audience + scopes, and physically partition data by tenant (issuer) — see ADR-0001. The MCP server forwards the caller's token unchanged and keeps no state, so a shared instance cannot mix tenants: org A's token only ever yields org A's data, regardless of which shared replica handled it. Per-request bearer is held in a request-scoped contextvar, so concurrent requests don't bleed tokens.

## Consequences

**Positive.** Zero per-attendee MCP deployment; nothing for Heropa to provision for the MCP layer. One stateless service to operate, horizontally scaled for ~100 concurrent users like the apps. Removes the dependency on a per-attendee Terraform stack for the MCP server.

**Negative / risks.** The shared MCP server is internet-reachable behind the ALB. It is a pure proxy to apps that enforce per-token, so this is not a data-isolation risk — but to avoid an open/abusable endpoint, an **optional `X-Service-Key` gate** is included (off by default; enable once each adapter is confirmed to forward the key, or lock down by network once the adapters' VPC/account is known). The apps remain the boundary regardless.

## Impact on prior artifacts

- The per-attendee deployment template (`taskvantage-apps/deploy/per-attendee-template/`, and the original `mcp-server-deployment-template.zip`) is **superseded for the MCP server**. Its adapter/admin-UI portion is the lab platform team's concern.
- Architecture docs that drew the MCP server inside the per-attendee "MCP edge" move it into the central box, leaving the adapter per-attendee.
