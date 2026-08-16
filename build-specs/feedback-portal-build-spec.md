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

**Stack.** Next.js (App Router) deployed on **Vercel** (project `o4aa-feedback-portal`, Root
Directory `feedback-portal/`), with **Neon** serverless Postgres (Vercel Marketplace integration) +
**S3** for recordings. Lives in a **`feedback-portal/` subfolder of `taskvantage-apps`** (decision
§8.3). Rationale: Vercel is the native home for a Next.js app — git-push deploys, preview URLs, zero
container/ALB ops; Neon gives serverless-friendly pooled Postgres. (Supersedes the earlier
ECS/ALB/RDS plan — see decision §8.2.) Live: `https://o4aa-feedback-portal.vercel.app`.

**Auth.** **Auth0 passwordless (email magic-link)** — a dedicated Auth0 tenant, integrated as
standard OIDC (authorization-code + PKCE via `nextjs-auth0`). No custom auth/token/email code, and it
dogfoods the sibling devcamp's platform (decision §8.1).

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

3. **Upload recording** — a single resumable **multipart upload** of the mp4 straight to S3 via
   presigned URLs (handles 0.5–2 GB files, survives flaky connections). **One file only** — no
   separate transcript upload; we self-transcribe (decision §8.4/§8.6). On completion, kicks off the
   ingest pipeline; shows progress ("transcribing… detecting chapters…").

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
- **Transcript** — self-hosted **faster-whisper** → time-coded **VTT** stored alongside the
  recording (audio never leaves the account). This is the sole transcript source; we do **not**
  accept or depend on Zoom's `.vtt` (ADR-0003, decision §8.6). Speaker diarization, if ever needed,
  is added in-pipeline (whisperx/pyannote), not via Zoom.
- **Scene-change detection** — ffmpeg `select='gt(scene,threshold)'` → a list of scene-boundary
  timestamps + a **keyframe thumbnail** per scene. Cheap, no model.
- Persist all artifacts + references in RDS.

Runs as an async worker **off Vercel** — Vercel functions cap at ~300s, too short for transcribing a
60–90 min recording, so Whisper runs on an offloaded worker (queue + a container/Lambda, or a managed
STT). Large mp4 uploads go **direct to S3** via presigned URLs, bypassing Vercel's function payload
limits. Whisper can run on CPU for a first cut; revisit GPU only if backlog demands it.

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

- **Bucket** with per-session prefixes; **long-term archive, no expiration** (decision §8.4).
  Lifecycle **transitions** manage cost: Standard/Standard-IA during the active review window
  (~90 days, instant playback) → **Glacier Flexible → Deep Archive** for cheap long-term hold
  (older recordings restore in minutes-to-hours, acceptable for an archive). Server-side encryption;
  block public access; presigned URLs for up/download.
- **Consent** captured at onboarding (timestamped), stating the recording is retained long-term for
  lab-improvement analysis.
- **Access** — recordings + analytics visible only to the lab team (admin role); a tester sees only
  their own session. Identity via Auth0 passwordless (§4.1).
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

## 8. Decisions (resolved July 2026)

1. **Portal auth — Auth0 passwordless (email magic-link).** A dedicated Auth0 tenant, integrated as
   standard OIDC (auth-code + PKCE via `nextjs-auth0`). No custom auth code; dogfoods the sibling
   devcamp platform. (§4.1)
2. **Hosting — Vercel** (project `o4aa-feedback-portal`), with **Neon** serverless Postgres via the
   Vercel Marketplace integration. *(Revised July 2026 — supersedes the original "reuse
   `taskvantage-apps` ECS/ALB/RDS" decision; Vercel is the native fit for the Next.js app and drops
   the container/ALB ops.)*
3. **Code home — a `feedback-portal/` subfolder in `taskvantage-apps`** (Vercel Root Directory).
4. **Retention — long-term S3 archive, no expiration.** Lifecycle *transitions* (Standard/IA →
   Glacier Flexible → Deep Archive) manage cost; recent recordings stay instantly playable, older
   ones restore on demand. Team-only access. (§6)
5. **Recording — one file per session** (whole session), with module boundaries recovered by
   auto-chapter + tester confirmation. Lowest tester friction. (§4.3)
6. **Transcript — always self-transcribe (faster-whisper); the tester's Zoom `.vtt` is not used.**
   Most local recordings have none, requiring it fights the one-file decision, and self-transcribing
   gives uniform time-coded output for everyone with audio staying in-account. (§4.2)
