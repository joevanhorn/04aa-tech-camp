# Lab Module 2: Bring an AI Agent Under Management [Estimate: 45 minutes]

## Objective

Register an AI agent in Okta Universal Directory as a first-class identity, assign a human owner, configure its public-key credential, link it to a user-sign-on app, and activate it — then bring its VantageCRM access online (managed connection + MCP Adapter resource) with the lab's setup helper and review it as the worked example. By the end of this lab, your agent exists in the AI Agents Registry, is owned and active, scoped to a specific user-facing app, authorized to request tokens for VantageCRM via XAA, and reachable through the adapter. Module 3 will exercise this access; in Lab 4 you'll build the VantageDesk equivalent from scratch.

## Scenario

It is 2026. TaskVantage's sales operations team has wired up **OpenCode** — an open-source AI coding agent — to help sales reps query and update VantageCRM. It runs on the team's machines, calling APIs, but it has no Okta identity. Security has flagged it as ungoverned: no human owner, no audit trail, and credentials sitting in a local config.

Today, you fix that. You will give the agent an identity in your Okta org, an owner who is accountable for its behavior, a public-key credential it can use to prove who it is, a linked sign-on app that defines which users it can act on behalf of, and a scoped managed connection to VantageCRM.

## Browser use for this lab

- Local browser for the Okta Admin Console.
- Virtual Desktop for any terminal work and the agent runtime.

---

### 2.1 What makes an Okta-registered AI agent different

Skim this before clicking — it sets the stakes for everything that follows.

An AI agent registered in Okta is not a service account, not an OAuth client, and not an API key. It is a first-class identity in Universal Directory with three properties no traditional non-human identity has by default:

| Property | What it means | Why it matters |
| --- | --- | --- |
| **Mandatory human owner** | At least one named person is accountable. Okta recommends 2 individual owners or a group of 2+ members. | Audit and incident response have someone to call. Stale agents get cleaned up. |
| **First-class lifecycle** | The agent transitions STAGED → ACTIVE → DEACTIVATED, with explicit Actions for each step. | OIG runs certification campaigns over agents in Lab 5. Deactivation revokes everything at once. |
| **Delegated access via XAA** | The agent has no permissions of its own. It exchanges its identity plus a user's identity for a scoped token to call resources *as the user*. | A user with no CRM access cannot get CRM data through the agent. Every backend call carries user context. |

The agent you register today acquires all three. The rest of the camp depends on this foundation.

---

### 2.2 Your agent: OpenCode (pre-installed on your VM)

The agent you bring under management is **OpenCode** — an open-source AI coding agent that is **already installed and configured on your Virtual Desktop**. You don't install or build anything; you register the OpenCode instance waiting on your VM as a first-class identity in Okta, then govern it. OpenCode is a *third-party* agent — not Okta-built, not Amazon-built — which makes it a realistic stand-in for the "a team wired up an agent" situation every enterprise faces.

Register it with the manual flow in 2.3. The rest of the camp assumes this OpenCode agent.

> **Optional — bring your own / Bedrock (at your discretion).** If your Heropa allocation includes AWS Bedrock AgentCore (with imports enabled on the AWS IAM Identity Center provider), or you'd rather register a different agent runtime, you can — **the Okta steps from 2.4 on are identical**; only the agent runtime differs. The Bedrock *import* shortcut is in 2.13.

---

### 2.3 Register your OpenCode agent

- From the Admin Console, go to **Directory** > **AI Agents**.
- Click **Register AI agent** > **Register manually**.
- Fill in:
  - **Name**: `TaskVantage Sales Agent`
  - **Description**: `OpenCode agent that helps sales reps query and update VantageCRM`
- Leave the optional **Application** link blank for now (you will link an app in 2.6 below).
- Click **Register**.
- On the Owners step that appears, click **Skip for now** (you will assign owners in 2.4 below).

The agent appears on the **Directory** > **AI Agents** page with status **STAGED**. Proceed to 2.4.

*NOTE: Registering it does not change the OpenCode runtime on your VM — it keeps running exactly as before. What changes is that Okta now knows about it and can govern it. OpenCode is already pointed at your Okta MCP Adapter (its endpoint and the agent credential are pre-configured on the VM); from here, every tool call OpenCode makes is brokered and governed by the steps you build below.*

### 2.4 Assign a human owner

The agent cannot be activated without at least one owner. This is enforced by Okta, not a recommendation.

