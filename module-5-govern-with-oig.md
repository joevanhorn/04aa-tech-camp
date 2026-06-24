# Lab Module 5: Govern the Agent's Access with OIG [Estimate: 50 minutes]

## Objective

Watch OIG add dynamic governance on top of the static configuration you built in Modules 2 through 4. By the end of this lab you will have:

- Approved an end-user's access request and seen a new tool appear in the catalog for that user
- Launched a certification campaign and watched the same tool disappear when the access is revoked
- Exercised the kill switch — deactivating the agent and confirming that no user, regardless of standing entitlements, can use it until it is reactivated

This is the round-trip that proves governance is not a separate paperwork process — it is a live control surface over what the agent can do, for whom, right now.

## Scenario

You have built the static half of the access model: access policy rules tied to group membership, scoped at the authorization server. That governs the *steady state*. But real organizations are not in steady state. Engineering managers occasionally need CRM read access for cross-functional projects. Auditors want quarterly reviews of who has access to what. And when something goes wrong, the security team needs a single switch that stops everything.

Today, Frank Boone — the Engineering Director who saw zero tools in Lab 3.6 — requests temporary CRM access through OIG to support a cross-functional product launch. You'll approve his request, watch the same tool-listing script that returned zero tools in Lab 3 now return the full CRM tool set for Frank (access is binary today — joining the gated group grants all CRM tools), then launch a certification campaign that revokes the access and watch those tools vanish. Finally, you'll deactivate the agent entirely and confirm nobody — not even Kim, who has full standing access — can use it.

## Browser use for this lab

- Local browser for the Okta Admin Console (approval and certification flows).
- Virtual Desktop browser for Frank's end-user perspective on the Okta End-User Dashboard.
- Virtual Desktop terminal for the tool-listing and tool-invocation scripts.

---

### 5.1 What OIG adds on top of access policies

Everything you built in Modules 2 through 4 is *static*: access policy rules evaluate group membership and grant scopes accordingly. These rules are evaluated identically every time, by every user, until an admin edits them. That's the right model for predictable, role-driven access. It's the wrong model for everything else.

OIG layers four dynamic capabilities on top — all attached directly to the existing group, with no additional access constructs introduced:

| Capability | What it adds | Where you'll see it in this lab |
| --- | --- | --- |
| **Access catalog** | A list of requestable resources (groups, apps) that end users can discover and request through their OIG dashboard. | 5.2 |
| **Access requests** | End-user-initiated workflows with approver chains, justifications, and audit trails. | 5.3 – 5.4 |
| **Time-bound elevation** | Granted memberships have an expiration; OIG removes the user from the granted group automatically when the clock runs out. | 5.4 |
| **Access certifications** | Periodic or on-demand reviews where an owner certifies whether each user's access is still needed. | 5.6 |

The point is not to replace access policies. The point is to make the inputs they depend on — group memberships — responsive to time-bound business need without forcing admins to manually edit the directory every time.

### 5.2 Review the preconfigured OIG setup

