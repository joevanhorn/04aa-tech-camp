# Lab Module 4: Build VantageDesk and Watch XAA in Flight [Estimate: 60 minutes]

## Objective

Build the VantageDesk side of the camp end-to-end — authorization server, scopes, access policy, managed connection — using your work on VantageCRM as the template. The VantageDesk API itself already exists: it is part of the one central, multi-tenant deployment at `https://vantagedesk.taskvantage-demo.com`, shared by every attendee's org and reached only as an API. You don't stand it up or deploy anything app-side. Your job is the Okta side: build `vantage-desk-as` (a custom authorization server in *your* org) with the ITSM scopes and an access policy. Because enrollment is by org, the central app trusts your new auth server automatically via your org's JWKS — no app-side registration or redeploy. Then invoke a tool through the agent and watch the full XAA token exchange happen: the adapter requests an ID-JAG carrying both agent and user identity, swaps it for a scoped access token at `vantage-desk-as`, and the call lands on the central VantageDesk as the actual user. By the end of this lab, the two halves of TaskVantage are configured identically in your org and you have seen the protocol that makes the whole thing work.

## Scenario

It is later in 2026. The IT help desk team has been watching the Sales Agent succeed and wants the same treatment: their agent should be able to look up tickets, file incidents, and surface knowledge base articles on behalf of a help desk technician — but only what the technician themselves can do.

Today you build that. You start from the same agent you already registered (no new agent needed — agents can hold multiple managed connections), and you add VantageDesk to its repertoire. Then you put the whole chain through its paces with Kim Liu, who already has the IT help desk role.

## Browser use for this lab

- Local browser for the Okta Admin Console (the auth-server / access-policy build steps and Okta System Log inspection).
- Virtual Desktop for the terminal scripts that invoke tools, trace the protocol, and read the central app's access log.

---

### 4.1 What XAA actually does at the protocol level

XAA — Cross App Access — is the protocol your adapter has been quietly using when you ran Module 3's filtering script. It is not a single token exchange. It is **two** exchanges, with a special intermediate token called an **ID-JAG** (Identity Assertion JWT Authorization Grant).

| Step | At | Inputs | Output | What it means |
| --- | --- | --- | --- | --- |
| 1 | Okta org authorization server | Agent client assertion (signed JWT) + user subject token (identity assertion from the org) | ID-JAG (short-lived, ~5 minutes) | "Okta vouches that this agent is authorized to act for this user with these scopes." |
| 2 | Resource authorization server (e.g., `vantage-desk-as`) | ID-JAG + agent client assertion | Access token (Bearer, audience-scoped) | "Here is a normal Bearer token. Use it to call the resource as the user." |

The agent then presents the access token to the MCP server, which forwards to VantageDesk, which sees a request that carries the user's identity — not the agent's. Audit logs, row-level filtering, and any other user-context behavior in VantageDesk works exactly as if Kim had clicked the buttons herself.

Two things make XAA different from a vanilla OAuth on-behalf-of flow:

- **The IdP is the broker, not the resource.** ID-JAG is issued by your org's authorization server, where the policy lives, where the managed connections are defined, where the audit happens. The resource just validates a token it trusts.
- **Tokens are scoped per resource, not portable.** The access token at the end of step 2 is only valid for `vantage-desk-as`. The same ID-JAG can be exchanged again at `vantage-crm-as` for a different access token, scoped differently. The agent's identity-of-the-user is preserved; the capability is per-resource.

*NOTE: XAA's ID-JAG mechanism is defined in IETF draft `draft-ietf-oauth-identity-assertion-authz-grant`, co-authored by Aaron Parecki of Okta. The two-exchange pattern is the standardized shape of agent-to-resource access in the broader ecosystem.*

### 4.2 Review vantage-crm-as as your template

Before you build the missing half, take one minute to look at the completed half. Everything you create for VantageDesk has a parallel here.

- From the Admin Console, go to **Security** > **API**.
- Click `vantage-crm-as` and confirm the four building blocks:

| Building block | Where it lives | What it looks like for CRM |
| --- | --- | --- |
| Authorization server | Security > API | `vantage-crm-as`, audience `api://vantage-crm` |
| Scopes | Scopes tab | 5 scopes: `crm.accounts.read`, `crm.accounts.write`, `crm.contacts.read`, `crm.opportunities.read`, `crm.opportunities.write` |
| Access policy rules | Access Policies tab | 4 rules (Sales mgmt, Sales reps, IT help desk, catch-all) — reviewed in Lab 3.2 |
| Managed connection on the agent | Directory > AI Agents > TaskVantage Sales Agent > Managed connections | One entry pointing at `vantage-crm-as` with all scopes allowed |

