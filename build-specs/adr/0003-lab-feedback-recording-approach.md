# ADR-0003: Lab feedback portal + session-recording approach

**Status:** Proposed — July 2026
**Related:** `../feedback-portal-build-spec.md` (full design + phased plan); supersedes the ad-hoc
`testing/Copy of Agentic Devcamp 2.0 Feedback Log.xlsx` grid for *collecting* feedback (the xlsx
grid remains a supported **export** format).

## Context

Today lab feedback is collected in a shared spreadsheet — a **reviewer × module** grid (rows =
testers, columns = modules, cells = free text), modelled on the Auth0 Agentic DevCamp feedback log.
It works but has real friction:

- Cells become dumping grounds — one tester packed **eight** numbered issues into a single module
  cell, so signal is hard to triage.
- There is **no way to point at *where* on screen** a problem happened; reviewers describe UI state
  in prose ("where is the Run Checks button?").
- It yields **no timing or friction data** — we can't tell how long a module took or where testers
  got stuck without reading every cell.

Two goals for the replacement:

1. Make giving feedback **fast and low-friction** for testers.
2. Build a **corpus of recorded sessions** to measure *average time per module* and surface *screens
   with indicators of user friction*.

### Recording-capture options considered

| Option | How | Verdict |
| --- | --- | --- |
| **VDI-native (ffmpeg)** | Configurator installs a recorder + scheduled task; segments auto-upload to S3 | Robust + free precise activity log, but a heavy new agent on the VDI, S3-from-VDI streaming, and lifecycle to own. Rejected in favor of Zoom. |
| **Browser `getDisplayMedia`** | Portal tab records a shared surface | Captures only one surface, needs the tab open, dies on tab close — poor fit for a multi-window lab. Rejected. |
| **Zoom local recording + upload** *(chosen)* | Tester records their **full screen** in Zoom, then uploads the `mp4` to the portal | Zero VDI agent; captures the whole screen incl. browser; familiar to SE testers; adds **narrated audio** (a direct friction signal). |

## Decision

1. **Testers record their full screen with Zoom** and upload the resulting `mp4` to the feedback
   portal after (or during) the lab. No recorder agent runs on the VDI.
2. **The portal generates its own time-coded transcript** from the uploaded `mp4` (Whisper on the
   backend). We do **not** depend on Zoom's auto-transcript — that is a cloud-recording feature,
   licensing/settings-dependent, and often absent on local recordings. If a tester also uploads
   Zoom's `.vtt`, we accept it; we never require it.
3. **Module boundaries are recovered by inference + confirmation**, not by OS instrumentation:
   scene-change detection (ffmpeg) + a light auto-chapter pass (module title read off the on-screen
   doc page) proposes chapter marks; the tester **confirms** them at upload. That confirmation step
   doubles as the "bot-assisted tagging" experience.
4. **Friction detection starts as heuristics over transcript + scene analysis** (long silences,
   frustration phrases, screen re-visits, dwell between scene changes), with vision-LLM keyframe
   classification deferred to a later phase.
5. **The reviewer × module xlsx grid is preserved as an export**, so the existing SE/Auth0 workflow
   is a drop-in consumer of the richer underlying data.

## Consequences

**Positive.** No new agent, streaming pipeline, or lifecycle to build/own on the VDI. Captures the
entire screen including browser elements. Narrated audio is a first-class friction signal the
spreadsheet never had. The portal becomes the single center of gravity (upload + transcribe +
chapter + tag + feedback + export).

**Negative / mitigations.**
- **Depends on the tester hitting "record."** The single biggest failure mode → hard checklist gate
  in Module 0 and the portal, plus a 30-second how-to and a reminder.
- **No free, precise activity log**, so module timing + dwell must be *inferred* from the video +
  transcript (scene-change + auto-chapter + user confirmation) rather than read from an OS log.
  Accepted; the confirmation step keeps timing accurate and becomes useful UX rather than overhead.
- **Large uploads** (a 60–90 min screen capture is ~0.5–2 GB) → resumable **multipart-to-S3 via
  presigned URLs**, designed in from the start.
- **Consent/retention** must be explicit (recordings of people working) → consent gate + S3 lifecycle
  retention window, detailed in the build spec.

## Open decisions (tracked in the build spec)

- Portal authentication: Okta OIDC (via a demo org) vs. lightweight email magic-link.
- Hosting: reuse the `taskvantage-apps` ECS/ALB/RDS footprint vs. standalone.
- Home for the code: new repo vs. subfolder in `taskvantage-apps`.
- Retention window for recordings + who may view them.