- From **Directory** > **AI Agents**, click into `TaskVantage Sales Agent`.
- Select the **Owners** tab and click **Add owners**.
- Select yourself (your personal admin account from Lab 1.2).
- Click **Save**.

*NOTE: Production deployments typically assign 2–3 individual owners or a group of 2+ members. For this lab, a single owner is enough to satisfy activation. In Lab 5, OIG will demonstrate ownership-driven access certification.*

### 2.5 Add a public-key credential

Okta uses a public key to verify the agent's identity when it requests tokens. The agent holds the matching private key.

- On the agent's page, go to the **Credentials** tab.
- Click **Add public key**.
- In the Add public key dialog, click **Generate new key**.
- Okta generates a keypair. Click **Copy to clipboard** and save the private key. On the VDI, save it as `~/.taskvantage/agent-private-key.json`.
- Click **Done**.
- The public key appears on the **Credentials** tab with status **INACTIVE**.
- Click the vertical ellipsis next to the key and select **Activate**. Status changes to **ACTIVE**.

*NOTE: The key has its own activation status, separate from the agent. Both must be active for the agent to authenticate. If you regenerate or rotate a key later, the new one starts INACTIVE and must be activated explicitly.*

*NOTE: The **private key your agent runtime uses must be the one whose public key is active here.** The XAA exchange (Lab 4) signs a client assertion with this key, and Okta validates it against the active credential's `kid` — if the agent/adapter was configured with a different (or stale) key, the exchange fails with `client_assertion_invalid_kid`. Whenever you regenerate the credential, re-sync the new private key to the runtime.*

### 2.6 Create and link a user-sign-on app

The linked sign-on app is the front door to your agent. Users authenticate to this OIDC app first; from there they reach the agent and, through the agent, the Okta-managed resources it brokers access to. The link does two things in the access model: it scopes the agent's audience to users assigned to the app (access control), and it anchors every agent action to a specific user sign-in event (visibility and audit). In this lab the agent runtime is OpenCode, which drives this sign-in itself through the adapter's brokered OAuth (no separate chat UI) — in other deployments the front-end might be a workflow tool or other application the agent is embedded in.

You will first create a new OIDC web application, then link it to your agent.

**Create the OIDC web application:**

- From the Admin Console, go to **Applications** > **Applications**.
- Click **Create App Integration**.
- Choose **OIDC – OpenID Connect**, then **Web Application**, and click **Next**.
- Fill in:
  - **App integration name**: `TaskVantage Agent UI`
  - **Grant type**: leave **Authorization Code** checked (default)
  - **Sign-in redirect URIs**: `https://{{agent_ui_host}}/authorization-code/callback`
  - **Sign-out redirect URIs**: `https://{{agent_ui_host}}/`
  - **Assignments**: select **Allow everyone in your organization to access**
- Click **Save**.
- On the resulting app page, note the **Client ID** and **Client secret** — these belong to the front-end UI, not the agent.

*NOTE: `{{agent_ui_host}}` is the front-end users sign in through to reach the agent. With OpenCode as your runtime on the VM, OpenCode drives this sign-in via the Okta MCP Adapter's brokered OAuth — the linked app scopes which users the agent may act for and anchors each agent action to a user sign-in event. Lab 3 exercises this flow against the linked app.*

**Link the app to your agent:**

- Go to **Directory** > **AI Agents** > **TaskVantage Sales Agent**.
- Select the **User sign-on** tab.
- Click **Link an application**.
- Choose `TaskVantage Agent UI` from the list and click **Link**.

The linked app now appears on the **User sign-on** tab. From now on, the agent will only honor XAA exchanges for users who are currently signed in to `TaskVantage Agent UI`.

### 2.7 Activate the agent

- Return to the agent's **General** tab.
- Click **Actions** > **Activate**.
- Click **Confirm**.

The agent's status changes from **STAGED** to **ACTIVE**.

### 2.8 Reference: the VantageCRM authorization server

You reviewed `vantage-crm-as` in Lab 1.9. The managed connection the lab is about to wire for you references it as the trust anchor for token exchange.

Quick recap, no clicks needed:

| Authorization Server | Audience | Scopes |
| --- | --- | --- |
| `vantage-crm-as` | `api://vantage-crm` | `crm.accounts.read`, `crm.accounts.write`, `crm.contacts.read`, `crm.opportunities.read`, `crm.opportunities.write` |

The access policy on `vantage-crm-as` allows AI agents that hold a valid managed connection to request these scopes. Your agent is about to become one — wired as the worked example you'll replicate for VantageDesk in Lab 4.

