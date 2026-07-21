# Lab Module 1: The World It'll Operate In — Environment Tour [Estimate: 25 minutes]

## Objective

Review your TaskVantage environment before introducing any AI agents. You will tour your Okta org, the two custom business applications (VantageCRM and VantageDesk), the MCP server that fronts them, and the Okta AI Agents administration area. By the end of this lab, you will know where everything lives and what state it is in before governance is applied.

> **Hosting model:** VantageCRM and VantageDesk are one central, multi-tenant,
> API-only deployment shared by every attendee's Okta org — *not* a per-attendee copy. They are
> resource servers only: no browser login, no app UI. The central app resolves which tenant your
> call belongs to from the token's **issuer**. Your agent and Okta MCP Adapter stay per-attendee;
> each app has its own central, shared MCP server (the VantageCRM MCP and the VantageDesk MCP). The "tour it in a browser" moments below
> (1.5 / 1.6) are delivered out-of-band — a provided screenshot or the **Lab Toolkit** on the
> Virtual Desktop, which calls the API as each user.

## Browser use for this lab

- Use a regular browser tab on your local machine for administrator tasks (Super Admin in your Okta org).
- Use the **Lab Toolkit** (the desktop icon on the Virtual Desktop) for all AI usage and for managing the MCP bridge.

---

**About this camp — read this before starting.**

Each capability introduced in this camp is delivered in two stages. First, you observe it working on **VantageCRM**, which is fully wired before you begin. Then you build the equivalent configuration on **VantageDesk**, which is intentionally incomplete. By the end of the camp, VantageDesk will be configured identically to VantageCRM. Watch for this pattern in every module.

When you see a step that asks you to *review* something on VantageCRM, look closely. The follow-up step on VantageDesk will assume you understood what you just saw. If anything is unclear, please ask your lab facilitator to help explain. AI Security is new to everyone, so don't be embarassed if something is unclear!

---

### Set up your Virtual Desktop (run this first)

Your Virtual Desktop needs a one-time setup that installs the tools this lab uses (OpenCode and the **Lab Toolkit**), points it at your paired MCP adapter bridge, and resolves your org's IDs. This is the only command you paste by hand — everything else is done in the Okta Admin Console or the Lab Toolkit.

1. On the Virtual Desktop, open **Windows PowerShell as Administrator** (right-click the Start button → *Windows PowerShell (Admin)*).
2. Paste this entire block and press **Enter**:

   ```powershell
   Set-ExecutionPolicy -Scope Process Bypass -Force
   $b = "$env:TEMP\bootstrap.ps1"
   Invoke-RestMethod "https://cdn.demo.okta.com/labs/techcamp-o4aa/bootstrap.ps1" -OutFile $b
   Unblock-File $b
   & $b -OrgUrl "https://{{idp.tenantDomain}}" `
        -BridgeAddress "{{bridge_address}}" `
        -OpenAIApiKey "{{6e623d84-b375-4f4d-a0e0-3cb4d1e34378.credentials.apiKey}}" `
        -PersonaPassword "{{bc64c69c-9d90-4e3a-bdaa-f27b28b659af.settings.persona_password}}" `
        -InstallToolkit
   ```

3. When prompted, sign in **once** with your Okta admin login and password. This one-time sign-in lets the setup resolve your org's IDs (the Lab Toolkit client and `vantage-crm-as`); nothing is stored beyond this VM.
4. When it finishes, confirm the **Lab Toolkit** icon is on the desktop — you'll use it starting in step 1.5.

*NOTE: The setup is idempotent — if anything looks off, just re-run the same block. If it reports a missing value, check the highlighted variable and re-run.*

### 1.1 Log into your TaskVantage Okta org

1. Navigate to your assigned Okta org URL: `https://{{idp.tenantDomain}}`
2. Sign in with your admin credentials.
3. Click the **Admin** tab in the upper-right corner to enter the Admin Console.

