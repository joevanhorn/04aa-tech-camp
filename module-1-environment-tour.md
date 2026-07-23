# Lab Module 1: The World It'll Operate In - Environment Tour [Estimate: 25 minutes]

## Objective

Tour your TaskVantage environment before adding any AI agents: your Okta org, the two apps (VantageCRM and VantageDesk), the MCP server that fronts them, and the AI Agents admin area. By the end you know where everything lives and its state before governance is applied.

<details>
<summary><b>Context: how the apps are hosted (read once)</b></summary>

- One central, multi-tenant, API-only deployment of VantageCRM and VantageDesk, shared by every attendee's org. Not a per-attendee copy.
- Resource servers only: no browser login, no app UI. Each app resolves your tenant from the token's **issuer**.
- Per-attendee: your agent and Okta MCP Adapter. Central and shared: each app's MCP server.
- The browser-tour moments (1.5 / 1.6) are delivered out-of-band: a screenshot or the **Lab Toolkit**, which calls the API as each user.
</details>

**Two tools you'll use:**
- **Local browser** for admin tasks (Super Admin in your Okta org).
- **Lab Toolkit** (desktop icon on the Virtual Desktop) for all AI usage and managing the MCP bridge.

<details>
<summary><b>Context: how this camp is structured (read once)</b></summary>

- Every capability is shown on **VantageCRM** (fully wired) first, then you build the same on **VantageDesk** (intentionally incomplete). By the end, they match.
- When a step says *review* something on CRM, look closely: the Desk step assumes you understood it.
- AI security is new to everyone. If anything is unclear, ask your facilitator.
</details>

---

### Set up your Virtual Desktop (run this first)

Your Virtual Desktop needs a one-time setup that installs the tools this lab uses (OpenCode and the **Lab Toolkit**), **starts and configures** your paired MCP adapter bridge (the command brings your bridge up on demand), and resolves your org's IDs. This is the only command you paste by hand; everything else is done in the Okta Admin Console or the Lab Toolkit.

1. On the Virtual Desktop, open **Windows PowerShell as Administrator** (right-click the Start button → *Windows PowerShell (Admin)*).
2. Paste this entire block and press **Enter**:

   ```powershell
   Set-ExecutionPolicy -Scope Process Bypass -Force
   $b = "$env:TEMP\bootstrap.ps1"
   Invoke-RestMethod "https://cdn.demo.okta.com/labs/techcamp-o4aa/bootstrap.ps1" -OutFile $b
   Unblock-File $b
   & $b -OrgUrl "https://{{idp.tenantDomain}}" -OpenAIApiKey "{{858e3bcd-36ca-4ebe-8e51-ebfcdbafb1e2.credentials.apiKey}}" -PersonaPassword "{{bc64c69c-9d90-4e3a-bdaa-f27b28b659af.settings.persona_password}}" -LaunchBridge -BridgeLauncherSecret "WP5PGgA-qexQe0aGkwKWp5_ygI8c0NmQ" -AdminUiClientId "{{bc64c69c-9d90-4e3a-bdaa-f27b28b659af.deploymentData.adminUiClientId}}" -InstallToolkit
   ```

   *NOTE: `-AdminUiClientId` resolves per org from the bootstrap `deploymentData`; `-BridgeLauncherSecret` is the bridge launcher fleet secret. Both start and configure your paired bridge on demand.*

3. When prompted, sign in **once** with your Okta admin login and password. This one-time sign-in lets the setup resolve your org's IDs (the Lab Toolkit client and `vantage-crm-as`); nothing is stored beyond this VM.
4. When it finishes, confirm the **Lab Toolkit** icon is on the desktop. You'll use it starting in step 1.5.

*NOTE: The setup is idempotent: if anything looks off, re-run the same block. If it reports a missing value, check the highlighted variable and re-run.*

### 1.1 Log into your TaskVantage Okta org

<details>
<summary><b>Why this matters</b></summary>

- You are the identity team accountable for the AI agent you're about to onboard.
- Every step in this camp runs from this admin seat.
</details>

1. Go to your org URL: `https://{{idp.tenantDomain}}`
2. Sign in with your admin credentials.
3. Click **Admin** (upper-right) to enter the Admin Console.

