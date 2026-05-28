# Lab Module 1: TaskVantage Environment Tour [Estimate: 25 minutes]

## Objective

Review your TaskVantage environment before introducing any AI agents. You will tour your Okta org, the two custom business applications (VantageCRM and VantageDesk), the MCP server that fronts them, and the Okta AI Agents administration area. By the end of this lab, you will know where everything lives and what state it is in before governance is applied.

## Browser use for this lab

- Use a regular browser tab on your local machine for administrator tasks (Super Admin in your Okta org).
- Use the Chrome browser on the Virtual Desktop to sign in as end users and run validation scripts.

---

**About this camp — read this before starting.**

Each capability introduced in this camp is delivered in two stages. First, you observe it working on **VantageCRM**, which is fully wired before you begin. Then you build the equivalent configuration on **VantageDesk**, which is intentionally incomplete. By the end of the camp, VantageDesk will be configured identically to VantageCRM — with your hands. Watch for this pattern in every module.

When you see a step that asks you to *review* something on VantageCRM, look closely. The follow-up step on VantageDesk will assume you understood what you just saw.

---

### 1.1 Log into your TaskVantage Okta org

- Navigate to your assigned Okta org URL: `{{org_url}}`
- Sign in with your admin credentials: `{{admin_username}}` / `{{admin_password}}`
- After logging in, click the **Admin** tab in the upper-right corner to enter the Admin Console.

### 1.2 Complete your personal admin profile

*NOTE: Your personal admin account does not have a first or last name set initially. Resolve this before continuing — these fields appear in audit events and access requests later.*

- From the Admin Console, select **Directory** > **People**.
- Locate your personal administrator account and click the two dashes under the **Person & username** column.
- Select the **Profile** tab, then click **Edit**.
- Enter your **First name** and **Last name**.
- Scroll down and click **Save**.

### 1.3 Review test users and personas

These personas will be used throughout the lab. The agent will act on behalf of these users; their group memberships drive what tools and data they can reach.

- From the Admin Console, go to **Directory** > **People**.
- Confirm the following users are present and **ACTIVE**. All passwords are `Tra!nme4321`.

| User | Role | Use in lab |
| --- | --- | --- |
| Alex Martinez | Sales Rep | Limited CRM access; cannot create accounts |
| Susan Potter | Sales Manager | Full CRM access; can create and edit accounts |
| Kim Liu | IT Help Desk Tier 1 | Full VantageDesk access; read-only on CRM |
| Frank Boone | Engineering Director | No CRM or ITSM access by default — will request access via OIG in Lab 5 |
| Sally Field | Executive | Indirect access only — uses the agent rather than apps directly |

*NOTE: The agent's behavior in later labs depends on who is asking. The same prompt issued by Alex and Susan will result in different tool sets and different data — that is the point.*

### 1.4 Review groups

- From the Admin Console, select **Directory** > **Groups**.
- Confirm the following groups exist:

| Group | Purpose |
| --- | --- |
| Sales Reps | Read access to accounts they own in VantageCRM |
| Sales Management | Read/write access to all accounts in VantageCRM |
| IT Help Desk | Full access to VantageDesk tickets and incidents |
| All Employees | Default group; minimum baseline access |

*NOTE: There is intentionally no group that grants "agent powers." Agent access is governed through OIG entitlements, not group membership — you will see this in Lab 5.*

### 1.5 Tour VantageCRM

VantageCRM is a custom-built CRM application that stands in for Salesforce, HubSpot, or similar. It holds the customer data your agent will read and modify.

- On the Virtual Desktop, open Chrome and navigate to `https://vantagecrm.{{lab_domain}}`.
- Sign in as **Susan Potter** (`susan.potter@atko.email` / `Tra!nme4321`).
- You will be redirected to Okta for authentication, then back to VantageCRM.
- Once signed in, browse:
  - **Accounts** — the company records the agent will reference
  - **Contacts** — individuals tied to accounts
  - **Opportunities** — sales records the agent may need to update

- Sign out, then sign in again as **Alex Martinez** (`alex.martinez@atko.email`).
- Note that Alex sees a smaller set of accounts — only those they own. This row-level filtering is enforced by VantageCRM itself, based on the authenticated user. The agent will inherit these same restrictions in later labs.

*NOTE: VantageCRM is fully wired up. It has an OIDC client for end-user login, a custom authorization server, scopes, access policies, and an authentication policy enforcing MFA. You will inspect each of these in the next several steps.*

### 1.6 Tour VantageDesk

VantageDesk is a custom-built IT service management app that stands in for ServiceNow or Jira Service Management.

- On the Virtual Desktop, open Chrome and navigate to `https://vantagedesk.{{lab_domain}}`.
- Sign in as **Kim Liu** (`kim.liu@atko.email` / `Tra!nme4321`).
- Browse:
  - **Tickets** — open, in-progress, and resolved support cases
  - **Incidents** — higher-severity events
  - **Knowledge Base** — articles the agent may surface as part of a resolution

- Sign out. Sign in again as **Alex Martinez** — note that Alex cannot access the IT Help Desk portal at all. They can only create new tickets via a self-service form.

*NOTE: VantageDesk has only the minimum configuration required to log in — an OIDC client and a default authentication policy. It has no custom authorization server, no MFA policy, no managed connection on the agent, and no OIG entitlements. You will build each of these in later modules.*

### 1.7 Run the environment check script