You will create the same four building blocks for VantageDesk over the next four sections.

### 4.3 Create the vantage-desk-as authorization server

- From the Admin Console, go to **Security** > **API**.
- Click **Add Authorization Server**.
- Fill in:
  - **Name**: `vantage-desk-as`
  - **Audience**: `api://vantage-desk`
  - **Description**: `Custom authorization server for VantageDesk ITSM resources`
- Click **Save**.

The server appears in the list of authorization servers with status **Active**. By default it has no scopes and no access policies — both of which you will add in the next two steps.

*NOTE: The `Audience` value is the identifier the access token's `aud` claim will carry. The central VantageDesk API validates this audience on every request — it accepts the token only if `aud` is the constant lab value `api://vantage-desk`, and resolves which tenant (org) the call belongs to from the token's **issuer**. So the audience is the same for every attendee's org; what makes your token *yours* is the issuer. If the audience doesn't match, the call is rejected before any data is touched. `{HumanReview}` — confirm `api://vantage-desk` is the constant audience the central app validates.*

### 4.4 Add scopes to vantage-desk-as

The scopes mirror the action types VantageDesk exposes.

- On the `vantage-desk-as` page, select the **Scopes** tab.
- Click **Add Scope** and create each of the following:

| Name | Display name | Description |
| --- | --- | --- |
| `itsm.tickets.read` | Read tickets | Look up tickets and their current state |
| `itsm.tickets.write` | Write tickets | Create new tickets and update existing ones |
| `itsm.incidents.read` | Read incidents | Look up incidents and their current state |
| `itsm.incidents.write` | Write incidents | Update incident status, severity, and assignment |
| `itsm.kb.read` | Read knowledge base | Search and retrieve knowledge base articles |

Leave all other scope settings at their defaults. Save after each.

When done, the **Scopes** tab shows five scopes. These are the building blocks of every ITSM tool the adapter will gate.

### 4.5 Create the access policy rules

The access policy is what differentiates Kim (full ITSM access) from Alex (no ITSM access) when the adapter asks Okta "what can this user do at vantage-desk-as?"

- On the `vantage-desk-as` page, select the **Access Policies** tab.
- Click **Add Policy**.
- Fill in:
  - **Name**: `TaskVantage Sales Agent — Desk policy`
  - **Description**: `Policy governing how the Sales Agent can request scopes at vantage-desk-as`
  - **Assign to clients**: select `TaskVantage Sales Agent` from the list
- Click **Create Policy**.

Now add the rules. Click **Add Rule** for each:

**Rule 1 — IT help desk full access**

| Setting | Value |
| --- | --- |
| Rule name | `IT help desk — full access` |
| IF Grant type is | `Token Exchange` `{HumanReview}` — confirm this is the right grant-type selector for ID-JAG exchange |
| AND User is in group | `IT Help Desk` |
| THEN Allow scopes | `itsm.tickets.read`, `itsm.tickets.write`, `itsm.incidents.read`, `itsm.incidents.write`, `itsm.kb.read` |

**Rule 2 — Catch-all deny**

| Setting | Value |
| --- | --- |
| Rule name | `Catch-all deny` |
| IF Grant type is | `Token Exchange` |
| AND User is | (any) |
| THEN Allow scopes | (none) |

Save the policy.

*NOTE: This is intentionally narrower than the VantageCRM policy. Sales has no ITSM business by default — Frank Boone, an engineering director, doesn't either. In Lab 5, Frank will request ITSM access through OIG and you will see this exact catch-all start denying him until his entitlement bundle is approved.*

### 4.6 Connect the agent to VantageDesk

The auth server and policy exist. Now bind them to the agent.

- From the Admin Console, go to **Directory** > **AI Agents** > **TaskVantage Sales Agent**.
- Select the **Managed connections** tab. You will see your existing CRM connection from Lab 2.9.
- Click **Add connection**.
- In the Add connection dialog:
  - **Resource type**: select **Authorization server**.
  - **Authorization server**: select `vantage-desk-as` from the dropdown.
  - **Scopes**: select **Allow all** to grant the full scope set.
- Click **Add**.