**What just changed:** you're in the admin seat you'll configure everything from.

<details>
<summary>Can't sign in?</summary>

You must have accepted the org invite from the previous module. If you haven't, do that first.
</details>

### 1.2 Complete your personal admin profile

<details>
<summary><b>Why this matters</b></summary>

- Your personal admin account has no first or last name set yet.
- These fields appear in audit events and access requests later.
</details>

1. From the Admin Console, select **Directory** > **People**.
2. Find your personal admin account. Because no name is set, its **Person & username** column shows **two dashes (--)** instead of a name. Click that **--** account.
3. Select the **Profile** tab, then click **Edit**.
4. Enter your **First name** and **Last name**.
5. Scroll down and click **Save**.

**What just changed:** your admin identity now shows a real name in audit events and access requests.

### 1.3 Review test users and personas

<details>
<summary><b>Context: what the personas are for (read once)</b></summary>

- These personas are used throughout the lab.
- The agent acts on behalf of these users. Their group memberships drive which tools and data they can reach.
- The agent acts *as* these people, bounded by them: its effective access is the intersection of what it may do and what the user may do. Meeting the personas now is meeting the limits the agent will inherit later.
</details>

1. From the Admin Console, go to **Directory** > **People**.
2. Confirm the users below are present and **ACTIVE**.

All personas share the same password, `{{bc64c69c-9d90-4e3a-bdaa-f27b28b659af.settings.persona_password}}` (provided with your lab credentials).

| User | Role | Use in lab |
| --- | --- | --- |
| Alex Martinez | Sales Rep | CRM-group member: gets the full CRM tool set, but VantageCRM shows him only the accounts he owns (data row-filtering) |
| Susan Potter | Sales Manager | Full CRM access; sees all accounts |
| Kim Liu | IT Help Desk Tier 1 | Full VantageDesk access; also a CRM-group member (CRM tools with role-bounded data) |
| Frank Boone | Engineering Director | No CRM or ITSM access by default; requests access via OIG in Lab 5 |
| Sally Field | Executive | Indirect access only; uses the agent rather than apps directly |

<details>
<summary><b>Context: same tools, different data (read once)</b></summary>

- Every user sees the **same** tool catalog: tools belong to the agent, not the user.
- What differs is which tools Okta lets each user actually USE (decided at invocation) and what **data** comes back inside them.
- The same prompt from Alex and Susan can return different data even when both are authorized for the same tools.
</details>

### 1.4 Review groups

1. From the Admin Console, select **Directory** > **Groups**.
2. Confirm the following groups exist:

| Group | Purpose |
| --- | --- |
| Sales Management | CRM access; members see **all** accounts (manager visibility) |
| Sales Reps | CRM access; members see only the accounts they **own** (row-level) |
| IT Help Desk | VantageDesk (ITSM) access, and CRM too, under the binary model (see Module 3.1) |
| CRM Read - Cross-Functional | Empty until OIG grants temporary CRM access in Lab 5 |
| Engineering | No CRM/ITSM access by default (Frank's group) |
| Everyone | Built-in default group; baseline only, no app or tool access |

*NOTE: There is intentionally no group that grants "agent powers." Agent access is governed through OIG entitlements, not group membership. You'll see this in Lab 5.*

### 1.5 Tour VantageCRM (out-of-band)

<details>
<summary><b>Context: what VantageCRM is (read once)</b></summary>

- Custom-built CRM standing in for Salesforce, HubSpot, or similar. Holds the customer data your agent will read and modify.
- **API-only**: no app UI to log into.
- Lives centrally at *crm.taskvantage.oktademo.app*, shared by every attendee org, and resolves your tenant from the token issuer.
- No browser app, so you tour the data by calling the API as each user, using the provided screenshot or the **Lab Toolkit**. Both call *GET /api/accounts* with each user's token.
</details>

1. Open the **Lab Toolkit** (desktop icon).
2. Choose **2) Read CRM accounts**.
3. When prompted for a persona, select **Susan Potter (Sales Manager)**. She is in Sales Management, so she sees **all 8 accounts**.
4. Run it again, selecting **Alex Martinez (Sales Rep)**. He sees only the accounts he owns: **2 accounts (ACC-1001 and ACC-1002)**.

