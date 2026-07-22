# Lab Module 3: First Day on the Job - See Okta Govern the Agent's Tools by User [Estimate: 30 minutes]

## Objective

Run the same agent you registered in Lab 2 as three different users, and watch Okta govern which of its tools each user may use. Enforcement happens when a tool is invoked, not by hiding the menu. Every user sees the **full** catalog; what changes per user is whether Okta will issue a token to run a tool.

In this lab you will:

- Review the access policy and tool-to-scope mapping on **vantage-crm-as**.
- List the agent's full CRM tool catalog as Alex Martinez (sales rep) and Susan Potter (sales manager), and see Okta authorize all six tools for each.
- List the same catalog as Frank Boone (engineering director), and see all six tools blocked, because Okta authorizes none for him.
- Inspect the Okta System Log audit trail that records each authorized and denied attempt.

<details>
<summary><b>Context: the scenario (read once)</b></summary>

- The TaskVantage Sales Agent is registered, owned, and connected. The sales team asks: "If anyone in the company can sign in and talk to this agent, what stops the wrong person from getting account data they shouldn't see?"
- You answer by running the same agent request as three users. Only the user changes between runs; nothing is reconfigured.
- Every user (Susan, Alex, Frank) sees the **same** six-tool CRM catalog. Tool visibility is a property of the agent, not the user.
- Susan (sales manager) and Alex (sales rep) are both in a CRM group that vantage-crm-as grants access to, so Okta authorizes all six tools for each.
- Frank (engineering director, no CRM relationship) is in no CRM group, so Okta authorizes none. He sees all six tools but is blocked from using any.
</details>

> **Okta hides nothing; it governs at use-time.** Every user sees the full tool catalog. What differs is whether Okta will issue that user a token when they invoke a tool. Access today is binary: membership in any vantage-crm-as policy group authorizes the **full** crm.* tool set; a non-member is authorized for **none** (they still see all six, but every invocation is denied: "Authentication failed for resource"). Authorized users still see different data: VantageCRM row-filters results by the caller's sub and groups (Module 1.5), so a rep sees fewer accounts than a manager.

**Browser use for this lab:**

- **Local browser** for the Okta Admin Console (review and audit steps).
- **Virtual Desktop** for the **Lab Toolkit**, which simulates the agent's tool-listing call.

---

### 3.1 How the adapter exposes the catalog and Okta governs use

<details>
<summary><b>Context: how the adapter exposes tools and governs use (read once)</b></summary>

The MCP Adapter is the policy enforcement point between the agent and the resources behind it, and it enforces at **use-time**, not at list-time. Two distinct things happen.

**Listing tools (visibility is resource-based, not user-based).** When the agent asks "what tools are available?", the adapter returns the agent's **full** catalog: every tool registered for the resources the agent is connected to. This list is the same for every user. Alex, Susan, Kim, and Frank all see the same six CRM tools. The adapter does not trim the menu per user.

**Invoking a tool (Okta authorizes at the token exchange).** When a user invokes a tool, the adapter performs the Okta ID-JAG / XAA token exchange for that user against the tool's resource auth server (vantage-crm-as). At that moment it:

1. Verifies the caller is a registered, active AI agent with a managed connection that covers the resource (your work in Lab 2).
2. Reads the user's identity from the user-context token the agent presents.
3. Requests a user-scoped token from vantage-crm-as. Okta evaluates the access policy rules, which key off group membership. Match a rule and **Okta issues the token**: the tool call proceeds. Match none and **Okta issues no token**: the action is denied with "Authentication failed for resource."

Today every CRM rule grants the **same full crm.* scope set**, so authorization is effectively binary: match any rule and you can use all six CRM tools; match none and you can use none. Both see all six in the catalog.
</details>

<details>
<summary>Why not a graduated tool subset per group?</summary>

