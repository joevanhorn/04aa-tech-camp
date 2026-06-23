# O4AA Lab Infrastructure — Environment Automation

Scripts that stand up, wire, and reset a **dedicated O4AA Tech Camp lab environment** (one Okta org +
the attendee's MCP Adapter), for the lab engineering team to review and own. They are mirrored here
from `taskvantage-apps/deploy/` (the canonical source); keep them in sync if you change either copy.

These were built and **validated end-to-end** against a live preview org + the shared central apps /
MCP server (see `../reference/crm-path-validation-runbook.md` for the full play-by-play and
`../reference/xaa-bridge-wiring-lessons.md` for the failure modes). All are **idempotent, stdlib-only
Python** (plus one bash wrapper); most take `--dry-run`.

## The lab environment, end to end

```
 ┌─ per-attendee Okta org ─────────────┐     ┌─ central, shared (taskvantage acct) ─┐
 │ groups + 4 personas                 │     │ VantageCRM / VantageDesk (API-only)  │
 │ vantage-crm-as (+4-rule policy)     │     │ central MCP server (/crm/mcp,/desk)  │
 │ [attendee builds: agent, sign-on    │     └──────────────────────────────────────┘
 │  app, vantage-desk-as in the lab]   │     ┌─ per-attendee MCP Adapter (the bridge)┐
 └─────────────────────────────────────┘     │ deployed by the lab platform's CFN    │
                                              └───────────────────────────────────────┘
```

## Setup order (per attendee org)

1. **`provision_lab_org.py`** — empty Okta org → lab-ready pre-state. Creates the 5 groups, the 4
   persona users (susan/alex/kim/frank@atko.email, group-mapped), and `vantage-crm-as` (audience
   `api://vantage-crm`, the 5 `crm.*` scopes, a **`groups` claim**, and the **4-rule per-user policy**
   that drives Module 3's tool filtering — assigned `ALL_CLIENTS` with the XAA grant types).
   ```bash
   export OKTA_ORG=https://<org>.okta.com OKTA_API_TOKEN=<SSWS super-admin>
   export LAB_USER_PASSWORD='<persona login password>'
   python provision_lab_org.py            # --dry-run to preview
   ```
2. **`enroll_tenant.py`** — trust the org in the central apps (so tokens minted under its issuer are
   accepted). Needs the apps operator key (`labapps-admin-api-key`, taskvantage acct).
   ```bash
   ADMIN_API_KEY=<apps operator key> python enroll_tenant.py enroll https://<org>.okta.com
   ```
3. **MCP Adapter (the bridge)** — deployed by the **lab platform's** own CFN automation (not in this
   folder). See "Bridge provisioning gotchas" below — two real ones bit us.
4. *(attendee, during the lab)* registers the agent (Module 2.3-2.7).
5. **`setup-crm-resource.sh`** → wraps **`wire_adapter_resource.py`** — pre-wires the attendee's
   **CRM** end to end (the worked example): creates the agent's `INCLUDE_ONLY crm.*` managed connection
   in Okta, imports the agent into the adapter, marks it DCR-selectable, syncs, and registers the CRM
   resource at `https://<mcp-host>/crm/mcp`. The attendee builds the **Desk** equivalent by hand in
   Module 4. (`wire_adapter_resource.py --preset desk …` is the same automation if you ever need it.)
   ```bash
   export OKTA_API_TOKEN=<org SSWS>  ADAPTER_ADMIN_TOKEN=<adapter admin bearer>
   export ORG_DOMAIN=<org>.okta.com  ADAPTER_HOST=https://<attendee-adapter>
   ./setup-crm-resource.sh
   ```
   **Token delivery is an open lab-engineering decision** — the wrapper carries an inline
   `LAB ENGINEERING CALLOUT` block with the options (VDI env vars / secret store / provisioning
   injection). Don't bake long-lived secrets into the VDI image.

## Reset between iterations

**`reset_lab.py`** — wipe only the attendee-built artifacts (agent, sign-on app, `vantage-desk-as`,
Frank's temporary cross-functional grant); the pre-state from step 1 is preserved. Optional
adapter-side agent delete with `--adapter`/`--adapter-token`.
```bash
python reset_lab.py --dry-run        # then without --dry-run
```

## Bridge provisioning gotchas (found validating against a live preview org)

Both bit the lab platform's bridge CFN during testing — flagging for the team that owns it:

1. **AI Agents API: scope is necessary but not sufficient — the management app needs an admin ROLE.**
   The bridge creates an Okta-management app and grants it `okta.aiAgents.read/manage` + `okta.apps.read`,
   then calls the AI Agents API — which **403s (`E0000006`) until that app also holds an Okta admin
   role** (super-admin, or a custom role with AI-Agent admin permission). These read-403s don't emit a
   System-Log FAILURE, so the log looks clean while the stack rolls back. **Fix: after the scope grant,
   assign the management app an admin role** (`POST /oauth2/v1/clients/{clientId}/roles`). Same gotcha
   we documented wiring the bridge by hand (see the runbook's "Admin API access").

2. **AWS VPC / Internet-Gateway limit (5/region).** The CFN creates its own VPC + IGW; a demo account
   at the 5-VPC cap fails with `VpcLimitExceeded` / max-internet-gateways and rolls back. Options: point
   the stack at a region with headroom, raise the `L-F678F1CE` (VPC) + `L-A4707A72` (IGW) quotas, or
   free a VPC. Ideally the CFN supports a **bring-your-own-VPC** parameter to avoid creating one.

## Notes
- Persona row-level visibility keys on the token `sub` (= the user's Okta `userName`) matching the seed
  owner emails, and on the **`groups` claim** — both vantage AS must emit `groups` (Module 3/5). The
  app also references a group literally named **"Sales Management"**; `provision_lab_org.py` creates it.
- After an **adapter restart**, hydrated resources can drop their granular scopes and fall back to
  `mcp:read` → re-run `setup-crm-resource.sh` (it re-syncs). See the runbook.
- Canonical source: `taskvantage-apps/deploy/`. This copy is for lab-engineering review/sync.