**What just changed:** you saw row-level filtering enforced by VantageCRM itself, based on each user's token. The agent inherits these same restrictions in later labs.

<details>
<summary>How VantageCRM is wired</summary>

- Fully wired as a resource server: custom authorization server, scopes, a groups claim, and an access policy mapping groups to scopes.
- No human login, because no human signs in to the API-only app.
- You'll inspect the auth server and access policy in the next several steps.
</details>

### 1.6 Tour VantageDesk (out-of-band)

<details>
<summary><b>Context: what VantageDesk is (read once)</b></summary>

- Custom-built IT service management app standing in for ServiceNow or Jira Service Management.
- **API-only**, like VantageCRM: no app UI.
- Lives centrally at *desk.taskvantage.oktademo.app*, shared by every attendee org, and resolves your tenant from the token issuer.
- Tour it out-of-band, using the provided screenshot or the **Lab Toolkit**, which calls *GET /api/tickets* with each user's token.
</details>

1. Open the **Lab Toolkit** and choose **3) Read Desk tickets**.
2. When prompted for a persona, select **Kim Liu (IT Help Desk)**. She carries the ITSM scopes, so she sees the full ticket queue (Tickets, Incidents, Knowledge Base).
3. Run it again, selecting **Alex Martinez (Sales Rep)**. He has no ITSM scopes, so the call returns nothing.

**What just changed:** the Kim-vs-Alex difference is purely **scope**: who has the ITSM scopes and who does not.

<details>
<summary>Why Alex gets nothing, and what's not built yet</summary>

- In later labs, when Alex is the user, Okta refuses to authorize any Desk tool. He can see them, but the action is denied because no ITSM token is issued for him.
- There's no portal and no self-service ticket form. Access is decided entirely by what the token carries.
- VantageDesk has none of the Okta-side wiring yet: no authorization server, no scopes, no access policy, no managed connection, no OIG entitlements. You'll build each in later modules, modeled on VantageCRM.
</details>

### 1.7 Check your environment

<details>
<summary><b>Context: the MCP servers and adapter (read once)</b></summary>

- Each app has its own MCP server: the **VantageCRM MCP** (`mcp-crm.taskvantage.oktademo.app`) exposes the CRM tools, the **VantageDesk MCP** (`mcp-desk.taskvantage.oktademo.app`) exposes the ITSM tools.
- Together they make up the agent's tool catalog (such as *crm.lookup_account* and *itsm.create_ticket*).
- In later labs the **Okta MCP Adapter** sits between the agent and these MCP servers and:
  1. Verifies the agent is properly registered in Okta.
  2. Exposes the agent's full tool catalog to every user, while letting Okta authorize *which* tools each user may actually invoke, enforced at the token exchange, not by hiding tools.
  3. Performs the XAA token exchange so backend calls hit the apps as the user, not as the agent.
</details>

<details>
<summary><b>Why this matters</b></summary>

- The MCP Adapter is the policy enforcement point: the choke where the agent-∩-user-∩-resource intersection gets enforced at token exchange.
- Every governed action in later labs passes through it.
</details>

The environment check verifies the central apps and both MCP servers are reachable, confirms TLS certificates are valid, and sets up the environment that later labs reuse.

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

**What just changed:** the environment later labs reuse (OKTA_ORG, OKTA_DOMAIN, MCP_URL, CRM_URL, DESK_URL) is set and verified.

<details>
<summary>The toolkit proves every claim</summary>

- The Lab Toolkit never asks you to take its word for anything. Every persona action (reads, tool listing, tool invocation) prints the **decoded token Okta actually issued** for that user: sub, audience, scopes, issuer. On a denial it prints Okta's verbatim refusal, so you're always looking at the real artifact rather than a label the toolkit computed.
- Two menu items make that provable:
  - **8) Side-by-side allow vs deny** runs the same request as two users and shows one grant and one denial together.
  - **9) Prove it can't be faked** demonstrates that enforcement is server-side (Okta refusing to mint a token, and a resource rejecting a token cut for the wrong app).
