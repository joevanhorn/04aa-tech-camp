# Lab Module 2: Getting a Badge - Bring an AI Agent Under Management [Estimate: 45 minutes]

## Objective

By the end of this lab, your agent exists in the AI Agents Registry, is owned and active, scoped to a specific user-facing app, authorized to request tokens for VantageCRM via XAA, and reachable through the adapter. Module 3 exercises this access; in Lab 4 you build the VantageDesk equivalent from scratch.

**In this lab you will:**
- Register an AI agent in Okta Universal Directory as a first-class identity
- Assign a human owner to the agent
- Configure its public-key/private-key credential
- Link it to a user-sign-on app for human login, and activate it
- Bring its VantageCRM access online (managed connection + MCP Adapter resource) with the lab's setup helper, and review it as the worked example

<details>
<summary><b>Context: the ungoverned agent (read once)</b></summary>

- It is 2026. TaskVantage's sales operations team wired up **OpenCode**, an open-source AI coding agent, to help sales reps query and update VantageCRM.
- It runs on the team's machines, calling APIs, but has no Okta identity. Security flagged it as ungoverned: no human owner, no audit trail, credentials sitting in a local config.
- Today you fix that: give the agent an identity in your Okta org, an accountable owner, a PGP keypair credential, a linked sign-on app that defines which users it can act for, and a scoped managed connection to VantageCRM.
</details>

**Browser use for this lab:**
- **Local browser** for the Okta Admin Console.
- **Virtual Desktop** for the **Lab Toolkit** and the agent runtime.

---

### 2.1 What makes an Okta-registered AI agent different

<details>
<summary><b>Context: agent vs service account (read once)</b></summary>

- An Okta-registered AI agent is not a service account, not an OAuth client, not an API key.
- It is a first-class identity in Universal Directory with three properties no traditional non-human identity has by default (table below).
- The agent you register today acquires all three. The rest of the camp depends on this foundation.
</details>

| Property | What it means | Why it matters |
| --- | --- | --- |
| **Mandatory human owner** | At least one named person is accountable. Okta recommends 2 individual owners or a group of 2+ members. | Audit and incident response have someone to call. Stale agents get cleaned up. |
| **First-class lifecycle** | The agent transitions STAGED → ACTIVE → DEACTIVATED, with explicit Actions for each step. | OIG runs certification campaigns over agents in Lab 5. Deactivation revokes everything at once. |
| **Delegated access via XAA** | The agent has no permissions of its own. It exchanges its identity plus a user's identity for a scoped token to call resources *as the user*. | A user with no CRM access cannot get CRM data through the agent. Every backend call carries user context. |

---

### 2.2 Your agent: OpenCode (pre-installed on your VM)

<details>
<summary><b>Context: why OpenCode (read once)</b></summary>

- **OpenCode** is already installed and configured on your Virtual Desktop. You register it; you don't install or build anything.
- It is a *third-party* agent (not Okta-built, not Amazon-built), a realistic stand-in for the "a team wired up an agent" situation every enterprise faces.
- Register it with the manual flow in 2.3. The rest of the camp assumes this OpenCode agent.
</details>

---

### 2.3 Register your OpenCode agent

1. Go to **Directory** > **AI Agents**.
2. Click **Register AI agent** > **Register manually**.
3. Enter the **Name**: `TaskVantage Sales Agent`
4. Enter the **Description**: `OpenCode agent that helps sales reps query and update VantageCRM`
5. Leave the optional **Application** link blank (you link an app in 2.6).
6. Click **Register**.
7. On the Owners step, click **Skip for now** (you assign owners in 2.4).

The agent appears on **Directory** > **AI Agents** with status **STAGED**. Proceed to 2.4.

**What just changed:** the agent exists as a first-class identity in the directory, not a credential floating in a local config: an identity Okta can own, audit, and revoke.

*NOTE: Registering does not change the OpenCode runtime on your VM. It keeps running as before, but Okta now knows about it and can govern it. OpenCode is already pointed at your Okta MCP Adapter, so every tool call it makes is brokered by the steps below.*

### 2.4 Assign a human owner

<details>
<summary><b>Why this matters</b></summary>

- The agent cannot be activated without at least one owner. Okta enforces this.
- An owner is an accountable human, like a new hire's manager. There are no orphaned ghost agents to chase down later.
</details>

