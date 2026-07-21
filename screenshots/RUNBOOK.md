# Screenshot-bot runbook — O4AA lab modules

Produces module guides with real embedded screenshots using **`lab-screenshot`**
(joevanhorn/lab-screenshot): a Playwright + Claude bot that reads a markdown guide, follows the
steps in a browser, and captures a screenshot at each `[SCREENSHOT: ...]` marker.

**Pilot: Module 5** (`screenshots/module-5.md`, 18 markers). Validate the flow here, then tag the rest.

---

## How this works

1. A **tagged** copy of a module (this dir) carries `[SCREENSHOT: description]` markers — one per key
   visual state. (We keep these in `screenshots/`, NOT in the live `module-*.md`, so attendees never
   see raw markers.)
2. Before a run the tagged copy is **rendered** for the target org — every `{{…}}` Mustache
   placeholder replaced with that org's real value (URLs, persona password, auth-server ids).
3. The bot runs the rendered guide, captures each marker, and emits the guide with base64 PNGs
   embedded where the markers were.
4. We lift those images into the published module.

Single marker type: the VDI is reachable in the lab browser, so the bot captures the Lab Toolkit /
OpenCode surfaces the same way it captures the Okta consoles.

---

## Prerequisites

### Environment state — the gating item
Module 5 assumes the org is at **end-of-Module-4 state**. Before the run the target org needs:
- 5 persona users (susan/alex/kim/frank/sally) + the 5 groups — `provision_lab_org.py`.
- `vantage-crm-as` + `vantage-desk-as` built and wired; **agent registered + ACTIVE**; **CRM + Desk
  adapter resources** wired on the paired bridge (so 5.5/5.7/5.8 toolkit calls resolve).
- **OIG request-access** configured for `CRM Read - Cross-Functional` **and Frank's manager set**
  (`provision_lab_org.py --approver-login <admin>`) — else 5.3/5.4 don't route.
- Persona **TOTP** enrolled (`~/o4aa-totp-*`) and a **super-admin** with TOTP for the admin console.
- A **paired bridge** at `10.0.0.5` + the **VDI** with the Lab Toolkit installed, pointed at this org.

> This is a full lab environment, not just an org. Decide the source: (a) provision a fresh org +
> pair a bridge/VDI ourselves, or (b) spin up a dedicated Heropa lab instance for screenshots. Open
> question — see "Decide before running".

### Tooling
- The bot runs on a machine **with a display/browser** (interactive MFA) — your laptop, not the
  headless sandbox. Install per its README (`pip install -e .` + `playwright install chromium`).
- **`ANTHROPIC_API_KEY`** set (the bot drives Claude — Sonnet 4.6 recommended, Opus for hard flows).
- Target org **SSWS API token** (optional but enables factor/user ops).

---

## Render the tagged guide for the target org

Substitute the placeholders in `module-5.md` for the org's real values, e.g.:

| Placeholder | Value |
| --- | --- |
| `{{idp.tenantDomain}}` | the org's end-user domain (e.g. `demo-….okta.com`) |
| `{{…settings.persona_password}}` | the shared persona password |
| `{{…authServerIds.0}}` | the `vantage-crm-as` id (only in the expected-output code blocks) |

Produces `module-5.rendered.md`. (The code-block placeholders are cosmetic — they only need to be
right for the rendered guide to read correctly; they don't affect navigation.)

---

## Run

Web UI (recommended):
```bash
cd ~/lab-screenshot && source venv/bin/activate
lab-screenshot app        # http://localhost:8384 → upload module-5.rendered.md, set org + model, Start
```

CLI:
```bash
lab-screenshot check screenshots/module-5.rendered.md          # dry-run: lists the 18 markers
lab-screenshot login --org https://<org>.okta.com --username <admin> --totp-secret <ADMIN_TOTP>
lab-screenshot run   screenshots/module-5.rendered.md --org https://<org>.okta.com --agent \
    -o screenshots/module-5.output.md
```

### Human-in-the-loop hand-offs for Module 5
The bot pauses and asks (web UI chat / terminal) at these; be ready to help:
- **Admin MFA** on the Okta Admin Console sign-in (approve push / TOTP).
- **5.3 identity switch** — sign in as **Frank** (end-user dashboard, incognito) to submit the request.
- **5.4 switch back** to the **admin** session to approve.
- **5.5 / 5.7 / 5.8 / 5.9 Lab Toolkit** — drive the toolkit menu on the VDI (list/invoke tools as the
  named persona); the bot captures the resulting screen.
- Between 5.6 revoke and 5.7, note the **token-refresh timing** (~1h) — force it via Universal Logout
  or agent deactivate if the toolkit still shows USABLE right after the revoke.

---

## After the run
- **Download Output** → `module-5.output.md` with embedded base64 PNGs at the 18 marker positions.
- Review each shot; re-run any that captured the wrong state (raise **Max iterations per section** for
  the campaign wizard if it needs more clicks).
- Lift the images into the published `module-5-govern-with-oig.md`.

---

## Decide before running
1. **Environment source** — provision a fresh org + pair a bridge/VDI ourselves, or a dedicated
   Heropa screenshot instance? (M5 needs the full wired stack, not just an org.)
2. **How to reach end-of-M4 state** — pre-provision it via our scripts (fast), or walk M1–M4 first.
3. **Which admin identity** the bot signs in as (the super-admin with TOTP for that org).