The agent now shows two managed connections: one to `vantage-crm-as` (from Lab 2) and one to `vantage-desk-as` (just added). The agent's reach has doubled.

### 4.7 Re-list tools — see ITSM appear

Run the tool-listing script again as Kim Liu, who is in `IT Help Desk` and matches both rule 3 on CRM (limited read) and rule 1 on Desk (full access).

```bash
~/Desktop/list-agent-tools.sh --user kim.liu@atko.email
```

Expected output:

```
Acting as: kim.liu@atko.email  (groups: IT Help Desk, All Employees)
User identity asserted via: Okta org (subject token for XAA exchange)
Agent: TaskVantage Sales Agent (ACTIVE)

→ Calling MCP Adapter at https://mcp.{{lab_domain}}/tools
→ Adapter resolved effective scopes:
    From vantage-crm-as:  crm.accounts.read, crm.contacts.read
    From vantage-desk-as: itsm.tickets.read, itsm.tickets.write,
                          itsm.incidents.read, itsm.incidents.write,
                          itsm.kb.read

8 tools available to this user:
  ▸ crm.lookup_account       Look up a customer account by name or ID
  ▸ crm.lookup_contact       Look up a contact by name or email
  ▸ itsm.lookup_ticket       Look up a ticket by ID or queue
  ▸ itsm.create_ticket       Create a new support ticket
  ▸ itsm.update_ticket       Update an existing ticket
  ▸ itsm.lookup_incident     Look up an incident by ID
  ▸ itsm.update_incident     Update an incident's status or severity
  ▸ itsm.search_kb           Search the knowledge base

4 tools filtered out (scope not granted to this user):
  ✗ crm.create_account, crm.update_account,
    crm.lookup_opportunity, crm.update_opportunity

0 tools filtered out (resource not yet configured).
```

The "resource not yet configured" bucket is empty — every tool the adapter knows about is now gated against an authorization server. Compare this to Lab 3.4 where six ITSM tools sat in that bucket; your work in 4.3 through 4.6 cleared it.

### 4.8 Invoke a tool through the agent

Filtering is done. Time to actually call something.

```bash
~/Desktop/invoke-agent-tool.sh \
    --user kim.liu@atko.email \
    --tool itsm.lookup_ticket \
    --args '{"ticket_id":"TKT-1734"}'
```

Expected output:

```
Acting as: kim.liu@atko.email
Tool: itsm.lookup_ticket
Args: {"ticket_id":"TKT-1734"}

→ Adapter performing XAA token exchange (step 1 + step 2)
→ Adapter forwarding to the central MCP server at https://mcp.taskvantage-demo.com/mcp
→ MCP server routing to VantageDesk as kim.liu@atko.email
✓ Tool returned in 247 ms.

Result:
  Ticket: TKT-1734
  Subject: "Outlook calendar sync failing for Sales team"
  Status: In Progress
  Priority: P2
  Assignee: kim.liu@atko.email
  Requester: susan.potter@atko.email
  Created: 2026-04-22 09:14
  Updated: 2026-04-23 11:02
  Description: Multiple Sales team members reporting that calendar events
               created in Outlook aren't syncing to Google Workspace...
```

The agent did not just *describe* what calling a tool would look like. It actually called one. The result came back from the central VantageDesk, where the call was authenticated as Kim, scoped to `itsm.tickets.read`, resolved to your org's tenant partition by the token issuer, and audited against her identity.

### 4.9 Inspect XAA in flight (verbose mode)

Re-run the same invocation with `--verbose`. The script will now print every intermediate token so you can see the protocol with your own eyes.

```bash
~/Desktop/invoke-agent-tool.sh \
    --user kim.liu@atko.email \
    --tool itsm.lookup_ticket \
    --args '{"ticket_id":"TKT-1734"}' \
    --verbose
```

Output (decoded for readability):