1. From **Directory** > **AI Agents**, click into **TaskVantage Sales Agent**.
2. Select the **Owners** tab.
3. Click **Add owners**.
4. Select yourself (your personal admin account from Lab 1.2).
5. Click **Save**.

**What just changed:** the agent has an accountable owner, the precondition Okta requires before activation.

*NOTE: Production deployments typically assign 2 to 3 individual owners or a group of 2+ members. A single owner satisfies activation for this lab. Lab 5 demonstrates ownership-driven access certification.*

### 2.5 Add a public-key credential

<details>
<summary><b>Why this matters</b></summary>

- Okta uses a public key to verify the agent's identity when it requests tokens. The agent holds the matching private key.
- This keypair is the badge that proves who the agent is, far stronger than a shared secret.
- You never handle the private key: the Okta MCP Adapter (the bridge) holds and syncs it automatically.
</details>

1. On the agent's page, go to the **Credentials** tab.
2. Click **Add public key**.
3. Click **Generate new key**.
4. Click **Done**. The public key appears on the **Credentials** tab with status **INACTIVE**.
5. Click the vertical ellipsis next to the key and select **Activate**. Status changes to **ACTIVE**.

**What just changed:** the agent has an active public key; the bridge holds the matching private key.

*NOTE: The key has its own activation status, separate from the agent. Both must be active for the agent to authenticate. If you regenerate or rotate a key later, the new one starts INACTIVE and must be activated explicitly.*

*NOTE: The active public key must correspond to the private key the runtime/bridge uses to sign the XAA client assertion (Lab 4); a mismatch fails with client_assertion_invalid_kid. The bridge manages this sync automatically now.*

### 2.6 Create and link a user-sign-on app

<details>
<summary><b>Why this matters</b></summary>

- The linked sign-on app is the front door to your agent. Users authenticate to this OIDC app first; from there they reach the agent and, through it, the Okta-managed resources it brokers.
- The link does two things: it scopes the agent's audience to users assigned to the app (access control), and it anchors every agent action to a specific user sign-in event (visibility and audit).
- In this lab the agent runtime is OpenCode, which drives this sign-in itself through the adapter's brokered OAuth (no separate chat UI). In other deployments the front-end might be a workflow tool or another application the agent is embedded in.
</details>

**Create the OIDC web application:**

1. Go to **Applications** > **Applications**.
2. Click **Create App Integration**.
3. Choose **OIDC – OpenID Connect**, then **Web Application**, and click **Next**.
4. Enter the **App integration name**: `TaskVantage Agent UI`
5. Leave **Grant type** as **Authorization Code** (default).
6. Enter the **Sign-in redirect URI**: `https://{{agent_ui_host}}/authorization-code/callback`
7. Leave **Federation Broker Mode** OFF (skip the checkbox).
8. Under **Assignments**, select **Allow everyone in your organization to access**.
9. Click **Save**.
10. On the app page, note the **Client ID** and **Client secret**. These belong to the front-end UI, not the agent.

*NOTE: `{{agent_ui_host}}` is the front-end users sign in through to reach the agent. OpenCode drives this sign-in via the Okta MCP Adapter's brokered OAuth. The linked app scopes which users the agent may act for and anchors each agent action to a user sign-in event. Lab 3 exercises this flow.*

**Link the app to your agent:**

1. Go to **Directory** > **AI Agents** > **TaskVantage Sales Agent**.
2. Select the **User sign-on** tab.
3. Click **Link an application**.
4. Choose **TaskVantage Agent UI** and click **Link**.

**What just changed:** the agent will only honor XAA exchanges for users currently signed in to **TaskVantage Agent UI**. This sets the first half of the intersection: *which people* the agent may act for. Effective access is (agent may do) ∩ (user may do) ∩ (resource exposes); without a linked user, an API-key agent would just act as itself.

### 2.7 Activate the agent

<details>
<summary><b>Why this matters</b></summary>

- Activating transitions the agent from STAGED to ACTIVE, which is what makes it usable. No user can broker a token through it until it is ACTIVE.
- Lab 5's kill switch is exactly this in reverse: one deactivation revokes everything at once.
</details>

1. Return to the agent's **General** tab.
2. Click **Actions** > **Activate**.
3. Click **Confirm**.

**What just changed:** the agent's status is **ACTIVE**; the badge is live and tokens can now be brokered through it.

