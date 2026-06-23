# Lab Module 1: TaskVantage Environment Tour [Estimate: 25 minutes]

## Objective

Review your TaskVantage environment before introducing any AI agents. You will tour your Okta org, the two custom business applications (VantageCRM and VantageDesk), the MCP server that fronts them, and the Okta AI Agents administration area. By the end of this lab, you will know where everything lives and what state it is in before governance is applied.

> **Hosting model (ADR-0001):** VantageCRM and VantageDesk are **one central, multi-tenant,
> API-only deployment** that every attendee's Okta org connects to — *not* a per-attendee copy.
> They are resource servers only: no browser login, no app UI, no per-app OIDC client. Every
> interaction is an agentic API call carrying a Bearer access token; the central app resolves which
> tenant (org) the call belongs to from the token's **issuer**. Your **agent and Okta MCP Adapter
> remain per-attendee**; the **MCP server is one central, shared service** (ADR-0002). The "tour it
> in a browser" moments below (Modules 1.5 / 1.6)
> are delivered out-of-band as a provided screenshot or a small read script that calls the API as
> each user — there is no app to sign into.

## Browser use for this lab

- Use a regular browser tab on your local machine for administrator tasks (Super Admin in your Okta org).
- Use the terminal on the Virtual Desktop to run the read scripts and the environment check script. The central apps are API-only, so there is no end-user app login.

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
- Confirm the following users are present and **ACTIVE**. All personas share the same password, `{{persona_password}}` (provided with your lab credentials).

| User | Role | Use in lab |
| --- | --- | --- |
| Alex Martinez | Sales Rep | CRM-group member — gets the full CRM tool set, but VantageCRM shows him only the accounts he owns (data row-filtering) |
| Susan Potter | Sales Manager | Full CRM access; sees all accounts |
| Kim Liu | IT Help Desk Tier 1 | Full VantageDesk access; also a CRM-group member (CRM tools with role-bounded data) |
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

### 1.5 Tour VantageCRM (out-of-band)

VantageCRM is a custom-built CRM application that stands in for Salesforce, HubSpot, or similar. It holds the customer data your agent will read and modify. It is **API-only** — there is no app UI to log into. It lives centrally at `https://vantagecrm.taskvantage-demo.com`, shared by every attendee org, and resolves your tenant from the token issuer.

Because there is no browser app, you tour the data by calling the API as each user. Use the provided screenshot **or** run the small read script on the Virtual Desktop. Both call `GET /api/accounts` with each user's access token.

- On the Virtual Desktop, open a terminal and run the read script for Susan:

```bash
~/Desktop/read-crm-accounts.sh susan.potter
```

  Susan Potter is in **Sales Management**, so her token carries `crm.accounts.read` for all accounts — she sees **all 8 accounts**.

- Now run it as Alex:

```bash
~/Desktop/read-crm-accounts.sh alex.martinez
```

  Alex Martinez is a Sales Rep, so he sees only the accounts he owns — **2 accounts (ACC-1001 and ACC-1002)**.

- The difference is row-level filtering enforced by VantageCRM itself, based on the `sub` + `groups` in each user's token. The agent will inherit these same restrictions in later labs.

*NOTE: VantageCRM is fully wired up as a resource server. It has a custom authorization server, scopes, a `groups` claim, and an access policy that maps groups to scopes. There is no OIDC client for human login and no app sign-in policy, because no human signs in to the API-only app. You will inspect the auth server and its access policy in the next several steps.*

### 1.6 Tour VantageDesk (out-of-band)

VantageDesk is a custom-built IT service management app that stands in for ServiceNow or Jira Service Management. Like VantageCRM, it is **API-only** — there is no app UI. It lives centrally at `https://vantagedesk.taskvantage-demo.com`, shared by every attendee org, and resolves your tenant from the token issuer.

Tour it out-of-band — view the provided screenshot, or run the read script on the Virtual Desktop, which calls `GET /api/tickets` with each user's token:

- On the Virtual Desktop, open a terminal and run the read script for Kim:

```bash
~/Desktop/read-desk-tickets.sh kim.liu
```

  Kim Liu is in **IT Help Desk**, so her token carries the ITSM scopes — she sees the full ticket queue (Tickets, Incidents, Knowledge Base).

- Now run it as Alex:

```bash
~/Desktop/read-desk-tickets.sh alex.martinez
```

  Alex Martinez is not in IT Help Desk, so his token carries **no ITSM scopes at all**. The call returns nothing — and in later labs the adapter will surface **no Desk tools** to the agent when Alex is the user.

- The Kim-vs-Alex difference here is purely **scope**: who has the ITSM scopes and who does not. There is no portal, and no self-service ticket form — access is decided entirely by what the token carries.

*NOTE: VantageDesk has none of the Okta-side wiring yet — no custom authorization server, no scopes, no access policy, no managed connection on the agent, and no OIG entitlements. You will build each of these in later modules, modeled on VantageCRM.*

### 1.7 Run the environment check script

