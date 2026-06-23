# O4AA E2E Walkthrough — Findings Log

Live, module-by-module walkthrough of the lab guide against the dedicated reset-able
org `demo-o4aa-techcamp-testing.okta.com` + its adapter
`adapter.o4aa-techcamp-testing.oktademo.app`. Each issue is flagged here as found; a
cleanup sprint follows the walkthrough.

Severity: **[BUG]** breaks the lab / **[DOC]** guide inaccurate / **[NIT]** polish / **[Q]** open question.

> **Docs sub-agent (branch `docs/reconcile-central-mcp`, pushed, not merged).** Tasked with
> reconciling docs to the central-MCP model, it found the **architecture was already correct**
> (no edits) and the *actual* stale content was the **per-user tool-filtering story**: Modules
> 1/3/4/5 + intro documented a **graduated** model (rep=3 tools, mgr=6, Kim=8, Frank-via-OIG=3
> read) that contradicts the live **binary** reality. It rewrote those to binary on the branch
> (Alex=6, Kim=12, Frank-post-OIG=full 6). This overlaps several Module-1/3 findings below —
> they're partly pre-addressed on that branch; fold it into the cleanup sprint.
>
> **RESOLVED by the adapter maintainer (design intent, not a gap):** tool *visibility* is
> **resource-based, not user-based** — the adapter exposes whatever tools the MCP server provides
> for a linked resource. Per-user differentiation is **data/application-layer** (`require_scope`
> for capability + `groups` row-filtering for data). So the binary tool model is correct **by
> design**; graduated per-*tool* filtering is explicitly NOT an adapter responsibility and should
> not be framed as a missing feature. The camp's "different access per persona" story lives on two
> real axes: (1) **resource granularity** — genuine tool-level differences (Frank=0 tools since no
> managed-connection grant → XAA fails; Alex/Susan=CRM resource's tools; Kim=CRM+Desk); (2)
> **within a resource** — data-layer (row filtering + `require_scope` 403s on unpermitted calls).
> The docs should teach this model rather than present binary as a shortfall. Ship binary as-is.

---

## Reset (pre-walkthrough)

- **[BUG] `reset_lab.py` deletes the AI agent before deactivation propagates → HTTP 400.**
  The script issues `lifecycle/deactivate` then `DELETE` back-to-back. Deactivate succeeds
  (agent → INACTIVE) but the immediate DELETE 400s because the status change hasn't
  propagated. Retrying DELETE a few seconds later returns 202 and the agent deletes.
  *Fix:* after deactivate, poll the agent status until INACTIVE (or retry DELETE with
  backoff) before reporting success. Today the script prints "deleted (HTTP 400)" — both
  misleading (it didn't delete) and a swallowed error.

- **[Q] AI-agent DELETE is async (202 + eventual 404).** Reset "complete" is reported before
  the agent is actually gone (GET still 200 for a few seconds). For an automated
  reset→re-provision loop, add a poll-until-404 so a re-register doesn't collide with a
  not-yet-deleted agent of the same name.

- **[Q] `reset_lab.py` does not restore the `vantage-crm-as` access-policy rules.** If an
  attendee pinned their agent's client into the rules (new Module 2.11), those stale client
  refs would persist across resets. In this iteration the rules were already `ALL_CLIENTS`,
  so nothing to clean — but the reset should explicitly reassert `ALL_CLIENTS` (or the
  provisioned pre-state) on every rule to be iteration-safe.

- **[BUG] `provision_lab_org.py` is not idempotent across rule renames — re-provisioning
  duplicates policy rules.** The provisioner matches `vantage-crm-as` rules **by name**, so
  when the binary change renamed rules ("Sales reps — read access" → "Sales reps — full
  access"), re-running it created the new-named rules **alongside** the old ones — 7 rules
  instead of 4 (two per group). A clean fresh-org run only makes 4, so this only bites on
  re-provision after a rename, but the lab team will hit it. *Fix:* match rules by a stable
  key (priority or a metadata tag), or reconcile by deleting rules not in `CRM_RULES` before
  creating. Cleaned up by hand this iteration (deleted the 3 orphan "read/limited" rules).

- **[Q] Gotcha-6 / Module 2.11 may be environment-specific.** Before reset, all four
  `vantage-crm-as` rules were `ALL_CLIENTS`, yet the prior persona validation passed
  (Alex/Susan got real CRM data via XAA STEP 3 jwt-bearer). That contradicts the taskvantage
  finding that `ALL_CLIENTS` does NOT cover the agent-principal jwt-bearer leg
  (`no_matching_policy`). **Verify during Module 2/3 of this walkthrough whether pinning the
  agent client is actually required in this adapter config** — if `ALL_CLIENTS` works here,
  Module 2.11 is either unnecessary or only needed on certain adapter versions, and the step
  text should say so.

---

## Module 1 — Environment Tour

Good news: Module 1 already reflects the central-MCP / API-only model (ADR-0002 callout, §1.5–1.7,
binary-access NOTE in §1.10). The remaining issues are guide-vs-reality mismatches:

- **[BUG] Persona password mismatch.** §1.3 says "All passwords are `Tra!nme4321`", but
  `provision_lab_org.py` sets the persona password from `$LAB_USER_PASSWORD` (the test env uses
  `O4aaLab!Tc2026#`). An attendee following the guide can't log in as a persona. *Fix:* make the
  provisioner set the exact password the guide documents (or template the password into the guide).

- **[DOC/Q] §1.3 lists a 5th persona "Sally Field — Executive" that the provisioner never creates.**
  Only alex/susan/kim/frank exist. Either add Sally to `provision_lab_org.py` (she's described as
  "indirect access only — uses the agent rather than apps directly", which could be a nice Module 3/5
  beat) or drop her from the guide. Decision needed.

- **[DOC] §1.4 group table is incomplete and slightly off.** It lists Sales Reps, Sales Management,
  IT Help Desk, **All Employees**. Live/provisioned groups are Sales Management, Sales Reps,
  IT Help Desk, **CRM Read - Cross-Functional**, **Engineering** (+ built-in **Everyone**). The guide
  omits Engineering (Frank's group) and CRM Read - Cross-Functional (used in the Lab 5 OIG round-trip),
  and "All Employees" should be "Everyone" (the built-in). *Fix:* reconcile the table to the
  provisioner's groups.

- **[DOC] §1.3 persona descriptions contradict the binary access model.** §1.3 says Alex has
  "Limited CRM access; cannot create accounts" and Kim is "read-only on CRM". Under the binary model
  every CRM-group member's token carries the **full** `crm.*` set, so Alex **does** get the
  `crm.accounts.write` tool — he can create accounts at the tool level; the only Alex-vs-Susan
  difference is **row-level data** (Alex sees his 2 owned accounts, Susan sees all 8). §1.5/§1.10
  already reframe this as data-level, but §1.3's table still implies tool/scope-level limits. *Fix:*
  align §1.3 with the binary reality (or note graduated per-persona tool limits are the deferred
  follow-up). This also softens the Module 3 "different tools per persona" story — see Module 3.

- **[OK] §1.7 tool count says "12 tools (6 CRM + 6 Desk)"** — consistent with the spec; the stale
  "14 tools" lives in the architecture doc (sub-agent reconciling). Will confirm the live count = 12
  during Module 3 (CRM=6 already observed; need Desk=6).

- **[OK] §1.9 `vantage-crm-as`** — audience `api://vantage-crm`, 5 `crm.*` scopes, `groups` claim:
  matches the live AS (`aus14gb7aiipxSaUH698`).

---

## Module 2 — Register Agent + Wire CRM

Re-registered the agent fresh (`wlp14gy6bezRcJ4zb698`). Findings on the underlying ops
(the lab does these in the GUI; relevant for the lab-platform's automation + example-agent
pre-wiring):

- **[Q/BUG] AI-agent OWNER assignment (§2.4) is not exposed on the public API.**
  `/workload-principals/api/v1/ai-agents/{id}/owners` returns **405 for GET/POST/PUT** (every
  method). Owner assignment appears to be GUI-only (admin internal API). Since owner is *required*
  for activation, any automated staging/reset of agents (incl. the example agent) can't set the
  owner via the documented public API — it needs the GUI or an internal endpoint. Flag for the
  platform team. (Did it via Playwright GUI for this run.)

- **[RESOLVED] AI-agent ↔ OIDC-app link (§2.6) IS API-achievable — via `appId`, asynchronously.**
  The field is **`appId`** (not `clientId`, which the schema rejects). `PUT
  /workload-principals/api/v1/ai-agents/{id}` with `{profile, platform, appId}` returns **202** and
  the link applies a few seconds later (poll for it). The earlier 405s were wrong-method/path noise.
  So automation CAN link the app headlessly; the `fetch-secret` path then works too. (Still: this
  link is **mandatory** for XAA — see below.)
  The adapter's `fetch-secret` depends on this Okta-side link — it 502s with *"AI Agent has no
  linked OAuth app"* until the link exists. **Workaround that works for brokering:** configure the
  adapter agent directly — `PUT /api/admin/agents/{slug}` accepts `{client_id, client_secret}` and
  the adapter uses those for ConfidentialRelay, bypassing the Okta-side link + `fetch-secret`
  entirely. So the wiring automation has two viable shapes: (a) GUI-link the app then `fetch-secret`,
  or (b) create the app via API and push client_id/secret straight to the adapter. The lab/Module
  2.6 assumes (a); the automation may prefer (b). Document which is canonical.
  **CORRECTION (verified via adapter logs): option (b) is NOT sufficient.** Configuring the adapter
  with client_id/secret directly gets the *brokered relay* working (the adapter obtains an Okta user
  token), but the **XAA ID-JAG leg (STEP 1+2) then fails** with
  `invalid_request: 'subject_token' is invalid` (source token `aud=<app>, cid=None`) because Okta
  has no agent↔app identity-assertion binding. **The Okta-side app↔agent link (§2.6) is mandatory
  for XAA to work.** So the automation MUST establish the link (GUI or internal admin API), then
  `fetch-secret`. The public `workload-principals` API does not expose the link — this is a real
  gap for the lab-platform's example-agent pre-wiring and any headless setup.

- **[BUG] `provision_lab_org.py` access policy: idempotent-by-existence + never activated + clients
  emptied by reset.** `ensure_policy` returns the existing policy without reconciling, creates it
  with `clients.include=["ALL_CLIENTS"]` but the live policy was found **INACTIVE with
  `clients.include=[]`**. Two compounding issues: (1) the policy is created but never explicitly
  activated (an INACTIVE policy matches nothing → 0 tools); (2) deleting the agent + sign-on app
  during reset **cascades to empty the policy's `clients.include`** (Okta drops the now-deleted
  client refs), and re-running the provisioner does NOT repair it. *Fix:* `ensure_policy` should PUT
  the desired `conditions.clients` and POST `lifecycle/activate` every run (reconcile, not
  create-if-absent), and `reset_lab.py` should reassert the policy clients/active state.

- **[BUG confirmed] Gotcha 6 is REAL and required (resolves the open Q above).** With the policy
  ACTIVE: `ALL_CLIENTS` → Susan gets **0 tools**; pinning the agent's `[client_id, principal_id]`
  into `conditions.clients.include` is required. So Module 2.11 is necessary, not environment-
  specific. (Note: pinning alone still 0 until the §2.6 link + correct MCP host are also fixed —
  three independent bugs stacked here.)

- **[BUG/NIT] I wired the resource to the wrong MCP host.** Used
  `mcp.o4aa-techcamp-testing.oktademo.app` (does not resolve) instead of the central
  `mcp.taskvantage-demo.com`. Operator error, but it shows `setup-crm-resource.sh` /
  `wire_adapter_resource.py` need the central MCP host baked in or validated (fail fast if the
  `--mcp-host` doesn't resolve), since it's not obvious it's the shared central host.

- **[BUG — the real Module 3 blocker] Stale adapter resource survives reset and binds to a deleted
  connection.** The adapter resource `aus14gb7aiipxsauh698` persisted across the reset; on re-import
  the syncer reassigned its `agent_id` to the new agent but kept the **old `connection_id`
  (`mcn14gorq…`, the deleted previous-iteration agent's connection)**. The wire script's
  `_find_resource` matched it by agent_slug and updated url/enabled but **not** connection_id, so
  XAA used a dead connection → *"Could not create auth headers"* → 0 tools. **Fix:** `reset_lab.py`
  must delete the agent's adapter resources (not just the adapter agent), OR the syncer/wire must
  reconcile `connection_id` to the agent's current managed connection. **Workaround that fixed it:**
  delete the resource, re-sync (syncer materializes a fresh resource bound to the *current*
  connection `mcn14gy8…`), then re-run the wire script. After that: **Susan = 6 CRM tools + ACC-1003
  Fabrikam (she owns).** So the full chain works once all four issues are cleared: app link (§2.6) +
  policy active & agent pinned (§2.11) + correct central MCP host + clean connection binding.

- **[NIT] Adapter tool-discovery isn't agent-scoped.** During Susan's `tools/list` the adapter
  iterated **all 6 router resources** (incl. another agent's `progear` auth servers) and attempted
  ID-JAG for each under Susan's principal — they fail with `invalid_target`/`subject_token` and just
  add log noise. Final catalog is correct (only the agent's own resource resolves), but a
  multi-agent adapter logs a lot of cross-agent exchange failures per request. Worth confirming this
  is intended (filter to the session agent's resources before attempting exchange).

- **[NIT] Re-syncing creates stray empty `aus…-N` resources** (e.g. `aus14gb7aiipxsauh698-3`,
  enabled=false, url=None) for the same agent. Harmless (router skips disabled), but clutters the
  resource list across iterations.

- **[OK] Adapter keypair generation works:** `POST /api/admin/agents/{slug}/credentials/generate-keypair`
  → `{status: success, kid}`; the adapter holds the private key and registers the public key in
  Okta. This is the brokered-signing model (adapter signs the XAA assertion), which is *different*
  from Module 2.5's "generate in Okta, save the private key to your VDI" framing — worth reconciling
  §2.5 to say the adapter holds the signing key (the VDI/OpenCode side doesn't sign the XAA leg).

- **[OK] Adapter import** is clean and idempotent; warns helpfully ("no linked OIDC app",
  "STAGED → imported as disabled", "private key not set").

---

## Module 3 — Per-User Tool Filtering

- **[OK] Binary filtering validated end-to-end through the bridge** (after the Module 2 fixes):
  - Alex (Sales Rep): **6 CRM tools**, `lookup_account` → ACC-1001 Northwind (owner alex — correct row-level cut)
  - Susan (Sales Mgr): **6 CRM tools**, → ACC-1003 Fabrikam (owner susan)
  - Frank (Engineering): **0 tools** (not in any CRM group)
  This matches the binary model the docs were reconciled to (member → full CRM set; non-member →
  none; Alex-vs-Susan differ only in row-level data). The sub-agent's Module 3 rewrite (Alex=6) is
  consistent with reality.
- **[DOC] Tool names are namespaced `<authServerId>__crm.<tool>`** (e.g.
  `aus14gb7aiipxsauh698__crm.lookup_account`). If any module shows bare `crm.lookup_account`, note
  the adapter prepends the resource id. Cosmetic, but worth a heads-up in the guide.
- **[Pending] Desk=6 tool count** still to confirm in Module 4 (CRM=6 confirmed → 12 total expected).

---

## Module 4 — Build VantageDesk From Zero

Built `vantage-desk-as` (`aus14gz0qvo55DPSZ698`) end-to-end via API as the attendee would: AS +
5 `itsm.*` scopes + `groups` claim + access policy (active, agent pinned) + IT-Help-Desk rule,
then `wire_adapter_resource.py --preset desk` for the managed connection + 2nd adapter resource
→ `/desk/mcp`.

- **[OK] Desk build + XAA validated.** Kim (IT Help Desk) → **12 tools (6 ITSM + 6 CRM)**, ITSM
  call returned TKT-1739. Confirms total catalog = **12** (6 CRM + 6 Desk) — matches Module 1.7.
  The sub-agent's Module 4 rewrite (Kim=12) is correct. Kim gets CRM too because she's in
  IT Help Desk, which has a full-CRM rule under the binary model (she's a dual-domain user).
- **[OK] The build-from-zero path had NO new blocking bugs** — because it's a fresh AS (no stale
  adapter resource/connection to collide with, unlike the reset CRM case). The only requirements
  are the ones Module 4 already documents: policy **Active** + agent **pinned** as a client.
- **[BUG — cross-module inconsistency] Module 2.11 over-specifies the policy client; Module 4.5 is
  right.** Verified empirically: pinning **only the agent principal (`wlp…`)** in the AS access
  policy is sufficient — Susan=6 (CRM) and Kim=12 (Desk) both work with principal-only. The
  sign-on **app client_id is NOT needed in the policy** (the §2.6 `appId` link handles the app
  side; the XAA legs authenticate as the agent principal via `private_key_jwt`). **Fix:** correct
  the just-merged Module 2.11 to pin **only the agent principal**, matching Module 4.5's NOTE
  ("the assigned client must be the AI agent itself, not its user-sign-on app"). "Add both" still
  works (superset) but is misleading and contradicts §4.5.
- **[OK] Module 4.5's `no_matching_policy` NOTE is accurate** — assigning only the sign-on app
  (not the principal) would fail; the principal is the client Okta evaluates during XAA.

---

## Module 5 — Govern with OIG

Validated the **technical heart** of Module 5 (the membership round-trip, §5.5/§5.7) directly,
simulating the OIG grant/revoke by adding/removing Frank from `CRM Read - Cross-Functional`:

- **[OK] §5.5 grant round-trip works.** Frank: **0 tools → 6 CRM tools** the moment he's added to
  `CRM Read - Cross-Functional` (rule 4 fires); his `lookup_account` returns an empty list
  (correct — he owns no accounts; the tools are present, the data is row-filtered). Full XAA chain
  healthy in logs: ID-JAG STEP 1+2 SUCCESS (expires 300s) → STEP 3 SUCCESS (access_token, crm.*).
- **[BUG — significant for §5.7 + the kill-switch narrative] Revocation is NOT immediate: the
  adapter caches the resource token for 3600s (1 hour).** After removing Frank from the group
  (confirmed gone in Okta — only Everyone + Engineering), the adapter **still served 6 tools** across
  multiple fresh logins over several minutes. Adapter log:
  `[TOKEN-CACHE] Cached (service) user=…frank… resource=aus14gb7aiipxsauh698 (TTL: 3600s)`. The
  per-(user,agent,connection,resource) token cache is not invalidated on group change, so a revoked
  user keeps access until the cached token expires (up to an hour). **This directly undercuts §5.7
  ("Verify Frank's tools are gone") and the §5.8 "kill switch" immediacy.** Fix options: (a) set a
  short resource-token TTL for the lab (e.g. 60–120s) so revocation visibly takes effect; (b) add an
  adapter cache-flush/"revoke now" admin action and have §5.7 call it; (c) document the lag explicitly
  in §5.7 and have attendees wait out the TTL. Worth confirming whether §5.8 agent-deactivation flushes
  the token cache (didn't test — kept the agent active to preserve walkthrough state).
- **[Q/BUG] OIG catalog entry, certification campaign, and approver routing are NOT provisioned.**
  §5.2–§5.4/§5.6 assume a preconfigured catalog entry for `CRM Read - Cross-Functional` (duration,
  approver, eligibility), a `Quarterly review — AI agent CRM access` campaign, and the admin
  configured as Frank's manager. `provision_lab_org.py` creates the group + rule 4 but **none of the
  OIG governance constructs**. Either the lab platform provisions these, or the provisioner must add
  them (catalog publish + campaign + manager relationship). Several `{HumanReview}` markers in §5.2–5.6
  already flag unverified IGA menu paths/labels — those need a real OIG pass once the constructs exist.
- **[DOC] Persona password again.** §5.3 logs in as Frank with `Tra!nme4321` — same mismatch as §1.3
  (provisioner sets `O4aaLab!Tc2026#`). Same fix.
- **[NOT RUN] §5.6 certification campaign and §5.8/§5.9 deactivate-reactivate kill switch** — require
  the OIG campaign construct (not provisioned) and would disrupt walkthrough state; deferred. The
  membership round-trip above exercises the same access-propagation path the campaign's revoke uses.

---

## Deep-dive: why scopes can't control the tool set (graduated filtering)

> **RESOLUTION (adapter maintainer):** this is **by design**, not a defect. Tool visibility is
> resource-based; per-user control is data/application-layer (`require_scope` + `groups` row
> filtering). The "fix options" below are NOT planned work — kept only as reference for if the
> product direction ever changes. Current path (binary tools + app-layer enforcement) is correct.

Investigated whether the limitation is in the custom MCP server. Conclusion: it's **two
independent gaps**, and the MCP server is one of them.

**Gap 1 — no scope→tool mapping anywhere in the stack.**
- MCP server (`mcp-server/app/server.py`) is a **thin proxy by design**: tools are registered
  statically per path (`/crm/mcp` → 6 CRM, `/desk/mcp` → 6 ITSM); `tools/list` never inspects the
  token or its scopes. **Proven empirically:** calling `https://mcp.taskvantage-demo.com/crm/mcp`
  directly with a *bogus* `Bearer dummy-token-zero-scopes` still returns all 6 CRM tools. No tool
  declares a required scope; the server only forwards the Bearer to the backend (which does
  row-level *data* filtering by `sub`/`groups`).
- Adapter filters at **resource granularity** (whole resource's tools if XAA yields a valid
  audience-scoped token, else none) — no per-tool scope mapping. Hence the binary all-6-or-0.

**Gap 2 — the token never carries narrowed scopes.** The adapter requests the connection's full
INCLUDE_ONLY scope set for every user; Okta custom-AS rules match only when requested scopes are a
**subset** of a rule's allowed set, so a per-group subset rule → `no_matching_policy` → 0 tools
(why we went binary). Even a narrowed token wouldn't help given Gap 1.

**Both must be closed together** — fixing either alone changes nothing.

**Fix options (recommend #1 for the lab):**
1. **Filter by the `groups` claim in the MCP server.** Token already carries `groups`; have the
   server decode the JWT and return a per-group tool subset. Sidesteps Gap 2 (keep binary scopes),
   delivers "different tools per persona." Cost: server is no longer a pure thin proxy; contradicts
   Module 1.7's "the adapter filters tools."
2. **Per-tier resources/paths** (`/crm/read/mcp` ↔ read scopes) + separate adapter resources +
   managed connections. Config-only but multiplies resources/connections per agent.
3. **True scope→tool enforcement**: annotate tools with required scopes, adapter requests only the
   user's entitled scopes (needs per-user entitlement awareness) + server/adapter filters by granted
   scopes + Okta downscoping. Correct but touches all three layers.
