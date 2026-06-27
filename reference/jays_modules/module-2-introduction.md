# Module 2: The Blueprint [~10 minutes]

## How Identity Makes AI Agents Governable

Without an identity layer, an AI agent is invisible to your security stack. It doesn't appear in your directory. It doesn't participate in access policies. It doesn't generate audit events. It's a ghost with API keys.

Okta for AI Agents changes that by making the agent a **first-class identity** — the same way a human employee is. Once the agent has an identity, everything else follows: access policies apply to it, governance workflows cover it, and every action it takes is logged against it.

Here's what that looks like end-to-end:

## The Four Things You'll Configure

```
┌──────────────────────────────────────────────────────────────┐
│                                                              │
│  1. IDENTITY        2. ACCESS           3. CONTROL           │
│  Register agent     Auth server +       CIBA policy          │
│  Assign owner       scopes + policy     (human-in-the-loop)  │
│  Add credentials    Managed connection                       │
│  Link to app                                                 │
│                                                              │
│                     4. VISIBILITY                             │
│                     System Log — every action audited         │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

**Identity** — The agent is registered in Okta Universal Directory as a workload principal. It has a name, a human owner, and a public-key credential. It can be activated, deactivated, and governed.

**Access** — A custom authorization server defines what scopes (permissions) exist for VantageDesk. An access policy determines which users get which scopes. A managed connection on the agent authorizes it to request tokens from that server. The MCP Adapter enforces all of this at runtime.

**Control** — A CIBA (Client-Initiated Backchannel Authentication) policy gates sensitive actions. When the agent attempts something consequential — like escalating an incident to P1 — the adapter pauses execution and sends a push notification to the user's Okta Verify. The action only proceeds if the human approves.

**Visibility** — Every token exchange, every tool call, every CIBA approval or denial is recorded in the Okta System Log. Full attribution: which user, which agent, which resource, which action, when.

## The Flow at Runtime

When you type a prompt to the agent in Module 6, here's what happens behind the scenes:

```
You (as Kim Liu) → opencode.io → Okta MCP Adapter → Okta → VantageDesk
```

Step by step:

1. **You type a prompt** — "Look up ticket TKT-1734"
2. **opencode.io** decides it needs the `itsm.lookup_ticket` tool
3. **The MCP Adapter** intercepts the call. It checks:
   - Is this agent registered and active in Okta? ✓
   - Does Kim Liu have an active session on the linked app? ✓
   - Is `itsm.tickets.read` in Kim's effective scopes? ✓
4. **The Adapter performs XAA token exchange** — swaps Kim's identity + the agent's credential for a short-lived, scoped access token at VantageDesk's authorization server
5. **The tool call executes** — VantageDesk sees a request authenticated as Kim Liu, scoped to `itsm.tickets.read`, attributed to the TaskVantage agent
6. **The result flows back** through the adapter to opencode.io, which presents it to you

If Kim didn't have the right scope? The tool never appears in the catalog. The agent can't even try.

If the action requires CIBA? The adapter holds at step 4 and sends a push notification. Only on approval does it continue.

## What Makes This Different

| Traditional approach | With Okta for AI Agents |
|---|---|
| Agent uses a static API key | Agent uses short-lived, user-scoped tokens |
| Same permissions for every user | Permissions follow the user's identity |
| No audit trail for agent actions | Every action logged with user + agent attribution |
| No way to stop a rogue agent | Kill switch: deactivate the agent, all access stops |
| Sensitive actions execute autonomously | CIBA gates consequential actions behind human approval |

## What's Already Set Up For You

Your lab environment comes pre-configured with:

- **VantageDesk** — running and accessible, populated with tickets, incidents, and knowledge base articles
- **Okta MCP Adapter** — deployed and pointed at your Okta org and VantageDesk's MCP server
- **opencode.io** — installed on your Virtual Desktop, configured to use the MCP Adapter
- **Kim Liu** — a test user in your Okta org with Okta Verify enrolled, member of the `IT Help Desk` group
- **Groups** — `IT Help Desk`, `All Employees` pre-created

## What You'll Build

Over the next four modules, you will create:

- The agent identity (Module 3: "The World It'll Operate In" tours what exists; Module 4: "Getting a Badge" creates the agent)
- The access layer (Module 5: "Getting a Desk" builds the auth server, scopes, policy, and managed connection)
- The live experience (Module 6: "First Day on the Job" — talk to the agent, watch it work)
- The human gate (Module 7: "Knowing When to Ask" — CIBA in action)
- The proof (Module 8: "The Performance Review" — audit trail walkthrough)

Each module builds on the previous one. By the end, you'll have a complete, governed AI agent you can point at any backend and say: "This is how we do it securely."

---

**Ready?** In the next module, you'll tour the environment — see what's running, confirm connectivity, and understand the starting state before you build anything.
