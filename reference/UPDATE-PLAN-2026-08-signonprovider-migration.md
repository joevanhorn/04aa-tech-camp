# Tech Camp Update Plan: signOnProvider Migration + Bridge 0.16.x

**Date:** 2026-08-17
**Trigger:** Okta moved AI Agent SSO binding into the application (`signOnProvider`, auto-created OIDC apps, client_id = workload principal ID) and the bridge moved to 0.16.x (import redesign, private_key_jwt relay, read-only auth-method labels). Attendee orgs for the next camp will be on the migrated model.
**Grounding:**
- Platform inventory: `ofcto-workforce-taskvantage/docs/O4AA_PLATFORM_CHANGES_2026-08.md`
- Live validation on migrated org `demo-o4aa-techcamp-xaa2` (full DCR, relay, XAA, tool-call chain green on 2026-08-17)
- Bridge fixes: PR #4 on `joevanhorn/okta-agent-mcp-adapter` (`fix/dcr-private-key-jwt-agents`), required for DCR linking of migrated agents; upstream mirror pending
- Repo sweep of `04aa-tech-camp` (all file:line references below are from that sweep)

**Publishing note:** the live guides are mirrored to `demo-assets` (`assets/labs/techcamp-o4aa/en/*.md`) with different section numbering. Every module-text change below must be applied here first, then mirrored (see `reference/UPDATES-2026-07-26-live-test-fixes.md:16`).

---

## Category 1: Technical updates

Ordered by dependency. T1 and T2 block everything downstream.

| # | Item | Files / systems | Detail |
|---|------|-----------------|--------|
| T1 | **Merge the DCR private_key_jwt fixes upstream, then cut a 0.16.x bundle** | adapter repo `deploy/bundle/`; S3 `s3://okta-terraform-demo/o4aa-bridge/` | PR #4 must be in the build or DCR linking of migrated agents fails (503 or authorize redirect loop). Build from main, publish `okta-mcp-adapter-bundle-0.16.x.tar.gz`, replace the 0.15.14 artifact referenced at `lab-infra/heropa-userdata.md:111`. The launcher glob (`bridge-launcher.py:31`) is version-agnostic, no change there. |
| T2 | **Add the gateway callback to the agent's auto-created app** | `lab-infra/wire_adapter_resource.py` or a new provisioning step | Auto-created apps ship with only `localhost:8080`. Nothing in the repo registers `<GATEWAY_BASE_URL>/oauth/callback`, and the brokered OAuth in Modules 3 and 4 depends on it. Add an SSWS step that appends the callback to the app at `signOnProvider.appInstanceId` after agent registration. Also add the agent-UI redirect URI here if Module 2 keeps a front-end flow. |
| T3 | **Update `wire_adapter_resource.py` for the 0.16 import contract** | `lab-infra/wire_adapter_resource.py:117-164, 237-244, 278-282` | (a) Handle `selection_required: true` + `candidates` from `POST /api/admin/okta/agents/{id}/import` (currently swallowed, then fails as "agent not found after import"). (b) Read the new agent fields (`oauth_client_id`, `sign_on_provider_app_instance_id`, `token_endpoint_auth_method`). (c) Revisit the `principal_id == okta_agent_id` match at L162: on migrated agents the OAuth client_id also equals the wlp ID, so disambiguate on `okta_ai_agent_id` explicitly. |
| T4 | **Fix `AGENT_CID_NAME_MAP` for wlp client IDs** | `build-specs/lab-apps-build-spec.md:84,87,157,171,435`; deployed VantageCRM/VantageDesk config | The lab apps map `0oa...` client IDs to agent display names for the access log ("Client: TaskVantage Sales Agent", surfaced in Module 4 §4.11). The agent's client_id is now `wlp...`. Update the map format/values and redeploy the apps. |
| T5 | **Org provisioning: create the example agent with `signOnProvider`** | successor to `archive/provision_lab_org.py:456-473`; org template | The pre-loaded `VantageCRM Example Agent` (Module 1 §1.8) should be created with `signOnProvider: {type: NEW_OIDC_APP}` so what attendees tour matches what they build. Registration API is otherwise unchanged (202 async already handled). Service-app admin role requirement is already documented at `lab-infra/README.md:92-98`, no change. |
| T6 | **Bridge env + Heropa redeploy** | `lab-infra/BRIDGE-PROVISIONING.md:19,38,83,199`; `lab-infra/LAB-REQUIREMENTS.md:10-14`; Heropa build host | Update bundle name/paths and raise the version floor from ">= 0.15.14" to the new 0.16.x build (the floor exists for the Module 5.8 kill-switch behavior, which 0.16 retains). Redeploy the Heropa bridge host from the new bundle and retest `bind-to-org.sh` against a migrated org. Do NOT enable `AGENT_ROUTING_ENABLED`: the labs route via `X-MCP-Agent` (bootstrap.ps1) and per-resource paths, not per-agent paths. |
| T7 | **Verify, no change expected** | `lab-infra/bridge-launcher/bridge-launcher.py:207-208`; toolkit; custom AS grants | (a) The `^0oa` regex only validates the Admin UI SPA client (still an `0oa` app); confirm it is never fed the agent client. (b) Lab Toolkit mocks the MCP data path, not the admin API; re-run its auth path once against the 0.16 bridge (X-MCP-Agent binding tightened in `8015ac9`). (c) Infra AS policies already grant token-exchange + jwt-bearer (`provision_lab_org.py:97-98`), which matches what migrated-org XAA needs. |
| T8 | **Full E2E validation run before content freeze** | xaa2 org + new bundle | Re-run the Module 2-5 flow end to end (register with auto-create, wire CRM, tool calls as all three personas, OIG request/cert, kill switch) on a migrated org with the new bundle. The xaa2 validation covered the adapter chain; this run covers the lab's exact scripts and personas. |

