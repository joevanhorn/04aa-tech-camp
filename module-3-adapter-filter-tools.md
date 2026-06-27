# Lab Module 3: See Okta Govern the Agent's Tools by User [Estimate: 30 minutes]

## Objective

By the end of this lab you will have run the same agent — the one you registered in Lab 2 — as three different users and watched Okta govern *which of its tools each user is allowed to use*, enforced at the moment a tool is invoked rather than by hiding the menu. Every user sees the **full** catalog; what changes per user is whether Okta will issue a token to actually run a tool — capability here is not security-by-obscurity.

- Review the access policy and tool-to-scope mapping on `vantage-crm-as`
- List the agent's full CRM tool catalog as Alex Martinez (sales rep) and Susan Potter (sales manager) — and see Okta authorize all six tools for each
- List the same catalog as Frank Boone (engineering director) — see all six tools, every one blocked, because Okta authorizes none for him
- Inspect the Okta System Log audit trail that records each authorized and denied attempt

## Scenario

The TaskVantage Sales Agent is registered, owned, and connected. The sales team is asking the obvious question: "If anyone in the company can sign in and talk to this agent, what stops the wrong person from getting account data they shouldn't see?"

You'll answer that by running the same agent request as three users. Every user — Susan, Alex, and Frank — sees the **same** six-tool CRM catalog when they list the agent's tools; tool *visibility* is a property of the agent, not the user. The difference is what Okta will *authorize*. Susan (a sales manager) and Alex (a sales rep) are both in a CRM group that `vantage-crm-as` grants access to, so Okta authorizes all six tools for each of them. Frank (an engineering director with no CRM relationship) is in no CRM group, so Okta authorizes none — he can see all six tools but is blocked from using any of them. No reconfiguration between runs — only the user changes.

> **Okta hides nothing; it governs at use-time.** Every user SEES the agent's full tool catalog. What differs is whether Okta will issue that user a token for the resource when they try to invoke a tool. Access today is binary (0-or-all): membership in *any* `vantage-crm-as` policy group means Okta authorizes the **full** `crm.*` tool set; a non-member is authorized for **none** (they still see all six, but every invocation is denied — "Authentication failed for resource"). The lab does **not** currently authorize a sales rep for a narrower read-only *tool* subset than a sales manager — graduated per-user tool authorization is a known follow-up (see `lab-infra/README.md`). What still differs per user is the **data** each one sees inside the tools they're authorized for: VantageCRM row-filters results by the caller's `sub` + `groups` (Module 1.5), so a rep sees fewer accounts than a manager even when both are authorized for the same tools.

## Browser use for this lab

- Local browser for the Okta Admin Console (review and audit steps).
- Virtual Desktop for the **Lab Toolkit**, which simulates the agent's tool-listing call.

---

### 3.1 How the adapter exposes the catalog and Okta governs use

The MCP Adapter is the policy enforcement point between the agent and the resources behind it — but it does its enforcement at **use-time**, not at list-time. Two distinct things happen:

**Listing tools (visibility is resource-based, not user-based).** When the agent asks "what tools are available?", the adapter returns the agent's **full** catalog — the complete set of tools registered for the resources the agent is connected to. This list is the same for every user. Alex, Susan, Kim, and Frank all see the same six CRM tools. The adapter does not trim the menu per user.

**Invoking a tool (Okta authorizes at the token exchange).** When a user actually invokes a tool, the adapter performs the Okta ID-JAG / XAA token exchange for *that user* against the tool's resource auth server (`vantage-crm-as`). At that moment:

1. **Identify the agent.** Verify the caller is a registered, active AI agent with a managed connection that covers the resource. (Your work in Lab 2.)
2. **Identify the user.** Read the user's identity from the user-context token the agent presents (the user the agent is acting for).
3. **Ask Okta for a token.** The adapter requests a user-scoped token from `vantage-crm-as`. Okta evaluates the auth server's access policy rules, which key off group membership. If the user matches a rule, **Okta issues the token** and the tool call proceeds. If the user matches no rule, **Okta issues no token** — the action is denied with "Authentication failed for resource."

Today every CRM rule grants the **same full `crm.*` scope set**, so authorization is effectively binary: a user who matches any rule can use all six CRM tools; a user who matches none can use none — but **both see all six in the catalog**.