### 2.9 Pre-wire your agent's CRM access (the worked example)

Your agent has an identity but no authorized resources yet. Bringing VantageCRM online takes two pieces: an Okta **managed connection** (so the agent may *request* `crm.*` scopes at `vantage-crm-as`) and, in your **MCP Adapter**, a **resource** that routes CRM tool calls to the backend. The lab wires **both** for you here — the complete CRM path — so you start with a working example to study. In Lab 4 you build the equivalent for VantageDesk *by hand, from zero* — that's where you learn the mechanic. This is the camp's review-then-build pattern.

Run the setup helper from your Virtual Desktop:

```bash
~/Desktop/setup-crm-resource.sh
```

It creates your agent's **INCLUDE_ONLY** `crm.*` managed connection in Okta, imports the agent into your adapter, marks it **DCR-selectable**, and registers the CRM **resource** at `https://{{mcp_host}}/crm/mcp`. It prints each step and finishes with `OK: 'vantage-crm' wired …`.

**Review the managed connection it created.** From **Directory** > **AI Agents** > `TaskVantage Sales Agent` > **Managed connections**, open the `vantage-crm-as` entry. Confirm it is **Only allow** (INCLUDE_ONLY) with the five granular `crm.*` scopes.

*NOTE: Why "Only allow" with the granular list — **not "Allow all"**? The managed connection caps which scopes the agent may *request*; which scopes a given **user** actually gets still comes from `vantage-crm-as`'s access policy (Lab 1.10 / Lab 3), keyed on group membership — that policy drives Lab 3's per-user tool filtering. "Allow all" is not just broader: with the Okta MCP Adapter it makes the agent fall back to requesting a generic `mcp:read` scope the custom auth server doesn't define, and the token exchange fails (`no_matching_scope` / `invalid_scope`). You set this yourself for VantageDesk in Lab 4 — remember **"Only allow"**.*

### 2.10 Review your CRM tool resource in the adapter

The other half the helper wired lives in your **Okta MCP Adapter** — the broker OpenCode actually calls (OpenCode never reaches Okta or VantageCRM directly). It authenticates the agent, performs the XAA token exchange, and routes each tool call to the right backend. Two things had to become true for a CRM call to flow, and the helper did both: the adapter now **knows your agent** (imported, and marked **DCR-selectable** so OpenCode can link to it on first connect), and it has a **resource** — its view of "this agent may reach VantageCRM with these scopes" — pointed at the CRM tools.

Open the adapter admin console at `https://{{adapter_admin_host}}`, sign in, and review — this is the example you'll replicate for Desk:
- **Agents** → `TaskVantage Sales Agent` is present, **DCR-selectable** on.
- **Resources** → one resource for `vantage-crm-as`: URL `https://{{mcp_host}}/crm/mcp`, auth **okta-cross-app**, **enabled**, scopes = your five granular `crm.*` scopes (*not* `mcp:read`).

*NOTE: Why the CRM-specific `/crm/mcp` path? One shared MCP server hosts both VantageCRM and VantageDesk tools, but the adapter binds **one resource to one managed connection and mints one audience-scoped token** — an `api://vantage-crm` token for this CRM resource. The server publishes the 6 CRM tools at `/crm/mcp` and the 6 Desk tools at `/desk/mcp`, so each resource is handed only the tools its token is valid for. Point a resource at the wrong path and its tools come back rejected with `Audience doesn't match`. That's also why VantageDesk needs its **own** resource in Lab 4 — not a second connection bolted onto this one.*

*NOTE: The signing credential matters here. The adapter signs the XAA client assertion (Lab 4) with your agent's private key, and it must be the one whose public key is **ACTIVE** in Okta (2.5) — same `kid` — or Lab 4 fails with `client_assertion_invalid_kid`. The setup helper uses the credential the lab pre-staged for your agent; if you regenerated the key in 2.5, re-stage the matching private key.*

**Lab 4 returns here.** After you build `vantage-desk-as` and its managed connection in Lab 4, you'll add a **second** resource — by hand in the adapter console — pointing at `https://{{mcp_host}}/desk/mcp`, then re-sync. The adapter caches connections, so new scopes take effect only after a sync.

### 2.11 Add your agent to the VantageCRM access policy