In principle the policy could grant a rep fewer scopes than a manager. The lab does not do this yet: the adapter requests the managed connection's full INCLUDE_ONLY scope set for every user, so a narrower per-group rule denies that user entirely (Okta returns no_matching_policy) instead of authorizing a smaller subset. Authorization stays 0-or-all. Tracked in lab-infra/README.md.
</details>

> **NOTE: the honest governance story.** A user can see tools they are not allowed to use. Okta does not hide the menu; it refuses to authorize the action at invocation. Enforcement happens at the point of action, against the live policy, and every denial is audited.

### 3.2 Review the access policy on vantage-crm-as

<details>
<summary><b>Why this matters</b></summary>

- The access policy drives the entire authorization decision: whether Okta will issue a user a token when they invoke a tool.
- See it before you watch its consequences in 3.4 through 3.6.
</details>

1. From the Admin Console, go to **Security** > **API**.
2. Click **vantage-crm-as**.
3. Select the **Access Policies** tab.
4. Click into the policy that applies to the AI agent client.
5. Review the rules:

| Rule order | Rule name | If user is in group... | Granted scopes |
| --- | --- | --- | --- |
| 1 | Sales managers — full access | **Sales Management** | full **crm.\*** set |
| 2 | Sales reps — access | **Sales Reps** | full **crm.\*** set |
| 3 | IT help desk — access | **IT Help Desk** | full **crm.\*** set |
| 4 | Cross-functional readers — access | **CRM Read - Cross-Functional** | full **crm.\*** set |
| Catch-all | Deny | (anyone else) | (none) |

where the **full crm.* set** is **crm.accounts.read**, **crm.accounts.write**, **crm.contacts.read**, **crm.opportunities.read**, **crm.opportunities.write**.

**What just changed:** you've seen the four group-to-scope rules and the catch-all that will deny Frank.

*NOTE: Okta evaluates rules top to bottom and stops at the first match. Because every CRM rule grants the same full scope set (the binary model, see 3.1), any match authorizes all six tools regardless of which rule fired. The catch-all is what fails Frank Boone: he sees all six tools, but Okta issues him no token, so every invocation is denied.*

*NOTE: Rule 4 gates the **CRM Read - Cross-Functional** group, which is empty right now, so no user matches rule 4. It is populated only via OIG access requests in Lab 5, where Frank is added temporarily and his tools flip from blocked to usable and back. The rule exists today; the membership is the dynamic part.*

### 3.3 Review the tool catalog and scope mapping

The adapter knows about six CRM tools. Every user sees all six: the catalog is the agent's full capability set, independent of who is asking. The scope below is what Okta must authorize at invoke-time: when a user runs a tool, Okta must issue a token for the matching scope on vantage-crm-as, or the call is denied.

| Tool | Scope Okta must authorize at invoke-time |
| --- | --- |
| **crm.lookup_account** | **crm.accounts.read** |
| **crm.create_account** | **crm.accounts.write** |
| **crm.update_account** | **crm.accounts.write** |
| **crm.lookup_contact** | **crm.contacts.read** |
| **crm.lookup_opportunity** | **crm.opportunities.read** |
| **crm.update_opportunity** | **crm.opportunities.write** |

*NOTE: The agent also has six VantageDesk tools, but they aren't wired in this build. vantage-desk-as doesn't exist yet, so the adapter has no resource to exchange a token against. Desk tools show nothing ("resource not configured") until you build the auth server in Lab 4.*

### 3.4 List tools as Alex Martinez (Sales Rep)

<details>
<summary><b>Why this matters</b></summary>

- The tools turn **[USABLE]** not because the agent has CRM rights, but because *Alex* does: the agent borrows the keys Alex already carries.
- Effective access is the intersection of what the agent can do and what the user may do. Here the user side is populated, so the door opens.
</details>

1. Open the **Lab Toolkit** (desktop icon).
2. Choose **4) List the agent's tools**.
3. Select **Alex Martinez (Sales Rep)** when prompted for a persona.