Decision needed: whether to add the `refresh_token` grant to auto-created agent apps (relay sessions currently cannot refresh; attendees re-auth on expiry). For a 4-hour camp, one-hour tokens are probably fine, so the default is to skip it and note the behavior.

## Category 2: Module text updates

| # | Module / section | Change |
|---|------------------|--------|
| M1 | **Module 2 §2.3 (L58-72), register the agent** | Rewrite for the new register flow. The "leave the optional Application link blank" instruction and the deferred linking premise are gone: registration now creates and binds the OIDC app (`signOnProvider`). Update the step list and the "you link an app in 2.6" forward reference. |
| M2 | **Module 2 §2.6 (L115-147), the big one** | Replace "Create and link a user-sign-on app" wholesale. New shape: review the auto-created app, note that its Client ID equals the agent's principal ID (`wlp...`), note there is no client secret (`private_key_jwt`), and add the required redirect URI(s). The "note the Client ID and Client secret" instruction (L136) and the User sign-on tab linking walk-through are invalid. Verify the current Admin Console tab/label names on a migrated org before writing; preserve exact Okta UI names per house style. |
| M3 | **Module 2 §2.12 verify table (L250-273)** | Update rows: the sign-on app row (now auto-created, named after the agent unless renamed), and reframe the `wlp...` note at L269. It is currently glossed as "principal id"; it is now also the agent's OAuth client_id, which is worth one teaching sentence since attendees will see it in tokens in Modules 3-4. |
| M4 | **Module 2 §2.9-2.10 (L178-228), bridge review** | Update the adapter walk-through for the 0.16 Admin UI: Agent Detail now has a Linked Application panel and read-only "Auth method" / "Keys managed on" labels. The §2.5 framing ("the bridge holds and syncs the private key", L100) stays correct, validated live. |
| M5 | **Module 4 §4.7 (L168-187), add the Desk resource** | Adjust "leave the auth method as okta-cross-app": auth method is now derived from the connection and shown read-only. Reword the hand-add fallback accordingly. |
| M6 | **Modules 3-4 token transcripts** | Update the illustrative decoded-token panels and XAA hop outputs where the agent's identity appears: `cid` and `act.sub` are now the `wlp...` value (verified live: `cid: wlp..., act: {sub: wlp..., sub_profile: "ai_agent web_app"}`). The `{{adapter_dcr_client_id}}` panels (M3 L126/179/233, M4 L249) are the DCR client and stay as-is. Module 4 §4.11 access-log output (L346, 357-358) depends on T4. |
| M7 | **Module 1 §1.8 (L245-251)** | Remove the "Click Settings (top-right)" instruction (already removed from the published copy per `reference/UPDATES-2026-07-26-live-test-fixes.md:31-34`; still present in this source). Refresh the AI Agents area description for the migrated model, including what the pre-loaded agent's binding looks like. |
| M8 | **Framing touch-ups** | `lab-intro.md:67` ("Give it a credential and a sign-on app") and `module-6-wings-earned.md:15` ("a linked sign-on app"): adjust to the auto-created binding. Module 2 intro rows (L11, 19). Module 4 L119 note ("the assigned client must be the AI agent, not its user-sign-on app") stays but gains force: they now share one client_id story, so reword to prevent confusion. |
| M9 | **Reference docs** | Mark `reference/e2e-walkthrough-findings.md` §on `appId` linking (L125-145) and `reference/okta-xaa-id-jag-analysis.md:73` as superseded by the signOnProvider model (banner note, do not silently edit findings docs). `reference/xaa-bridge-wiring-lessons.md:120-139` pending module section should be written against the new import dialog. |
| M10 | **Mirror to demo-assets** | Apply every M-item to the published `en/*.md` copies (different section numbering) after this repo's versions are approved. |