### 2.8 Reference: the VantageCRM authorization server

<details>
<summary><b>Context: the trust anchor (read once)</b></summary>

- You reviewed **vantage-crm-as** in Lab 1.9. The managed connection the lab is about to wire references it as the trust anchor for token exchange.
- Its access policy allows AI agents that hold a valid managed connection to request these scopes. Your agent is about to become one, wired as the worked example you'll replicate for VantageDesk in Lab 4.
- No clicks needed here; this is a recap.
</details>

| Authorization Server | Audience | Scopes |
| --- | --- | --- |
| **vantage-crm-as** | **api://vantage-crm** | **crm.accounts.read**, **crm.accounts.write**, **crm.contacts.read**, **crm.opportunities.read**, **crm.opportunities.write** |

### 2.9 Pre-wire your agent's CRM access (the worked example)

<details>
<summary><b>Why this matters</b></summary>

- Your agent has an identity but no authorized resources yet.
- Bringing VantageCRM online takes two pieces: an Okta **managed connection** (so the agent may *request* **crm.\*** scopes at **vantage-crm-as**) and, in your **MCP Adapter**, a **resource** that routes CRM tool calls to the backend.
- The lab wires **both** for you here, the complete CRM path, so you start with a working example to study. In Lab 4 you build the VantageDesk equivalent by hand, from zero: that's where you learn the mechanic. This is the review-then-build pattern.
</details>

Run the setup helper from the **Lab Toolkit** on your Virtual Desktop:

1. Open the **Lab Toolkit** (desktop icon).
2. Choose **7) Set up my CRM resource**.

It creates your agent's **INCLUDE_ONLY** **crm.\*** managed connection in Okta, imports the agent into your adapter, marks it **DCR-selectable**, and registers the CRM **resource** at `https://{{mcp_host}}/crm/mcp`. It prints each step and finishes with **OK: 'vantage-crm' wired …**.

**Review the managed connection it created:**

1. Go to **Directory** > **AI Agents** > **TaskVantage Sales Agent** > **Managed connections**.
2. Open the **vantage-crm-as** entry.
3. Confirm it is **Only allow** (INCLUDE_ONLY) with the five granular **crm.\*** scopes.

**What just changed:** the agent may now *request* CRM scopes. The managed connection only caps what it can ask for; the access policy (2.11) decides what each user actually gets.

*NOTE: Use **"Only allow"**, not "Allow all". With the Okta MCP Adapter, "Allow all" makes the agent fall back to requesting a generic mcp:read scope the custom auth server doesn't define, and the token exchange fails (no_matching_scope / invalid_scope). The managed connection only caps which scopes the agent may *request*; which scopes a given user actually gets still comes from **vantage-crm-as**'s access policy. You set this yourself for VantageDesk in Lab 4.*

### 2.10 Review your CRM tool resource in the adapter

<details>
<summary><b>Context: what the adapter does (read once)</b></summary>

- The adapter is the broker OpenCode actually calls. OpenCode never reaches Okta or VantageCRM directly.
- It authenticates the agent, performs the XAA token exchange, and routes each tool call to the right backend.
- The helper made two things true: the adapter now **knows your agent** (imported, marked **DCR-selectable** so OpenCode can link to it on first connect), and it has a **resource** (its view of "this agent may reach VantageCRM with these scopes") pointed at the CRM tools.
</details>

Open the adapter admin console at `https://{{adapter_admin_host}}`, sign in, and review. This is the example you'll replicate for Desk:

- **Agents** → **TaskVantage Sales Agent** is present, **DCR-selectable** on.
- **Resources** → one resource for **vantage-crm-as**: URL `https://{{mcp_host}}/crm/mcp`, auth **okta-cross-app**, **enabled**, scopes = your five granular **crm.\*** scopes (*not* mcp:read).

