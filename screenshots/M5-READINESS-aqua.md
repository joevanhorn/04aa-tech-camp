# Module 5 screenshot-bot readiness — `demo-aqua-hoverfly-22341.okta.com`

Prep status for running `lab-screenshot` against the **rendered** guide
`screenshots/module-5.aqua.md` (18 `[SCREENSHOT]` markers). Companion to `RUNBOOK.md`.

- **Org:** `demo-aqua-hoverfly-22341.okta.com` (id `00o15aruocs4D6hi9698`)
- **Rendered guide:** `screenshots/module-5.aqua.md` (produced from `module-5.md`)
- **State:** pre-lab **baseline** (verified 32/0/0), **not** end-of-Module-4.

## TL;DR — marker readiness

| Tier | Count | Meaning |
| --- | --- | --- |
| **NOW** | **11** | Runnable against the current baseline + OIG (OIG admin-console + Frank's end-user flows). No agent, bridge, or VDI needed. |
| **NEEDS-AGENT** | **3** | Needs a registered + **ACTIVE** AI agent literally named **TaskVantage Sales Agent** (Okta admin-console screens; agent activation is GUI-only). |
| **NEEDS-BRIDGE** | **4** | Needs the full end-of-Module-4 stack: agent + paired **adapter/bridge** + wired CRM/Desk resources + a **VDI Lab Toolkit** pointed at this org. |

The 11 NOW markers can be captured today. The other 7 are gated on infrastructure that
cannot be stood up headlessly from this sandbox (GUI activation + a bridge/VDI we can't reach).

## Per-marker map (all 18)

| # | Section | Marker (abbrev.) | Tier | Gated on |
| --- | --- | --- | --- | --- |
| 1 | 5.2 | CRM Read - Cross-Functional group is empty | NOW | baseline group |
| 2 | 5.2 | vantage-crm-as access policy rule 4 gates the group | NOW | baseline crm-as (`aus15g048hlwQzjYZ698`) |
| 3 | 5.2 | Access Requests catalog entry (2h / manager approval) | NOW | OIG request-condition (ACTIVE) |
| 4 | 5.3 | Frank's dashboard request form, ready to submit | NOW | Frank login + OIG catalog |
| 5 | 5.3 | Frank's request shows Pending Approval | NOW | " |
| 6 | 5.4 | Pending-approval detail (requester/justification/2h) | NOW | admin = Frank's manager (set) |
| 7 | 5.4 | Request shows Approved | NOW | " |
| 8 | 5.4 | Group now shows Frank as member w/ expiry | NOW | " |
| 9 | 5.5 | Lab Toolkit: Frank's 6 CRM tools **USABLE** | **NEEDS-BRIDGE** | toolkit + agent + CRM resource |
| 10 | 5.6 | Certification campaign wizard configured | NOW | admin-console OIG |
| 11 | 5.6 | New campaign in Scheduled state | NOW | " |
| 12 | 5.6 | Active campaign, Frank's Revoke decision | NOW | " |
| 13 | 5.7 | Lab Toolkit: Frank's 6 CRM tools **BLOCKED** | **NEEDS-BRIDGE** | toolkit + agent + CRM resource |
| 14 | 5.8 | Deactivate confirmation dialog (TaskVantage Sales Agent) | **NEEDS-AGENT** | ACTIVE agent of that name |
| 15 | 5.8 | Agent page status DEACTIVATED | **NEEDS-AGENT** | " (GUI deactivate) |
| 16 | 5.8 | Lab Toolkit: Kim invoke → 401 (agent DEACTIVATED) | **NEEDS-BRIDGE** | toolkit + agent + Desk resource |
| 17 | 5.9 | Agent page status back to ACTIVE | **NEEDS-AGENT** | " (GUI activate) |
| 18 | 5.9 | Lab Toolkit: Kim invoke → TKT-1734 success | **NEEDS-BRIDGE** | toolkit + agent + Desk resource |

**NOW (11):** 1,2,3,4,5,6,7,8,10,11,12 &nbsp;•&nbsp; **NEEDS-AGENT (3):** 14,15,17 &nbsp;•&nbsp; **NEEDS-BRIDGE (4):** 9,13,16,18

## What's already done (baseline, verified)

- 5 groups, 5 personas (susan/alex/kim/frank/sally@atko.email); Frank → Engineering; Kim → IT Help Desk.
- **vantage-crm-as** `aus15g048hlwQzjYZ698` (aud `api://vantage-crm`, 5 crm scopes, `groups` claim,
  access policy with the 4 group rules incl. rule 4 for CRM Read - Cross-Functional, + toolkit read rule).
- NOMFA policy; **O4AA Lab Toolkit** OIDC app (`client_id 0oa15g04t9cGDhbvQ698`);
  **O4AA Adapter Admin UI** OIDC app (`client_id 0oa15g02p7jBPPHNp698`).
- **VantageCRM Access Requests** OIN host app (`scim2testapp_basic`) + OIG request-condition
  `rco113dynoFphUdSy697` (**ACTIVE**, EVERYONE / PT2H / manager approval); Frank's manager = `joe.vanhorn@okta.com`.
- **VantageCRM Example Agent** `wlp15g085np9KWK1H698` (**STAGED**) + its CRM managed connection.

This baseline satisfies all 11 NOW markers, including the full OIG request→approve→certify round trip
Frank drives in 5.2–5.4 and 5.6.

## Bridge / adapter investigation — none reachable

Probed the likely adapter/admin hostnames for this org; **no bridge is reachable**:

| Host | Result |
| --- | --- |
| `adapter.demo-aqua-hoverfly-22341.oktademo.app` | NXDOMAIN |
| `admin.demo-aqua-hoverfly-22341.oktademo.app` | NXDOMAIN |
| `adapter.aqua-hoverfly-22341.oktademo.app` | NXDOMAIN |
| `adapter.hoverfly-22341.oktademo.app` | NXDOMAIN |
| `adapter.demo-aqua-hoverfly-22341.okta.com` | resolves only via the Okta `*.okta.com` wildcard (18.209.113.128); `GET /api/admin/resources` fails to connect (`000`) — not an adapter |

There is also **no `vantage-desk-as`** on the org (auth servers present: `default`, `vantage-crm-as` only)
and **no agent named "TaskVantage Sales Agent"** (only the STAGED example agent). So every NEEDS-* marker
is currently blocked. Reaching end-of-Module-4 requires the ordered work below.

---

## Remaining work to reach end-of-Module-4 (unblocks the 7 markers)

Reference scripts live in `taskvantage-apps/deploy/`. Central hosts are already live:
MCP `mcp.taskvantage-demo.com`; apps `vantagecrm/vantagedesk.taskvantage-demo.com`.

### Step A — Register + activate "TaskVantage Sales Agent"  *(unblocks 14, 15, 17)*
The 3 NEEDS-AGENT markers are pure Okta admin-console screens of this agent; they need it to exist
and be ACTIVE, but **not** the bridge/toolkit.

1. Register the agent in Okta (Directory > AI Agents, or `POST /workload-principals/api/v1/ai-agents`
   `{"profile":{"name":"TaskVantage Sales Agent"}}`). The name must match the guide exactly.
2. **Assign an owner, then Activate — GUI only.** AI-agent activation greys out until an owner is set,
   and the API `lifecycle/activate` no-ops silently. Do owner + Activate in the Admin Console
   (this is the one manual GUI step; cannot be done headlessly).

> If you only need markers 14/15/17 (agent status screens) and are willing to skip the toolkit
> invoke shots (16/18), Step A + a browser is sufficient — B–F are not required for those three.

### Step B — Build `vantage-desk-as`  *(prereq for 16, 18)*
Mirror `vantage-crm-as`: audience `api://vantage-desk`, the 5 `itsm.*` scopes, a `groups` claim, an
access policy (ALL_CLIENTS + XAA grant types) with an **IT Help Desk** rule (only Kim's group gets ITSM).
**Not built here — documented in the Appendix** (see "Optional build" note below). Turnkey API sequence there.

### Step C — Pair an adapter (bridge) for the org  *(prereq for 9, 13, 16, 18)*
Deploy/obtain a Module-4 adapter bound to this org (the lab platform normally does this per attendee),
then, using the recipe validated in prior runs:
- adapter `POST /api/admin/agents/{slug}/credentials/generate-keypair` (adapter holds the private key;
  the kid must be an ACTIVE Okta app credential kid);
- create the agent's OIDC sign-on app (token-exchange grant, redirect `…/oauth/callback`);
- **link** it via `PUT /workload-principals/api/v1/ai-agents/{id}` with `appId` (async 202; not clientId);
- in **both** crm-as and desk-as access policies, **pin the agent principal** (`wlp…`) — ALL_CLIENTS does
  not match the agent's private_key_jwt assertion (0 tools otherwise).

### Step D — Wire CRM + Desk adapter resources  *(unblocks 9, 13 via CRM; 16, 18 via Desk)*
```bash
export ADAPTER_ADMIN_TOKEN="<okta org-AS admin bearer>"   # e.g. Admin-UI session token
# CRM (Frank's USABLE/BLOCKED listings 9,13):
python deploy/wire_adapter_resource.py --preset crm \
    --adapter https://<adapter-host> --okta-agent-id <TaskVantage-Sales-Agent wlp id> \
    --auth-server-id aus15g048hlwQzjYZ698 --mcp-host mcp.taskvantage-demo.com \
    --org-domain demo-aqua-hoverfly-22341.okta.com --okta-token <SSWS> 
# Desk (Kim's invoke 16,18):
python deploy/wire_adapter_resource.py --preset desk \
    --adapter https://<adapter-host> --okta-agent-id <wlp id> \
    --auth-server-id <vantage-desk-as id from Step B> --mcp-host mcp.taskvantage-demo.com \
    --org-domain demo-aqua-hoverfly-22341.okta.com --okta-token <SSWS>
```
Verify each ends `OK: … wired (INCLUDE_ONLY, N scopes)`. (Managed connection must be INCLUDE_ONLY with
granular scopes or the adapter falls back to `mcp:read` → 0 tools.)

### Step E — Enroll the org in the central apps  *(prereq for any Toolkit data call: 9,13,16,18)*
```bash
export ADMIN_API_KEY="$(aws secretsmanager get-secret-value --secret-id labapps-admin-api-key \
    --region us-east-2 --query SecretString --output text)"
python deploy/enroll_tenant.py enroll https://demo-aqua-hoverfly-22341.okta.com
```
One enroll covers both VantageCRM and VantageDesk (shared Redis registry).

### Step F — VDI with the Lab Toolkit pointed at this org  *(the capture surface for 9,13,16,18)*
- A Windows VDI reachable in the lab browser, with the **Lab Toolkit** installed and its
  `toolkit.config.json` set to: org `demo-aqua-hoverfly-22341.okta.com`, toolkit `client_id`
  **`0oa15g04t9cGDhbvQ698`**, and the adapter URL from Step C.
- Enroll **Kim** and **Frank** TOTP for the no-MFA/persona flows as needed (`~/o4aa-totp-kim.liu`,
  `~/o4aa-totp-frank.boone` exist but are org-specific — re-enroll for aqua).
- The Toolkit's menu items 4 (list tools) and 5 (invoke tool) produce the 9/13/16/18 screens.

**Order:** A and B are independent; C depends on A+B; D depends on C; E is independent (do anytime before a
data call); F depends on C/D/E. Sequence: **A ∥ B → C → D → E → F**.

---

## Task-3 note — `vantage-desk-as` was intentionally **not** built (documented instead)

Per the task's "build only if confident, else document," I chose to document. Rationale:
1. The org is a **verified-clean 32/0/0 baseline**; adding a desk-as (AS + scopes + claim + policy + rule)
   deviates from that controlled baseline.
2. Building desk-as **alone unblocks zero markers** — all 4 markers it participates in (16,18 need Desk;
   9,13 need CRM) also require the unreachable bridge + VDI toolkit and the GUI-activated agent. There is
   no partial-credit screenshot gained by creating the AS now.
3. The exact structure is turnkey below; build it as part of Step B when the full stack is assembled.

**Appendix — exact `vantage-desk-as` build (SSWS, mirrors `vantage-crm-as`):**
```
POST /api/v1/authorizationServers
  {"name":"vantage-desk-as","description":"O4AA lab — VantageDesk resource AS",
   "audiences":["api://vantage-desk"]}
# 5 scopes (consent IMPLICIT, metadataPublish ALL_CLIENTS):
POST /api/v1/authorizationServers/{asid}/scopes  {"name":"itsm.tickets.read", ...}
   itsm.tickets.read, itsm.tickets.write, itsm.incidents.read, itsm.incidents.write, itsm.kb.read
# groups claim (RESOURCE / GROUPS / value ".*" / REGEX / alwaysIncludeInToken true):
POST /api/v1/authorizationServers/{asid}/claims  {"name":"groups", ...}
# policy (ALL_CLIENTS) + activate:
POST /api/v1/authorizationServers/{asid}/policies
  {"type":"OAUTH_AUTHORIZATION_POLICY","name":"VantageDesk access policy",
   "conditions":{"clients":{"include":["ALL_CLIENTS"]}}}
# rule — IT Help Desk group, full itsm scopes, XAA grant types:
POST /api/v1/authorizationServers/{asid}/policies/{pid}/rules
  {"type":"RESOURCE_ACCESS","name":"IT help desk — full access","priority":1,
   "conditions":{"grantTypes":{"include":[
       "urn:ietf:params:oauth:grant-type:token-exchange",
       "urn:ietf:params:oauth:grant-type:jwt-bearer"]},
     "scopes":{"include":[<5 itsm scopes>]},
     "people":{"users":{"exclude":[]},"groups":{"include":["<IT Help Desk group id>"]}}}}
# (add a "Lab toolkit — read (auth code)" rule if the Toolkit mints desk tokens directly, per the CRM pattern)
```
Then, in Module 4's flow, pin the agent principal in this policy and wire the Desk adapter resource (Step D).

---

## Persona password — FLAGGED, unresolved

The rendered guide's Frank sign-in (5.3) carries a **placeholder token**, not a real password:

> `<<PERSONA_PASSWORD — obtain from Heropa>>`

Reason: this org was Heropa-provisioned, and the local shared value (`~/o4aa-lab-password`) **does not
authenticate** against aqua — a primary-auth check for `frank.boone@atko.email` and `susan.potter@atko.email`
both returned `401 Authentication failed`. No aqua-specific password is stored anywhere on this host
(no `aqua/hoverfly` references in memory or repos; `o4aa-env2/3` are unrelated WinRM dirs).

**Action before a run:** obtain the persona password for this Heropa instance and replace the token in
`screenshots/module-5.aqua.md` (single occurrence, line ~103). Do not commit the real value.