*NOTE: You must have accepted the org invite from the previous module. If you haven't, do that first.*

**Why this mattered:** You are the identity team that will be accountable for the new hire you're about to onboard — the AI agent. Everything in this camp is configured from this admin seat.

### 1.2 Complete your personal admin profile

*NOTE: Your personal admin account has no first or last name set yet. Set them now — these fields appear in audit events and access requests later.*

1. From the Admin Console, select **Directory** > **People**.
2. Find your personal admin account. Because it has no name yet, its **Person & username** column shows **two dashes (--)** instead of a name — click that **--** account.
3. Select the **Profile** tab, then click **Edit**.
4. Enter your **First name** and **Last name**.
5. Scroll down and click **Save**.

### 1.3 Review test users and personas

These personas will be used throughout the lab. The agent will act on behalf of these users; their group memberships drive what tools and data they can reach.

1. From the Admin Console, go to **Directory** > **People**.
2. Confirm the users below are present and **ACTIVE**.

All personas share the same password, `{{bc64c69c-9d90-4e3a-bdaa-f27b28b659af.settings.persona_password}}` (provided with your lab credentials).

| User | Role | Use in lab |
| --- | --- | --- |
| Alex Martinez | Sales Rep | CRM-group member — gets the full CRM tool set, but VantageCRM shows him only the accounts he owns (data row-filtering) |
| Susan Potter | Sales Manager | Full CRM access; sees all accounts |
| Kim Liu | IT Help Desk Tier 1 | Full VantageDesk access; also a CRM-group member (CRM tools with role-bounded data) |
| Frank Boone | Engineering Director | No CRM or ITSM access by default — will request access via OIG in Lab 5 |
| Sally Field | Executive | Indirect access only — uses the agent rather than apps directly |

*NOTE: Every user sees the **same** tool catalog — tools belong to the agent, not the user. What differs is which tools Okta lets each user actually USE (decided at invocation) and what **data** comes back inside them. So the same prompt from Alex and Susan can return different data even when both are authorized for the same tools — that is the point.*

**Why this mattered:** The agent will act *as* these people, bounded by them — its effective access is the intersection of what it may do and what the user may do. Meeting the personas now is meeting the limits the agent will inherit later.

### 1.4 Review groups

1. From the Admin Console, select **Directory** > **Groups**.
2. Confirm the following groups exist:

| Group | Purpose |
| --- | --- |
| Sales Management | CRM access; members see **all** accounts (manager visibility) |
| Sales Reps | CRM access; members see only the accounts they **own** (row-level) |
| IT Help Desk | VantageDesk (ITSM) access — and CRM too, under the binary model (see Module 3.1) |
| CRM Read - Cross-Functional | Empty until OIG grants temporary CRM access in Lab 5 |
| Engineering | No CRM/ITSM access by default (Frank's group) |
| Everyone | Built-in default group; baseline only — no app or tool access |

*NOTE: There is intentionally no group that grants "agent powers." Agent access is governed through OIG entitlements, not group membership — you'll see this in Lab 5.*

### 1.5 Tour VantageCRM (out-of-band)

VantageCRM is a custom-built CRM that stands in for Salesforce, HubSpot, or similar. It holds the customer data your agent will read and modify. It is **API-only** — no app UI to log into. It lives centrally at *crm.taskvantage.oktademo.app*, shared by every attendee org, and resolves your tenant from the token issuer.

Because there is no browser app, you tour the data by calling the API as each user, using the provided screenshot or the **Lab Toolkit**. Both call *GET /api/accounts* with each user's token.

1. Open the **Lab Toolkit** (desktop icon).
2. Choose **2) Read CRM accounts**.
3. Select **Susan Potter (Sales Manager)** when prompted for a persona. She is in Sales Management, so she sees **all 8 accounts**.
4. Run it again, this time selecting **Alex Martinez (Sales Rep)**. He sees only the accounts he owns — **2 accounts (ACC-1001 and ACC-1002)**.

