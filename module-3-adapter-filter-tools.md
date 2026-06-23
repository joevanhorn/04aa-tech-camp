# Lab Module 3: See the Adapter Filter Tools by User [Estimate: 30 minutes]

## Objective

Watch the MCP Adapter constrain the agent's tool catalog based on the requesting user. By the end of this lab you will have seen the same agent — the one you registered in Lab 2 — return three different tool lists for three different users, driven entirely by what each user is permitted to do in VantageCRM. The agent's "capabilities" are not a property of the agent. They are a property of the user the agent is acting for.

## Scenario

The TaskVantage Sales Agent is registered, owned, and connected. The sales team is asking the obvious question: "If anyone in the company can sign in and talk to this agent, what stops the wrong person from getting account data they shouldn't see?"

You'll answer that by running the same agent request as three users and observing that what comes back depends on the user. Susan (a sales manager) and Alex (a sales rep) are both in a CRM group that `vantage-crm-as` grants access to, so each gets the agent's full CRM tool set. Frank (an engineering director with no CRM relationship) is in no CRM group, so he gets nothing. No reconfiguration between runs — only the user changes.

> **Access today is binary (0-or-all).** Membership in *any* `vantage-crm-as` policy group grants the **full** `crm.*` tool set; a non-member gets **none**. The lab does **not** currently hand a sales rep a narrower read-only *tool* subset than a sales manager — graduated per-user tool filtering is a known follow-up (see `lab-infra/README.md`). What still differs per user is the **data** each one sees inside those tools: VantageCRM row-filters results by the caller's `sub` + `groups` (Module 1.5), so a rep sees fewer accounts than a manager even when both hold the same tools.

## Browser use for this lab

- Local browser for the Okta Admin Console (review and audit steps).
- Virtual Desktop for the terminal script that simulates the agent's tool-listing call.

---

### 3.1 How the adapter filters tools

The MCP Adapter is the policy enforcement point between the agent and the resources behind it. When the agent asks "what tools can I use right now?", the adapter does not just hand over its full catalog. It does this:

1. **Identify the agent.** Verify the caller is a registered, active AI agent with a managed connection that covers the resources the catalog touches. (Your work in Lab 2.)
2. **Identify the user.** Read the user's identity from the user-context token the agent presents (the user the agent is acting for). No user context, no further work.
3. **Resolve the user's effective scopes.** Ask Okta which scopes this user is permitted to request from `vantage-crm-as`. The answer comes from the auth server's access policy rules, which key off group membership. Today every CRM rule grants the **same full `crm.*` scope set**, so the resolution is effectively binary: a user who matches any rule gets all CRM scopes; a user who matches none gets none.
4. **Map scopes to tools.** The adapter holds a static map of `tool → required scope`. It returns only the tools whose required scopes are in the user's effective set. Because matched users get the full scope set today, a matched user sees the full CRM tool catalog and a non-matched user sees nothing.

> **Why not a graduated tool subset per group?** Conceptually the access policy *could* grant a sales rep fewer scopes (read-only) than a manager, and the adapter would then surface fewer tools. The lab does not do this yet: the adapter requests the managed connection's full `INCLUDE_ONLY` scope set for every user, and Okta returns `no_matching_policy` when a request isn't a subset of a matched rule — so a narrower per-group rule denies that user entirely instead of trimming their tools. Until the adapter narrows its request per user (or Okta does an intersection grant), access stays 0-or-all. Tracked in `lab-infra/README.md`.

The agent never sees a tool that does not match the user. There is no client-side filtering. There is no "ask and be denied later." The adapter shapes the catalog before the agent ever sees it.

### 3.2 Review the access policy on vantage-crm-as

The access policy is what drives the entire filtering decision. Worth seeing it before you watch its consequences.

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

*NOTE: Okta evaluates rules top to bottom and stops at the first match. Susan Potter is in `Sales Management`, so rule 1 matches; Alex Martinez is in `Sales Reps`, so rule 2 matches. Because every CRM rule currently grants the **same full scope set** (the binary model — see 3.1), matching a rule yields all six CRM tools regardless of which rule matched. The catch-all is what makes Frank Boone see zero tools. (A future graduated model would let rule 2 grant a strict subset of rule 1; today it does not — see `lab-infra/README.md`.)*

