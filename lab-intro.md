# Lab Intro: TaskVantage AI Agents Tech Camp

> **START HERE: launch your lab environment right now, before you read anything else.**
>
> 1. Go to the launchpad.
> 2. Spin up your **Virtual Desktop (VDI)**.
>
> ***NOTE: Do this first, then keep reading. A fresh environment takes a few minutes to provision, so it will be ready by the time you reach Lab 1.***

Over the next three to four hours you take an unmanaged AI agent, turn it into an Okta-governed identity with controlled access to two business apps, then watch that governance work end to end.

<details>
<summary><b>Context: what this module is (read once)</b></summary>

- This module is the introduction: it sets the world, introduces the people, and points at the structure that follows.
- The work itself happens in Labs 1 through 5.
- By the end, "we have AI agents in production" and "we know what our AI agents can do" become the same sentence.
</details>

---

## About TaskVantage

<details>
<summary><b>Context: the company and your role (read once)</b></summary>

- TaskVantage is a fictional mid-size software company in mid-2026: a real sales org, IT help desk, engineering team, and executive layer, but small enough that one person knows who built every system. You are on its identity team.
- For eighteen months, departments have built AI agents to move faster. Sales Ops built one for reps to look up account context and update opportunities in VantageCRM. The IT help desk wants its own. Engineering managers ask weekly for "just read access" to CRM data for cross-functional projects.
- Each conversation starts the same way: *"can the agent just have an API key for now?"*
</details>

The board met last week. They asked the question every IT leader has heard in 2026, phrased three ways:

- *What agents do we actually have?*
- *What can they do, and on whose behalf?*
- *How do we stop one if it goes wrong?*

You don't have answers for any of these yet. Today, you build them.

---

## Why an agent needs its own identity

<details>
<summary><b>Context: why an API key is the wrong answer (read once)</b></summary>

- A traditional app does exactly what it was coded to do, and nothing more. An AI agent decides **at runtime** what to call and reach, based on whatever a user asks of it.
- Hand an agent a service account or API key and it can do everything that credential can do, for *anyone* who talks to it.
- A sales rep who may only read their own accounts, working through an agent that holds a broad credential, reaches data they were never entitled to. You haven't given the agent access; you've built a **privilege-escalation path** into your stack.
</details>

The fix: stop treating the agent as a *credential* and start treating it as an **identity**, its own first-class identity in Okta, bound to the user it acts for. Its effective access becomes an intersection:

> **what the agent may do  ∩  what the _user_ may do  ∩  what the resource exposes**

- The API-key model drops the middle term. First-class identity puts the user back in.
- The agent can only ever act where the person it's helping can act, and every action is attributable to both the agent and that user.
- A service-account key is a master key: it opens every lock, but the reader never records who walked through. A first-class identity is a personal key ring: the agent borrows only the keys the user it serves already carries, and the door knows whose they were.

### The mental model: an agent's first day on the job

Everything you do today follows the arc of onboarding a new employee, because governing an agent *is* that:

| Today you... | ...just like a new hire |
| --- | --- |
| Register the agent as an identity in Okta, with an accountable owner | Day one: a record in the directory, and a manager responsible for them |
| Give it a credential and a sign-on app | A badge, and the set of people it may act for |
| Wire its access to an app, scoped | A desk, and keys to the rooms the job needs |
| Watch it act *as* each user, bounded by that user | A new hire can only open the doors their own badge opens |
| Put its access through review, and keep a kill switch | Access reviews, and the ability to suspend the badge instantly |

By the end, the agent is one of the most governed identities in your org, and the board's three questions are answered: what it is, what it can do and for whom, and how to stop it in one click.

---

## The people you will work with

You spend most of this camp as a TaskVantage admin (your own personal admin account, which you finish setting up at the start of Lab 1). Several other identities matter, because what the agent can do depends on whose behalf it is acting. You run flows from their perspective at multiple points.

| Person | Role | Why they matter to the story |
| --- | --- | --- |
| **Susan Potter** | Sales Manager | Full CRM access. The standard agent user: Okta authorizes the full CRM tool set for her, and she sees all accounts. |
| **Alex Martinez** | Sales Rep | A CRM-group member, so Okta authorizes the full CRM tool set for him too, but VantageCRM row-filters his **data** to the accounts he owns. The "same agent, same tools authorized, less data" comparison case. (Tool-level differentiation per role is a future graduated model, not wired today.) |
| **Kim Liu** | IT Help Desk Tier 1 | Full VantageDesk access; also a CRM-group member (so Okta authorizes CRM tools for her, with role-bounded data). Cross-system user; Okta authorizes the agent's full ITSM toolkit for her in Lab 4. |
| **Frank Boone** | Engineering Director | No CRM or ITSM access by default: he can SEE the agent's tools like everyone else, but Okta blocks his use of them until OIG grants access. The OIG round-trip in Lab 5 happens to him: he requests temporary access, watches his tools flip from blocked to usable, and watches them blocked again. |
| **Sally Field** | Executive | Interacts with the agent rather than the apps directly. Appears in the background; her existence frames why "the agent's access is the user's access" matters. |

The exact passwords and account details are in Lab 1.3. No need to memorize anything yet.

---

## The two business applications