The difference is row-level filtering enforced by VantageCRM itself, based on each user's token. The agent will inherit these same restrictions in later labs.

*NOTE: VantageCRM is fully wired as a resource server — custom authorization server, scopes, a groups claim, and an access policy mapping groups to scopes. There's no human login, because no human signs in to the API-only app. You'll inspect the auth server and access policy in the next several steps.*

### 1.6 Tour VantageDesk (out-of-band)

VantageDesk is a custom-built IT service management app that stands in for ServiceNow or Jira Service Management. Like VantageCRM, it is **API-only** — no app UI. It lives centrally at *desk.taskvantage.oktademo.app*, shared by every attendee org, and resolves your tenant from the token issuer.

Tour it out-of-band, using the provided screenshot or the **Lab Toolkit**, which calls *GET /api/tickets* with each user's token.

1. Open the **Lab Toolkit** and choose **3) Read Desk tickets**.
2. Select **Kim Liu (IT Help Desk)** when prompted for a persona. She carries the ITSM scopes, so she sees the full ticket queue (Tickets, Incidents, Knowledge Base).
3. Run it again, this time selecting **Alex Martinez (Sales Rep)**. He has no ITSM scopes, so the call returns nothing.

The Kim-vs-Alex difference is purely **scope**: who has the ITSM scopes and who does not. In later labs, when Alex is the user, Okta refuses to authorize any Desk tool — he can see them, but the action is denied because no ITSM token is issued for him. There's no portal and no self-service ticket form; access is decided entirely by what the token carries.

*NOTE: VantageDesk has none of the Okta-side wiring yet — no authorization server, no scopes, no access policy, no managed connection, no OIG entitlements. You'll build each of these in later modules, modeled on VantageCRM.*

### 1.7 Check your environment

Each app has its own MCP server: the **VantageCRM MCP** (`mcp-crm.taskvantage.oktademo.app`) exposes the CRM tools, and the **VantageDesk MCP** (`mcp-desk.taskvantage.oktademo.app`) exposes the ITSM tools. Together they make up the agent's tool catalog (such as *crm.lookup_account* and *itsm.create_ticket*). In later labs, the **Okta MCP Adapter** sits between the agent and these MCP servers and:

1. Verifies the agent is properly registered in Okta.
2. Exposes the agent's full tool catalog to every user, while letting Okta authorize *which* tools each user may actually invoke — enforced at the token exchange, not by hiding tools.
3. Performs the XAA token exchange so backend calls hit the apps as the user, not as the agent.

Run the environment check now. It verifies the central apps and both MCP servers are reachable, confirms TLS certificates are valid, and sets up the environment that later labs reuse.

1. Open the **Lab Toolkit** (desktop icon).
2. Choose **1) Check my environment**.
3. You should see output similar to:

```
TaskVantage environment check
─────────────────────────────
✓ Okta org reachable        (https://{{idp.tenantDomain}})
✓ VantageCRM reachable      (https://crm.taskvantage.oktademo.app — central)
✓ VantageDesk reachable     (https://desk.taskvantage.oktademo.app — central)
✓ VantageCRM MCP reachable  (https://mcp-crm.taskvantage.oktademo.app — 6 CRM tools)
✓ VantageDesk MCP reachable (https://mcp-desk.taskvantage.oktademo.app — 6 Desk tools)
✓ TLS certificates valid

Environment ready:
  OKTA_ORG, OKTA_DOMAIN, MCP_URL, CRM_URL, DESK_URL
  (the Lab Toolkit reuses these in future steps)

Ready to proceed to Lab 2.
```

*NOTE: If any line shows a red ✗ instead of a green ✓, raise your hand for a proctor before continuing. Later labs depend on all checks passing.*

**Why this mattered:** The MCP Adapter you just confirmed is the policy enforcement point — the choke where the agent-∩-user-∩-resource intersection actually gets enforced at token exchange. Every governed action in later labs passes through it.

