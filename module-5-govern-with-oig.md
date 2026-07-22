# Lab Module 5: The Performance Review - Govern the Agent's Access with OIG [Estimate: 50 minutes]

## Objective

OIG adds dynamic governance on top of the static configuration you built in Modules 2 through 4. By the end you will have:

- Approved an end-user's access request and seen Okta flip that user's tools from blocked to usable. The catalog he sees never changes; what changes is whether Okta authorizes the actions.
- Launched a certification campaign and watched the same tools go back to blocked when the access is revoked.
- Exercised the kill switch: deactivated the agent and confirmed no user, regardless of standing entitlements, can use it until it is reactivated.

<details>
<summary><b>Context: the round-trip you'll run (read once)</b></summary>

- Governance is a live control surface over what the agent can do, for whom, right now. Not a separate paperwork process.
- Static half (already built): access policy rules tied to group membership, scoped at the authorization server. Governs the steady state.
- Dynamic half (this lab): requests, approvals, time-bound elevation, certification, and a kill switch for the exceptions.
- Today's actor is Frank Boone, the Engineering Director whose tools all showed BLOCKED in Lab 3.6.
  - Frank could always SEE the six CRM tools (every user sees the full catalog). He couldn't USE them, because Okta wouldn't issue him a token.
  - You approve his temporary CRM request, watch the same tool-listing script show all six USABLE, then revoke via certification and watch them flip back to BLOCKED.
  - Authorization is binary today: joining the gated group means Okta authorizes all CRM tools.
- Finally you deactivate the agent and confirm nobody, not even Kim (full standing access), can use it.
</details>

**Browser use for this lab:**
- Local browser for the Okta Admin Console (approval and certification flows).
- Virtual Desktop browser for Frank's end-user perspective on the Okta End-User Dashboard.
- Virtual Desktop **Lab Toolkit** for the tool-listing and tool-invocation steps.

---

### 5.1 What OIG adds on top of access policies

<details>
<summary><b>Context: static access policies vs dynamic OIG (read once)</b></summary>

- Modules 2 through 4 are static: access policy rules evaluate group membership and grant scopes. They evaluate identically every time, for every user, until an admin edits them. Right for predictable, role-driven access.
- OIG layers four dynamic capabilities on top, all attached directly to the existing group. No additional access constructs.
- OIG does not replace access policies. It makes their input, group membership, responsive to time-bound business need without admins manually editing the directory.
</details>

| Capability | What it adds | Where you'll see it in this lab |
| --- | --- | --- |
| **Access catalog** | A list of requestable resources (groups, apps) that end users can discover and request through their OIG dashboard. | 5.2 |
| **Access requests** | End-user-initiated workflows with approver chains, justifications, and audit trails. | 5.3 – 5.4 |
| **Time-bound elevation** | Granted memberships have an expiration; OIG removes the user from the granted group automatically when the clock runs out. | 5.4 |
| **Access certifications** | Periodic or on-demand reviews where an owner certifies whether each user's access is still needed. | 5.6 |

### 5.2 Review the preconfigured OIG setup

<details>
<summary><b>Context: what's preconfigured vs what you'll build (read once)</b></summary>

- Preconfigured in your tenant: the requestable group Frank will ask for, and its catalog configuration.
- You build one piece yourself: the certification campaign, in 5.6.
- Pattern is plain Okta IGA: groups are the unit of access; OIG layers request/approval/time-bound/certification directly on top of group membership.
- The access policy rule you reviewed in Lab 3.2 already handles the scope grant. No additional access constructs are involved.
</details>

**Confirm the cross-functional group and its access policy rule:**

<details>
<summary><b>Why this matters</b></summary>

- The rule and the group are the access machinery. They have been in place since Lab 1.
- Rule 4 has never fired in any of your script runs because nobody has been a member of the gated group. That changes in 5.4.
</details>

1. Go to **Directory** > **Groups** and open **CRM Read - Cross-Functional**. It is empty, no members yet.
2. Go to **Security** > **API** > **vantage-crm-as** > **Access Policies**.
3. Confirm rule 4 (**Cross-functional readers — access**) gates this group with the full **crm.\*** scope set.

*Every CRM rule grants the same scope set today (see Module 3.1).*

**What just changed:** nothing yet. You confirmed the access machinery exists but stays dormant until someone joins the group (5.4).

**Review the group's access catalog configuration:**

The group has been published to the OIG access catalog so end users can discover and request membership through their End-User Dashboard.