> **Why not a graduated tool subset per group?** Conceptually the access policy *could* grant a sales rep fewer scopes (read-only) than a manager, and Okta would then authorize fewer tools for them at invoke-time. The lab does not do this yet: the adapter requests the managed connection's full `INCLUDE_ONLY` scope set for every user, and Okta returns `no_matching_policy` when a request isn't a subset of a matched rule — so a narrower per-group rule denies that user entirely instead of authorizing a smaller tool subset. Until the adapter narrows its request per user (or Okta does an intersection grant), authorization stays 0-or-all. Tracked in `lab-infra/README.md`.

> **NOTE — the honest governance story.** A user can SEE tools the agent has that they are not allowed to use. Okta does not hide the menu; it refuses to authorize the action at the moment of invocation. This is a *stronger* control than security-by-obscurity: enforcement happens at the point of action, against the live access policy, and every denial is audited. There is no "filtered catalog" that a user could be tricked into thinking is the whole story — the whole catalog is visible, and the boundary is the token Okta will or won't issue.

### 3.2 Review the access policy on vantage-crm-as

The access policy is what drives the entire authorization decision — whether Okta will issue a user a token for the resource when they invoke a tool. Worth seeing it before you watch its consequences.

- From the Admin Console, go to **Security** > **API**.
- Click `vantage-crm-as`.
- Select the **Access Policies** tab.
- Click into the policy that applies to the AI agent client. Review the rules:

| Rule order | Rule name | If user is in group... | Granted scopes |
| --- | --- | --- | --- |
| 1 | Sales managers — full access | `Sales Management` | full `crm.*` set |
| 2 | Sales reps — access | `Sales Reps` | full `crm.*` set |
| 3 | IT help desk — access | `IT Help Desk` | full `crm.*` set |
| 4 | Cross-functional readers — access | `CRM Read - Cross-Functional` | full `crm.*` set |
| Catch-all | Deny | (anyone else) | (none) |

where the **full `crm.*` set** is `crm.accounts.read`, `crm.accounts.write`, `crm.contacts.read`, `crm.opportunities.read`, `crm.opportunities.write`.

*NOTE: Okta evaluates rules top to bottom and stops at the first match. Susan Potter is in `Sales Management`, so rule 1 matches; Alex Martinez is in `Sales Reps`, so rule 2 matches. Because every CRM rule currently grants the **same full scope set** (the binary model — see 3.1), matching a rule means Okta authorizes all six CRM tools regardless of which rule matched. The catch-all is what makes Frank Boone fail authorization — he still sees all six tools, but Okta won't issue him a token, so every invocation is denied. (A future graduated model would let rule 2 grant a strict subset of rule 1; today it does not — see `lab-infra/README.md`.)*

*NOTE: Rule 4 gates a group named `CRM Read - Cross-Functional`. That group is empty at this point in the camp — no user matches rule 4 right now. The group is populated only via OIG access requests in Lab 5, where you will watch a user (Frank) be added to it temporarily, see rule 4 start firing for him, and watch his tools flip from blocked to usable and back as the membership is revoked. The rule exists today; the membership is the dynamic part.*

### 3.3 Review the tool catalog and scope mapping

The adapter knows about six CRM tools. Every user sees all six when they list the agent's tools — the catalog is the agent's full capability set, independent of who is asking. The scope below is what Okta requires at *invoke-time*: when a user tries to run a tool, Okta must authorize the matching scope on `vantage-crm-as` (by issuing a token) or the call is denied.

| Tool | Scope Okta must authorize at invoke-time |
| --- | --- |
| `crm.lookup_account` | `crm.accounts.read` |
| `crm.create_account` | `crm.accounts.write` |
| `crm.update_account` | `crm.accounts.write` |
| `crm.lookup_contact` | `crm.contacts.read` |
| `crm.lookup_opportunity` | `crm.opportunities.read` |
| `crm.update_opportunity` | `crm.opportunities.write` |

*NOTE: The agent also has six VantageDesk tools, but they are not yet wired in this lab build — `vantage-desk-as` does not exist, so the adapter has no resource to exchange a token against for them. The Lab Toolkit's tool-listing focuses on the CRM tools; Desk tools show nothing / "resource not configured" until you build the auth server in Lab 4.*

### 3.4 List tools as Alex Martinez (Sales Rep)

- Open the **Lab Toolkit** (desktop icon) and choose **4) List the agent's tools**, then select **Alex Martinez (Sales Rep)** when prompted for a persona.

- Expected output:

```
== The agent's tools - and what Okta lets Alex Martinez use ==
   The agent exposes 6 tools - every user SEES the full catalog.
   With Alex Martinez's entitlements, Okta authorizes 6 of 6:
     [USABLE]  {{crm_as_id}}__crm.lookup_account
     [USABLE]  {{crm_as_id}}__crm.create_account
     [USABLE]  {{crm_as_id}}__crm.update_account
     [USABLE]  {{crm_as_id}}__crm.lookup_contact
     [USABLE]  {{crm_as_id}}__crm.lookup_opportunity
     [USABLE]  {{crm_as_id}}__crm.update_opportunity
   ^ USABLE = Okta will issue Alex Martinez a token for this resource, so the action is authorized.
```

Alex's `Sales Reps` membership matched a rule on `vantage-crm-as`, so Okta authorizes the full CRM tool set for him — authorization is binary today (member = all CRM tools usable). He sees all six tools because every user sees the full catalog; the `[USABLE]` marking is Okta saying it will issue him a token for each one. What still differs from a manager is the **data**: when Alex actually calls `crm.lookup_account`, VantageCRM row-filters the results to the accounts he owns (Module 1.5). (Tool names are namespaced `<authServerId>__crm.*`; Desk tools aren't wired in this lab build, so they don't appear here.)

**Why this mattered:** The tools turned `[USABLE]` not because the agent has CRM rights, but because *Alex* does — the agent borrowed the keys Alex already carries. Effective access is the intersection of what the agent can do and what the user may do; here the user side is populated, so the door opens.

### 3.5 List tools as Susan Potter (Sales Manager)

- In the **Lab Toolkit**, choose **4) List the agent's tools** again, this time selecting **Susan Potter (Sales Manager)**.

- Expected output:

```
== The agent's tools - and what Okta lets Susan Potter use ==
   The agent exposes 6 tools - every user SEES the full catalog.
   With Susan Potter's entitlements, Okta authorizes 6 of 6:
     [USABLE]  {{crm_as_id}}__crm.lookup_account
     [USABLE]  {{crm_as_id}}__crm.create_account
     [USABLE]  {{crm_as_id}}__crm.update_account
     [USABLE]  {{crm_as_id}}__crm.lookup_contact
     [USABLE]  {{crm_as_id}}__crm.lookup_opportunity
     [USABLE]  {{crm_as_id}}__crm.update_opportunity
   ^ USABLE = Okta will issue Susan Potter a token for this resource, so the action is authorized.
```

Susan's `Sales Management` membership matched a CRM rule — Okta authorizes all six. Susan and Alex see the **same six tools** and Okta authorizes the **same six** for both, because authorization is binary today: both are members of a CRM group, so both get the full set. (Every user sees the full catalog regardless — that part is identical even for someone with no access; see 3.6.) Where Susan and Alex diverge is in the **data** each tool returns — Susan, in `Sales Management`, sees all accounts; Alex sees only his own (Module 1.5). The agent did not change. Okta responded to *who is asking* by deciding member-vs-non-member at the token exchange; VantageCRM then differentiated the two members by row-level data filtering.

**Why this mattered:** Same agent, same catalog, two different users — and the authorization tracked the *user*, not the agent. The agent is one key ring serving whoever it acts for; Susan and Alex each got in on their own authority, and the data each saw stayed bounded by that same identity.

*NOTE: A future graduated model would also differentiate Susan and Alex at the **tool** level (e.g. Okta would not authorize the `create`/`update` tools for Alex — they'd show `[BLOCKED]` for him). That isn't wired today — see the binary-authorization note in 3.1. For now the manager/rep distinction shows up in the rows returned, not in which tools Okta authorizes.*

### 3.6 List tools as Frank Boone — see the catch-all in action

- In the **Lab Toolkit**, choose **4) List the agent's tools** one more time, this time selecting **Frank Boone (Engineering)**.

- Expected output:

```
== The agent's tools - and what Okta lets Frank Boone use ==
   The agent exposes 6 tools - every user SEES the full catalog.
   With Frank Boone's entitlements, Okta authorizes 0 of 6:
     [BLOCKED] {{crm_as_id}}__crm.lookup_account
     [BLOCKED] {{crm_as_id}}__crm.create_account
     [BLOCKED] {{crm_as_id}}__crm.update_account
     [BLOCKED] {{crm_as_id}}__crm.lookup_contact
     [BLOCKED] {{crm_as_id}}__crm.lookup_opportunity
     [BLOCKED] {{crm_as_id}}__crm.update_opportunity
   ^ BLOCKED = the agent HAS the tool, but Okta won't issue Frank Boone a token for that resource, so the action is denied at use-time.
```

