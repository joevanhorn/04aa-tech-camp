# Lab Module 5: Govern the Agent's Access with OIG [Estimate: 50 minutes]

## Objective

Watch OIG add dynamic governance on top of the static configuration you built in Modules 2 through 4. By the end of this lab you will have:

- Approved an end-user's access request and seen a new tool appear in the catalog for that user
- Launched a certification campaign and watched the same tool disappear when the access is revoked
- Exercised the kill switch — deactivating the agent and confirming that no user, regardless of standing entitlements, can use it until it is reactivated

This is the round-trip that proves governance is not a separate paperwork process — it is a live control surface over what the agent can do, for whom, right now.

## Scenario

You have built the static half of the access model: access policy rules tied to group membership, scoped at the authorization server. That governs the *steady state*. But real organizations are not in steady state. Engineering managers occasionally need CRM read access for cross-functional projects. Auditors want quarterly reviews of who has access to what. And when something goes wrong, the security team needs a single switch that stops everything.

Today, Frank Boone — the Engineering Director who saw zero tools in Lab 3.6 — requests temporary CRM read access through OIG to support a cross-functional product launch. You'll approve his request, watch the same tool-listing script that returned zero tools in Lab 3 now return three for Frank, then launch a certification campaign that revokes the access and watch those tools vanish. Finally, you'll deactivate the agent entirely and confirm nobody — not even Kim, who has full standing access — can use it.

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

The OIG building blocks for this lab — the requestable group Frank will ask for, its catalog configuration, and the certification campaign you will launch later — have all been preconfigured in your tenant. The pattern is plain Okta IGA: groups are the unit of access, OIG layers the request/approval/time-bound/certification workflow directly on top of group membership. The access policy rule you reviewed in Lab 3.2 already handles the scope grant. No additional access constructs are involved.

Review what's there now.

**The cross-functional group and its access policy rule:**

You saw the rule in Lab 3.2 — it sits as rule 4 on `vantage-crm-as`, gating the group `CRM Read - Cross-Functional`. Confirm both are present:

- From the Admin Console, go to **Directory** > **Groups** and find `CRM Read - Cross-Functional`. It is empty — no members yet.
- Go to **Security** > **API** > `vantage-crm-as` > **Access Policies** and confirm rule 4 (`Cross-functional readers — read access`) gates this group with the three read scopes.

Together, the rule and the group are the access machinery. They have been in place since Lab 1. The reason rule 4 has never fired in any of your script runs is simply that nobody has been a member of the gated group. That changes in 5.4.

**The group's access catalog configuration:**

The group has been published to the OIG access catalog so end users can discover and request membership through their End-User Dashboard.

- From the Admin Console, go to **Identity Governance** > **Catalog** `{HumanReview}` — verify exact path and UI label for the access catalog.
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

**The certification campaign:**

- Still in **Identity Governance**, go to **Access Certifications** > **Campaigns** `{HumanReview}` — verify menu path.
- Find the campaign named `Quarterly review — AI agent CRM access`. Status should be **Draft** or **Ready to launch**.
- Click into it and review its configuration:

| Property | Value |
| --- | --- |
| Scope | Active memberships in `CRM Read - Cross-Functional` |
| Reviewers | Resource owner (fallback: group owner) |
| Review duration | 7 days |

You will launch this campaign in 5.6, after Frank's membership has been granted.

### 5.3 Submit an access request as Frank

Switch perspectives. You will now act as Frank Boone, the requesting user.

- On the Virtual Desktop, open a new Chrome incognito window.
- Navigate to your Okta End-User Dashboard at `https://{{org_url}}` and sign in as Frank (`frank.boone@atko.email` / `Tra!nme4321`).
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
Sign-in app: TaskVantage Agent UI (active session simulated)
Agent: TaskVantage Sales Agent (ACTIVE)

→ Calling MCP Adapter at https://mcp.{{lab_domain}}/tools
→ Adapter resolved effective scopes via vantage-crm-as:
    Matched rule 4 (Cross-functional readers — read access):
      crm.accounts.read, crm.contacts.read, crm.opportunities.read

3 tools available to this user:
  ▸ crm.lookup_account       Look up a customer account by name or ID
  ▸ crm.lookup_contact       Look up a contact by name or email
  ▸ crm.lookup_opportunity   Look up an opportunity by name or stage

