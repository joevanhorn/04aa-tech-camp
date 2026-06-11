# Okta AI Agents Tech Camp

A hands-on customer / prospect tech camp for governing AI agents on the Okta Workforce Identity Cloud. Modeled on the format of the existing ITP Tech Camp. Approximately 3.5 hours of guided lab work.

The two business apps — **VantageCRM** and **VantageDesk** — are **one central, multi-tenant, API-only deployment** shared by every attendee (resource servers only, no app UI or human sign-in; each app keys the tenant off the access token's issuer). Each attendee gets their own **agent, MCP server, Okta MCP Adapter, and Okta org**. See `build-specs/adr/0001-central-multitenant-api-only.md` for the hosting decision.

## Status

**Drafting.** All five module bodies, the intro, and the architecture diagram are drafted to v1-quality. Not yet validated against the live product — see `{HumanReview}` flags throughout the modules for items that need verification at lab GA (System Log event names, exact UI menu paths, grant-type selectors, etc.). URLs to external documentation have not yet been validated.

## What's here

| File | Contents |
| --- | --- |
| `lab-intro.md` | Narrative wrapper. Introduces TaskVantage, the personas, the architecture, the camp's two recurring patterns (review-then-build and same-agent-different-access), and pre-flight checklist. |
| `lab-architecture.md` | Architecture overview with the v8 Mermaid diagram. The central, multi-tenant, API-only apps vs. the per-attendee agent/MCP/adapter/Okta-org split, component roles, and the trust boundary. |
| `module-1-environment-tour.md` | 25 min. Sign in, review preconfigured personas/groups/apps, run env-check, build first piece of config (VantageDesk auth policy). |
| `module-2-bring-agent-under-management.md` | 45 min. Register an agent (Bedrock import or manual), owner + key, managed connection to VantageCRM. |
| `module-3-adapter-filter-tools.md` | 30 min. Run the tool-listing script as three different users — Alex, Susan, Frank — and watch the catalog change without the agent changing. |
| `module-4-build-vantagedesk-watch-xaa.md` | 60 min. Build the VantageDesk auth server / scopes / policy / managed connection, then exercise XAA end-to-end with decoded ID-JAG inspection. |
| `module-5-govern-with-oig.md` | 50 min. Frank requests CRM access through OIG, gets approved, sees tools appear; certification campaign revokes him; kill switch deactivates the agent. |
| `reference/architecture-diagram-source.md` | The standalone Mermaid source for the architecture diagram. Edit here and the wrapped version in `lab-architecture.md` should be kept in sync. |
| `reference/okta-xaa-id-jag-analysis.md` | Background research on Okta's XAA / ID-JAG / Cross App Access protocol and enterprise governance model. Source material for the camp, useful for proctors and authors. |

## Camp arc

1. **Module 1 — Environment Tour.** Get oriented. First piece of user-built config.
2. **Module 2 — Bring the Agent Under Management.** Register, own, credential, connect to the central CRM.
3. **Module 3 — See the Adapter Filter Tools by User.** Same agent, three users, three outcomes.
4. **Module 4 — Build VantageDesk and Watch XAA in Flight.** Build the missing half, watch the protocol.
5. **Module 5 — Govern with OIG.** Request, approve, certify, kill switch.

## Recurring patterns

- **Review-then-build.** Every capability is introduced first on VantageCRM (fully wired before the camp starts) and then built by the attendee on VantageDesk. By end of camp the two halves are configured identically — by the attendee's hands.
- **Same agent, different access.** The same tool-listing and tool-invocation scripts are run against different users at different points in time. The agent never changes. What changes is who's asking and what they're currently entitled to do. The whole camp tells the story that agent capability is a property of the user-and-moment, not a property of the agent.

## Conventions

- `{{double_brace_placeholders}}` — values that vary per-attendee or per-lab-environment (`{{org_url}}`, `{{lab_domain}}`, etc.).
- `{HumanReview}` — flags for things being verified against live Okta at lab GA. The shape of the lesson is correct; the specific text may shift before final release.
- *NOTE blocks (italic)* — context, rationale, or things to watch for. Not optional reading.

## What's not in this repo yet

- **Final URL validation pass.** Every external link in every module needs a search-and-fetch verification before customer delivery (per the standing URL validation workflow).
- **`{HumanReview}` flag resolution.** All speculative product items need to be verified against the live Okta product and either confirmed or corrected.
- **Docx / customer-facing format conversion.** Markdown drafts here; ITP-styled docx is the eventual customer deliverable.
- **Infrastructure-team dependencies.** Build specs for the lab environment that the docs reference: the central, multi-tenant, API-only VantageCRM and VantageDesk apps (tenant-by-issuer), the per-attendee MCP server with the 12-tool catalog, the per-attendee Okta MCP Adapter wired for XAA + scope filtering, the `check-environment.sh` / `list-agent-tools.sh` / `invoke-agent-tool.sh` scripts on the VDI.

## Original-source notes

These drafts emerged from a multi-session collaboration. Version numbers were used in working filenames (`module-3-draft-v4.md`, `module-5-draft-v5.md`, etc.) to track iteration. In this repo, version suffixes have been dropped — git history tracks evolution from here on. The earlier numbered drafts in the working directory are not included.