Style: all rewrites follow the existing rules, no em dashes, no AI-tell constructions, exact Okta UI names, "limit" not "cap".

## Category 3: Screenshot updates

Screenshot markers live in `archive/modules-screenshots/*.md` (the live modules carry no images); capture runs via the `lab-screenshot` Playwright bot per `archive/modules-screenshots/RUNBOOK.md`, which needs a temp admin on a **migrated** org (xaa2 works today; ideally the refreshed attendee-org template). Recapture only what the model change touches.

| Priority | Set | Markers | Why |
|----------|-----|---------|-----|
| P1 | **Module 2 admin-console set** | `module-2.md` L63 (register dialog), L79 (Owners), L97 (Credentials), L124 (app page "showing Client ID and Client secret": now secret-less and auto-created), L137 (User sign-on tab), L151 (activate), L186 (managed connection) | The register and app screens changed shape; L124 and L137 are flatly wrong under the new model. Effectively the full 9-shot admin sequence re-shoots to keep visual continuity. |
| P1 | **Module 2 bridge UI set** | L199 (Agents view), L202 (Resources view) | 0.16 Admin UI: new import dialog styling, Linked Application panel, auth-method labels. |
| P1 | **Module 4 bridge + connections** | L156 (two managed connections), L173 (bridge Resources view), L321 (verbose XAA decoded chain) | L321 shows the token chain; the agent client values become `wlp...`. |
| P2 | **Module 1 AI Agents area** | `module-1.md` L200 (empty AI Agents list) plus the embedded copies (`module-1-admin-captured.md:106`, `module-1.embedded.md:186`) | List page gains sign-on provider column/details on migrated orgs; embedded variants must be regenerated, not just the marker set. |
| P2 | **Module 5 lifecycle dialogs** | `module-5.md` L249 (Deactivate dialog), L253 (DEACTIVATED), L290 (ACTIVE) | Lifecycle is now async server-side; verify the dialogs and status chips before assuming reuse. |
| P3 | **Module 3 System Log** | L206 (token-exchange chain), and Module 2 L252 (`target.type eq "AIAgent"` events) | Event stream now includes `workload_principal.*` operations and the app-creation events fire together with registration; recapture so the log matches the prose. |
| Skip | Persona/group/Toolkit-only shots | Module 1 L52-187, Module 3 Toolkit shots, Module 5 OIG flow shots | Unaffected by the platform change unless the E2E run (T8) shows otherwise. OIG and Toolkit UIs did not move. |

## Sequencing

1. T1 (PR merge + bundle) and T2/T3 (infra scripts) first; they gate T8.
2. T8 E2E validation run on a migrated org locks the exact UI labels and token values.
3. M-items written against T8's observed reality (especially M2's tab names).
4. Screenshots last, from the same run/org state the text describes.
5. M10 mirror to demo-assets once modules are approved, then republish.