Expected output (the decoded-token and Raw-HTTP panels print first: the real adapter token Okta issued, not a label):

```
== The agent's tools - and what Okta lets Alex Martinez use ==
   --- Adapter token Okta issued to Alex Martinez (decoded JWT) ---
     sub : alex.martinez@atko.email
     aud : api://{{adapter_audience}}
     scp : openid offline_access
     cid : {{adapter_dcr_client_id}}
     iss : https://{{idp.tenantDomain}}
     iat : 1745405048  (2026-04-23 11:24:08 UTC)
     exp : 1745408648  (2026-04-23 12:24:08 UTC)
   --- Raw HTTP + Okta correlation id ---
     GET  https://{{adapter_admin_host}}/oauth/authorize?...
          x-okta-request-id: {{authorize_request_id}}
     POST https://{{adapter_admin_host}}/oauth2/v1/token   -> HTTP 200
          x-okta-request-id: {{token_request_id}}
   The agent exposes 6 tools - every user SEES the full catalog.
   With Alex Martinez's entitlements, Okta authorizes 6 of 6:
     [USABLE]  {{bc64c69c-9d90-4e3a-bdaa-f27b28b659af.authServerIds.0}}__crm.lookup_account
     [USABLE]  {{bc64c69c-9d90-4e3a-bdaa-f27b28b659af.authServerIds.0}}__crm.create_account
     [USABLE]  {{bc64c69c-9d90-4e3a-bdaa-f27b28b659af.authServerIds.0}}__crm.update_account
     [USABLE]  {{bc64c69c-9d90-4e3a-bdaa-f27b28b659af.authServerIds.0}}__crm.lookup_contact
     [USABLE]  {{bc64c69c-9d90-4e3a-bdaa-f27b28b659af.authServerIds.0}}__crm.lookup_opportunity
     [USABLE]  {{bc64c69c-9d90-4e3a-bdaa-f27b28b659af.authServerIds.0}}__crm.update_opportunity
   ^ USABLE = Okta will issue Alex Martinez a token for this resource, so the action is authorized.
```

*NOTE: The `sub` is the persona; the `iat`/`exp` epoch values and `x-okta-request-id` strings are illustrative: yours will differ each run. The two request-ids are the live correlation threads into the Okta System Log (§3.7). The token shown is the adapter token Okta minted for Alex's brokered login; the per-tool `[USABLE]`/`[BLOCKED]` decision below comes from Okta actually attempting the CRM token exchange for each tool.*

<details>
<summary>Reading the output</summary>

- Alex's Sales Reps membership matched a rule on vantage-crm-as, so Okta authorizes the full CRM tool set (authorization is binary today: member = all CRM tools usable).
- He sees all six because every user sees the full catalog; [USABLE] means Okta will issue him a token for that tool.
- What differs from a manager is the **data**: when Alex calls crm.lookup_account, VantageCRM row-filters results to the accounts he owns (Module 1.5).
- Tool names are namespaced authServerId__crm.*; Desk tools aren't wired in this build, so they don't appear.
</details>

**What just changed:** Okta authorized all six CRM tools for Alex; the data each returns stays filtered to the accounts he owns.

### 3.5 List tools as Susan Potter (Sales Manager)

<details>
<summary><b>Why this matters</b></summary>

- Same agent, same catalog, two different users: the authorization tracks the *user*, not the agent.
- The agent is one key ring serving whoever it acts for; Susan and Alex each get in on their own authority.
</details>

1. In the **Lab Toolkit**, choose **4) List the agent's tools** again.
2. Select **Susan Potter (Sales Manager)**.

Expected output:

```
== The agent's tools - and what Okta lets Susan Potter use ==
   --- Adapter token Okta issued to Susan Potter (decoded JWT) ---
     sub : susan.potter@atko.email
     aud : api://{{adapter_audience}}
     scp : openid offline_access
     cid : {{adapter_dcr_client_id}}
     iss : https://{{idp.tenantDomain}}
     iat : 1745405121  (2026-04-23 11:25:21 UTC)
     exp : 1745408721  (2026-04-23 12:25:21 UTC)
   --- Raw HTTP + Okta correlation id ---
     GET  https://{{adapter_admin_host}}/oauth/authorize?...
          x-okta-request-id: {{authorize_request_id}}
     POST https://{{adapter_admin_host}}/oauth2/v1/token   -> HTTP 200
          x-okta-request-id: {{token_request_id}}
   The agent exposes 6 tools - every user SEES the full catalog.
   With Susan Potter's entitlements, Okta authorizes 6 of 6:
     [USABLE]  {{bc64c69c-9d90-4e3a-bdaa-f27b28b659af.authServerIds.0}}__crm.lookup_account
     [USABLE]  {{bc64c69c-9d90-4e3a-bdaa-f27b28b659af.authServerIds.0}}__crm.create_account
     [USABLE]  {{bc64c69c-9d90-4e3a-bdaa-f27b28b659af.authServerIds.0}}__crm.update_account
     [USABLE]  {{bc64c69c-9d90-4e3a-bdaa-f27b28b659af.authServerIds.0}}__crm.lookup_contact
     [USABLE]  {{bc64c69c-9d90-4e3a-bdaa-f27b28b659af.authServerIds.0}}__crm.lookup_opportunity
     [USABLE]  {{bc64c69c-9d90-4e3a-bdaa-f27b28b659af.authServerIds.0}}__crm.update_opportunity
   ^ USABLE = Okta will issue Susan Potter a token for this resource, so the action is authorized.
```

<details>
<summary>Reading the output</summary>

- Susan's Sales Management membership matched a CRM rule, so Okta authorizes all six.
- Susan and Alex see the **same six tools** and Okta authorizes the **same six** for both: authorization is binary today, and both are CRM group members.
- They diverge in the **data** each tool returns: Susan sees all accounts; Alex sees only his own (Module 1.5).
- The agent did not change. Okta decided member-vs-non-member at the token exchange; VantageCRM then differentiated the two members by row-level filtering.
</details>

**What just changed:** Okta authorized the same six tools for Susan as for Alex; only the data each sees differs.

*NOTE: A future graduated model would also differentiate Susan and Alex at the tool level (e.g. Okta would not authorize create/update tools for Alex: they'd show [BLOCKED]). That isn't wired today, see the binary-authorization note in 3.1.*

### 3.6 List tools as Frank Boone: see the catch-all in action

<details>
<summary><b>Why this matters</b></summary>

- This is the intersection made concrete: the agent has the tools, but Frank's authority is empty, so the agent can do nothing *for him* that he couldn't do himself.
- The menu isn't hidden; his badge just won't open the door.
- This is exactly why a service app with its own API key would have been dangerous: that model drops the user, so it would have let Frank through. You cannot escalate through this agent.
</details>

1. In the **Lab Toolkit**, choose **4) List the agent's tools** one more time.
2. Select **Frank Boone (Engineering)**.

Expected output:

```
== The agent's tools - and what Okta lets Frank Boone use ==
   --- Adapter token Okta issued to Frank Boone (decoded JWT) ---
     sub : frank.boone@atko.email
     aud : api://{{adapter_audience}}
     scp : openid offline_access
     cid : {{adapter_dcr_client_id}}
     iss : https://{{idp.tenantDomain}}
     iat : 1745405194  (2026-04-23 11:26:34 UTC)
     exp : 1745408794  (2026-04-23 12:26:34 UTC)
   --- Raw HTTP + Okta correlation id ---
     GET  https://{{adapter_admin_host}}/oauth/authorize?...
          x-okta-request-id: {{authorize_request_id}}
     POST https://{{adapter_admin_host}}/oauth2/v1/token   -> HTTP 200
          x-okta-request-id: {{token_request_id}}
   The agent exposes 6 tools - every user SEES the full catalog.
   With Frank Boone's entitlements, Okta authorizes 0 of 6:
     [BLOCKED] {{bc64c69c-9d90-4e3a-bdaa-f27b28b659af.authServerIds.0}}__crm.lookup_account
     [BLOCKED] {{bc64c69c-9d90-4e3a-bdaa-f27b28b659af.authServerIds.0}}__crm.create_account
     [BLOCKED] {{bc64c69c-9d90-4e3a-bdaa-f27b28b659af.authServerIds.0}}__crm.update_account
     [BLOCKED] {{bc64c69c-9d90-4e3a-bdaa-f27b28b659af.authServerIds.0}}__crm.lookup_contact
     [BLOCKED] {{bc64c69c-9d90-4e3a-bdaa-f27b28b659af.authServerIds.0}}__crm.lookup_opportunity
     [BLOCKED] {{bc64c69c-9d90-4e3a-bdaa-f27b28b659af.authServerIds.0}}__crm.update_opportunity
   ^ BLOCKED = the agent HAS the tool, but Okta won't issue Frank Boone a token for that resource, so the action is denied at use-time.
```

<details>
<summary>Reading the output</summary>

- Frank sees the **same six tools** Alex and Susan saw: the catalog is the agent's, not the user's.
- Frank is in Engineering, a group with no rule on vantage-crm-as. When he tries to use any tool, the catch-all denies, Okta issues no token, and the action fails.
- He has the full menu in front of him and can't run a single item.
</details>

**What just changed:** Frank sees all six tools and Okta denies every one; no scoped CRM token is minted for him.

> **NOTE: Frank sees 6, can use 0.** Okta does not hide the tools from Frank. It lets him see exactly what the agent can do, and refuses to authorize any of it. That is governance at the moment of action, not a trimmed-down menu.

**See the denial at invoke-time:**

1. In the **Lab Toolkit**, choose **5) Invoke a tool**.
2. Select **Frank Boone (Engineering)**.
3. Invoke **crm.lookup_account**.

Frank is a valid user, so the adapter still mints him an adapter token and the token/HTTP/XAA panels print exactly as they did for the list. The refusal happens one hop later, when the adapter tries to exchange that token for a **scoped CRM token** at vantage-crm-as and Okta's catch-all denies it. The denial surfaces at the tool call, verbatim from Okta:

```
== Invoke a tool as Frank Boone (Engineering) ==
   --- Adapter token Okta issued to Frank Boone (Engineering) (decoded JWT) ---
     sub : frank.boone@atko.email
     aud : api://{{adapter_audience}}
     scp : openid offline_access
     ...
   --- Raw HTTP + Okta correlation id ---
     GET  https://{{adapter_admin_host}}/oauth/authorize?...
          x-okta-request-id: {{authorize_request_id}}
     POST https://{{adapter_admin_host}}/oauth2/v1/token   -> HTTP 200
          x-okta-request-id: {{token_request_id}}
   --- XAA exchange trace: ID-JAG -> scoped token (Story 6) ---
     Hop 1  persona -> adapter (brokered auth-code/PKCE)
     Hop 2  adapter -> Okta CRM AS (identity assertion / token exchange, server-side)
     ...
   calling crm.lookup_account ...
   --- Okta/adapter denial (verbatim MCP response) ---
   {"code":-32603,"message":"Authentication failed for resource '{{bc64c69c-9d90-4e3a-bdaa-f27b28b659af.authServerIds.0}}'"}
   Frank Boone can SEE this tool, but the XAA exchange at the CRM AS was refused
   (access_denied / Policy evaluation failed) - no scoped token was minted for this resource.
   --- Okta System Log correlation (Story 3) ---
   (no x-okta-request-id on this hop - open the deep link and eyeball the event)
     Admin console: https://{{org_subdomain}}-admin.okta.com/report/system_log_2?q=frank.boone@atko.email
```

<details>
<summary>What the denial block is</summary>