- TaskVantage runs on a custom-built CRM (**VantageCRM**) and a custom-built ITSM (**VantageDesk**). Deliberately fake apps that stand in for whatever your real organization uses.
- Resource servers only: no app UI, no human sign-in. Every interaction is an agentic API call carrying a Bearer access token, and each app resolves your tenant from the token's **issuer**.
- The agent never talks to either app directly. It talks to each app's **MCP server** through the **Okta MCP Adapter**, the policy enforcement point you see in action repeatedly.
- Per-attendee: your agent, Okta MCP Adapter, and Okta org. Central and shared: the two MCP servers (one per app) and the two apps.

The full picture is below.

[embed architecture image here]

---

## Your agent in Lab 2: OpenCode

- In Lab 2 you bring an agent under Okta management.
- The agent is **OpenCode**, an open-source AI coding agent **already installed and configured on your Virtual Desktop**.
- You don't install or build anything. You register the OpenCode instance waiting on your VM as a first-class identity in Okta and govern it. The rest of the camp assumes this path.

---

## The camp's arc

| Lab | What happens | Time |
| --- | --- | --- |
| **1 - The World It'll Operate In** *(Environment Tour)* | Sign in to the Okta Admin Console, meet the personas, see both apps (out-of-band screenshots / the Lab Toolkit), run the environment check from the Lab Toolkit, build your first piece of configuration (the VantageDesk auth server access policy). | 25 min |
| **2 - Getting a Badge** *(Bring the Agent Under Management)* | Register your pre-installed OpenCode agent, assign an owner, generate a key, create the managed connection to VantageCRM. | 45 min |
| **3 - First Day on the Job** *(Govern the Agent's Tools by User)* | Run the agent's tool-listing call as three different users (every user sees the same full catalog) and watch Okta authorize a different set of those tools for each at use-time. The toolkit hands you the decoded token Okta issued, its System Log audit record, and a deep link to the event; a side-by-side mode puts one user's grant and another's denial on a single screen. | 30 min |
| **4 - Getting a Desk** *(Build VantageDesk and Watch XAA in Flight)* | Build the missing half (auth server, scopes, policy, managed connection), then invoke a tool end-to-end and watch the ID-JAG / two-step exchange happen with your own eyes. | 60 min |
| **5 - The Performance Review** *(Govern with OIG)* | Submit an access request, approve it, watch Okta start authorizing Frank's tools; revoke via certification, watch the authorization fall away; exercise the kill switch. | 50 min |
| **Wings Earned** *(Conclusion)* | Step back: the agent is now one of the most governed identities in your org, and the board's three questions are answered, then prove enforcement is server-side, not a client flag, with the toolkit's "prove it can't be faked" mode. ~5 min. | 5 min |

About 3.5 hours of actual work. Build in a break after Lab 2 or in the middle of Lab 4 if your group is pacing more slowly.

---

## The shape of the work

<details>
<summary><b>Context: two patterns that repeat (read once)</b></summary>

Watching for these two patterns makes the structure easier to follow.
</details>

**Review-then-build.**
- Each major capability is introduced first on VantageCRM (already fully wired), then built by you on VantageDesk (intentionally incomplete).
- Authorization server, scopes, access policy, managed connection: you observe each on CRM first, then create it on Desk.
- Access to the API-only apps is gated by the auth server's access policy mapping groups to scopes; there is no per-app sign-in policy, because no human signs in to the apps.
- By the end of Lab 4, both columns of the architecture are identically configured. The first instance of the pattern appears in Lab 1.10.

**Same agent, different access.**
- You keep running the same Lab Toolkit actions (**List the agent's tools**, **Invoke a tool**) against different users. The agent's identity does not change, and neither does its configuration between most runs.
- The catalog every user sees does not change either: tool *visibility* is a property of the agent, so Alex, Susan, Kim, and Frank all see the same tools.
- Every persona action prints the **decoded token Okta actually issued** for that user (or Okta's verbatim refusal), so you watch the real artifact, not a label the toolkit computed.
- What changes is whether Okta authorizes a given user to actually invoke a tool, decided at the token exchange. If the user isn't entitled, Okta issues no token and the action is denied (*Authentication failed for resource*). Okta doesn't hide the menu; it refuses the action. Agent capability is governed at the moment of action, against the live access policy: a stronger control than hiding tools.

*NOTE: Today authorization is binary: a user in a relevant group gets the full tool set for that app; a non-member gets none but still sees them all. Data is then filtered per user inside the authorized tools. Finer per-role tool subsets are a planned enhancement.*

---

## How to read this guide

A few conventions appear throughout the labs.

- ***NOTE: italic blocks*** are context: why a step matters, or what to watch for. Read them; they often save you a frustrating debugging session two labs later.
- **Double-brace placeholders** like `{{idp.tenantDomain}}` (your org) are Mustache variables the lab platform fills in at runtime from your live demo environment.
- **Lab Toolkit steps** point you at a numbered choice in the desktop **Lab Toolkit** (and a persona, when prompted). The code blocks that follow show the output you should see. If your output diverges substantially, raise it with a proctor before continuing; later labs fail in confusing ways when an earlier one quietly went wrong.

---

## Before you start Lab 1

Confirm these are all true:

- [ ] The Virtual Desktop you launched at the start of this intro has finished provisioning, and you can reach it.
- [ ] You have accepted the invite to your Okta org and logged in as an admin.
- [ ] OpenCode is available on the desktop of your VDI.
- [ ] You see all the noted users in your lab tenant, and you are listed as the manager for all of them.

When all four are checked, open Lab Module 1 and begin.