### 1.8 Tour the Okta AI Agents area

This is where you will spend most of Labs 2 through 5.

1. From the Admin Console, go to **Directory** > **AI Agents**.
2. Note the list is empty — no agents registered yet. Lab 2 changes this.
3. Click **Settings** (top-right) to review the AI Agents global settings. Note the default credential rotation window and default agent session duration. Leave these at their preconfigured values.

### 1.9 Review the custom authorization server (VantageCRM)

VantageCRM has its own custom authorization server in Okta. This is the trust anchor the MCP adapter will use during XAA token exchange in Lab 4.

1. From the Admin Console, go to **Security** > **API**.
2. Confirm **vantage-crm-as** is present:

   | Authorization Server | Audience | Scopes |
   | --- | --- | --- |
   | **vantage-crm-as** | **api://vantage-crm** | **crm.accounts.read**, **crm.accounts.write**, **crm.contacts.read**, **crm.opportunities.read**, **crm.opportunities.write** |

3. Click into **vantage-crm-as** and open the **Scopes** tab. Each scope corresponds to a tool category the agent may invoke. Note the constant audience **api://vantage-crm** and the **groups** claim the server adds to tokens — the central app uses both to authorize and tenant-resolve each call.
4. Click the **Access Policies** tab. You'll look at this policy closely in 1.10. It won't match anything until Lab 2 creates the agent.

*NOTE: There is no **vantage-desk-as** yet. You'll create the VantageDesk authorization server, its scopes, and its access policy in Lab 4 — modeled on what you just reviewed.*

### 1.10 Review the authorization server access policy (VantageCRM)

Because the apps are API-only, there is **no app sign-in policy** — no human signs in to VantageCRM or VantageDesk. Access is gated by the **access policy on the custom authorization server**: its token-issuance rules decide which groups receive which scopes. This is the **review-then-build** pattern — review the VantageCRM policy now, build the VantageDesk equivalent in Lab 4.

**Review (VantageCRM):**

1. From the Admin Console, go to **Security** > **API** and click into **vantage-crm-as**.
2. Open the **Access Policies** tab and review the preconfigured policy and its rules. Each rule maps a group to the scopes its members' tokens may carry:

   | If the user is in… | The issued token may carry… |
   | --- | --- |
   | Sales Reps | the full crm.* scope set |
   | Sales Management | the full crm.* scope set |

This is why Susan and Alex saw different data in 1.5 even though their tokens carry the **same** scopes: the difference is **data-level**, not scope-level. The policy issues both a read-capable token, then VantageCRM row-filters results by the caller's identity — Susan (Sales Management) sees all accounts, Alex (Sales Reps) sees only the accounts he owns.

*NOTE: Today every CRM rule grants the same full scope set — access is binary (in a CRM group → all CRM scopes; in none → none). Graduated per-group scopes (e.g. read-only for reps) are a known follow-up — see **lab-infra/README.md**.*

*NOTE: There is no **vantage-desk-as** yet, so no VantageDesk policy to review. In Lab 4 you'll create the VantageDesk authorization server, its ITSM scopes, and the access policy that grants those scopes to IT Help Desk (and withholds them from everyone else, including Alex) — modeled on what you reviewed here.*

**Why this mattered:** This access policy is the layer the agent's tokens will be judged against — the rules of the rooms, set before anyone gets a key. When the agent later borrows a user's access, this is what decides which scopes that user's token can carry at all.

---

**End of lab.** You've seen the central, API-only apps respond differently to Susan, Alex, and Kim purely on the basis of their tokens, and reviewed the prebuilt **vantage-crm-as** and its access policy — the model you'll rebuild for VantageDesk in Lab 4. In Lab 2, you bring your first AI agent — the OpenCode instance pre-installed on your VM — under Okta governance by registering it manually.