- The `--- Okta/adapter denial (verbatim MCP response) ---` block is the **actual JSON-RPC error Okta/the adapter returned**, not a toolkit label.
- The scoped-token mint at vantage-crm-as failed (`access_denied` / "Policy evaluation failed"), so no CRM-audience token was ever issued and the call never reached VantageCRM.
- That refusal happens server-side at the CRM AS, so there is no client-visible request-id for it. The toolkit hands you a System Log deep link keyed to Frank so you can read Okta's own record of the denial (see §3.7).
</details>

*NOTE: The `-32603` code and exact error string are representative: the message you see comes straight through from the adapter's MCP response. What is fixed is the shape: Frank got an adapter token (he is a real user), but Okta refused the per-resource scoped token, so the tool cannot run.*

*NOTE: In Lab 5, Frank requests access through OIG and is added temporarily to CRM Read - Cross-Functional. This same step then matches rule 4 instead of the catch-all, flipping all six tools from [BLOCKED] to [USABLE]. The catalog he sees won't change; what changes is whether Okta authorizes the actions.*

**See the grant and the denial side by side.**

Running Alex and Frank one after another already makes the point, but the Lab Toolkit can put both outcomes on a single screen.

1. In the **Lab Toolkit**, choose **8) Side-by-side allow vs deny**.

In one keystroke it runs the **same** CRM read as Alex (a real issued token + data) and then as Frank (Okta's verbatim refusal). No persona prompt; the two are wired in:

```
== Side-by-side: the SAME call, two users (Story 4) ==
   GET https://crm.taskvantage.oktademo.app/api/accounts  (token: api://vantage-crm via lab-toolkit)
   Same agent, same tool, same request. Okta decides per user.

-- [1] Alex Martinez (Sales Rep) --------------------------------------------
   --- Token Okta issued to Alex Martinez (Sales Rep) (decoded JWT) ---
     sub : alex.martinez@atko.email
     aud : api://vantage-crm
     scp : crm.accounts.read crm.accounts.write crm.contacts.read crm.opportunities.read crm.opportunities.write
     ...
   --- Raw HTTP + Okta correlation id ---
     GET  https://{{idp.tenantDomain}}/oauth2/{{crm_as_id}}/v1/authorize?...
          x-okta-request-id: {{authorize_request_id}}
     POST https://{{idp.tenantDomain}}/oauth2/{{crm_as_id}}/v1/token   -> HTTP 200
          x-okta-request-id: {{token_request_id}}
   HTTP 200 - 2 records (access GRANTED)
   --- Okta System Log correlation (Story 3) ---
     ...

-- [2] Frank Boone (Engineering) --------------------------------------------
   Okta refused to issue Frank Boone (Engineering) a token (access DENIED):
   --- Okta denial (verbatim response) ---
     error             : access_denied
     error_description : User is not assigned to a policy that permits this scope.
     x-okta-request-id : {{authorize_request_id}}
     (This is Okta refusing to issue a token at /authorize - not a toolkit label.)
   --- Okta System Log correlation (Story 3) ---
     ...

   Two real Okta artifacts, one grant + one denial - both verifiable in Okta's audit log.
```

*NOTE: Contrast this with §3.6's tool invoke. Here Frank asks the toolkit's CRM client directly for a scoped CRM token, so Okta refuses at **/authorize** and hands back a client-visible `x-okta-request-id` for the denial. Two real Okta responses, one grant and one refusal, from the same request, on one screen.*

**Don't trust the toolkit: verify the token yourself.**

Whenever a persona read issues a token (e.g. **2) Read CRM accounts**), the Lab Toolkit prints the exact off-tool affordances to check Okta's work:

```
   --- Verify this yourself, off this tool (Story 7) ---
     1) Paste the token at https://jwt.io to read the signed claims.
     2) Or introspect it live at Okta:
        curl -s -X POST 'https://{{idp.tenantDomain}}/oauth2/{{crm_as_id}}/v1/introspect' \
             -d 'token=<paste-token>&token_type_hint=access_token&client_id={{toolkit_client_id}}'
```