The managed connection (2.9) lets your agent *request* `crm.*` scopes; the **access policy** on `vantage-crm-as` decides whether to *issue* them. That policy was seeded keyed to the persona groups (Lab 1.10), but it also has to name **your agent as an allowed client** — otherwise the token exchange your agent performs in Lab 3 is rejected with `no_matching_policy`, even though every scope and group looks correct.

*NOTE: Why isn't "Any client" enough? The XAA flow your agent uses (Lab 3/4) exchanges a **JWT-bearer client assertion** signed as the agent **principal** — a distinct client identity from a normal app. Okta's "Any client" condition does **not** match that agent-principal assertion, so the policy has to name the agent explicitly. This is the single most common reason a correctly-scoped agent still gets zero tools.*

1. Go to **Security** > **API** > **Authorization Servers** > `vantage-crm-as` > **Access Policies**.
2. Open the CRM access policy and edit its **Assign to** clients (the client condition lives on the *policy*, not the individual rules).
3. Switch from *Any client* to **The following clients** and add **your agent** — select `TaskVantage Sales Agent` from the list. This is the agent **principal**; you do **not** add the user-sign-on app (2.6). The principal is the identity Okta evaluates during the XAA exchange, exactly as you'll do for VantageDesk in Lab 4.5.
4. **Save**.

> The lab seeds the policy with `ALL_CLIENTS` so the org provisions cleanly, but `ALL_CLIENTS` does **not** cover the agent-principal assertion — this step is what actually entitles *your* agent. Skipping it is fine until Lab 3, where it surfaces as an empty tool list with `no_matching_policy` in the System Log.

### 2.12 Verify the configuration

Spend a minute confirming the agent is set up correctly. Lab 3 will fail in confusing ways if anything is missing.

**In the Okta Admin Console**, your agent's profile should show:

| Field | Expected Value |
| --- | --- |
| Status | ACTIVE |
| Owner | Your admin account (Owners tab) |
| Credentials | 1 public key, ACTIVE (Credentials tab) |
| User sign-on app | TaskVantage Agent UI (User sign-on tab) |
| Managed connections | 1 connection to `vantage-crm-as` (Managed connections tab) |
| Access policy | Your agent (`TaskVantage Sales Agent`) listed in the `vantage-crm-as` policy's **Assign to** clients (2.11) |

**In the adapter admin console** (2.10), confirm:

| Field | Expected Value |
| --- | --- |
| Agent | `TaskVantage Sales Agent` imported, principal id (`wlp…`) populated |
| DCR-selectable | On |
| Resource | 1 resource for `vantage-crm-as`, URL `https://{{mcp_host}}/crm/mcp`, **enabled**, auth `okta-cross-app` |

**In the System Log** (Reports > System Log), filter on `target.type eq "AIAgent"` and confirm you see lifecycle events: agent created, owner added, key added, key activated, app linked, agent activated, managed connection created.

---

### 2.13 (Optional) Import from Bedrock AgentCore instead

If you're using Bedrock (and AI agent imports are enabled on the AWS IAM Identity Center provider — confirmed in Lab 1.8), you can register the agent by import instead of the manual flow in 2.3:

- From the Admin Console, go to **Directory** > **AI Agents**.
- Click **Register AI agent** > **Import from AI agent providers**.
- Click **Import** next to **AWS IAM Identity Center**. The imported agent (`TaskVantage Sales Agent`) appears with status **STAGED**.

From 2.4 onward (owner, credential, sign-on app, activation, managed connection) the steps are identical regardless of runtime. The Bedrock-side runtime is unchanged by the import; what changes is that Okta can now govern it. Background: [Secure an Imported Amazon Bedrock AgentCore Agent](https://support.okta.com/help/s/article/secure-an-imported-amazon-bedrock-agentcore-agent).

---

**End of lab.** Your agent is registered, owned, active, credentialed, and scoped to a sign-on app — and its VantageCRM access is wired and reviewed: an INCLUDE_ONLY managed connection plus a DCR-selectable agent and an enabled CRM resource at `/crm/mcp` in your adapter. In Lab 3, you will see this agent in action: the MCP Adapter will route a user's prompt through the agent, filter the tool catalog based on the user's entitlements, and demonstrate that the same prompt issued by Alex Martinez versus Susan Potter results in different tool sets and different data — driven entirely by the user's authorization, not the agent's.

A reminder of the camp's pattern: the VantageDesk authorization server, managed connection, and adapter resource do not exist yet. You will build all three in Lab 4, modeled on what you just built for VantageCRM — and re-sync the adapter so the new `/desk/mcp` resource comes online.
