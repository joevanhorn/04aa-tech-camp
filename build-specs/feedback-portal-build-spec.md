# Build Spec: Lab Feedback Portal

**Status:** Draft for review — July 2026
**Decision record:** `adr/0003-lab-feedback-recording-approach.md`
**Supersedes (for collection):** `../testing/Copy of Agentic Devcamp 2.0 Feedback Log.xlsx`
(kept as an export format)

A web portal that (a) makes giving lab feedback fast and frictionless, and (b) builds a corpus of
recorded tester sessions we can mine for *time-per-module* and *screens with friction*.

---

## 1. Goals & non-goals

**Goals**
- Replace the reviewer × module spreadsheet with a **fast** structured feedback experience — a
  useful signal per module in seconds, prose where the tester wants it.
- Let testers **point at the screen**: attach a clip, timestamp, or screenshot from their own
  recording to any piece of feedback.
- Build a **searchable corpus** of full-screen recordings + transcripts.
- Produce **analytics**: average time per module, and per-screen/per-module **friction indicators**.
- **Export** the reviewer × module xlsx grid unchanged, so the existing SE workflow still works.

**Non-goals (initially)**
- No live streaming / real-time monitoring of testers.
- No automated grading or pass/fail of testers.
- No VDI-side agent (see ADR-0003 — recording is Zoom + upload).

---

## 2. What we're modelling on (the Auth0 grid)

`testing/Copy of Agentic Devcamp 2.0 Feedback Log.xlsx` is a two-sheet workbook:
- **SE Pilot Feedback** — rows = reviewers, columns = modules (`Overview`, `00 – Introduction`,
  `01 – Pre-requisites`, … `07 – End to End`, `Conclusion`, `General Feedback`), cells = free text.
  A header prompts reviewers to look for: *technical inaccuracies, awkward transitions,
  intuitiveness, length, style/approach, improvement opportunities, does the story resonate*.
- **SE Pilot Participants** — the roster.

We keep the mental model (per-module feedback + the "look out for" prompts) but make the *capture*
structured and fast, and add the recording/timeline dimension the grid can't express.

Our module set is the TaskVantage arc, not Auth0's: `lab-intro`, `module-1 … module-6`. The module
list is config-driven so it tracks the repo.

---

## 3. System overview

```
Tester (VDI / laptop)                    Portal (web)                     Backend / AWS
────────────────────         ────────────────────────────      ─────────────────────────────
 Zoom: record full screen  ─►  Upload (resumable multipart) ──►  S3  (recordings/{session}/…)
 narrate while working          Quick per-module feedback  ──►   RDS (feedback, spans, assets)
                                Review & tag over timeline ◄──   Enrichment jobs:
                                  (bot-suggested chapters          • Whisper transcript (VTT)
                                   & friction moments)             • ffmpeg scene-change + keyframes
                                Export xlsx / CSV / JSON  ◄──      • auto-chapter (module titles)
                                                                   • friction heuristics
                                                                   • aggregate analytics
```

Three logical components:

1. **Feedback Portal (web app)** — onboarding/consent, quick per-module feedback, recording upload,
   review & tag, export, and an analytics view.
2. **Ingest & transcription pipeline** — presigned multipart upload → S3; on completion, jobs
   normalize the video, generate a time-coded transcript (Whisper), detect scene changes, and cut
   keyframes.
3. **Enrichment & analytics** — auto-chapter (module spans), friction heuristics, and cohort
   aggregates (avg time per module, friction heatmap), plus the bot-suggested tag candidates the
   portal surfaces.

---

## 4. Component detail

### 4.1 Feedback Portal (web)

**Stack (proposed).** Next.js (App Router) + Postgres + S3, containerized on **ECS Fargate behind
the existing `labapps` ALB** (reuse the `taskvantage-apps/deploy/terraform` footprint + RDS), or
standalone — see Open Decisions. Rationale: we already operate this stack for the lab apps; another
small service is low marginal ops.

**Surfaces**

1. **Onboarding & consent** — pick your name (roster) or sign in; a clear consent notice that the
   session screen recording is collected for lab-improvement analysis, with the retention window.
   A **checklist gate**: "Start your Zoom full-screen recording before Module 1" + a 30-sec how-to.

2. **Quick per-module feedback** (the fast path — the Auth0 grid, reimagined):
   - For each module: a **1–5 rating**, the "look out for" list as **one-tap chips**
     (`inaccuracy`, `awkward transition`, `confusing`, `too long`, `style`, `improvement`,
     `story`), and an **optional free-text** box.
   - **Autosaves** per field. A tester can leave a real signal per module in ~5 seconds and still
     write prose where it matters.
   - Each free-text item can carry **attached media** (clip / timestamp / screenshot) added from the
     Review & tag surface.

