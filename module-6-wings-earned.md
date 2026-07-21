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
Only what the signed-in user may do. Effective access is the intersection of *(what the agent may do)* ∩ *(what the user may do)* ∩ *(what the resource exposes)*. Alex and Susan reached the CRM tools on their own authority; Frank saw them but couldn't use one until OIG granted him access — and you watched it flip back when the grant was revoked. You cannot escalate through this agent — and it isn't a soft, client-side check: the Lab Toolkit's **9) Prove it can't be faked** shows Okta refusing to mint a token Frank isn't owed, and a resource rejecting a real token minted for the wrong app (a live 401, audience mismatch). Enforcement is server-side.

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

## Prove it can't be faked

Everything above is a claim until you can show enforcement isn't something the client chooses to honor. Before you leave the toolkit, run the one action built to answer the CISO's real question — *what if someone just turns the check off?* — the Lab Toolkit's **9) Prove it can't be faked**. In one keystroke it stages a legit baseline and then two **live** rejections, neither of them a toolkit-computed label:

```
== Prove it can't be faked (Story 5) ==

-- [0] Legit baseline: Alex Martinez reads CRM --
   --- Valid CRM token Okta issued to Alex Martinez (decoded JWT) ---
     sub : alex.martinez@atko.email
     aud : api://vantage-crm
     scp : crm.accounts.read crm.contacts.read crm.opportunities.read ...
     ...
   GET https://crm.taskvantage.oktademo.app/api/accounts -> HTTP 200 - 2 records. This token is real and current.

-- [1] Okta says no: Frank Boone requests the same token --
   Okta refused at /authorize - no token was ever minted:
   --- Okta denial (verbatim response) ---
     error             : access_denied
     error_description : User is not assigned to a policy that permits this scope.
     x-okta-request-id : {{authorize_request_id}}
     (This is Okta refusing to issue a token at /authorize - not a toolkit label.)

-- [2] The server says no: Alex Martinez's REAL CRM token, presented to Desk --
   Same unmodified token from step 0 - a real key cut for the wrong door.
   GET https://desk.taskvantage.oktademo.app/api/tickets  Authorization: Bearer <Alex's CRM token>
   HTTP 401 (server-side rejection):
   {"error":"invalid_token","error_description":"Audience doesn't match"}
   The Desk resource server rejected it - the token's aud says api://vantage-crm, not Desk.

   Both rejections are live HTTP from Okta / the app - not toolkit-computed labels.
```

Two independent enforcement points, both server-side:

- **Okta refuses to mint.** Frank asks for a CRM token he isn't entitled to, and Okta denies it at `/authorize` — the token never comes into existence. There is nothing to "turn off": the decision lives at the IdP, and the client's opinion of it is irrelevant.
- **The resource refuses the wrong token.** Alex's token is genuine — freshly issued by Okta in step 0 — but it is audience-bound to `api://vantage-crm`. Present it to VantageDesk and the Desk resource server rejects it with a live `401 Audience doesn't match`. A real key, the wrong door.

That is the whole point for a CISO or a board: enforcement is **server-side, not a client flag**. No amount of clever prompting, tampered tooling, or "just skip the check" changes the outcome, because the check isn't in the agent or the toolkit — it's in Okta and in the resource. What you saw as `[BLOCKED]` in Lab 3 and as a denied invoke in Lab 4 is the same wall, and it holds even when you try to climb it directly.

## One sentence to take back

> "We can give AI agents to our whole workforce and prove — to auditors, to the board — exactly who authorized what, what the agent did and on whose behalf, and shut any of it down in one click."

You didn't take that on faith — you watched Okta refuse to mint a token it shouldn't, and watched a resource reject a real token cut for the wrong audience. Enforcement you can demonstrate on demand is the difference between telling the board you're governed and *showing* them.

---

**End of camp.** Thank you for building with us.