Paste the token at jwt.io, or introspect it live at Okta. Either way you confirm the claims against Okta itself, not against the toolkit's rendering of them.

### 3.7 Inspect the audit trail in System Log

<details>
<summary><b>Why this matters</b></summary>

- Because the agent acts *as* the user rather than as itself, every attempt is attributable to both: which agent, on whose authority.
- The user never dropped out of the chain. A shared API key would have logged the agent and erased the person it was acting for.
</details>

<details>
<summary><b>Context: the correlation id is already on your screen (read once)</b></summary>

- The runs you just performed each generated a chain of events in the Okta System Log.
- Every persona run printed a **Raw HTTP + Okta correlation id** panel carrying the `x-okta-request-id` for the token exchange.
- When you read accounts (**2) Read CRM accounts**) or invoked a tool (**5) Invoke a tool**), the toolkit offered a one-time Okta **admin** sign-in (read-only, cached for the session) and printed Okta's own audit record for the action **inline**, next to a deep link straight to that event.
</details>

The toolkit prints Okta's audit record inline:

```
   --- Okta System Log correlation (Story 3) ---
   GET /api/v1/logs?filter=debugContext.debugData.requestId eq "{{token_request_id}}"
   Okta's own audit record for this action:
     eventType : app.oauth2.as.token.grant
     outcome   : SUCCESS
     actor     : Alex Martinez [User] alex.martinez@atko.email
     target    : vantage-crm-as [AuthorizationServer] api://vantage-crm
     published : 2026-04-23T11:24:09.512Z
     uuid      : {{event_uuid}}
     Admin console: https://{{org_subdomain}}-admin.okta.com/report/system_log_2?q={{token_request_id}}
```

Follow the deep link the toolkit already printed (it opens the System Log pre-filtered to exactly this event), or, if you skipped the admin sign-in, paste the `x-okta-request-id` from the Raw HTTP panel into **Reports** > **System Log** yourself. Either way you land on the same record. For each run you will see a sequence similar to:

| Event | Actor | Target | What it tells you |
| --- | --- | --- | --- |
| **app.oauth2.token.grant.access_token** | the agent's OAuth client | the user | The user-context token the Lab Toolkit simulated |
| **ai_agent.token_exchange.request** | **TaskVantage Sales Agent** | **vantage-crm-as** | The adapter asking Okta to issue this user a token for the resource |
| **ai_agent.token_exchange.scope_evaluation** | the access policy | the user | Which rule matched (or the catch-all): whether Okta authorized the action |
| **ai_agent.token_exchange.grant** / **...deny** | Okta | the user | Whether a token was issued (action authorized) or refused (action denied) |

**What just changed:** every grant and denial you produced is now attributable in Okta's audit log to the user, the agent, and the rule that fired.

*NOTE: The audit trail records the per-user authorization decision at use-time: for each tool the user tried to use, did Okta issue a token or deny it? Every grant and denial is recorded against the user, the agent, and the rule that fired (or didn't). Compliance teams can answer "what was our agent authorized to do for Alex, and what was Frank refused?" with no application-side instrumentation.*

---

**End of lab.** You have seen Okta act as the policy enforcement point at the moment of action: same agent, same six-tool catalog for everyone, three different authorization outcomes. Neither the agent nor the catalog changed between runs. What changed was Okta's answer to "will I issue this user a token to run this tool?", and that answer governs the agent's behavior.

In Lab 4 you do two things. First, build the missing half (vantage-desk-as, its scopes, its access policy, and the managed connection on the agent) using everything you reviewed here as reference. Second, exercise a tool invocation end-to-end: the adapter does the XAA token exchange, hands a user-scoped access token to the MCP server, and the call lands on VantageCRM (or VantageDesk) as the user. Use-time authorization is half the story; Module 4 is the other half.