3. **Upload recording** — resumable **multipart upload** straight to S3 via presigned URLs (handles
   0.5–2 GB files, survives flaky connections). Optional `.vtt` upload accepted but not required.
   On completion, kicks off the ingest pipeline; shows progress ("transcribing… detecting
   chapters…").

4. **Review & tag** — the recording with an **auto-built timeline**: proposed **module chapters**
   and flagged **friction moments** already marked. The tester scrubs, and with one action grabs a
   **clip** (in/out), a **timestamp**, or a **screenshot** and attaches it to a feedback item. The
   bot pre-suggests moments ("you spent 8 min on Module 3 around 00:22 — comment?"), so tagging is
   mostly *confirm + one sentence*.

5. **Export** — the reviewer × module **xlsx** (drop-in for the SE workflow) plus CSV/JSON of the
   structured records for analysis.

6. **Analytics view** (admin) — avg time per module across the cohort, a per-module friction score,
   and drill-down to the clips/quotes behind each score.

### 4.2 Ingest & transcription pipeline

Triggered when a multipart upload finalizes (S3 event → job):

- **Normalize/transcode** to a web-playable rendition (and keep the original).
- **Transcript** — Whisper → time-coded **VTT** stored alongside the recording. This is the
  self-generated transcript that dodges Zoom cloud-recording dependence (ADR-0003).
- **Scene-change detection** — ffmpeg `select='gt(scene,threshold)'` → a list of scene-boundary
  timestamps + a **keyframe thumbnail** per scene. Cheap, no model.
- Persist all artifacts + references in RDS.

Runs as an async worker (ECS task / job queue). Whisper can run on CPU for a first cut; revisit GPU
only if backlog demands it.

### 4.3 Enrichment & analytics

- **Auto-chapter (module spans).** Combine scene boundaries + a light read of the **module title**
  visible on the on-screen doc page (OCR/vision on candidate keyframes) + transcript cues → propose
  `module_spans`. The tester confirms/adjusts in Review & tag. Confirmed spans give accurate
  **time-per-module**.
- **Friction heuristics (Phase 4).** Over transcript + scenes, per module/screen:
  - **Dwell outliers** — a scene/module far longer than the cohort median.
  - **Backtracking** — returning to an earlier screen (scene-similarity revisit).
  - **Long silences** followed by bursts (stuck → recovered).
  - **Frustration phrases** in the transcript ("why isn't", "doesn't work", "where is", "stuck").
  - **Repeated retries** — same command/screen re-attempted.
  Each contributes to a per-screen **friction score**; the top moments become bot-suggested tags.
- **Vision-LLM classification (Phase 5, deferred).** Sample keyframes at flagged moments → classify
  *error visible / confused navigation / smooth*. Richest signal, added once the pipeline is solid.
- **Aggregates.** Avg + distribution of time per module; friction heatmap per module/screen;
  optional drop-off (where sessions end early).

---

## 5. Data model (sketch)

- `participants` — id, name, email, cohort.
- `sessions` — id, participant, started_at, status, consent_at.
- `recordings` — id, session, s3_key (original + rendition), duration, transcript_vtt_key, status.
- `module_spans` — id, session, module_key, start_offset, end_offset, source (`auto`/`confirmed`).
- `feedback_items` — id, session, module_key, rating, categories[], text, created_at.
- `media_assets` — id, session, type (`clip`/`screenshot`/`timestamp`), start_offset, end_offset,
  s3_key/thumb_key, linked_feedback_item.
- `friction_events` — id, session, module_key, offset, kind, score, evidence (quote/thumb).

Module keys come from a config list mirroring the repo (`lab-intro`, `module-1`…`module-6`).

---

## 6. Storage, retention, consent, access

- **Bucket** with per-session prefixes; **lifecycle** rule enforcing the retention window (to set —
  see Open Decisions). Server-side encryption; block public access; presigned URLs for up/download.
- **Consent** captured at onboarding (timestamped), with the retention window shown.
- **Access** — recordings + analytics visible only to the lab team (admin role); a tester sees only
  their own session. Auth model in Open Decisions.
- Account/region: reuse the lab footprint (account **959737396568**, us-east-2) unless standalone.

---

## 7. Phased implementation plan

Each phase delivers value on its own; feedback collection works before any recording exists.

- **Phase 0 — Scaffold.** Repo/app scaffold, data model + migrations, module-config, onboarding +
  **consent gate**, participant roster. Infra: bucket + RDS schema + service skeleton.
- **Phase 1 — Quick per-module feedback + xlsx export.** The Auth0-parity fast path (rating + chips +
  free text, autosave) and the reviewer × module **xlsx export**. *This alone replaces the
  spreadsheet.*
- **Phase 2 — Recording ingest.** Resumable **multipart upload → S3**, transcode, **Whisper
  transcript**, scene-change + keyframes. Playback in the portal.
- **Phase 3 — Review & tag.** Timeline UI; grab **clip/timestamp/screenshot** and attach to feedback;
  **auto-chapter** proposal + tester confirmation (module spans).
- **Phase 4 — Friction heuristics + analytics.** Heuristic friction scoring over transcript + scenes;
  bot-suggested tag candidates; cohort **analytics view** (avg time/module, friction heatmap).
- **Phase 5 — Vision-LLM friction (deferred).** Keyframe classification at flagged moments to enrich
  scores and suggestions.

Suggested review checkpoints: after Phase 1 (does the fast path feel faster than the sheet?) and
after Phase 3 (is tag-from-recording smooth enough that testers actually do it?).

---

## 8. Open decisions (need your call before/at build)

1. **Portal auth** — Okta OIDC via a demo org (on-brand, SSO) **vs.** lightweight email magic-link
   (lowest friction for external SE testers). *Lean: magic-link for the pilot, OIDC if it graduates.*
2. **Hosting** — reuse `taskvantage-apps` ECS/ALB/RDS **vs.** standalone stack. *Lean: reuse.*
3. **Code home** — new repo **vs.** subfolder in `taskvantage-apps` (e.g. `feedback-portal/`).
   *Lean: subfolder in `taskvantage-apps` to reuse the deploy pipeline.*
4. **Retention window** for recordings + who may view them (team-only assumed).
5. **Recording timing** — record the *whole* session in one file (simplest) vs. per-module clips
   (cleaner chapters but more tester overhead). *Lean: one file + auto-chapter.*
6. **Do we require the tester's Zoom `.vtt`** or always self-transcribe? *Lean: self-transcribe;
   accept theirs if provided.*