This is the heart of the lab. Frank sees the **same six tools** Alex and Susan saw — the catalog is the agent's, not the user's. But Frank is in `Engineering`, a group with no rule on `vantage-crm-as`. So when Frank tries to *use* any of these tools, the catch-all denies, Okta issues no token, and the action fails. He has the full menu in front of him and can't run a single item on it.

**Why this mattered:** This is the intersection made concrete. The agent has the tools, but Frank's authority is empty — and the agent can do nothing *for him* that he couldn't do himself. The menu isn't hidden; his badge just won't open the door. This is exactly why a service app with its own API key would have been dangerous: that model drops the user, so it would have let Frank through. You cannot escalate through this agent.

> **NOTE — Frank sees 6, can use 0.** This is the corrected mental model in one line: Okta does not hide the six tools from Frank. It lets him see exactly what the agent can do, and refuses to authorize him to do any of it. That is governance at the moment of action, not a trimmed-down menu. To confirm it for yourself, try 3.6a below — Frank can *list* the tools but cannot *invoke* one.

- To see the denial at invoke-time, in the **Lab Toolkit** choose **5) Invoke a tool**, select **Frank Boone (Engineering)**, and invoke `crm.lookup_account`. Expected output:

```
   BLOCKED by Okta: Authentication failed for resource '{{crm_as_id}}'
   Frank Boone can SEE this tool, but Okta did not authorize the action - no token was issued for this resource.
```

In Lab 5, Frank will request access through OIG, get added temporarily to `CRM Read - Cross-Functional`, and this same Lab Toolkit step will start matching rule 4 instead of falling to the catch-all — flipping all six tools from `[BLOCKED]` to `[USABLE]` for him. The catalog he sees won't change; what changes is whether Okta authorizes the actions.

### 3.7 Inspect the audit trail in System Log

The runs you just performed each generated a chain of events in the Okta System Log. Walk through them now while they're fresh.

- From the Admin Console, go to **Reports** > **System Log**.
- In the search bar, filter on `target.type eq "AIAgent" and actor.id eq "{agent_id}"` (use your agent's ID from Lab 2). Set the time range to the last 15 minutes.
- You should see, for each of the three tool-listing runs, a sequence similar to:

| Event | Actor | Target | What it tells you |
| --- | --- | --- | --- |
| `app.oauth2.token.grant.access_token` | the agent's OAuth client | the user | The user-context token the Lab Toolkit simulated |
| `ai_agent.token_exchange.request` | `TaskVantage Sales Agent` | `vantage-crm-as` | The adapter asking Okta to issue this user a token for the resource |
| `ai_agent.token_exchange.scope_evaluation` | the access policy | the user | Which rule matched (or the catch-all) — i.e. whether Okta authorized the action |
| `ai_agent.token_exchange.grant` / `…deny` | Okta | the user | Whether a token was issued (action authorized) or refused (action denied) |

*NOTE: This is the audit-and-visibility half of the access model — and note what it records. The user always SEES the full catalog (visibility isn't gated), so the audit trail is about the **per-user authorization decision at use-time**: for each tool the user tried to use, did Okta issue a token or deny it? Every grant and denial is recorded against the user, the agent, and the rule that fired (or didn't). Compliance teams can answer "what was our agent authorized to do for Alex last Tuesday — and what was Frank refused?" without any application-side instrumentation.*

**Why this mattered:** Because the agent acts *as* the user rather than as itself, every attempt is attributable to both — which agent, on whose authority. That is only possible because the user never dropped out of the chain; a shared API key would have logged the agent and erased the person it was acting for.

---

**End of lab.** You have seen Okta behave as the policy enforcement point at the moment of action: same agent, same six-tool catalog for everyone, three different authorization outcomes. The agent did not change between runs, and neither did the catalog each user could see. What changed was Okta's answer to "will I issue this user a token to run this tool?" — and that answer is what governs the agent's behavior.

In Lab 4, two things happen. First, you build the missing half — `vantage-desk-as`, its scopes, its access policy, and the managed connection on the agent — using everything you reviewed and ran here as your reference. Second, you exercise a tool invocation end-to-end: the adapter does the XAA token exchange, hands a user-scoped access token to the MCP server, and the call lands on VantageCRM (or VantageDesk) as the user. Use-time authorization is half the story. Module 4 is the other half.
