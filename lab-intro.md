# Lab Intro: TaskVantage AI Agents Tech Camp

Welcome. Over the next three to four hours, you will take an unmanaged AI agent and turn it into an Okta-governed identity with controlled access to two business applications, then watch every dimension of that governance work end to end. By the time you finish, you will have done the actual work that makes "we have AI agents in production" and "we know what our AI agents can do" the same sentence.

This module is the introduction. It sets the world you are about to operate in, introduces the people in it, and points you at the structure that follows. The work itself happens in Labs 1 through 5.

---

## About TaskVantage

TaskVantage is the fictional company you work for in this camp. It is a mid-size software company in mid-2026 — large enough to have a real sales organization, a real IT help desk, an engineering team, and an executive layer; small enough that one person knows who built every system. You are on its identity team.

Over the past eighteen months, individual departments across TaskVantage have built AI agents to make their work faster. Sales Operations built an agent that helps reps look up account context and update opportunities in VantageCRM. The IT help desk has been quietly asking for one of their own. Engineering managers ask weekly for "just read access" to CRM data for cross-functional projects. Each of these conversations starts the same way: *"can the agent just have an API key for now?"*

The board met last week. They asked the question every IT leader has heard in 2026, phrased three different ways:

- *What agents do we actually have?*
- *What can they do, and on whose behalf?*
- *How do we stop one if it goes wrong?*

You do not have answers for any of these yet. Today, you build them.

---

## The people you will work with

You spend most of this camp as a TaskVantage admin — your own personal admin account, which you will finish setting up at the start of Lab 1. But several other identities matter to the story, because the whole point of governance is that *what the agent can do depends on whose behalf it is acting*. You will run flows from their perspective at multiple points in the camp.

| Person | Role | Why they matter to the story |
| --- | --- | --- |
| **Susan Potter** | Sales Manager | Full CRM access. The standard agent user — full CRM tool set, and sees all accounts. |
| **Alex Martinez** | Sales Rep | A CRM-group member, so the agent surfaces him the full CRM tool set too — but VantageCRM row-filters his **data** to the accounts he owns. The "same agent, same tools, less data" comparison case. (Tool-level differentiation per role is a future graduated model — not wired today.) |
| **Kim Liu** | IT Help Desk Tier 1 | Full VantageDesk access; also a CRM-group member (so she gets CRM tools, with role-bounded data). Cross-system user; gets the agent's full ITSM toolkit in Lab 4. |
| **Frank Boone** | Engineering Director | No CRM or ITSM access by default. The OIG round-trip in Lab 5 happens to him: he requests temporary access, watches it appear, and watches it disappear. |
| **Sally Field** | Executive | Interacts with the agent rather than the apps directly. Appears in the background — her existence frames why "the agent's access is the user's access" matters. |

The exact passwords and account details are in Lab 1.3 — no need to memorize anything yet.

---

## The two business applications

TaskVantage runs on a custom-built CRM (**VantageCRM**) and a custom-built ITSM (**VantageDesk**). They are deliberately fake apps that offer similar capabilities to real applications you may be familiar with. Think of them as stand-ins for whatever your real organization uses.

They are resource servers only: there is no app UI and no human sign-in to them. Every interaction for today's lab will be an agentic API call carrying a Bearer access token, and each app resolves which tenant (your org) a call belongs to from the token's **issuer**. The agent never talks to either app directly. It talks to a MCP server through the **Okta MCP Adapter**, which is the policy enforcement point you will see in action repeatedly. Your **agent and Okta MCP Adapter — and your Okta org — are per-attendee**; the **MCP server and the two apps are central/shared** (see ADR-0002).

The full picture is below.

[embed architecture image here]

---

## Your agent in Lab 2: OpenCode

In Lab 2 you bring an agent under Okta management. The agent is **OpenCode** — an open-source AI coding agent that is **already installed and configured on your Virtual Desktop**. You don't install or build anything; you register the OpenCode instance waiting on your VM as a first-class identity in Okta and govern it. This is the path the rest of the camp assumes.