*NOTE: The adapter binds one resource to one managed connection and mints one audience-scoped (**api://vantage-crm**) token. One shared MCP server publishes CRM tools at **/crm/mcp** and Desk tools at **/desk/mcp**, so each resource gets only the tools its token is valid for. Point a resource at the wrong path and its tools come back rejected with *Audience doesn't match*. This is why VantageDesk needs its own resource in Lab 4.*

*NOTE: The adapter signs the XAA client assertion with the private key whose public key is ACTIVE in Okta (2.5); a mismatched kid fails Lab 4 with client_assertion_invalid_kid. The bridge manages this sync automatically now.*

<details>
<summary>Lab 4 returns here</summary>

After you build **vantage-desk-as** and its managed connection in Lab 4, you'll add a **second** resource by hand in the adapter console, pointing at `https://{{mcp_host}}/desk/mcp`, then re-sync. The adapter caches connections, so new scopes take effect only after a sync.
</details>

### 2.11 Add your agent to the VantageCRM access policy

<details>
<summary><b>Why this matters</b></summary>

- The managed connection (2.9) lets your agent *request* **crm.\*** scopes; the **access policy** on **vantage-crm-as** decides whether to *issue* them.
- That policy was seeded keyed to the persona groups (Lab 1.10), but it also has to name **your agent as an allowed client**. Otherwise the token exchange your agent performs in Lab 3 is rejected with no_matching_policy, even though every scope and group looks correct.
</details>

*NOTE: "Any client" is not enough. The XAA flow signs a JWT-bearer client assertion as the agent **principal**, which Okta's "Any client" condition does not match, so the policy must name the agent explicitly. This is the single most common reason a correctly-scoped agent still gets zero tools.*

1. Go to **Security** > **API** > **Authorization Servers** > **vantage-crm-as** > **Access Policies**.
2. Open the CRM access policy and edit its **Assign to** clients (the client condition lives on the *policy*, not the individual rules).
3. Switch from *Any client* to **The following clients** and add **your agent**: select **TaskVantage Sales Agent** from the list. This is the agent **principal**; you do **not** add the user-sign-on app (2.6). The principal is the identity Okta evaluates during the XAA exchange, exactly as you'll do for VantageDesk in Lab 4.5.
4. **Save**.

**What just changed:** the connection lets the agent *request* and this policy lets Okta *issue*. All three intersection terms now have an owner: a user with no CRM access still gets nothing through the agent.

> The lab seeds the policy with ALL_CLIENTS so the org provisions cleanly, but ALL_CLIENTS does not cover the agent-principal assertion. This step is what entitles *your* agent. Skip it and Lab 3 surfaces an empty tool list with no_matching_policy in the System Log.

### 2.12 Verify the configuration

Spend a minute confirming the agent is set up correctly. Lab 3 will fail in confusing ways if anything is missing.

**In the Okta Admin Console**, your agent's profile should show:

| Field | Expected Value |
| --- | --- |
| Status | ACTIVE |
| Owner | Your admin account (Owners tab) |
| Credentials | 1 public key, ACTIVE (Credentials tab) |
| User sign-on app | TaskVantage Agent UI (User sign-on tab) |
| Managed connections | 1 connection to **vantage-crm-as** (Managed connections tab) |
| Access policy | Your agent (**TaskVantage Sales Agent**) listed in the **vantage-crm-as** policy's **Assign to** clients (2.11) |

**In the adapter admin console** (2.10), confirm:

| Field | Expected Value |
| --- | --- |
| Agent | **TaskVantage Sales Agent** imported, principal id (**wlp…**) populated |
| DCR-selectable | On |
| Resource | 1 resource for **vantage-crm-as**, URL `https://{{mcp_host}}/crm/mcp`, **enabled**, auth **okta-cross-app** |

**In the System Log** (Reports > System Log), filter on `target.type eq "AIAgent"` and confirm you see lifecycle events: agent created, owner added, key added, key activated, app linked, agent activated, managed connection created.

---

**End of lab.** Your agent is registered, owned, active, credentialed, and scoped to a sign-on app, and its VantageCRM access is wired and reviewed: an INCLUDE_ONLY managed connection plus a DCR-selectable agent and an enabled CRM resource at **/crm/mcp** in your adapter. In Lab 3 you see this agent in action: the MCP Adapter exposes the agent's full tool catalog to every user, but Okta authorizes a different set of tools per user at the token exchange. The same prompt from Alex Martinez (who can use the CRM tools) versus Frank Boone (who sees them but isn't authorized) yields different results, and Alex versus Susan returns the same tools but different data, driven entirely by the user's authorization, not the agent's.

A reminder of the camp's pattern: the VantageDesk authorization server, managed connection, and adapter resource do not exist yet. You build all three in Lab 4, modeled on what you just built for VantageCRM, then re-sync the adapter so the new **/desk/mcp** resource comes online.