```
[1] User subject token (identity assertion from your Okta org):
    {
      "iss": "https://{{org_url}}",
      "sub": "kim.liu@atko.email",
      "groups": ["IT Help Desk", "All Employees"],
      "exp": 1735200000
    }

[2] Agent client assertion (signed with agent's private key):
    {
      "iss": "TaskVantage Sales Agent client_id",
      "sub": "TaskVantage Sales Agent client_id",
      "aud": "https://{{org_url}}",
      "exp": 1735196700
    }

[3] Step 1 — POST https://{{org_url}}/oauth2/v1/token
    grant_type=urn:ietf:params:oauth:grant-type:token-exchange
    subject_token=<user subject token from step 1>
    actor_token=<agent client assertion from step 2>
    requested_token_type=urn:ietf:params:oauth:token-type:id-jag
    audience=api://vantage-desk
    scope=itsm.tickets.read

[4] ID-JAG issued (decoded):
    {
      "iss": "https://{{org_url}}",
      "aud": "vantage-desk-as",
      "sub": "kim.liu@atko.email",
      "client_id": "TaskVantage Sales Agent client_id",
      "scope": "itsm.tickets.read",
      "exp": 1735193700  // ~5 minutes from now
    }

[5] Step 2 — POST https://{{org_url}}/oauth2/vantage-desk-as/v1/token
    grant_type=urn:ietf:params:oauth:grant-type:jwt-bearer
    assertion=<ID-JAG from step 4>
    client_assertion=<agent client assertion>

[6] Access token issued (decoded):
    {
      "iss": "https://{{org_url}}/oauth2/vantage-desk-as",
      "aud": "api://vantage-desk",
      "sub": "kim.liu@atko.email",
      "scope": "itsm.tickets.read",
      "exp": 1735196700
    }

[7] Tool invocation — adapter → central MCP server:
    POST https://mcp.taskvantage-demo.com/mcp  (tools/call: itsm.lookup_ticket)
    Authorization: Bearer <access token from step 6>
    Body: {"ticket_id":"TKT-1734"}

✓ Result returned (see standard output).
```

`{HumanReview}` — the exact `grant_type` URIs, token URLs, and claim names should be confirmed against current Okta XAA implementation. The shape (two POST requests, ID-JAG in between) is set by the IETF spec, but Okta-specific endpoints and parameter names may differ slightly.

Walk through what you see:
- **Sub claim stays put.** `kim.liu@atko.email` appears in the user subject token (step 1), the ID-JAG (step 4), and the final access token (step 6). The user's identity is preserved end-to-end.
- **Audience narrows.** The ID-JAG's audience is `vantage-desk-as`. The access token's audience is the constant lab value `api://vantage-desk` — the same for every attendee's org; the central app tells tenants apart by issuer, not audience. Each step scopes the token further toward its eventual use.
- **Scope narrows.** Kim is allowed five Desk scopes per the policy. Only `itsm.tickets.read` was requested for this specific tool — that's the only scope in the ID-JAG and access token. Least-privilege by construction.

### 4.10 Verify the request landed as the user

The central VantageDesk is API-only — there is no admin web page to open. Instead, read the access log out-of-band: the central app exposes `GET /admin/access-log`, scoped to *your* tenant (the app picks the partition from your token's issuer), so you only ever see your own org's records. Run the read script on the Virtual Desktop:

```bash
~/Desktop/show-access-log.sh --user kim.liu@atko.email --filter TKT-1734
```

It calls `GET https://vantagedesk.taskvantage-demo.com/admin/access-log` with your tenant-scoped token and prints the matching line:

```
2026-04-23 11:24:08  GET  /api/tickets/TKT-1734
  Bearer subject:    kim.liu@atko.email
  Client:            TaskVantage Sales Agent
  Audience:          api://vantage-desk
  Scopes:            itsm.tickets.read
  Source:            mcp.taskvantage-demo.com (shared MCP server)
```

*(If your environment serves this step as a rendered screenshot instead of a live script, the captured access-log line is identical — same fields, same values.)*

The `Client` field reads `TaskVantage Sales Agent`, not a raw client ID: the central app resolves the token's `cid` to a display name via its `AGENT_CID_NAME_MAP`. The request hit VantageDesk as Kim — the agent appears in the `Client` field, full attribution preserved, but the *actor* is Kim. If you wanted to know who was looking at TKT-1734 from Kim's perspective in VantageDesk, this log line is your answer. The agent's involvement is a fact, not a substitute for the user.

---

**End of lab.** VantageDesk now matches VantageCRM end-to-end: authorization server, scopes, access policy, managed connection. You watched the protocol that makes user-scoped agent access possible — ID-JAG, two-step exchange, audience and scope narrowing on each hop. And you saw the consequence at the backend: a request that carries the user's identity, not the agent's.

One module remains. Lab 5 introduces OIG — access requests, certification campaigns, time-bound elevations, and the kill switch. You will watch Frank Boone request CRM access, get it approved, see the same tool-listing script start returning real tools for him, and then watch the access expire and the tools disappear again.