If you'd rather bring a different agent — importing one from AWS Bedrock AgentCore, or registering another custom runtime — that's at your discretion (Lab 2.11). The Okta steps are identical regardless of runtime; only the agent itself differs. Either way you end at the same point: an active agent in your AI Agents Registry.

---

## The camp's arc

| Lab | What happens | Time |
| --- | --- | --- |
| **1 — Environment Tour** | Sign in to the Okta Admin Console, meet the personas, see both apps (out-of-band screenshots / read scripts), run the env-check script, build your first piece of configuration (the VantageDesk auth server access policy). | 25 min |
| **2 — Bring the Agent Under Management** | Register your pre-installed OpenCode agent, assign an owner, generate a key, create the managed connection to VantageCRM. | 45 min |
| **3 — See the Adapter Filter Tools by User** | Run the agent's tool-listing call as three different users and watch three different catalogs come back. Inspect the audit trail. | 30 min |
| **4 — Build VantageDesk and Watch XAA in Flight** | Build the missing half — auth server, scopes, policy, managed connection — then invoke a tool end-to-end and watch the ID-JAG / two-step exchange happen with your own eyes. | 60 min |
| **5 — Govern with OIG** | Submit an access request, approve it, watch tools appear; revoke via certification, watch them disappear; exercise the kill switch. | 50 min |

About 3.5 hours of actual work. Build in a break after Lab 2 or in the middle of Lab 4 if your group is pacing more slowly.

---

## The shape of the work

Two patterns repeat throughout the camp. Watching for them makes the structure easier to follow.

**Review-then-build.** Each major capability is introduced first on VantageCRM, where it is already fully wired before you start, and then built by you on VantageDesk, which is intentionally incomplete. Authorization server, scopes, access policy, managed connection — every one of these you observe on CRM first, then create on Desk. (Access to the API-only apps is gated by the auth server's access policy mapping groups to scopes — there is no per-app sign-in policy, because no human signs in to the apps.) By the end of Lab 4, both columns of the architecture are identically configured. The first instance of the pattern appears in Lab 1.10.

**Same agent, different access.** Throughout the camp, you keep running the same script — `list-agent-tools.sh` or `invoke-agent-tool.sh` — against different users, sometimes against the same user at different points in time. The agent's identity does not change. Its configuration does not change between most of the runs. What changes is *who is asking* and *what they are currently entitled to do*. The story the camp tells is that agent capability is a property of the user-and-moment, not a property of the agent. (Today the **tool catalog** is gated binary — a user in a relevant group gets the full tool set for that app, a non-member gets none — and **data** is then filtered per user inside the tools; finer per-role tool subsets are a planned enhancement.)

---

## How to read this guide

A few conventions appear throughout the labs.

- ***NOTE: italic blocks*** are context — explanation of why a step matters, or what to watch for. Read them; they often save you a frustrating debugging session two labs later.
- **`{{double_brace_placeholders}}`** are values that vary per-attendee or per-lab-environment, like `{{org_url}}` or `{{lab_domain}}`. Your environment provides the real values; the guide uses placeholders so a single guide works across deployments.
- **Code blocks** show commands you run on the VDI terminal and the output you should see back. If your output diverges substantially, raise it with a proctor before continuing — later labs often fail in confusing ways when an earlier one quietly went wrong.

---

## Before you start Lab 1

Confirm these are all true:

- [ ] Your Heropa allocation is active and you can reach the Virtual Desktop.
- [ ] You have your Okta org URL and admin credentials in hand.
- [ ] You know which Lab 2 path you intend to take (A or B). If unsure, default to whichever the proctor recommends for your cohort.
- [ ] You have at least three uninterrupted hours ahead of you. The labs build on each other; stopping in the middle of Lab 4 and resuming the next day is doable but adds friction.

When all four are checked, open Lab Module 1 and begin.
