# Lab Module 3: See the Adapter Filter Tools by User [Estimate: 30 minutes]

## Objective

Watch the MCP Adapter constrain the agent's tool catalog based on the requesting user. By the end of this lab you will have seen the same agent — the one you registered in Lab 2 — return three different tool lists for three different users, driven entirely by what each user is permitted to do in VantageCRM. The agent's "capabilities" are not a property of the agent. They are a property of the user the agent is acting for.

## Scenario

The TaskVantage Sales Agent is registered, owned, and connected. The sales team is asking the obvious question: "If anyone in the company can sign in and talk to this agent, what stops the wrong person from getting account data they shouldn't see?"

You'll answer that by running the same agent request as three users and observing that none of them sees the same thing. Alex (a sales rep) gets a read-only tool set. Susan (a sales manager) gets the full set. Frank (an engineering director with no CRM relationship) gets nothing. No reconfiguration between runs — only the user changes.

## Browser use for this lab

- Local browser for the Okta Admin Console (review and audit steps).
- Virtual Desktop for the terminal script that simulates the agent's tool-listing call.

---

### 3.1 How the adapter filters tools

The MCP Adapter is the policy enforcement point between the agent and the resources behind it. When the agent asks "what tools can I use right now?", the adapter does not just hand over its full catalog. It does this:

1. **Identify the agent.** Verify the caller is a registered, active AI agent with a managed connection that covers the resources the catalog touches. (Your work in Lab 2.)
2. **Identify the user.** Read the user's identity from the active sign-in to `TaskVantage Agent UI` — the app you linked in 2.6. No active sign-in, no further work.
3. **Resolve the user's effective scopes.** Ask Okta which scopes this user is permitted to request from `vantage-crm-as`. The answer comes from the auth server's access policy rules, which key off group membership.
4. **Map scopes to tools.** The adapter holds a static map of `tool → required scope`. It returns only the tools whose required scopes are in the user's effective set.

The agent never sees a tool that does not match the user. There is no client-side filtering. There is no "ask and be denied later." The adapter shapes the catalog before the agent ever sees it.

### 3.2 Review the access policy on vantage-crm-as

The access policy is what drives the entire filtering decision. Worth seeing it before you watch its consequences.

- From the Admin Console, go to **Security** > **API**.
- Click `vantage-crm-as`.
- Select the **Access Policies** tab.
- Click into the policy that applies to the AI agent client. Review the rules:

| Rule order | Rule name | If user is in group... | Granted scopes |
| --- | --- | --- | --- |
| 1 | Sales managers — full access | `Sales Management` | `crm.accounts.read`, `crm.accounts.write`, `crm.contacts.read`, `crm.opportunities.read`, `crm.opportunities.write` |
| 2 | Sales reps — read access | `Sales Reps` | `crm.accounts.read`, `crm.contacts.read`, `crm.opportunities.read` |
| 3 | IT help desk — limited read | `IT Help Desk` | `crm.accounts.read`, `crm.contacts.read` |
| 4 | Cross-functional readers — read access | `CRM Read - Cross-Functional` | `crm.accounts.read`, `crm.contacts.read`, `crm.opportunities.read` |
| Catch-all | Deny | (anyone else) | (none) |

*NOTE: Okta evaluates rules top to bottom and stops at the first match. Susan Potter is in `Sales Management`, so rule 1 matches and rules 2 onward are never considered for her. The catch-all is what makes Frank Boone see zero tools.*

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
Sign-in app: TaskVantage Agent UI (active session simulated)
Agent: TaskVantage Sales Agent (ACTIVE)

→ Calling MCP Adapter at https://mcp.{{lab_domain}}/tools
→ Adapter resolved effective scopes via vantage-crm-as:
    Matched rule 2 (Sales reps — read access):
      crm.accounts.read, crm.contacts.read, crm.opportunities.read

3 tools available to this user:
  ▸ crm.lookup_account       Look up a customer account by name or ID
  ▸ crm.lookup_contact       Look up a contact by name or email
  ▸ crm.lookup_opportunity   Look up an opportunity by name or stage

3 tools filtered out (scope not granted to this user):
  ✗ crm.create_account       requires crm.accounts.write
  ✗ crm.update_account       requires crm.accounts.write
  ✗ crm.update_opportunity   requires crm.opportunities.write

6 tools filtered out (resource not yet configured):
  ✗ itsm.lookup_ticket, itsm.create_ticket, itsm.update_ticket,
    itsm.lookup_incident, itsm.update_incident, itsm.search_kb
```

Alex's `Sales Reps` membership matched rule 2 — read access only. The agent on Alex's behalf can read but cannot write. The ITSM tools sit in the second filtered group because the adapter has nowhere to ask about them yet.

### 3.5 List tools as Susan Potter (Sales Manager)

- Run the script again, this time as Susan:

```bash
~/Desktop/list-agent-tools.sh --user susan.potter@atko.email
```

- Expected output:

```
Acting as: susan.potter@atko.email  (groups: Sales Management, All Employees)
Sign-in app: TaskVantage Agent UI (active session simulated)
Agent: TaskVantage Sales Agent (ACTIVE)

→ Calling MCP Adapter at https://mcp.{{lab_domain}}/tools
→ Adapter resolved effective scopes via vantage-crm-as:
    Matched rule 1 (Sales managers — full access):
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

Susan's `Sales Management` membership matched rule 1 — full access. Same agent, same script, double the tools. The agent did not change. The adapter responded to *who is asking*.

### 3.6 List tools as Frank Boone — see the catch-all in action

- One more run, this time as Frank:

```bash
~/Desktop/list-agent-tools.sh --user frank.boone@atko.email
```

- Expected output:

```
Acting as: frank.boone@atko.email  (groups: Engineering, All Employees)
Sign-in app: TaskVantage Agent UI (active session simulated)
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
| `app.oauth2.token.grant.access_token` | `TaskVantage Agent UI` | the user | The user-sign-in token the script simulated |
| `ai_agent.token_exchange.request` | `TaskVantage Sales Agent` | `vantage-crm-as` | The adapter asking Okta what this user can request |
| `ai_agent.token_exchange.scope_evaluation` | the access policy | the user | Which rule matched and which scopes were granted |
| `ai_agent.tool_catalog.return` | the adapter | the user | The filtered catalog the user received |

*NOTE: This is the audit-and-visibility half of the access model. Every filtering decision the adapter made is recorded against the user, the agent, and the rule that fired. Compliance teams can answer "what did our agent expose to Alex last Tuesday?" without any application-side instrumentation.*

---

**End of lab.** You have seen the adapter behave as the policy enforcement point: same agent, three users, three outcomes. The agent did not change between runs. What changed was Okta's answer to "what can this user do?", and the adapter respected that answer faithfully.

In Lab 4, two things happen. First, you build the missing half — `vantage-desk-as`, its scopes, its access policy, and the managed connection on the agent — using everything you reviewed and ran here as your reference. Second, you exercise a tool invocation end-to-end: the adapter does the XAA token exchange, hands a user-scoped access token to the MCP server, and the call lands on VantageCRM (or VantageDesk) as the user. Filtering is half the story. Module 4 is the other half.