- You'll use these in Lab 3 and the conclusion.
</details>

### 1.8 Tour the Okta AI Agents area

This is where you'll spend most of Labs 2 through 5.

1. From the Admin Console, go to **Directory** > **AI Agents**.
2. Note the one pre-loaded agent, **VantageCRM Example Agent**, with status **STAGED**: a reference agent that ships with the lab environment. You'll register your **own** agent here in Lab 2.
3. Click **Settings** (top-right) to review the AI Agents global settings. Note the default credential rotation window and default agent session duration. Leave these at their preconfigured values.

### 1.9 Review the custom authorization server (VantageCRM)

<details>
<summary><b>Why this matters</b></summary>

- VantageCRM has its own custom authorization server in Okta.
- This is the trust anchor the MCP adapter uses during XAA token exchange in Lab 4.
</details>

1. From the Admin Console, go to **Security** > **API**.
2. Confirm **vantage-crm-as** is present:

   | Authorization Server | Audience | Scopes |
   | --- | --- | --- |
   | **vantage-crm-as** | **api://vantage-crm** | **crm.accounts.read**, **crm.accounts.write**, **crm.contacts.read**, **crm.opportunities.read**, **crm.opportunities.write** |

3. Click into **vantage-crm-as** and open the **Scopes** tab. Each scope corresponds to a tool category the agent may invoke. Note the constant audience **api://vantage-crm** and the **groups** claim the server adds to tokens: the central app uses both to authorize and tenant-resolve each call.
4. Click the **Access Policies** tab. You'll look at this policy closely in 1.10. It won't match anything until Lab 2 creates the agent.

*NOTE: There is no **vantage-desk-as** yet. You'll create the VantageDesk authorization server, its scopes, and its access policy in Lab 4, modeled on what you just reviewed.*

### 1.10 Review the authorization server access policy (VantageCRM)

<details>
<summary><b>Context: what gates access here (read once)</b></summary>

- The apps are API-only, so there is **no app sign-in policy**: no human signs in to VantageCRM or VantageDesk.
- Access is gated by the **access policy on the custom authorization server**: its token-issuance rules decide which groups receive which scopes.
- This is the **review-then-build** pattern: review the VantageCRM policy now, build the VantageDesk equivalent in Lab 4.
</details>

<details>
<summary><b>Why this matters</b></summary>

- This access policy is the layer the agent's tokens are judged against: the rules of the rooms, set before anyone gets a key.
- When the agent later borrows a user's access, this decides which scopes that user's token can carry at all.
</details>

**Review (VantageCRM):**

1. From the Admin Console, go to **Security** > **API** and click into **vantage-crm-as**.
2. Open the **Access Policies** tab and review the preconfigured policy and its rules. Each rule maps a group to the scopes its members' tokens may carry:

   | If the user is in... | The issued token may carry... |
   | --- | --- |
   | Sales Reps | the full crm.* scope set |
   | Sales Management | the full crm.* scope set |

**What just changed:** you saw why Susan and Alex saw different data in 1.5 even though their tokens carry the **same** scopes: the difference is **data-level**, not scope-level. The policy issues both a read-capable token, then VantageCRM row-filters results by the caller's identity (Susan sees all accounts, Alex sees only the accounts he owns).

<details>
<summary>Scope model detail and VantageDesk note</summary>

- Today every CRM rule grants the same full scope set: access is binary (in a CRM group → all CRM scopes; in none → none). Graduated per-group scopes (e.g. read-only for reps) are a known follow-up: see **lab-infra/README.md**.
- There is no **vantage-desk-as** yet, so no VantageDesk policy to review. In Lab 4 you'll create the VantageDesk authorization server, its ITSM scopes, and the access policy that grants those scopes to IT Help Desk (and withholds them from everyone else, including Alex), modeled on what you reviewed here.
</details>

---

**End of lab.** You've seen the central, API-only apps respond differently to Susan, Alex, and Kim purely on the basis of their tokens, and reviewed the prebuilt **vantage-crm-as** and its access policy: the model you'll rebuild for VantageDesk in Lab 4. In Lab 2, you bring your first AI agent (the OpenCode instance pre-installed on your VM) under Okta governance by registering it manually.