3 tools filtered out (scope not granted to this user):
  ✗ crm.create_account, crm.update_account, crm.update_opportunity

6 tools filtered out (Desk scope not granted):
  ✗ itsm.lookup_ticket, itsm.create_ticket, itsm.update_ticket,
    itsm.lookup_incident, itsm.update_incident, itsm.search_kb
```

Compare to Lab 3.6: 0 tools then, 3 now. The agent did not change. Rule 4 did not change. The only change is Frank's group membership — and that propagated automatically through the same evaluation path that Alex's and Susan's memberships have always taken.

### 5.6 Launch the certification campaign

Time passes. The Q2 launch wraps up. Per the security team's quarterly hygiene process, an access review fires — does Frank still need this access? You will launch the preconfigured campaign you reviewed in 5.2 and act as the reviewer.

- From the Admin Console, go to **Identity Governance** > **Access Certifications** > **Campaigns**.
- Open the `Quarterly review — AI agent CRM access` campaign.
- Click **Launch Campaign**.

The campaign is now **In Progress**. As the reviewer, you have a queue of active memberships to review.

- From the campaign's page, find Frank's active membership in `CRM Read - Cross-Functional`.
- Click **Review** and choose **Revoke**.
- Reason: `Q2 launch completed — access no longer needed`
- Click **Confirm**.

OIG immediately removes Frank from the `CRM Read - Cross-Functional` group. His membership is revoked.

*NOTE: In a real campaign, the reviewer would also have the option to **Certify** — confirming that the membership is still appropriate. For this lab, you exercised the revoke path. The certify outcome leaves the membership in place; revoke removes it. Both decisions are captured in the campaign's audit trail.*

### 5.7 Verify Frank's tools are gone

Run the same script one more time:

```bash
~/Desktop/list-agent-tools.sh --user frank.boone@atko.email
```

Expected output:

```
Acting as: frank.boone@atko.email  (groups: Engineering, All Employees)
Sign-in app: TaskVantage Agent UI (active session simulated)
Agent: TaskVantage Sales Agent (ACTIVE)

→ Calling MCP Adapter at https://mcp.{{lab_domain}}/tools
→ Adapter resolved effective scopes via vantage-crm-as:
    (no rule matched — catch-all denies)

0 tools available to this user.
```

Frank is no longer in `CRM Read - Cross-Functional`. Rule 4 no longer matches. The catch-all denies again. Round-trip complete: Frank gained access through a request, exercised it during his project window, and lost it through certification — all without any edit to the access policy or to the agent's configuration. The full lifecycle is in the System Log: request submitted, approved, membership granted with expiry, membership revoked.

### 5.8 Exercise the kill switch — deactivate the agent

Imagine a scenario where the security team needs to stop the agent immediately. A compromised key, an unexpected behavior, a suspected misuse — whatever the cause, the response should be one action, not a multi-step rollback. That action is deactivation.

- From the Admin Console, go to **Directory** > **AI Agents** > **TaskVantage Sales Agent**.
- Click **Actions** > **Deactivate**.
- A confirmation dialog appears. Read it — note that deactivation stops new token issuance but does not retroactively revoke tokens already in flight. The ID-JAG's 5-minute TTL bounds your exposure window.
- Click **Confirm**.

The agent's status changes from **ACTIVE** to **DEACTIVATED**.

Verify the kill is real — attempt to use the agent as Kim Liu, who has full standing access through her IT Help Desk role:

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

→ Adapter performing XAA token exchange (step 1)
✗ Token exchange failed: agent TaskVantage Sales Agent is DEACTIVATED.
   The IdP refused to issue an ID-JAG.

No call was made to the MCP server. No tool was invoked. The agent is offline.
```

Kim has done nothing wrong, has lost no group memberships. But because the agent is the broker of all access, deactivating the agent stops all activity through it. That is the operational shape of an agent kill switch.

*NOTE: For real-time revocation of tokens already issued (not just blocking new issuance), Okta's Universal Logout feature targets active sessions across linked apps. Universal Logout coverage for AI agents specifically is on the product roadmap — for today's lab, deactivation plus the short ID-JAG TTL is the practical kill switch. `{HumanReview}` — confirm Universal Logout for AI Agents status at lab GA and update this section if it has shipped.*

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
