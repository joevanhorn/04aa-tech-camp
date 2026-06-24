# O4AA Lab — Environment Requirements

Prerequisites the **lab environment must satisfy** for the user-facing modules to behave as written.
This is for the lab-engineering / platform team — it is **not** attendee-facing (the modules describe
what the user does and sees; the build requirements live here). See `README.md` for the
provisioning/setup scripts and order.

## MCP Adapter (the bridge)

- **Version ≥ 0.15.14.** Agent **deactivation** must kill all tool calls with a **401** (the Module 5.8
  kill switch). This is patched in `release/0.15.14` (porting to `main`). On older builds, deactivation
  only blocks *new* token exchanges while a session already holding a cached resource token keeps
  working until the token expires — i.e. the kill is **not** immediate. Module 5.8 is written assuming
  the patched behavior, so the deployed adapter must be ≥ 0.15.14.

- **Resource-token lifetime.** The adapter reuses the **Okta** token lifetime. Today that is **~1 hour**
  because the adapter brokers against the **org authorization server**. This is why a membership/
  certification **revoke** (Module 5.7) is not immediate — it takes effect at the next token re-mint.
  **Custom-authorization-server lifetimes** (which allow a shorter TTL, for snappier revocation in the
  classroom) are newly supported and being rolled in; set a short TTL for the lab build when available.
  Module 5.7 is written so it reads correctly at ~1h and points the attendee at the immediate levers
  (Universal Logout / agent deactivation); update the "~1 hour" figure if you shorten the TTL.

- **Agent wiring (already documented).** The agent-registration → CRM/Desk wiring chain has its own
  hard requirements (Okta agent↔app link via `appId`; `vantage-crm-as`/`vantage-desk-as` policy
  **active** with the agent **principal** pinned as a client; the **central** MCP host; clean adapter
  resource↔connection binding). See `../reference/e2e-walkthrough-findings.md` and
  `../reference/xaa-bridge-wiring-lessons.md`.

## Okta org provisioning (Module 5 / OIG)

- `provision_lab_org.py` must run with `--approver-login <admin>` so the requester (Frank) has a
  **manager** set — Module 5.4's manager-approval routing depends on it.
- The provisioner sets up the requestable-group machinery for Module 5.3–5.5 (OIN host app +
  `CRM Read - Cross-Functional` assignment + an active request-condition: requesters = EVERYONE,
  fixed **PT2H**, the org's pre-created *Requester's Manager Approval* sequence).
- The **certification campaign (5.6) is intentionally NOT provisioned** — the attendee builds it by
  hand in the module (review-then-build). No provisioning API exists for campaigns anyway.

## Verify-at-GA checklist (live-console label/path pass)

Certification campaigns, OIG request flows, and the adapter Admin UI are built/labelled in their
consoles. The modules carry `{HumanReview}` markers where exact UI labels/sub-paths still need a
confirmation pass against the live build at GA:

- **Module 2**: adapter Admin UI labels; VDI helper packaging + token delivery; Bedrock default-owner
  provisioning decision.
- **Module 3**: System Log event names / filter for `target.type eq "AIAgent"`.
- **Module 4**: the `Token Exchange` grant-type selector label; XAA grant-type URIs / token endpoints /
  claim names; whether a synced Desk connection auto-creates the adapter resource.
- **Module 5**: the in-app access-**catalog** label/sub-path under Access Requests; the end-user
  dashboard **Requests / My Access** label; **Pending my approval** sub-path; the campaign wizard's
  per-step field labels and minimum start offset. *(Verified already: nav path is Identity Governance >
  Access Certifications > Certification campaigns; Create campaign → Resource.)*