The MCP server is the single endpoint that fronts both VantageCRM and VantageDesk. It exposes a catalog of tools (e.g., `crm.lookup_account`, `itsm.create_ticket`) that the AI agent will use. In later labs, the **Okta MCP Adapter** sits between the agent and this MCP server and is responsible for:

1. Verifying the agent is properly registered in Okta
2. Filtering the tool catalog based on the requesting user's entitlements
3. Performing the XAA token exchange so backend calls hit VantageCRM/VantageDesk as the user, not as the agent

For this lab, run the environment check script on your Virtual Desktop. The script verifies reachability of the **central apps** and the **central MCP server**, confirms TLS certificates are valid, and exports environment variables that subsequent labs will use.

- On the Virtual Desktop, open a terminal and run:

```bash
~/Desktop/check-environment.sh
```

- You should see output similar to:

```
TaskVantage environment check
─────────────────────────────
✓ Okta org reachable        (https://{{org_url}})
✓ VantageCRM reachable      (https://vantagecrm.taskvantage-demo.com — central)
✓ VantageDesk reachable     (https://vantagedesk.taskvantage-demo.com — central)
✓ MCP server reachable      (https://mcp.{{lab_domain}} — 12 tools registered: 6 CRM + 6 Desk)
✓ TLS certificates valid

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

*NOTE: Your org has **AWS IAM Identity Center** pre-integrated as an AI agent provider app, with imports already enabled. The primary Lab 2 path registers your pre-installed OpenCode agent manually and does not use this provider — it's only needed for the optional Bedrock-import path (Lab 2.13).*

### 1.9 Review the custom authorization server (VantageCRM)

VantageCRM has its own custom authorization server in Okta. This is the trust anchor the MCP adapter will use during XAA token exchange in Lab 4.

- From the Admin Console, go to **Security** > **API**.
- Confirm `vantage-crm-as` is present:

| Authorization Server | Audience | Scopes |
| --- | --- | --- |
| `vantage-crm-as` | `api://vantage-crm` | `crm.accounts.read`, `crm.accounts.write`, `crm.contacts.read`, `crm.opportunities.read`, `crm.opportunities.write` |

- Click into `vantage-crm-as` and review the **Scopes** tab. Each scope corresponds to a tool category the agent may invoke. Note the **constant audience `api://vantage-crm`** and the **`groups` claim** the server adds to issued tokens — the central app uses both to authorize and tenant-resolve each call.
- Click the **Access Policies** tab. This is the access policy you will look at more closely in 1.10 — its token-issuance rules decide which groups receive which scopes (and let the not-yet-created agent client request tokens). It will not match anything until Lab 2 creates the agent.

*NOTE: There is no entry for `vantage-desk-as` yet. You will create the VantageDesk authorization server, its scopes, and its access policy in Lab 4 — modeled on what you just reviewed here.*

### 1.10 Review the authorization server access policy (VantageCRM)

Because the apps are API-only, there is **no app sign-in policy** — no human signs in to VantageCRM or VantageDesk. What gates access is the **access policy on the custom authorization server**: its token-issuance rules decide **which groups receive which scopes**. That is what you will review here on VantageCRM, then build for VantageDesk in Lab 4.

This is part of the **review-then-build** pattern: review the VantageCRM access policy now, build the VantageDesk equivalent later.

**Review (VantageCRM):**

- From the Admin Console, go to **Security** > **API** and click into `vantage-crm-as`.
- Open the **Access Policies** tab and review the preconfigured policy and its rules. Each rule maps a **group** to the **scopes** its members' tokens may carry:

| If the user is in… | The issued token may carry… |
| --- | --- |
| Sales Reps | the full `crm.*` scope set |
| Sales Management | the full `crm.*` scope set |

*NOTE: Today every CRM access-policy rule grants the **same full scope set** — access is binary (in a CRM group → all CRM scopes; in none → none). Graduated per-group scopes (e.g. read-only for reps) are a known follow-up, not yet wired — see `lab-infra/README.md`.*

- This is why Susan and Alex saw different data in 1.5 even though their **tokens carry the same scopes**: the difference is **data-level**, not scope-level. The access policy issues both a read-capable token; VantageCRM then **row-filters** results by the caller's `sub` + `groups` — Susan (`Sales Management`) sees all accounts, Alex (`Sales Reps`) sees only the accounts he owns. There is no MFA-to-app step and no sign-in policy, because no human logs into the app — the policy governs **whether a user's token gets CRM scopes at all**, and the app handles the row-level cut.

*NOTE: There is no `vantage-desk-as` yet, so there is no VantageDesk access policy to review. In Lab 4 you will create the VantageDesk authorization server, its ITSM scopes, and the access policy that grants those scopes to **IT Help Desk** (and withholds them from everyone else, including Alex) — modeled exactly on what you reviewed here.*

---

**End of lab.** Your environment is familiar: you have seen the central, API-only apps respond differently to Susan, Alex, and Kim purely on the basis of their tokens, and you have reviewed the prebuilt `vantage-crm-as` and its access policy — the model you will rebuild for VantageDesk in Lab 4. In Lab 2, you will bring your first AI agent — the OpenCode instance pre-installed on your VM — under Okta governance by registering it manually (with optional Bedrock/BYO alternatives).