1. Go to **Identity Governance** > **Access Requests** (this opens the governance Access Requests app).
2. Open the access **catalog** and find the entry for the group **CRM Read - Cross-Functional**.
3. Review the catalog configuration attached to the group:

| Property | Value |
| --- | --- |
| Resource | Group **CRM Read - Cross-Functional** |
| Description | Temporary read-only access to VantageCRM for engineering and other cross-functional users |
| Default duration | 2 hours (for this lab; production would be 30+ days) |
| Approval required from | The requester's manager |
| Eligible requesters | Anyone in **All Employees** |

*NOTE: The requestable resource is the group itself, with no entitlement bundle or wrapper. On approval, OIG adds the requester to the group for the configured duration; on expiry or revoke, it removes them. The access policy never changes, only the membership moves.*

<details>
<summary><b>Context: the certification campaign you'll build in 5.6 (read once)</b></summary>

- The group and its catalog entry are preconfigured. The certification campaign is not; you create and launch it in 5.6.
- This is the camp's review-then-build pattern: you reviewed the access machinery above, then you build the governance review that sits over it.
- A certification campaign is a time-boxed review in which a reviewer certifies or revokes each user's access to a resource. The one you build reviews active memberships in **CRM Read - Cross-Functional**:

| Property | Value (you'll set these in 5.6) |
| --- | --- |
| Scope | Active memberships in **CRM Read - Cross-Functional** |
| Reviewers | Resource owner (you), fallback group owner |
| Review duration | 7 days |

- Build it in 5.6 after Frank's membership has been granted, so the campaign has something to review.
</details>

### 5.3 Submit an access request as Frank

Switch perspectives. You now act as Frank Boone, the requesting user.

1. On the Virtual Desktop, open a new Chrome incognito window.
2. Go to your Okta End-User Dashboard at `https://{{idp.tenantDomain}}` and sign in as Frank (`frank.boone@atko.email` / `{{bc64c69c-9d90-4e3a-bdaa-f27b28b659af.settings.persona_password}}`).
3. Click the **Requests** tab (or **My Access**, depending on your dashboard version), then **Request Access**.
4. Search for **CRM Read - Cross-Functional** and click **Request**.
5. Enter the **Justification**: `Supporting Q2 cross-functional product launch — need to review account context for sales team partners`
6. Leave **Duration** at the default (2 hours).
7. Click **Submit**.

**What just changed:** Frank's request shows **Pending Approval**. Close the incognito window.

### 5.4 Approve the request as Frank's manager

<details>
<summary><b>Why this matters</b></summary>

- Frank requests access through the same OIG request-and-approval flow a human employee would use.
- The agent is a first-class identity, not an API key. Its access is governed like a person's: a justification and an approver chain, not a config change.
</details>

Switch back to your admin browser session. For this lab, you (the admin user) are configured as Frank's manager, so the approval routes to you.

1. Go to **Identity Governance** > **Access Requests** > **Pending my approval**.
2. Click into Frank's request.
3. Review the requester (**frank.boone@atko.email**), the requested access (membership in **CRM Read - Cross-Functional**), the justification, and the duration (2 hours).
4. Click **Approve**.
5. Optionally add an approver note: `Approved for Q2 launch support — please remove when complete`
6. Click **Confirm**.

**What just changed:** the request moves to **Approved**. OIG adds Frank to **CRM Read - Cross-Functional** with an expiry timestamp 2 hours from now.

*NOTE: Check **Directory** > **Groups** > **CRM Read - Cross-Functional** now, Frank appears as a member. He is removed automatically when the 2-hour clock runs out, or earlier if you revoke via certification in 5.6.*

### 5.5 Verify Frank can now USE the tools

<details>
<summary><b>Why this matters</b></summary>

- In Lab 3.6 Frank could SEE all six CRM tools but every one showed BLOCKED: no rule matched him, so Okta wouldn't issue a token.
- Nothing about the access policy, its rules, or the catalog Frank sees has changed since then.
- Frank is now a member of **CRM Read - Cross-Functional**, so rule 4 fires and Okta authorizes the previously blocked tools.
- The agent's effective access is the live intersection of what it may do, what the user may do, and what the resource exposes. Frank's authority grew, so the agent can now act for him, with no edit to the agent.
</details>

1. Open the **Lab Toolkit** and choose **4) List the agent's tools**.
2. Select **Frank Boone (Engineering)** when prompted for a persona.

Expected output:

```
== The agent's tools - and what Okta lets Frank Boone use ==
   The agent exposes 6 tools - every user SEES the full catalog.
   With Frank Boone's entitlements, Okta authorizes 6 of 6:
     [USABLE]  {{bc64c69c-9d90-4e3a-bdaa-f27b28b659af.authServerIds.0}}__crm.lookup_account
     [USABLE]  {{bc64c69c-9d90-4e3a-bdaa-f27b28b659af.authServerIds.0}}__crm.create_account
     [USABLE]  {{bc64c69c-9d90-4e3a-bdaa-f27b28b659af.authServerIds.0}}__crm.update_account
     [USABLE]  {{bc64c69c-9d90-4e3a-bdaa-f27b28b659af.authServerIds.0}}__crm.lookup_contact
     [USABLE]  {{bc64c69c-9d90-4e3a-bdaa-f27b28b659af.authServerIds.0}}__crm.lookup_opportunity
     [USABLE]  {{bc64c69c-9d90-4e3a-bdaa-f27b28b659af.authServerIds.0}}__crm.update_opportunity
   ^ USABLE = Okta will now issue Frank Boone a token for this resource, so the action is authorized.
```

**What just changed:** all six CRM tools flipped from BLOCKED (Lab 3.6) to USABLE, driven only by Frank's new group membership. The catalog, the agent, and rule 4 are unchanged.

*NOTE: Okta now authorizes the **full** CRM tool set for Frank, not a read-only slice, because authorization is binary today: matching any CRM rule grants all **crm.\*** scopes (see Module 3.1). A future graduated model would make the cross-functional grant genuinely read-only at the tool level (some tools would stay BLOCKED); that isn't wired yet, see **lab-infra/README.md**.*

### 5.6 Create and launch the certification campaign

<details>
<summary><b>Why this matters</b></summary>

- The Q2 launch wraps up. Per the security team's quarterly hygiene process, an access review fires: does Frank still need this access?
- You create the certification campaign you scoped in 5.2, launch it, and act as the reviewer.
</details>

**Create the campaign.**

1. Go to **Identity Governance** > **Access Certifications** (left nav) and stay on the **Certification campaigns** tab.
2. Click **Create campaign** and choose **Resource campaign** (the button is a menu; the other option is a *user* campaign, you want **Resource**). The wizard opens.
3. Under **Campaign details**, set:
   - **Name**: `Quarterly review — AI agent CRM access`
   - **Description**: `Quarterly hygiene review of temporary CRM access granted to cross-functional users`
   - **Start**: set it to **now / the earliest the picker allows** (the wizard defaults to ~3 hours out) so the campaign starts immediately.
   - **Duration / review period**: `7 days`
4. Under **Resource**, pick resource type **Group**, then select **CRM Read - Cross-Functional**.
5. Under **Reviewer**, choose **Resource owner**.
6. Under **Remediation**, set **On revoke** → **Remove access**. Leave **No response** at its default.
7. Finish the wizard and click **Create**.

<details>
<summary>What these choices do</summary>

- Resource type choices are **Application**, **Group**, **AI Agent** (plus **Collection** if that EA feature is enabled).
- Picking the group scopes the campaign to its active memberships: exactly the people granted access through the request flow, Frank included.
- You are the resource owner, so the review lands in your queue.
- **On revoke → Remove access** is what makes a **Revoke** decision actually pull the user out of the group.
- **No response** governs reviews left unanswered past the deadline.
</details>

**What just changed:** the campaign lands in **Scheduled** and becomes **Active** at the start time you set.

**Run it.**

1. The campaign moves to **Active** shortly after its start time. Open it from the **Active** tab. (If it's still under **Scheduled**, wait for the start time or edit it earlier.)
2. On the campaign's page, find Frank's active membership in **CRM Read - Cross-Functional**.
3. Click **Review** and choose **Revoke**.
4. Enter the reason: `Q2 launch completed — access no longer needed`
5. Click **Confirm**.

**What just changed:** OIG removes Frank from **CRM Read - Cross-Functional** immediately at the directory (check **Directory** > **Groups** to confirm). His tool access reflects this a little later, see the timing note in 5.7.

*NOTE: A real campaign also offers **Certify**, which leaves the membership in place. You exercised the revoke path here. Both decisions are captured in the campaign's audit trail.*

### 5.7 Verify Frank's access is revoked

<details>
<summary><b>Why this matters</b></summary>

- Frank's group membership is already gone (5.6). His tools stay visible (every user always sees the full catalog), but Okta stops authorizing them on the next token exchange, so they flip back to BLOCKED.
- Round-trip complete: Frank gained the ability to use these tools through a request, exercised it during his project window, and lost it through certification. No edit to the access policy or the agent's configuration, and the catalog he sees never changed.
- The full lifecycle is in the System Log: request submitted, approved, membership granted with expiry, membership revoked.
- A certification campaign is the agent's periodic access review, the same check your org runs on humans, catching standing access that's no longer needed.
</details>

Read the timing note below before you run this.

1. In the **Lab Toolkit**, choose **4) List the agent's tools**.
2. Select **Frank Boone (Engineering)**.

