<!-- READINESS: 0 markers. Module 6 is the pure-narrative conclusion — recap tables ("What you built", the board's three questions, "What comes next", takeaways) with no clicks, no admin-console navigation, no Lab Toolkit runs, and no new visual state an attendee reaches. Nothing screenshot-worthy; intentionally left untagged. If a "victory lap" capture is ever wanted, the only candidate is a re-shoot of the fully-configured agent's General/Managed-connections page (already covered by module-2/module-4 markers) — not added here to avoid duplicating those. -->
# Lab Module 6: Wings Earned — Conclusion [Estimate: 5 minutes]

## What you built

You started with an AI agent that had no identity, no owner, and no audit trail — a credential floating in a config file. In about three hours you turned it into one of the most governed identities in your org. You onboarded it like a new employee, and it earned its wings.

| Layer | What you configured | What it proves |
| --- | --- | --- |
| **Identity** | Agent registered in Okta UD, a human owner, a public-key credential, a linked sign-on app | The agent is known, owned, and accountable — it can be found, governed, and shut down. |
| **Access** | **vantage-crm-as** and **vantage-desk-as** authorization servers, scoped policies tied to group membership, one managed connection per app | The agent can only reach what the *user* may reach — no standing privilege, no static keys. Least privilege by construction. |
| **Governance** | An OIG access request + approval, a certification campaign, and the kill switch | Access is requested, reviewed, time-bound, and revocable — and one click suspends the whole agent. |
| **Visibility** | System Log capturing every token exchange and tool call, carrying both agent and user identity | Every action is attributable: who asked, what happened, when. Export it to your SIEM. |

## The three questions — answered

At the start, the board asked three things. You can now answer all three:

**1. What agents do we actually have?**
The agent is a first-class identity in Universal Directory, with an accountable owner — not a key in someone's config. It shows up where every other identity does.

**2. What can it do, and on whose behalf?**
Only what the signed-in user may do. Effective access is the intersection of *(what the agent may do)* ∩ *(what the user may do)* ∩ *(what the resource exposes)*. Alex and Susan reached the CRM tools on their own authority; Frank saw them but couldn't use one until OIG granted him access — and you watched it flip back when the grant was revoked. You cannot escalate through this agent.

**3. How do we stop one if it goes wrong?**
Deactivate it — one click, and instantly no user can broker a token through it, regardless of standing access. It's a reversible suspension, so you bring it back when the incident clears. To stop a single user without taking the agent down, Universal Logout ends their sessions.

## What you didn't have to do

- Write code
- Modify the agent's source
- Change either app's authentication
- Deploy custom middleware or a monitoring pipeline

The agent is a third-party tool. The apps are third-party resources. The only thing you configured is the identity layer between them. That is the point.

## What comes next

This lab covered the core secure-launch path across two apps. In production you'd layer on more:

| Capability | What it adds |
| --- | --- |
| **Human-in-the-loop (CIBA)** | Require a real-time push approval before the agent takes a sensitive action — so it knows when to stop and ask. |
| **ISPM agent discovery** | Find shadow agents you didn't know about — in browsers, on endpoints — and bring them under governance. |
| **OPA credential vaulting** | For resources that don't speak OAuth, vault and auto-rotate static credentials in Okta Privileged Access. |
| **More resources, same agent** | Add a managed connection and the new tools appear — the pattern you built for VantageDesk scales to any MCP-capable app. |

## For your own environment

Everything here applies directly to production:

1. **Swap the agent** — OpenCode → Claude Code, Copilot, Cursor, or any MCP-capable agent.
2. **Swap the resource** — VantageCRM / VantageDesk → ServiceNow, Salesforce, Jira, or any app behind an MCP server or custom authorization server.
3. **Keep the pattern** — agent identity → managed connection → scoped token exchange (as the user) → OIG governance → full audit trail.

## One sentence to take back

> "We can give AI agents to our whole workforce and prove — to auditors, to the board — exactly who authorized what, what the agent did and on whose behalf, and shut any of it down in one click."

---

**End of camp.** Thank you for building with us.
