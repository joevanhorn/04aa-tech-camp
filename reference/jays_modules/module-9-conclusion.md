# Module 9: Wings Earned [~5 minutes]

## What You Built

You started with an AI agent that had no identity, no governance, and no accountability. In under three hours, you turned it into one of the most governed entities in your organization.

Here's the end state:

| Layer | What you configured | What it proves |
|---|---|---|
| **Identity** | Agent registered in Okta UD, human owner assigned, public-key credential, linked to a sign-on app | The agent is known, owned, and accountable. It can be found, managed, and shut down. |
| **Access** | Custom authorization server with scoped permissions, access policy rules tied to group membership, managed connection on the agent | The agent can only access what the user is allowed to access. No over-privilege. No static keys. Least privilege by construction. |
| **Control** | CIBA policy on the escalation action, push approval via Okta Verify | Sensitive actions require a human in the loop. The agent knows when to stop and ask. |
| **Visibility** | System Log capturing every token exchange, tool call, and approval decision | Every action is auditable. Who asked, what happened, when, and whether a human approved it. |

## The Three Questions — Answered

At the start of this session, your CISO asked:

**1. Who authorized this agent to act?**
→ Okta did. The agent holds a managed connection that authorizes it to request tokens for specific resources. The user authenticates through the linked sign-on app. Both identities — agent and user — appear in every token and every log entry.

**2. What is it allowed to do — and for whom?**
→ Only what the user's scopes permit. Kim Liu in the IT Help Desk group gets full ITSM access. A user outside that group gets nothing. The MCP Adapter enforces this before the agent ever sees a tool. And for actions that cross a risk threshold — like escalating to P1 — a human must approve in real time.

**3. Can I prove it to an auditor?**
→ Yes. The System Log contains a complete, immutable record of every agent action: the user context, the agent identity, the scopes granted, the resource accessed, and the CIBA decision. Export it to your SIEM. Run it through a compliance report. It's all there.

## What You Didn't Have to Do

- Write code
- Modify the agent's source
- Change VantageDesk's authentication system
- Deploy custom middleware
- Build a monitoring pipeline

The agent is a third-party tool. The resource is a third-party application. The only thing you configured is the identity layer between them. That's the point.

## What Comes Next

This lab covered the core secure-launch path. In production, you'd layer on additional governance:

| Capability | What it adds |
|---|---|
| **Access Requests (OIG)** | End users request agent access through a governed workflow — approval chains, justifications, time-bound grants |
| **Access Certifications (OIG)** | Periodic reviews of who has access to what. Certify, modify, or revoke. Automated remediation. |
| **Kill Switch** | Deactivate the agent — one click, all access stops for all users, immediately |
| **ISPM Discovery** | Find agents you didn't know about. Shadow agents running in browsers, on endpoints, in platforms. Bring them under governance. |
| **OPA Credential Vaulting** | For resources that don't speak OAuth — vault static credentials in Okta Privileged Access, rotate them automatically |
| **Multi-resource expansion** | Same agent, additional resources. Add a managed connection, new tools appear. The pattern scales. |

Your SE can walk you through any of these — the environment supports it.

## For Your Own Environment

Everything you built today applies directly to your production deployment:

1. **Swap the agent** — Replace opencode.io with Claude Code, GitHub Copilot, Cursor, or any MCP-capable agent
2. **Swap the resource** — Replace VantageDesk with ServiceNow, Salesforce, Jira, or any application behind an MCP server or custom authorization server
3. **Keep the pattern** — Agent identity → managed connection → scoped token exchange → CIBA for sensitive actions → full audit trail

The architecture is the same. The configuration steps are the same. The compliance story is the same.

## One Sentence to Take Back

> "We can deploy AI agents to our entire workforce and prove — to auditors, to the board, to regulators — exactly who authorized what, what the agent did, and that a human was in the loop for anything sensitive."

---

**End of lab.** Thank you for building with us.