Once Okta re-evaluates Frank's access at the next token exchange, you'll see:

```
== The agent's tools - and what Okta lets Frank Boone use ==
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

**What just changed:** with Frank out of the group, rule 4 no longer matches and all six tools show BLOCKED again.

*NOTE (revocation timing): the membership change hits the directory immediately, but Okta keeps honoring Frank's current access token until it's re-minted (up to ~1 hour). Right after the revoke this step may still show all six USABLE; the revoke is enforced at the next token exchange. To enforce it now: end the user's sessions with **Universal Logout** (the "User session" tab, see 5.8), or deactivate the agent (5.8).*

### 5.8 Exercise the kill switch: deactivate the agent

<details>
<summary><b>Why this matters</b></summary>

- When the security team needs to stop the agent immediately (a compromised key, an unexpected behavior, a suspected misuse), the response should be one action, not a multi-step rollback. That action is deactivation.
- The agent is an identity: freeze its badge and instantly nobody can broker a token through it.
- It's a suspension, not a termination, so it's reversible. You bring it back online in 5.9.
- This is the board's "how do we stop it?" answered in one click.
</details>

1. Go to **Directory** > **AI Agents** > **TaskVantage Sales Agent**.
2. Click **Actions** > **Deactivate**.
3. Read the confirmation dialog, then click **Confirm**.

**What just changed:** the agent status moves from **ACTIVE** to **DEACTIVATED**. Every tool call through it now returns 401. A true, instant kill switch.

Verify the kill is real. Try to use the agent as Kim Liu, who has full standing access through her IT Help Desk role:

1. Open the **Lab Toolkit** and choose **5) Invoke a tool**.
2. Select **Kim Liu (IT Help Desk)** when prompted for a persona.
3. Invoke **itsm.lookup_ticket** for ticket **TKT-1734**.

Expected output:

```
Acting as: kim.liu@atko.email
Tool: itsm.lookup_ticket

→ Calling MCP Adapter…
✗ 401 Unauthorized — agent TaskVantage Sales Agent is DEACTIVATED.

No tool was invoked. The agent is offline.
```

**What just changed:** Kim, who lost no group memberships, is blocked too. Because the agent brokers all access, deactivating it stops every tool call with a 401.

*NOTE (scope of the kill): deactivation stops the whole agent (all users, all tools). To cut off one user without taking the agent down, use **Universal Logout**: the **"User session"** tab on the user's profile terminates their active sessions, so the next brokered call for that user fails. Use deactivation for "stop the agent," Universal Logout for "stop this person." Membership/certification revokes like 5.7 still take effect at the next token refresh (~1h on the org authorization server).*

### 5.9 Reactivate the agent

Leave the environment in a working state for the next attendee or your own further exploration.

1. Go to **Directory** > **AI Agents** > **TaskVantage Sales Agent** and click **Actions** > **Activate**.
2. Click **Confirm**.

Invoke the same tool as Kim again:

1. In the **Lab Toolkit**, choose **5) Invoke a tool**.
2. Select **Kim Liu (IT Help Desk)**.
3. Invoke **itsm.lookup_ticket** for ticket **TKT-1734**.

You get the same successful ticket lookup you saw at the end of Lab 4.

**What just changed:** the agent is **ACTIVE** again and Kim's standing access works as before. Frank's revoked membership stays revoked: kill switches are reversible, certification decisions are not.

---

**End of lab. End of camp.** You've seen both halves of the access model. Modules 2 through 4 built the static configuration for the steady state: groups, access policy rules, scopes, managed connections. Module 5 layered the dynamic governance for the exceptions: group memberships that come and go via request, approval, time, and review, with a single kill switch when nothing else will do.

This is the camp's end-state architecture. Same agent, same access policy rules, but the group memberships those rules depend on respond to people (requests, approvals, reviews, incidents) at the speed of organizational life. That is what makes a governed AI agent different from an AI agent with an API key.
