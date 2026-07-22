# Module 1 screenshot-bot readiness — `demo-aqua-hoverfly-22341.okta.com`

Prep status for running `lab-screenshot` against the **rendered** guide
`screenshots/module-1.aqua.md` (12 `[SCREENSHOT]` markers). Companion to `M5-READINESS-aqua.md`.

- **Org:** `demo-aqua-hoverfly-22341.okta.com` (id `00o15aruocs4D6hi9698`)
- **Rendered guide:** `screenshots/module-1.aqua.md` (produced from `module-1.md`)
- **State:** pre-lab **baseline** (verified 32/0/0), **not** end-of-Module-4.
- **Persona password:** `Tra!nme4321` — verified (Frank Boone primary-auth SUCCESS, no MFA).

## TL;DR — marker readiness

| Tier | Count | Meaning |
| --- | --- | --- |
| **NOW** | **7** | Admin-console screens, **admin-login-only**. No bridge, agent, VDI, or persona sign-in needed. Runnable against the current aqua baseline today. |
| **PHASE-2** | **5** | VDI / Lab-Toolkit screens. Need the Virtual Desktop + Lab Toolkit installed and pointed at this org, plus reachable central apps + MCP. **No bridge is reachable for aqua** (see M5-READINESS). |

Module 1 is *tour-only* — no config is mutated, so the 7 NOW markers are pure read-only admin-console
captures against the clean baseline. The 5 PHASE-2 markers all live in the VDI Lab Toolkit and are gated
on the same unreachable VDI/bridge stack documented in `M5-READINESS-aqua.md`, plus two live caveats below.

## Per-marker map (all 12)

| # | Section | Marker (abbrev.) | Tier | Gated on |
| --- | --- | --- | --- | --- |
| 1 | setup | Virtual Desktop after setup, Lab Toolkit icon on desktop | **PHASE-2** | VDI + bootstrap.ps1 run |
| 2 | 1.1 | Admin Console dashboard after admin sign-in | NOW | admin login only |
| 3 | 1.2 | Admin's own profile, First/Last name filled in | NOW | admin login only |
| 4 | 1.3 | Directory > People — 5 personas ACTIVE | NOW | baseline personas (present) |
| 5 | 1.4 | Directory > Groups — the 6 lab groups | NOW | baseline groups (present) |
| 6 | 1.5 | Lab Toolkit "Read CRM accounts" — Susan sees 8 | **PHASE-2** | VDI toolkit + CRM reachable |
| 7 | 1.5 | Lab Toolkit "Read CRM accounts" — Alex sees 2 (ACC-1001/1002) | **PHASE-2** | " |
| 8 | 1.6 | Lab Toolkit "Read Desk tickets" — Kim full queue | **PHASE-2** | VDI toolkit + Desk reachable (caveat below) |
| 9 | 1.7 | Lab Toolkit env-check — all green | **PHASE-2** | VDI toolkit + apps + MCP up (caveat below) |
| 10 | 1.8 | Directory > AI Agents — empty list | NOW | baseline (no agents registered) |
| 11 | 1.9 | vantage-crm-as Scopes tab — 5 scopes + audience api://vantage-crm | NOW | baseline crm-as (`aus15g048hlwQzjYZ698`) |
| 12 | 1.10 | vantage-crm-as Access Policies — group→scope rules | NOW | " |

**NOW (7):** 2, 3, 4, 5, 10, 11, 12 &nbsp;•&nbsp; **PHASE-2 (5):** 1, 6, 7, 8, 9

## What's already in place (baseline, verified — satisfies all 7 NOW markers)

- **Admin login** to `demo-aqua-hoverfly-22341.okta.com` (org id `00o15aruocs4D6hi9698`) — covers markers 2, 3.
  Marker 3 (1.2) is a *mutation* on the admin's own profile (set First/Last name); the bot performs it live,
  no precondition beyond the name being currently blank.
- **5 personas** ACTIVE: susan/alex/kim/frank/sally@atko.email — marker 4.
- **6 groups**: Sales Management, Sales Reps, IT Help Desk, CRM Read - Cross-Functional, Engineering, Everyone
  — marker 5.
- **Directory > AI Agents empty** — only the STAGED **VantageCRM Example Agent** `wlp15g085np9KWK1H698` exists,
  and STAGED agents don't appear in the registered-agents list; the tour expects an empty list — marker 10.
  *(If the STAGED example agent surfaces in the list on this org, marker 10's "empty list" caption won't match
  — verify the AI Agents list is genuinely empty before the run, or note it as expected drift.)*
- **vantage-crm-as** `aus15g048hlwQzjYZ698` — audience `api://vantage-crm`, the 5 crm scopes
  (crm.accounts.read/write, crm.contacts.read, crm.opportunities.read/write), `groups` claim, and the access
  policy with the group→scope rules — markers 11, 12.

The 7 NOW markers need **only an admin browser session** — no bridge, no agent activation, no VDI, no persona
sign-in. They are capturable today against the clean baseline.

## PHASE-2 markers — gated on VDI/Lab Toolkit (no bridge reachable for aqua)

Markers 1, 6, 7, 8, 9 all render the **VDI Lab Toolkit**. Per `M5-READINESS-aqua.md`, **no adapter/bridge is
reachable for this org** and there is **no VDI toolkit pointed at aqua**. Standing these up is the same
Step A–F work enumerated in the Module-5 readiness doc (register+activate agent, build desk-as, pair adapter,
wire resources, enroll tenant, VDI with toolkit). Two Module-1-specific caveats:

- **Marker 8 (1.6, Kim's Desk queue):** VantageDesk has **no `vantage-desk-as`** on this org until Module 4
  (auth servers present: `default`, `vantage-crm-as` only). The Lab Toolkit cannot mint a real Desk token for
  Kim here. In the lab flow 1.6 is explicitly a *"provided screenshot or Lab Toolkit"* out-of-band step — so
  marker 8 should be treated as a **provided-screenshot** capture, not a live toolkit run, until desk-as exists.
- **Marker 9 (1.7, env-check all green):** the central lab MCP `mcp.taskvantage.oktademo.app` is currently
  returning **503**, so the env-check's "MCP server reachable (12 tools)" line would render red ✗ and the
  all-green capture would fail. Marker 9 is blocked until the MCP host is back up — recheck before any run.

Markers 6 and 7 (1.5, CRM reads) need only the VDI toolkit + reachable CRM (central `crm.taskvantage.oktademo.app`)
and persona tokens; no desk-as. They come online with the VDI + toolkit + enrollment stack (Step E/F in
`M5-READINESS-aqua.md`), independent of the desk-as build.

## Recommended run scoping

- **Today (admin browser only):** capture the 7 NOW markers (2, 3, 4, 5, 10, 11, 12). This covers the entire
  admin-console half of the tour (1.1–1.4, 1.8–1.10).
- **Phase 2 (after VDI/bridge/MCP):** markers 1, 6, 7 once the VDI + toolkit + CRM enrollment is live;
  marker 9 once MCP is back up; marker 8 as a provided screenshot (or a live run only after Module 4 builds
  `vantage-desk-as`).