The MCP server is the single endpoint that fronts both VantageCRM and VantageDesk. It exposes a catalog of tools (e.g., `crm.lookup_account`, `itsm.create_ticket`) that the AI agent will use. In later labs, the **Okta MCP Adapter** sits between the agent and this MCP server and is responsible for:

1. Verifying the agent is properly registered in Okta
2. Filtering the tool catalog based on the requesting user's entitlements
3. Performing the XAA token exchange so backend calls hit VantageCRM/VantageDesk as the user, not as the agent

For this lab, run the environment check script on your Virtual Desktop. The script verifies network reachability to all components, confirms TLS certificates are valid, and exports environment variables that subsequent labs will use.

- On the Virtual Desktop, open a terminal and run:

```bash
~/Desktop/check-environment.sh
```

- You should see output similar to:

```
TaskVantage environment check
─────────────────────────────
✓ /etc/hosts entries verified
✓ Okta org reachable        (https://{{org_url}})
✓ VantageCRM reachable      (https://vantagecrm.{{lab_domain}})
✓ VantageDesk reachable     (https://vantagedesk.{{lab_domain}})
✓ MCP server reachable      (https://mcp.{{lab_domain}} — 14 tools registered)
✓ TLS certificates valid for *.{{lab_domain}}

Environment variables exported to ~/.taskvantage.env:
  OKTA_ORG, OKTA_DOMAIN, MCP_URL, CRM_URL, DESK_URL
  (source this file in future lab terminals)

Ready to proceed to Lab 2.
```

*NOTE: If any line shows a red ✗ instead of a green ✓, raise your hand for a lab proctor before continuing. Subsequent labs depend on all checks passing.*

### 1.8 Tour the Okta AI Agents area

This is where you will spend most of Labs 2 through 5.

- From the Admin Console, go to **Directory** > **AI Agents**.
- The list is currently empty — no agents have been registered yet. Lab 2 changes this.
- Click **Settings** (top-right) to review the AI Agents global settings. Note the default credential rotation window and the default agent session duration. Leave these at their preconfigured values.

*NOTE: Your org has **AWS IAM Identity Center** pre-integrated as an AI agent provider app, with imports already enabled. If you take Path A in Lab 2 (import from Bedrock AgentCore), this is the provider you will import from. Path B (manual registration) does not depend on it.*

### 1.9 Review the custom authorization server (VantageCRM)

VantageCRM has its own custom authorization server in Okta. This is the trust anchor the MCP adapter will use during XAA token exchange in Lab 4.

- From the Admin Console, go to **Security** > **API**.
- Confirm `vantage-crm-as` is present:

| Authorization Server | Audience | Scopes |
| --- | --- | --- |
| `vantage-crm-as` | `api://vantage-crm` | `crm.accounts.read`, `crm.accounts.write`, `crm.contacts.read`, `crm.opportunities.read`, `crm.opportunities.write` |

- Click into `vantage-crm-as` and review the **Scopes** tab. Each scope corresponds to a tool category the agent may invoke.
- Click the **Access Policies** tab. Note the preconfigured policy allowing the (not yet created) agent client to request tokens for these scopes. This policy will not match anything until Lab 2 creates the agent.

*NOTE: There is no entry for `vantage-desk-as` yet. You will create the VantageDesk authorization server, its scopes, and its access policy in Lab 4 — modeled on what you just reviewed here.*

### 1.10 Review and build the application authentication policy

In later labs, users authenticate to Okta before the agent acts on their behalf. The authentication policy controls what factors are required at that authentication moment.

This is the first instance of the **review-then-build** pattern. You will review the VantageCRM policy, then create the equivalent policy for VantageDesk.

**Review (VantageCRM):**

- From the Admin Console, go to **Security** > **Authentication Policies**.
- Click **VantageCRM** and review the Default Rule:

| Setting | Expected Value |
| --- | --- |
| Access is | Allowed after successful authentication |
| User must authenticate with | Password + Another factor |
| Possession factor constraints | Require user interaction enabled |
| AND Authentication methods | Allow any method that can be used to meet the requirement |

- Note that VantageCRM has its own authentication policy (not the default org-wide policy). The agent flows in later labs depend on this policy enforcing a second factor.

**Build (VantageDesk):**

- From the Admin Console, go to **Security** > **Authentication Policies**.
- Click **Add a policy**.
- Name the policy `VantageDesk` and click **Save**.
- The new policy will have a Catch-all Rule allowing password-only access. Edit the Catch-all Rule to match VantageCRM's Default Rule:
  - User must authenticate with: **Password + Another factor**
  - Possession factor constraints: **Require user interaction** enabled
  - Authentication methods: **Allow any method that can be used to meet the requirement**
- Click **Save**.
- Now apply this policy to the VantageDesk app. From the **Applications** view of the policy, click **Add app**, search for VantageDesk, and click **Add**.

**Verify:**

- On the Virtual Desktop, open an incognito Chrome window and sign into `https://vantagedesk.{{lab_domain}}` as **Kim Liu**.
- You should now be prompted for a second factor after entering the password.

*NOTE: The agent client itself authenticates differently — private key JWT, no user factor. User MFA only applies when a human user is in the loop, which is every flow in this lab except direct M2M calls.*

---

**End of lab.** Your environment is familiar and VantageDesk has its first piece of user-built configuration. In Lab 2, you will bring your first AI agent under Okta governance — either by importing from AWS Bedrock AgentCore, or by registering a bring-your-own agent manually.
