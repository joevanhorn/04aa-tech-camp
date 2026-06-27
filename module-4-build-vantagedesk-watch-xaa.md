# Lab Module 4: Build VantageDesk and Watch XAA in Flight [Estimate: 60 minutes]

## Objective

By the end of this lab the two halves of TaskVantage are configured identically in your org, and you will have watched the XAA protocol carry both agent and user identity all the way to the app. You build the entire VantageDesk side — authorization server, scopes, access policy, managed connection, and the matching MCP Adapter resource — using your VantageCRM work as the template. (The VantageDesk API already exists in the shared central deployment at `https://vantagedesk.taskvantage-demo.com`; you build only the Okta side — your org's new auth server is trusted automatically via JWKS, with no app-side registration or redeploy.)

- Create `vantage-desk-as`, a custom authorization server in your org, and add the ITSM scopes
- Build the access policy rules mapping the help desk group to those scopes
- Connect the agent you already registered to VantageDesk (managed connection) and add its MCP Adapter resource
- Re-list the agent's tools and see the ITSM tools appear
- Invoke a tool as Kim Liu and trace the two-step XAA exchange — ID-JAG → scoped token at `vantage-desk-as` → the call landing on the central VantageDesk as Kim herself

## Scenario

It is later in 2026. The IT help desk team has been watching the Sales Agent succeed and wants the same treatment: their agent should be able to look up tickets, file incidents, and surface knowledge base articles on behalf of a help desk technician — but only what the technician themselves can do.

Today you build that. You start from the same agent you already registered (no new agent needed — agents can hold multiple managed connections), and you add VantageDesk to its repertoire. Then you put the whole chain through its paces with Kim Liu, who already has the IT help desk role.

## Browser use for this lab

- Local browser for the Okta Admin Console (the auth-server / access-policy build steps and Okta System Log inspection).
- Virtual Desktop for the **Lab Toolkit**, which invokes tools, traces the protocol, and reads the central app's access log.

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
| Managed connection on the agent | Directory > AI Agents > TaskVantage Sales Agent > Managed connections | One entry pointing at `vantage-crm-as`, **Only allow** with the five granular CRM scopes |
| Adapter resource | Adapter admin console (Lab 2.10) | One resource for `vantage-crm-as`, URL `…/crm/mcp`, auth `okta-cross-app` |

You will create the same building blocks for VantageDesk over the next sections — the four Okta pieces, then the adapter resource that brings them online.

### 4.3 Create the vantage-desk-as authorization server

- From the Admin Console, go to **Security** > **API**.
- Click **Add Authorization Server**.
- Fill in:
  - **Name**: `vantage-desk-as`
  - **Audience**: `api://vantage-desk`
  - **Description**: `Custom authorization server for VantageDesk ITSM resources`
- Click **Save**.

The server appears in the list of authorization servers with status **Active**. By default it has no scopes and no access policies — both of which you will add in the next two steps.

*NOTE: The `Audience` value is the identifier the access token's `aud` claim will carry. The central VantageDesk API validates this audience on every request — it accepts the token only if `aud` is the constant lab value `api://vantage-desk`, and resolves which tenant (org) the call belongs to from the token's **issuer**. So the audience is the same for every attendee's org; what makes your token *yours* is the issuer. If the audience doesn't match, the call is rejected before any data is touched.*

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

*NOTE: The assigned client must be the **AI agent itself** (`TaskVantage Sales Agent`), not its user-sign-on app. During XAA the adapter authenticates to this auth server **as the agent** (via `private_key_jwt` with the agent's credential), so the agent principal is the client Okta evaluates. If only the sign-on app were assigned, the exchange would fail with `no_matching_policy`.*

Now add the rules. Click **Add Rule** for each:

**Rule 1 — IT help desk full access**

| Setting | Value |
| --- | --- |
| Rule name | `IT help desk — full access` |
| IF Grant type is | `Token Exchange` |
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

**Why this mattered:** The auth server and its policy are the **"what the _user_ may do"** term of the access intersection — the place Okta decides which scopes each person can borrow at VantageDesk. Building it by hand is setting up the rooms of the agent's second desk before you hand over any keys.

### 4.6 Connect the agent to VantageDesk

The auth server and policy exist. Now bind them to the agent.

- From the Admin Console, go to **Directory** > **AI Agents** > **TaskVantage Sales Agent**.
- Select the **Managed connections** tab. You will see your existing CRM connection from Lab 2.9.
- Click **Add connection**.
- In the Add connection dialog:
  - **Resource type**: select **Authorization server**.
  - **Authorization server**: select `vantage-desk-as` from the dropdown.
  - **Scopes**: select **Only allow**, and add the granular ITSM scope set: `itsm.tickets.read`, `itsm.tickets.write`, `itsm.incidents.read`, `itsm.incidents.write`, `itsm.kb.read`. (Not "Allow all" — see the Lab 2.9 note: "Allow all" makes the adapter request a generic `mcp:read` scope this auth server doesn't define, and the XAA exchange fails.)
- Click **Add**.

The agent now shows two managed connections: one to `vantage-crm-as` (from Lab 2) and one to `vantage-desk-as` (just added). The agent's reach has doubled.

**Why this mattered:** This is the **"what the agent may do"** term — the agent's own grant, the second key on its ring. The new hire now holds a badge for one more desk, but only the scopes you explicitly allowed here.

### 4.7 Re-sync the adapter and add the VantageDesk resource

The Okta side now knows your agent may reach VantageDesk — but your **MCP Adapter** doesn't yet. It caches managed connections, and it routes each backend audience through its own **resource**. In Lab 2.10 the setup helper wired your CRM resource for you; now you do the same wiring **by hand** for VantageDesk — the same steps the helper ran for CRM, in your own clicks. This is the step that makes the ITSM tools appear in 4.8.

Open the adapter admin console at `https://{{adapter_admin_host}}`.

- **Re-sync.** On `TaskVantage Sales Agent`, click **Sync** (or **Sync connections**). The adapter re-reads your managed connections and picks up the new `vantage-desk-as` connection, materializing it as a second **resource**. (If the sync doesn't auto-create the resource, add it by hand pointing at the `vantage-desk-as` authorization server.)
- **Point it at the Desk path.** Open the new resource and set its **MCP server URL** to your central MCP server's **Desk path**: `https://{{mcp_host}}/desk/mcp`. Leave the auth method as **okta-cross-app**. **Enable** the resource.

Your adapter now has **two** resources for one agent: the CRM resource at `/crm/mcp` (Lab 2.10) and the Desk resource at `/desk/mcp` (just added). Each mints its own audience-scoped token — `api://vantage-crm` for CRM tools, `api://vantage-desk` for ITSM tools — and routes to the matching tool subset on the one shared MCP server.

**Why this mattered:** Doing the wiring the Lab 2.10 helper had done for CRM is what it means to give the agent its second desk *yourself* — the resource is the live bridge between the agent's grant and the **"what the resource exposes"** term, the last piece before the ITSM tools can actually appear.

*NOTE: One adapter resource maps to exactly one managed connection and one audience. That's why VantageDesk needs its own resource rather than joining the CRM one: a single resource could only ever mint one audience's token, and VantageDesk rejects a CRM-audience token (and vice versa). The `/crm/mcp` and `/desk/mcp` paths exist so each resource is handed only the tools its token is valid for. If the adapter is ever restarted, re-run this sync — a freshly hydrated resource can lose its granular scopes and fall back to `mcp:read`, which `vantage-desk-as` doesn't define.*

### 4.8 Re-list tools — see ITSM appear

List the agent's tools again as Kim Liu, who is in `IT Help Desk` and matches both rule 3 on CRM and rule 1 on Desk. Because access is binary today, matching a CRM rule authorizes the full CRM tool set and matching the Desk rule authorizes the full Desk tool set — so Okta authorizes Kim for all twelve.

- Open the **Lab Toolkit** and choose **4) List the agent's tools**, then select **Kim Liu (IT Help Desk)** when prompted for a persona.

Expected output:

```
== The agent's tools - and what Okta lets Kim Liu (IT Help Desk) use ==
   The agent exposes 12 tools - every user SEES the full catalog.
   With Kim Liu (IT Help Desk)'s entitlements, Okta authorizes 12 of 12:
     [USABLE]  {{crm_as_id}}__crm.lookup_account
     [USABLE]  {{crm_as_id}}__crm.create_account
     [USABLE]  {{crm_as_id}}__crm.update_account
     [USABLE]  {{crm_as_id}}__crm.lookup_contact
     [USABLE]  {{crm_as_id}}__crm.lookup_opportunity
     [USABLE]  {{crm_as_id}}__crm.update_opportunity
     [USABLE]  {{desk_as_id}}__itsm.lookup_ticket
     [USABLE]  {{desk_as_id}}__itsm.create_ticket
     [USABLE]  {{desk_as_id}}__itsm.update_ticket
     [USABLE]  {{desk_as_id}}__itsm.lookup_incident
     [USABLE]  {{desk_as_id}}__itsm.update_incident
     [USABLE]  {{desk_as_id}}__itsm.search_kb
```

Before you built VantageDesk, the catalog held only the six CRM tools — there was no Desk resource for the adapter to expose. Wiring `vantage-desk-as` and its resource in 4.3–4.7 added the six ITSM tools to the catalog **for everyone**, and because Kim is a member of both the CRM and Desk groups, Okta authorizes her for all twelve. (As in Module 3, authorization is binary today: a member of a resource's group can use that resource's full tool set; a non-member sees the same tools but Okta won't authorize them. A graduated manager-vs-rep tool subset is a future model — see `lab-infra/README.md`. Data-level differences still apply: VantageCRM row-filters Kim's CRM results to what her role can see.)

### 4.9 Invoke a tool through the agent

Filtering is done. Time to actually call something.

- Open the **Lab Toolkit** and choose **5) Invoke a tool**, then select **Kim Liu (IT Help Desk)** when prompted for a persona. Invoke `itsm.lookup_ticket` for ticket `TKT-1734`.

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

**Why this mattered:** This is the intersection resolving to a single real call: the agent acted, but **as Kim**, bounded by what Kim may do. The action is attributable to both — which agent, on whose authority — exactly the property the API-key model can never give you.

### 4.10 Inspect XAA in flight (verbose mode)

Run the same invocation again, this time asking the toolkit to show the token exchange. It will now print every intermediate token so you can see the protocol with your own eyes.

- In the **Lab Toolkit**, choose **5) Invoke a tool** again, select **Kim Liu (IT Help Desk)**, and invoke `itsm.lookup_ticket` for ticket `TKT-1734`. When it asks **"Show the XAA token exchange? (y/N)"**, answer **y**.

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

*The shape here — two POST requests with an ID-JAG in between — is the IETF Cross-App Access pattern; the exact `grant_type` URIs, token endpoints, and claim names follow Okta's XAA implementation.*

Walk through what you see:
- **Sub claim stays put.** `kim.liu@atko.email` appears in the user subject token (step 1), the ID-JAG (step 4), and the final access token (step 6). The user's identity is preserved end-to-end.
- **Audience narrows.** The ID-JAG's audience is `vantage-desk-as`. The access token's audience is the constant lab value `api://vantage-desk` — the same for every attendee's org; the central app tells tenants apart by issuer, not audience. Each step scopes the token further toward its eventual use.
- **Scope narrows.** Kim is allowed five Desk scopes per the policy. Only `itsm.tickets.read` was requested for this specific tool — that's the only scope in the ID-JAG and access token. Least-privilege by construction.

**Why this mattered:** The two-step ID-JAG exchange is what carries *both* identities to the app at once — the user in `sub`, the agent in `client_id` — so the call lands "as the user" yet stays attributable to both. That dual carriage is the `act` chain from the intro: "which agent, on whose authority," made concrete in the token claims.

### 4.11 Verify the request landed as the user

The central VantageDesk is API-only — there is no admin web page to open. Instead, read the access log out-of-band: the central app exposes `GET /admin/access-log`, scoped to *your* tenant (the app picks the partition from your token's issuer), so you only ever see your own org's records. Read it from the **Lab Toolkit** on the Virtual Desktop:

- Open the **Lab Toolkit** and choose **6) Show the access log**, then look for the entry for `TKT-1734`.

It calls `GET https://vantagedesk.taskvantage-demo.com/admin/access-log` with your tenant-scoped token and prints the matching line:

```
2026-04-23 11:24:08  GET  /api/tickets/TKT-1734
  Bearer subject:    kim.liu@atko.email
  Client:            TaskVantage Sales Agent
  Audience:          api://vantage-desk
  Scopes:            itsm.tickets.read
  Source:            mcp.taskvantage-demo.com (shared MCP server)
```

*(If your environment serves this step as a rendered screenshot instead of the live Lab Toolkit, the captured access-log line is identical — same fields, same values.)*

The `Client` field reads `TaskVantage Sales Agent`, not a raw client ID: the central app resolves the token's `cid` to a display name via its `AGENT_CID_NAME_MAP`. The request hit VantageDesk as Kim — the agent appears in the `Client` field, full attribution preserved, but the *actor* is Kim. If you wanted to know who was looking at TKT-1734 from Kim's perspective in VantageDesk, this log line is your answer. The agent's involvement is a fact, not a substitute for the user.

---

**End of lab.** VantageDesk now matches VantageCRM end-to-end: authorization server, scopes, access policy, managed connection, and an MCP Adapter resource at `/desk/mcp`. You watched the protocol that makes user-scoped agent access possible — ID-JAG, two-step exchange, audience and scope narrowing on each hop. And you saw the consequence at the backend: a request that carries the user's identity, not the agent's.

One module remains. Lab 5 introduces OIG — access requests, certification campaigns, time-bound elevations, and the kill switch. You will watch Frank Boone request CRM access, get it approved, see the same tool-listing script start returning real tools for him, and then watch the access expire and the tools disappear again.