The OIG building blocks for this lab — the requestable group Frank will ask for and its catalog configuration — have been preconfigured in your tenant. (The certification campaign is the one piece you'll build yourself, in 5.6.) The pattern is plain Okta IGA: groups are the unit of access, OIG layers the request/approval/time-bound/certification workflow directly on top of group membership. The access policy rule you reviewed in Lab 3.2 already handles the scope grant. No additional access constructs are involved.

Review what's there now.

**The cross-functional group and its access policy rule:**

You saw the rule in Lab 3.2 — it sits as rule 4 on `vantage-crm-as`, gating the group `CRM Read - Cross-Functional`. Confirm both are present:

- From the Admin Console, go to **Directory** > **Groups** and find `CRM Read - Cross-Functional`. It is empty — no members yet.
- Go to **Security** > **API** > `vantage-crm-as` > **Access Policies** and confirm rule 4 (`Cross-functional readers — access`) gates this group with the full `crm.*` scope set (every CRM rule grants the same set today — see Module 3.1).

Together, the rule and the group are the access machinery. They have been in place since Lab 1. The reason rule 4 has never fired in any of your script runs is simply that nobody has been a member of the gated group. That changes in 5.4.

**The group's access catalog configuration:**

The group has been published to the OIG access catalog so end users can discover and request membership through their End-User Dashboard.

- From the Admin Console, go to **Identity Governance** > **Access Requests** (this opens the governance Access Requests app), and find the access **catalog** there. `{HumanReview: confirm the in-app label/sub-path to the catalog}`
- Find the entry for the group `CRM Read - Cross-Functional`.
- Review the catalog configuration attached to the group:

| Property | Value |
| --- | --- |
| Resource | Group `CRM Read - Cross-Functional` |
| Description | Temporary read-only access to VantageCRM for engineering and other cross-functional users |
| Default duration | 2 hours (for this lab; production would be 30+ days) |
| Approval required from | The requester's manager |
| Eligible requesters | Anyone in `All Employees` |

*NOTE: The requestable resource here is the group itself. There is no entitlement bundle, no wrapper, no separate access construct. The catalog configuration — duration, approver, eligibility — attaches directly to the group. When approved, OIG adds the requester to this group with the configured duration. When the duration expires (or the membership is revoked via certification), OIG removes them. The access policy is unchanged through the whole lifecycle — only the membership moves.*

**The certification campaign (you'll build this one in 5.6):**

The group and its catalog entry are preconfigured for you. The **certification campaign is not** — you'll create it yourself in 5.6, then launch it. That's the camp's review-then-build pattern again: you reviewed the access machinery above; now you'll build the governance review that sits over it.

A certification campaign is a time-boxed review in which a reviewer confirms (certifies) or revokes each user's access to a resource. The one you'll build reviews active memberships in `CRM Read - Cross-Functional`:

| Property | Value (you'll set these in 5.6) |
| --- | --- |
| Scope | Active memberships in `CRM Read - Cross-Functional` |
| Reviewers | Resource owner (you), fallback group owner |
| Review duration | 7 days |

No need to create anything yet — you'll do it in 5.6, after Frank's membership has been granted (so the campaign has something to review).

### 5.3 Submit an access request as Frank

Switch perspectives. You will now act as Frank Boone, the requesting user.

- On the Virtual Desktop, open a new Chrome incognito window.
- Navigate to your Okta End-User Dashboard at `https://{{org_url}}` and sign in as Frank (`frank.boone@atko.email` / `{{persona_password}}`).
- Click the **Requests** tab (or **My Access** depending on the dashboard version `{HumanReview}`) and then **Request Access**.
- Browse or search for `CRM Read - Cross-Functional`.
- Click **Request**.
- Fill in:
  - **Justification**: `Supporting Q2 cross-functional product launch — need to review account context for sales team partners`
  - **Duration**: leave at default (2 hours)
- Click **Submit**.

Frank now sees the request status as **Pending Approval**. Close the incognito window.

### 5.4 Approve the request as Frank's manager

Switch back to your admin browser session. For this lab, the admin user (you) is configured as Frank's manager in the approval chain `{HumanReview}` — confirm how approver routing is set up in the lab's preconfigured directory.

- From the Admin Console, go to **Identity Governance** > **Access Requests** > **Pending my approval** `{HumanReview}` — verify menu path.
- Click into Frank's request.
- Review:
  - The requester (`frank.boone@atko.email`)
  - The requested access (membership in `CRM Read - Cross-Functional`)
  - The justification
  - The requested duration (2 hours)
- Click **Approve**.
- Optionally add an approver note: `Approved for Q2 launch support — please remove when complete`
- Click **Confirm**.

The request status moves to **Approved**. OIG adds Frank to the `CRM Read - Cross-Functional` group with an expiry timestamp 2 hours from now.

*NOTE: If you check **Directory** > **Groups** > `CRM Read - Cross-Functional` now, Frank should appear as a member. He will be automatically removed when the 2-hour clock runs out — or earlier, if you revoke via certification in 5.6.*

### 5.5 Verify Frank's tools appeared

This is the round-trip moment. Lab 3.6 returned zero tools for Frank because no rule matched him. Nothing about the access policy or its rules has changed since then. What changed is that Frank is now a member of `CRM Read - Cross-Functional`, so rule 4 fires for him.

```bash
~/Desktop/list-agent-tools.sh --user frank.boone@atko.email
```

Expected output:

```
Acting as: frank.boone@atko.email  (groups: Engineering, All Employees,
                                            CRM Read - Cross-Functional)
User-context token: minted for vantage-crm-as (aud api://vantage-crm)
Agent: TaskVantage Sales Agent (ACTIVE)

→ Calling MCP Adapter at https://mcp.{{lab_domain}}/tools
→ Adapter resolved effective scopes via vantage-crm-as:
    Matched rule 4 (Cross-functional readers — access): full crm.* set
      crm.accounts.read, crm.accounts.write, crm.contacts.read,
      crm.opportunities.read, crm.opportunities.write

6 tools available to this user:
  ▸ crm.lookup_account       Look up a customer account by name or ID
  ▸ crm.create_account       Create a new customer account
  ▸ crm.update_account       Update an existing account
  ▸ crm.lookup_contact       Look up a contact by name or email
  ▸ crm.lookup_opportunity   Look up an opportunity by name or stage
  ▸ crm.update_opportunity   Update an opportunity's stage, amount, or details

0 tools filtered out (scope not granted to this user).

6 tools filtered out (Desk scope not granted):
  ✗ itsm.lookup_ticket, itsm.create_ticket, itsm.update_ticket,
    itsm.lookup_incident, itsm.update_incident, itsm.search_kb
```

Compare to Lab 3.6: 0 tools then, the full CRM set now. The agent did not change. Rule 4 did not change. The only change is Frank's group membership — and that propagated automatically through the same evaluation path that Alex's and Susan's memberships have always taken.

*NOTE: Frank gets the **full** CRM tool set, not a read-only slice, because access is binary today: matching any CRM rule grants all `crm.*` scopes (see Module 3.1). His row-level data visibility is still bounded by what `CRM Read - Cross-Functional` can see. A future graduated model would let the cross-functional grant be genuinely read-only at the tool level; that isn't wired yet — see `lab-infra/README.md`.*

### 5.6 Create and launch the certification campaign

Time passes. The Q2 launch wraps up. Per the security team's quarterly hygiene process, an access review fires — does Frank still need this access? You'll **create** the certification campaign you scoped out in 5.2, **launch** it, and act as the reviewer.

**Create the campaign.**

- From the Admin Console, go to **Identity Governance** > **Access Certifications** (left nav), and stay on the **Certification campaigns** tab.
- Click **Create campaign** and choose **Resource campaign** (the button is a menu — the other option is a *user* campaign; you want **Resource**). The campaign wizard opens.
- **Campaign details**: 
  - **Name**: `Quarterly review — AI agent CRM access`
  - **Description**: `Quarterly hygiene review of temporary CRM access granted to cross-functional users`
  - **Start**: the wizard defaults the start time to ~3 hours out. For the lab, set it to **now / the earliest the picker allows** so the campaign starts immediately instead of later. `{HumanReview: confirm the minimum start offset the UI permits}`
  - **Duration / review period**: `7 days`.
- **Resource**: pick resource type **Group** (the choices are **Application**, **Group**, **AI Agent** — plus **Collection** if that EA feature is enabled in the org), then select **`CRM Read - Cross-Functional`**. This scopes the campaign to that group's active memberships — exactly the people granted access through the request flow, Frank included.
- **Reviewer**: choose **Resource owner**. You are the owner for this lab, so the review lands in your queue.
- **Remediation**: set **On revoke** → **Remove access** (the page has two settings, *On revoke* and *No response*). This is what makes a **Revoke** decision actually pull the user out of the group. Leave **No response** at its default (it governs reviews left unanswered past the deadline).
- Finish the wizard and **Create**. The campaign lands in **Scheduled** state and becomes **Active** at the start time you set.

**Run it.**

- A campaign starts at its scheduled start time. If you set the start to now, it moves to **Active** shortly — open it from the **Active** tab. (If it's still under **Scheduled**, either wait for the start time or edit it earlier.)

The campaign is **Active**. As the reviewer, you have a queue of active memberships to review.

- From the campaign's page, find Frank's active membership in `CRM Read - Cross-Functional`.
- Click **Review** and choose **Revoke**.
- Reason: `Q2 launch completed — access no longer needed`
- Click **Confirm**.

OIG removes Frank from the `CRM Read - Cross-Functional` group immediately — his membership is revoked at the directory right away (check **Directory** > **Groups** to confirm). The agent's *tool access* reflects this a little later: see the timing note in 5.7.

*NOTE: In a real campaign, the reviewer would also have the option to **Certify** — confirming that the membership is still appropriate. For this lab, you exercised the revoke path. The certify outcome leaves the membership in place; revoke removes it. Both decisions are captured in the campaign's audit trail.*

### 5.7 Verify Frank's tools fall away

Frank's group membership is already gone (5.6). His access *through the agent* falls away on the next token refresh — see the timing note below before you run this.

Run the same script again:

```bash
~/Desktop/list-agent-tools.sh --user frank.boone@atko.email
```

Once the agent re-evaluates Frank's access, you'll see:

```
Acting as: frank.boone@atko.email  (groups: Engineering, All Employees)
User-context token: minted for vantage-crm-as (aud api://vantage-crm)
Agent: TaskVantage Sales Agent (ACTIVE)

→ Calling MCP Adapter at https://mcp.{{lab_domain}}/tools
→ Adapter resolved effective scopes via vantage-crm-as:
    (no rule matched — catch-all denies)

0 tools available to this user.
```

Frank is no longer in `CRM Read - Cross-Functional`. Rule 4 no longer matches. The catch-all denies again. Round-trip complete: Frank gained access through a request, exercised it during his project window, and lost it through certification — all without any edit to the access policy or to the agent's configuration. The full lifecycle is in the System Log: request submitted, approved, membership granted with expiry, membership revoked.

*NOTE — revocation timing: the membership change hits the directory **immediately**, but the agent keeps serving Frank the tools from his current access token until it's re-minted (a token lasts up to ~1 hour). So right after the revoke this script may still show 6 tools — the revoke is enforced at the **next** token exchange, not retroactively on a token already issued. To make a revoke take effect **now** instead of waiting out the token: end the user's sessions with **Universal Logout** (the "User session" tab, see 5.8), or deactivate the agent to stop everything (5.8).*

### 5.8 Exercise the kill switch — deactivate the agent

Imagine a scenario where the security team needs to stop the agent immediately. A compromised key, an unexpected behavior, a suspected misuse — whatever the cause, the response should be one action, not a multi-step rollback. That action is deactivation.

- From the Admin Console, go to **Directory** > **AI Agents** > **TaskVantage Sales Agent**.
- Click **Actions** > **Deactivate**.
- A confirmation dialog appears. Read it, then click **Confirm**.

Deactivating the agent **immediately kills every tool call through it** — the adapter returns **401** on any further request. That makes deactivation a true, instant kill switch.

The agent's status changes from **ACTIVE** to **DEACTIVATED**.

Verify the kill is real — try to use the agent as Kim Liu, who has full standing access through her IT Help Desk role:

```bash
~/Desktop/invoke-agent-tool.sh \
    --user kim.liu@atko.email \
    --tool itsm.lookup_ticket \
    --args '{"ticket_id":"TKT-1734"}'
```

Expected output:

```
Acting as: kim.liu@atko.email
Tool: itsm.lookup_ticket

→ Calling MCP Adapter…
✗ 401 Unauthorized — agent TaskVantage Sales Agent is DEACTIVATED.

No tool was invoked. The agent is offline.
```

Kim has done nothing wrong, has lost no group memberships. But because the agent is the broker of all access, deactivating the agent stops all activity through it — every tool call returns 401. That is the operational shape of an agent kill switch.

*NOTE — scope of the kill, and revoking a single user: deactivation kills the **whole agent** (all users, all tools). To cut off **one user** without taking the agent down, use **Universal Logout**: from the user's profile, the **"User session"** tab lets an admin terminate their active sessions, so the next brokered call for that user fails. Use deactivation for "stop the agent," Universal Logout for "stop this person." (Membership/certification revokes like 5.7 still take effect at the next token refresh — the token lifetime comes from Okta and is currently ~1h on the org authorization server; custom-authorization-server lifetimes, which allow a shorter TTL, are newly supported and being rolled in.)*

### 5.9 Reactivate the agent

Leave the environment in a working state for the next attendee or your own further exploration.

- From **Directory** > **AI Agents** > **TaskVantage Sales Agent**, click **Actions** > **Activate**.
- Click **Confirm**.

The agent returns to **ACTIVE**. Re-run the same invocation as Kim:

```bash
~/Desktop/invoke-agent-tool.sh \
    --user kim.liu@atko.email \
    --tool itsm.lookup_ticket \
    --args '{"ticket_id":"TKT-1734"}'
```

Expected output: the same successful ticket lookup you saw at the end of Lab 4. The agent is back online and Kim's standing access works as before. Frank's revoked membership remains revoked — kill switches are reversible, certification decisions are not.

---

**End of lab. End of camp.** You have now seen both halves of the access model. Modules 2 through 4 built the static configuration that handles the steady state — groups, access policy rules, scopes, managed connections. Module 5 layered the dynamic governance that handles the exceptions — group memberships that come and go via request, approval, time, and review, with a single kill switch when nothing else will do.

This is the camp's end-state architecture. Same agent, same access policy rules, but the group memberships those rules depend on respond to people — to requests, to approvals, to reviews, to incidents — at the speed of organizational life. That is what makes "governed AI agent" different from "AI agent with an API key."