*NOTE: Rule 4 gates a group named `CRM Read - Cross-Functional`. That group is empty at this point in the camp — no user matches rule 4 right now. The group is populated only via OIG access requests in Lab 5, where you will watch a user (Frank) be added to it temporarily, see rule 4 start firing for him, and watch his tools appear and then disappear as the membership is revoked. The rule exists today; the membership is the dynamic part.*

### 3.3 Review the tool catalog and scope mapping

The adapter knows about six CRM tools, each gated by one scope on `vantage-crm-as`.

| Tool | Required scope |
| --- | --- |
| `crm.lookup_account` | `crm.accounts.read` |
| `crm.create_account` | `crm.accounts.write` |
| `crm.update_account` | `crm.accounts.write` |
| `crm.lookup_contact` | `crm.contacts.read` |
| `crm.lookup_opportunity` | `crm.opportunities.read` |
| `crm.update_opportunity` | `crm.opportunities.write` |

*NOTE: The catalog also has six VantageDesk tools, but they are not yet reachable — `vantage-desk-as` does not exist, so the adapter has no scope to gate them against. Every Desk tool will be filtered out for every user until you build the auth server in Lab 4. The script will show this explicitly.*

### 3.4 List tools as Alex Martinez (Sales Rep)

- On the Virtual Desktop, open a terminal and run:

```bash
~/Desktop/list-agent-tools.sh --user alex.martinez@atko.email
```

- Expected output:

```
Acting as: alex.martinez@atko.email  (groups: Sales Reps, All Employees)
User context: user-context access token (simulated)
Agent: TaskVantage Sales Agent (ACTIVE)

→ Calling MCP Adapter at https://mcp.{{lab_domain}}/tools
→ Adapter resolved effective scopes via vantage-crm-as:
    Matched rule 2 (Sales reps — access): full crm.* set
      crm.accounts.read, crm.accounts.write, crm.contacts.read,
      crm.opportunities.read, crm.opportunities.write

6 tools available to this user:
  ▸ crm.lookup_account       Look up a customer account by name or ID
  ▸ crm.create_account       Create a new customer account
  ▸ crm.update_account       Update an existing account
  ▸ crm.lookup_contact       Look up a contact by name or email
  ▸ crm.lookup_opportunity   Look up an opportunity by name or stage
  ▸ crm.update_opportunity   Update an opportunity's stage, amount, or details

0 tools filtered out (scope not granted to this user).

6 tools filtered out (resource not yet configured):
  ✗ itsm.lookup_ticket, itsm.create_ticket, itsm.update_ticket,
    itsm.lookup_incident, itsm.update_incident, itsm.search_kb
```

Alex's `Sales Reps` membership matched rule 2, so the agent surfaces the full CRM tool set for him — access is binary today (member = all CRM tools). What still differs from a manager is the **data**: when Alex actually calls `crm.lookup_account`, VantageCRM row-filters the results to the accounts he owns (Module 1.5). The ITSM tools sit in the second filtered group because the adapter has nowhere to ask about them yet.

### 3.5 List tools as Susan Potter (Sales Manager)

- Run the script again, this time as Susan:

```bash
~/Desktop/list-agent-tools.sh --user susan.potter@atko.email
```

- Expected output:

```
Acting as: susan.potter@atko.email  (groups: Sales Management, All Employees)
User context: user-context access token (simulated)
Agent: TaskVantage Sales Agent (ACTIVE)

→ Calling MCP Adapter at https://mcp.{{lab_domain}}/tools
→ Adapter resolved effective scopes via vantage-crm-as:
    Matched rule 1 (Sales managers — full access): full crm.* set
      crm.accounts.read, crm.accounts.write, crm.contacts.read,
      crm.opportunities.read, crm.opportunities.write

6 tools available to this user:
  ▸ crm.lookup_account       Look up a customer account by name or ID
  ▸ crm.create_account       Create a new customer account
  ▸ crm.update_account       Update an existing account
  ▸ crm.lookup_contact       Look up a contact by name or email
  ▸ crm.lookup_opportunity   Look up an opportunity by name or stage
  ▸ crm.update_opportunity   Update an opportunity's stage, amount, or details

0 tools filtered out (scope not granted to this user).

6 tools filtered out (resource not yet configured):
  ✗ itsm.lookup_ticket, itsm.create_ticket, itsm.update_ticket,
    itsm.lookup_incident, itsm.update_incident, itsm.search_kb
```

