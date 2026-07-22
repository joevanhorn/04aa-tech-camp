# Module 1: An Agent Without an Identity [~10 minutes]

## The Problem

AI agents are everywhere. Your engineering team is using coding assistants. Your support team wants an agent that can triage tickets. Your operations team is building one that automates incident response. The CIO is pushing for more — faster deployment, broader adoption, measurable productivity gains.

But every one of those agents has the same problem: **no identity**.

They authenticate with hardcoded API keys stuffed in environment variables. They access backend systems with static credentials that never rotate. They act on behalf of users without any way to prove *which* user. When something goes wrong — and it will — there is no audit trail, no owner to call, and no kill switch to pull.

Your CISO is asking three questions:

1. **Who authorized this agent to act?**
2. **What is it allowed to do — and for whom?**
3. **Can I prove it to an auditor?**

Today, you answer all three.

## What You'll Build

By the end of this session, you will have taken a real AI agent — one you can talk to, ask questions, and give instructions — and turned it into a governed, auditable, identity-aware member of your workforce. Specifically:

- **Registered** the agent as a first-class identity in Okta Universal Directory, with a human owner accountable for its behavior
- **Scoped** its access so it can only reach the tools and data that the requesting user is authorized to use — not a blanket set of permissions, but per-user, per-resource, per-action
- **Secured** its communication through standards-based token exchange — no hardcoded credentials, no static API keys, short-lived tokens scoped to a single purpose
- **Gated** sensitive actions behind human approval — the agent stops and asks before doing anything consequential, via a push notification to your phone
- **Audited** every action it took — who asked, what the agent did, which resource it hit, and whether a human approved it

The agent doesn't lose any capability. It gains *trust*.

## The Stack

You will work with four components today:

| Component | What it does |
|---|---|
| **opencode.io** | The AI agent. Open-source, runs in your terminal. You talk to it in natural language and it calls tools on your behalf. |
| **Okta MCP Adapter** | Sits between the agent and backend systems. Handles authentication, filters available tools based on the user's permissions, and performs the secure token exchange. |
| **Okta** | Your identity provider. Where the agent is registered, where policies live, where tokens are issued, where everything is logged. |
| **VantageDesk** | An ITSM application (think ServiceNow, Jira Service Management). The agent will look up tickets, check incidents, and attempt escalations — all through the adapter. |

## The Pattern

This lab demonstrates one specific architecture pattern: **a third-party agent accessing third-party resources through the Okta MCP Adapter**.

The agent (opencode.io) wasn't built by you. The resource (VantageDesk) wasn't built by you. But the identity layer — the thing that makes it all governed — that's Okta, and that's what you configure today.

This same pattern applies whether the agent is Claude Code, GitHub Copilot, Cursor, or any other third-party AI assistant. And whether the resource is ServiceNow, Salesforce, Jira, or any internal API behind an MCP server.

## How This Session Works

- **Your local browser** is for the Okta Admin Console. You'll configure everything there.
- **Your Virtual Desktop** is where the agent lives. You'll interact with opencode.io there, and that's where Okta Verify is set up for the end-user persona.
- **You** are the platform/security engineer building the foundation.
- **Kim Liu** is the end user whose identity the agent will act on behalf of. She's already set up in your environment.

No code to write. No scripts to debug. Everything is configuration and conversation with the agent.

Let's begin.
