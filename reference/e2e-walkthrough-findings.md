# O4AA E2E Walkthrough — Findings Log

Live, module-by-module walkthrough of the lab guide against the dedicated reset-able
org `demo-o4aa-techcamp-testing.okta.com` + its adapter
`adapter.o4aa-techcamp-testing.oktademo.app`. Each issue is flagged here as found; a
cleanup sprint follows the walkthrough.

Severity: **[BUG]** breaks the lab / **[DOC]** guide inaccurate / **[NIT]** polish / **[Q]** open question.

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