Susan's `Sales Management` membership matched rule 1 — full access. Susan and Alex see the **same six tools** today, because access is binary: both are members of a CRM group, so both get the full set. Where they diverge is in the **data** each tool returns — Susan, in `Sales Management`, sees all accounts; Alex sees only his own (Module 1.5). The agent did not change. The adapter responded to *who is asking* by deciding member-vs-non-member; VantageCRM then differentiated the two members by row-level data filtering.

*NOTE: A future graduated model would also differentiate Susan and Alex at the **tool** level (e.g. Alex would lack the `create`/`update` tools). That isn't wired today — see the binary-access note in 3.1. For now the manager/rep distinction shows up in the rows returned, not the tools offered.*

### 3.6 List tools as Frank Boone — see the catch-all in action

- One more run, this time as Frank:

```bash
~/Desktop/list-agent-tools.sh --user frank.boone@atko.email
```

- Expected output:

```
Acting as: frank.boone@atko.email  (groups: Engineering, All Employees)
User context: user-context access token (simulated)
Agent: TaskVantage Sales Agent (ACTIVE)

→ Calling MCP Adapter at https://mcp.{{lab_domain}}/tools
→ Adapter resolved effective scopes via vantage-crm-as:
    (no rule matched — catch-all denies)

0 tools available to this user.

6 tools filtered out (scope not granted to this user):
  ✗ crm.lookup_account       requires crm.accounts.read
  ✗ crm.create_account       requires crm.accounts.write
  ✗ crm.update_account       requires crm.accounts.write
  ✗ crm.lookup_contact       requires crm.contacts.read
  ✗ crm.lookup_opportunity   requires crm.opportunities.read
  ✗ crm.update_opportunity   requires crm.opportunities.write

6 tools filtered out (resource not yet configured):
  ✗ itsm.lookup_ticket, itsm.create_ticket, itsm.update_ticket,
    itsm.lookup_incident, itsm.update_incident, itsm.search_kb
```

Frank is in `Engineering` — a group with no rule on `vantage-crm-as`. The catch-all denies, and the agent — for Frank — has nothing to do. In Lab 5, Frank will request access through OIG, get added temporarily to `CRM Read - Cross-Functional`, and this same script will start matching rule 4 instead of falling to the catch-all.

### 3.7 Inspect the audit trail in System Log

The runs you just performed each generated a chain of events in the Okta System Log. Walk through them now while they're fresh.

- From the Admin Console, go to **Reports** > **System Log**.
- In the search bar, filter on `target.type eq "AIAgent" and actor.id eq "{agent_id}"` `{HumanReview}` (use your agent's ID from Lab 2). Set the time range to the last 15 minutes.
- You should see, for each of the three script runs, a sequence similar to:

| Event `{HumanReview}` | Actor | Target | What it tells you |
| --- | --- | --- | --- |
| `app.oauth2.token.grant.access_token` | the agent's OAuth client | the user | The user-context token the script simulated |
| `ai_agent.token_exchange.request` | `TaskVantage Sales Agent` | `vantage-crm-as` | The adapter asking Okta what this user can request |
| `ai_agent.token_exchange.scope_evaluation` | the access policy | the user | Which rule matched and which scopes were granted |
| `ai_agent.tool_catalog.return` | the adapter | the user | The filtered catalog the user received |

*NOTE: This is the audit-and-visibility half of the access model. Every filtering decision the adapter made is recorded against the user, the agent, and the rule that fired. Compliance teams can answer "what did our agent expose to Alex last Tuesday?" without any application-side instrumentation.*

---

**End of lab.** You have seen the adapter behave as the policy enforcement point: same agent, three users, three outcomes. The agent did not change between runs. What changed was Okta's answer to "what can this user do?", and the adapter respected that answer faithfully.

In Lab 4, two things happen. First, you build the missing half — `vantage-desk-as`, its scopes, its access policy, and the managed connection on the agent — using everything you reviewed and ran here as your reference. Second, you exercise a tool invocation end-to-end: the adapter does the XAA token exchange, hands a user-scoped access token to the MCP server, and the call lands on VantageCRM (or VantageDesk) as the user. Filtering is half the story. Module 4 is the other half.
