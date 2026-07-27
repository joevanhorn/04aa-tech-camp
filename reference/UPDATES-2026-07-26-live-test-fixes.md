# O4AA Tech Camp — fixes from the 2026-07-24 live test

**Prepared 2026-07-26 · joevanhorn** — for demo engineering review ahead of upstream PRs.

**Inputs:** feedback-portal submissions since 7/23 (written feedback from two SEs + one full
2h24m recorded walkthrough, transcript-mined into 76 friction points; tester was hard-blocked
3 times before Module 5 and abandoned at §7.3), plus a full triage doc:
`taskvantage-apps/feedback-portal/docs/LAB-FEEDBACK-ISSUES-2026-07-24.md`.

All changes are merged to `main` on the mirrors below and were tested as described per repo.

---

## 1. `demo-assets` (mirror: `joevanhorn/demo-assets-mirror`, main @ `b31f8c6`)

### Module guides (`assets/labs/techcamp-o4aa/en/*.md`)
- **UI-label drift sweep** — every place the guide named a control that doesn't exist in the
  console as written (largest bug class in the live test): Owners tab is **Edit → Save** (not
  "Add owners"), **All clients** (not "any clients"), **Update Policy** (not "Save"),
  **Managed status**, **Display phrase** (not "Display name"), **Assign to**,
  "**and scopes requested**", **Create rule**, "DCR enabled" naming aligned to the Bridge UI.
- **Step-order fix (§4.1):** the *Enable immediate access with Federation Broker Mode*
  checkbox only appears after the Assignments selection — steps reordered, full checkbox
  label used, "leave **unchecked**" made explicit.
- **§4.2 restructured:** audience (Settings tab), the 5 scopes (Scopes tab), and the
  **groups claim (Claims tab)** are now discrete, located steps. Both written-feedback
  testers and the recorded tester stumbled on the same paragraph.
- **§4.6 verification rework:** correct field labels, names the agent being verified, and
  adds explicit "**in your local browser**" / "**switch to the VDI**" context markers
  (the guide previously hopped between consoles without saying so).
- **Removed a step that doesn't match the product:** "Click Settings (top-right)" on the
  AI Agents page — two testers independently couldn't find it. Replaced with a safe
  registry-review step and a `VERIFY-AT-GA` comment to restore it if/when the control's
  location is confirmed.
- **Advanced-mode gotchas called out:** the **Token Exchange** grant type only appears after
  clicking **Advanced** in rule creation (§5.11 — tester called this "a big big problem"),
  and the Toolkit's token sidebar/copy button requires **Advanced** view (§5.7).
- **§5.11 scope entry:** the five itsm scopes are now listed one-per-line as individual
  copyable spans with a note they must be added one at a time (pasting the list fails).
- **Persona credentials surfaced early:** a "Your persona credentials" box in the intro plus
  password references at each sign-in step (the recorded tester sat at a password prompt
  twice with no password in sight).
- **Removed all CLI-era "expected output" blocks (12 total).** Root cause of the
  "old CLI screenshot + new GUI screenshot stacked on every toolkit step" report: those were
  ASCII expected-output *code fences* from the CLI-toolkit era, rendered by the portal as
  dark copy-button blocks above the new GUI screenshots. The GUI screenshot is now the
  single "expected result"; explainers were re-anchored to real GUI elements (verdict
  banner, USABLE/BLOCKED cards, Signed-in identity card, Token journey sidebar — §6.3's
  hop-by-hop XAA walkthrough rewritten against the journey panel). Also fixes the earlier
  "copy-able tags don't resolve" complaints — those blocks were what people were copying.
  Bonus catch: §5.7's side-by-side prose said Alex but the captured screenshot runs Susan
  vs Frank — corrected.
- **Product rename:** "Okta MCP Adapter" → **"Okta MCP Bridge"** throughout prose, with a
  one-line clarification at first mention that the Bridge is an Okta Professional
  Services-delivered artifact. Literal hostnames (`adapter.taskvantage.lab`) unchanged.
- **Env-check section rewritten to match the real Toolkit output** (verdict banner +
  three reachability checks + environment values). The old fictional CLI transcript —
  including a "Lab CA trust" line the tool never prints — is gone.

### `bootstrap.ps1`
- Completion banner now directs attendees to the actual next step (double-click Lab
  Toolkit → **Check environment**) instead of "continue with Lab 1", and uses Bridge naming.

### `lab-toolkit-gui.zip` (rebuilt bundle, clean build, served-content verified)
- **No auto-sign-in as the first persona on launch.** The Toolkit used to boot straight into
  a real Okta login as Alex Martinez (surprise Okta Verify push included) — cost the
  recorded tester ~6 minutes of "which account am I supposed to use?". It now starts idle
  with a "No persona — select to sign in" placeholder and an on-screen pointer to Check
  environment.
- **Environment check shows an unmissable verdict banner first** ("✓ Environment ready" /
  "✕ found problems" with what-to-do) and auto-scrolls the result into view.
- Simple view now says the raw token + copy button live in **Advanced**.
- Check name "MCP adapter" → "MCP Bridge"; fictional "Lab CA trust" fixture check removed;
  includes the v2 branded icon (fixes the "PowerShell icon" report).
- Tested: 17 backend tests green; fixture-mode UI verified with Playwright; the built exe
  was run and confirmed serving the updated SPA.

### Deploy notes for this repo
- Please confirm the deploy pipeline **invalidates CloudFront for `labs/techcamp-o4aa/*`** —
  the CDN currently serves `04-first-day-on-the-job.md` two commits stale.
