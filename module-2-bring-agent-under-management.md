# Lab Module 2: Bring an AI Agent Under Management [Estimate: 45 minutes]

## Objective

Register an AI agent in Okta Universal Directory as a first-class identity, assign a human owner, configure its public-key credential, link it to a user-sign-on app, activate it, and connect it to the prebuilt VantageCRM authorization server. By the end of this lab, your agent exists in the AI Agents Registry, is owned and active, scoped to a specific user-facing app, and authorized to request tokens for VantageCRM via XAA. Module 3 will exercise this access.

## Scenario

It is 2026. TaskVantage's sales operations team has built an AI agent to help sales reps query and update VantageCRM. The agent currently exists as a piece of code — running, calling APIs, but with no Okta identity. Security has flagged it as ungoverned: no human owner, no audit trail, and credentials hardcoded in environment variables.

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

### 2.2 Choose your path

| Path | Use this path if... |
| --- | --- |
| **Path A: Import from Bedrock AgentCore** | Your Heropa allocation includes AWS Bedrock AgentCore with a preconfigured agent, *and* the AWS IAM Identity Center provider app in your Okta org has AI agent imports already enabled (a Heropa provisioning step you confirmed in Lab 1.8). |
| **Path B: Register a custom-code agent manually** | You do not have Bedrock provisioned, or you want to see the manual registration flow. |

Both paths converge at 2.4. After that, every step is identical.

---

## Path A: Import from Bedrock AgentCore

### 2.3.A Trigger the import

- From the Admin Console, go to **Directory** > **AI Agents**.
- Click **Register AI agent** > **Import from AI agent providers**.
- The AI agent providers page appears, listing provider apps configured for imports. You should see **AWS IAM Identity Center**.
- Click the **Import** button next to AWS IAM Identity Center.
- A notification confirms the import is running. When it finishes, the imported agent (`TaskVantage Sales Agent`) appears on the **Directory** > **AI Agents** page with status **STAGED**.

*NOTE: The Bedrock-side runtime is unchanged by the import. What changes is that Okta now knows about the agent and can govern it. For deeper background, see the [Secure an Imported Amazon Bedrock AgentCore Agent](https://support.okta.com/help/s/article/secure-an-imported-amazon-bedrock-agentcore-agent) reference.*

Proceed to 2.4.

---

## Path B: Register a custom-code agent manually

### 2.3.B Register the agent

- From the Admin Console, go to **Directory** > **AI Agents**.
- Click **Register AI agent** > **Register manually**.
- Fill in:
  - **Name**: `TaskVantage Sales Agent`
  - **Description**: `Helps sales reps query and update VantageCRM`
- Leave the optional **Application** link blank for now (you will link an app in 2.6 below).
- Click **Register**.
- On the Owners step that appears, click **Skip for now** (you will assign owners in 2.4 below).

The agent appears on the **Directory** > **AI Agents** page with status **STAGED**. Proceed to 2.4.

---

(Paths A and B converge here.)

### 2.4 Assign a human owner

The agent cannot be activated without at least one owner. This is enforced by Okta, not a recommendation.

- From **Directory** > **AI Agents**, click into `TaskVantage Sales Agent`.
- Select the **Owners** tab and click **Add owners**.
- Select yourself (your personal admin account from Lab 1.2).
- Click **Save**.

*NOTE: Production deployments typically assign 2–3 individual owners or a group of 2+ members. For this lab, a single owner is enough to satisfy activation. In Lab 5, OIG will demonstrate ownership-driven access certification.*

> **[FLAG — to resolve before lab GA]** When AI agent imports are enabled on the AWS IAM Identity Center provider app, a default owner *can* be configured to apply to all imported agents. If Heropa provisioning sets a default owner for Path A users, this step changes: their agent arrives with an owner already populated, and 2.4 becomes "review the default owner and add yourself as an additional owner." If provisioning leaves the default unset, the flow is uniform across paths as written. Decision needed on provisioning approach.

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

### 2.6 Create and link a user-sign-on app

The linked sign-on app is the front door to your agent. Users authenticate to this OIDC app first; from there they reach the agent and, through the agent, the Okta-managed resources it brokers access to. The link does two things in the access model: it scopes the agent's audience to users assigned to the app (access control), and it anchors every agent action to a specific user sign-in event (visibility and audit). In a real deployment this app is the chat UI, workflow tool, or other front-end through which users interact with the agent.

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

*NOTE: `{{agent_ui_host}}` is a placeholder for the front-end host where users would sign in to interact with the agent. In this lab the actual front-end is not deployed; the OIDC app exists so the linking constraint is enforceable in Okta. Lab 3 will simulate the user-sign-in flow against this app when exercising the agent.*

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

You reviewed `vantage-crm-as` in Lab 1.9. The managed connection you are about to build references it as the trust anchor for token exchange.

Quick recap, no clicks needed:

| Authorization Server | Audience | Scopes |
| --- | --- | --- |
| `vantage-crm-as` | `api://vantage-crm` | `crm.accounts.read`, `crm.accounts.write`, `crm.contacts.read`, `crm.opportunities.read`, `crm.opportunities.write` |

The access policy on `vantage-crm-as` allows AI agents that hold a valid managed connection to request these scopes. Your agent is about to become one.

### 2.9 Connect the agent to VantageCRM

This step turns your active agent into an agent that can actually do something. Without a managed connection, the agent has identity but no authorized resources.

- From **Directory** > **AI Agents**, click into `TaskVantage Sales Agent`.
- Select the **Managed connections** tab.
- Click **Add connection**.
- In the Add connection dialog:
  - **Resource type**: select **Authorization server**.
  - **Authorization server**: select `vantage-crm-as` from the dropdown.
  - **Scopes**: select **Allow all** to grant the full scope set.
- Click **Add**.

The new connection appears on the **Managed connections** tab.

*NOTE: "Allow all" grants every scope `vantage-crm-as` exposes. For real-world deployments, you would typically choose "Only allow" with a narrowed scope list — for example, only `crm.accounts.read` for a read-only research agent. In Lab 5, OIG will demonstrate scope-down via certification and time-bound entitlements. For this lab, the agent needs the full scope set so Lab 3's tool filtering has something to filter.*

### 2.10 Verify the configuration

Spend a minute confirming the agent is set up correctly. Lab 3 will fail in confusing ways if anything is missing.

**In the Admin Console**, your agent's profile should show:

| Field | Expected Value |
| --- | --- |
| Status | ACTIVE |
| Owner | Your admin account (Owners tab) |
| Credentials | 1 public key, ACTIVE (Credentials tab) |
| User sign-on app | TaskVantage Agent UI (User sign-on tab) |
| Managed connections | 1 connection to `vantage-crm-as` (Managed connections tab) |

**In the System Log** (Reports > System Log), filter on `target.type eq "AIAgent"` and confirm you see lifecycle events: agent created, owner added, key added, key activated, app linked, agent activated, managed connection created.

---

**End of lab.** Your agent is registered, owned, active, credentialed, scoped to a sign-on app, and connected to VantageCRM. In Lab 3, you will see this agent in action: the MCP Adapter will route a user's prompt through the agent, filter the tool catalog based on the user's entitlements, and demonstrate that the same prompt issued by Alex Martinez versus Susan Potter results in different tool sets and different data — driven entirely by the user's authorization, not the agent's.

A reminder of the camp's pattern: the VantageDesk authorization server and managed connection do not exist yet. You will build both in Lab 4, modeled on what you just built for VantageCRM.