- Housekeeping (separate/later): `en/screenshots/*.md` capture artifacts (~2MB embedded
  images, 7/21-era) are deployed and publicly served but referenced by nothing — safe to
  delete.

---

## 2. `managed-resources` (mirror: `joevanhorn/managed-assets-mirror`, main @ merge of `fix/o4aa-live-test-provisioning`)

All in `src/servicers/labs/techcamp-o4aa/` (+ one new wic passthrough). 74 jest tests green,
eslint clean. Two stacked changes:

### a. Required, verified tenant enrollment (`fix/o4aa-require-tenant-enrollment`)
Enrollment of the org into VantageCRM/VantageDesk was best-effort and silently skipped when
the admin key was absent — **the root cause of the broken second half of the lab on 7/24**
(apps 401 "issuer not from an enrolled org"; every persona read returned nothing). Now it
POSTs, verifies via GET, and fails the deployment loudly on any gap.

### b. Live-test provisioning gaps (`fix/o4aa-live-test-provisioning`)
- **Access Requests portal assignment (Module 7):** the servicer now assigns
  `okta_atspoke_sso` + the resource-catalog app — lab-personas group, Engineering group,
  the org owner, and the lab's password-only auth policy. Without this, Module 7 dead-ends
  three ways (no portal access for the admin, empty catalog experience, no Request tab for
  Frank + an unplanned MFA enrollment).
- **OIG request-condition setup is loud and resilient:** the governance request-sequences
  fetch retries 5×10s (fresh orgs lag), and any remaining gap — no sequence, condition
  without id, activation failure — **fails the deployment** with full HTTP detail instead
  of a swallowed `log.warn` (this silent path is how orgs shipped with an empty catalog).
- **Lab Toolkit client pinned on the `vantage-crm-as` access policy**, replacing
  `ALL_CLIENTS` — which does not match these token flows (diagnosed live on 7/24: "Susan
  denied"). Attendees still add their own agent principal in §4.5 by design. New
  passthrough: `updateAuthServerPolicy` in `src/external/wic/index.js`.
- **Enrollment now auto-detects app capability:** each enrollment host's `GET /healthz` is
  checked first; if it advertises `"auto_enroll": true` (see taskvantage-apps below), the
  host is skipped and **no admin key is needed at all**. Hosts without it keep the
  required+verified enrollment path, so this is safe to merge before or after the apps
  update.

---

## 3. `taskvantage-apps` (`joevanhorn/taskvantage-apps`, main @ merge of `feat/issuer-auto-registration`)

This is the central VantageCRM/VantageDesk/MCP codebase; **the camp's deployment at
`crm/desk.taskvantage.oktademo.app` needs a redeploy from this main to pick it up.**

- **Issuer auto-registration — removes the shared admin API key from org onboarding.**
  Any org whose token issuer matches `https://{org}.okta.com/oauth2/{authServerId}` is
  enrolled automatically on its **first fully verified token**:
  - strict shape gate (https only, no port/userinfo/path tricks, suffix anchored at the
    end of the host) runs **before** any JWKS URL is constructed;
  - the token must pass signature verification against the org's **own JWKS** plus the
    constant audience and expiry — only the party controlling the Okta org can register it;
  - nothing is persisted on failure; tenant-id collisions across suffixes are refused
    (first org wins, latecomer 401s).
  - Config: `AUTO_ENROLL_ISSUER_SUFFIXES` (default `.okta.com`; set empty to disable and
    restore explicit-enrollment behavior). `GET /healthz` now advertises
    `"auto_enroll": true|false` so provisioning adapts automatically.
  - Security posture: strictly narrower than key-based enrollment — only an org that
    proves control of its own `.okta.com` domain via its own signing keys can register,
    and the shared admin key disappears from lab-component settings entirely.
- The admin API remains for operator tasks (list/remove/reset tenants).
- Tested: 15 new tests on the real token path (local RSA keys, stubbed JWKS) covering
  happy path, forged signature, wrong audience, 8 malicious issuer shapes, disabled mode,
  and collisions; full suite 56 green; plus a live negative test against real Okta JWKS
  (forged-key token with a real issuer → network JWKS fetch → 401, no enrollment).
- Docs updated: `docs/TENANT-ENROLLMENT.md`.

**Suggested rollout order:** deploy the apps first (healthz starts advertising
`auto_enroll`), then the servicer change makes new lab-org deployments key-free
automatically. The servicer change is back-compatible either way.

---

## 4. `labs` / `builder` (labs-platform-mirror, demoplatform-builder-mirror)

No changes in this round. (The mermaid-diagram rendering support in the labs SPA was
submitted previously and is unrelated to this batch.)

---

## Known follow-ups / open items
- ~~Three `VERIFY-AT-GA` comments~~ **All resolved 7/26-27 (owner spot-checked):** the
  "AI Agents Settings" control does not exist (mention removed); the Bridge Admin UI does
  not display resource scope lists (guide now points at the agent's Resource connections
  tab in the Okta console); §4.7 lists the real `workload_principal.*` System Log event
  names verified against a live org — note owner assignment emits no AI_AGENT event.
- §5.7's screenshot comment marker wording ("Authentication failed for resource") vs the
  captured GUI ("Policy evaluation failed") — marker left as-is, prose matches the image;
  recapture at will.
- Feedback-portal (internal tooling) backlog: session-creation race produced 5 duplicate
  sessions for one tester; the portal's module list predates the module renumbering.
- Lab requirement reminder: Bridge deployments should be ≥ 0.15.14 (kill-switch cache fix).
