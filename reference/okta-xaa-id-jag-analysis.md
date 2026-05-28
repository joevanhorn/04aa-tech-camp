# Okta's AI agent identity: what actually ships and how it works

**Okta's AI agent identity story is a two-platform play built on a single open protocol.** On the workforce side, "Okta for AI Agents" registers AI agents as first-class non-human identities in Universal Directory and mediates their access to enterprise apps through Cross App Access (XAA) — a two-step token exchange protocol built on the IETF ID-JAG specification. On the CIAM side, Auth0 for AI Agents (GA since November 2025) provides developer SDKs for token vaulting, async authorization via CIBA, and fine-grained authorization for RAG. The workforce product enters GA on **April 30, 2026**; XAA remains in self-service Early Access on both platforms. The critical limitation today: **XAA only works within a single trust domain** — cross-organizational agent delegation is explicitly unsolved.

---

## The two products and where they sit

A Solutions Engineer must understand these as distinct but converging offerings:

| Product | Platform | Audience | Status |
|---------|----------|----------|--------|
| **Auth0 for AI Agents** | Auth0 / Customer Identity Cloud | Developers building GenAI apps | **GA** (Nov 2025) |
| **Okta for AI Agents** | Okta Workforce Identity Cloud | Enterprise IT governing agents | **EA** now; **GA April 30, 2026** |
| **Cross App Access (XAA)** | Both platforms | ISVs + Enterprise IT | **EA** (self-service) |

Auth0 is SDK-first and developer-facing — embed identity into agent code with framework integrations for LangChain, Vercel AI, LlamaIndex, and Genkit. The workforce side is admin-console-first — discover shadow agents, register them in Universal Directory, enforce enterprise policy via managed connections, and govern their lifecycle through OIG.

The architectural bridge between the two is **XAA**, an open protocol extending OAuth 2.0 that Okta is standardizing through the IETF. Auth0 will support XAA natively for B2B SaaS apps, meaning developers building on Auth0 can participate in XAA flows initiated by workforce Okta tenants.

---

## How Cross App Access actually works under the hood

XAA is **not** a simple on-behalf-of or token exchange. It is a **two-step token exchange flow** using a new token type called the **Identity Assertion JWT Authorization Grant (ID-JAG)**, defined in `draft-ietf-oauth-identity-assertion-authz-grant-02`, authored by Aaron Parecki (Okta), Karl McGuinness, and Brian Campbell (Ping Identity).

**Step 1 — User authenticates, requesting app gets ID token.** Standard OIDC authorization code + PKCE flow against the Okta org authorization server. Nothing new here.

**Step 2 — Requesting app exchanges ID token for ID-JAG at the org AS:**

```
POST /oauth2/v1/token HTTP/1.1
Host: example.okta.com

grant_type=urn:ietf:params:oauth:grant-type:token-exchange
&requested_token_type=urn:ietf:params:oauth:token-type:id-jag
&subject_token={ID_TOKEN}
&subject_token_type=urn:ietf:params:oauth:token-type:id_token
&client_assertion_type=urn:ietf:params:oauth:client-assertion-type:jwt-bearer
&client_assertion={SIGNED_JWT}
&audience=https://example.okta.com/oauth2/default
&scope=chat.read+chat.history
```

Okta evaluates the request against the **managed connection** configured by the IT admin. If the requesting app is authorized to access the resource app with those scopes, Okta returns a **short-lived ID-JAG** (default **300 seconds**, token type `urn:ietf:params:oauth:token-type:id-jag`, media type `oauth-id-jag+jwt`).

**Step 3 — Requesting app presents ID-JAG to the resource app's authorization server:**

```
POST /oauth2/default/v1/token HTTP/1.1
Host: example.okta.com

grant_type=urn:ietf:params:oauth:grant-type:jwt-bearer
&assertion={ID_JAG_TOKEN}
&client_assertion_type=urn:ietf:params:oauth:client-assertion-type:jwt-bearer
&client_assertion={SIGNED_JWT}
```

The resource AS validates the ID-JAG against its trust relationship with the IdP and issues a standard **Bearer access token** scoped to the user + requesting app context.

**What makes this architecturally different from standard OAuth consent:** IT admins control connections centrally in the Okta Admin Console — no end-user consent prompts. The IdP becomes the **authorization broker** between trust domains, enforcing least-privilege policies that users cannot bypass. The ID-JAG carries both user identity and requesting application identity, creating a full audit trail.

Key protocol constraints: ID-JAG is restricted to **confidential clients only**. The resource AS **SHOULD NOT** return refresh tokens — clients must re-submit the ID-JAG. DPoP (sender-constrained tokens) and Rich Authorization Requests (RFC 9396) are supported. Step-up authentication is triggered via `insufficient_user_authentication` error responses.

---

## Registering and configuring an AI agent in Okta Workforce

The lifecycle for an AI agent in the workforce product follows five phases.

**Discovery.** ISPM (Identity Security Posture Management) with the Secure Access Monitor browser plugin analyzes OAuth grants in real-time to surface shadow AI agents. It detects over-privileged credentials, unrotated API keys, stale service accounts, and unauthorized agent-to-app grants. ISPM covers **25+ prioritized risk detections** mapped to the OWASP Top 10 for Non-Human Identities.

**Registration.** Navigate to Admin Console → Directory → AI Agents → Register. Assign a name, optional linked OIDC application, and a **mandatory human owner** (up to 5 individual owners or a group with minimum 2 members). The agent enters STAGED status. Under the Credentials tab, add a public JWK or let Okta generate a keypair — the private key is used for `client_assertion` in token exchange requests. Activate the agent once it has at least one owner and one credential.

**Connection setup.** Open the agent → Managed Connections tab → Add Connection. Three resource types are available:

- **Authorization Server** — Uses XAA/ID-JAG flow for delegated user access to apps protected by Okta custom auth servers
- **Secret** — Retrieves a static credential vaulted in Okta Privileged Access (OPA)
- **Service Account** — Retrieves vaulted service account credentials for a Universal Directory app

For XAA connections, configure allowed scopes on the connection to enforce least-privilege.

**XAA admin configuration** requires enabling the feature flag (Settings → Features → Early Access → Cross App Access), adding both requesting and resource apps from the OIN catalog, establishing managed connections on the requesting app's Manage Connections tab (add requesting apps under "App granted consent" and resource apps under "Apps providing consent"), and assigning users to both apps.

**Governance.** OIG provides access request workflows with configurable approval chains for agent-linked apps, and access certification campaigns that can filter specifically for AI agents as a resource type. Time-bound access policies automatically revoke when the approved period expires. The "Resource Owner" reviewer type assigns reviews to the agent-linked app owner, falling back to the agent owner if the app owner is deactivated.

---

## How this relates to service apps and client credentials

Traditional **service apps** in Okta use the client credentials grant for machine-to-machine communication — no user context, no refresh tokens, works with custom authorization servers only. AI agents **extend this model** in several concrete ways:

Service apps authenticate with either client secret (Basic Auth) or private key JWT (`client_assertion`). AI agents always use **private key JWT** authentication. But the critical difference is the grant type: service apps use `client_credentials`, while AI agents acting on behalf of users use `token-exchange` to obtain an ID-JAG that **preserves the user context** through the delegation chain. The agent's token carries both the agent's identity and the delegating user's identity.

AI agents also get capabilities service apps lack: registration in Universal Directory as workload principals with mandatory human ownership, managed connections with scope constraints, governance integration (access requests, certifications, lifecycle management), and ISPM-based discovery. Think of AI agent identity as "service apps with governance, user delegation, and lifecycle management built in."

For agents that don't need user delegation — pure M2M scenarios — standard client credentials flow still works and may be simpler. The agent identity model adds overhead that only pays off when the agent acts on behalf of human users or requires enterprise governance controls.

---

## Auth0's approach differs in philosophy and implementation

Auth0 for AI Agents targets developers embedding identity into customer-facing GenAI applications. Its four GA capabilities each solve a distinct problem:

**Token Vault** stores external provider refresh tokens (Google, Slack, GitHub, Salesforce — **35+ pre-integrated providers** plus custom OAuth) and performs server-side token exchange using RFC 8693. The application never touches raw provider credentials. SDKs wrap this cleanly:

```typescript
// Vercel AI SDK
const withGmail = auth0AI.withTokenVault({
  connection: 'google-oauth2',
  scopes: ['https://www.googleapis.com/auth/gmail.readonly'],
});
```

```python
# LangChain Python
with_slack = auth0_ai.with_token_vault(
    connection="sign-in-with-slack",
    scopes=["channels:read"],
)
```

**Async Authorization** implements CIBA (Client-Initiated Backchannel Authentication) with Rich Authorization Requests for human-in-the-loop approvals. The agent backend sends a CIBA request to `/bc-authorize`, polls `/oauth/token` with `grant_type=urn:openid:params:grant-type:ciba`, and the user approves via Guardian push notification or email. Key constraint: the `requested_expiry` parameter determines the notification channel — values ≤ 300 seconds (the default) route to mobile push via Guardian, while values of 301–259,200 seconds (up to 72 hours) route to email only. This is a deterministic channel selection driven by Guardian's hard, non-configurable 5-minute push notification expiry, not a fallback mechanism. If MFA is not configured for the tenant, CIBA requests with `requested_expiry` ≤ 300 will fail entirely.

**FGA for RAG** uses Auth0 Fine-Grained Authorization (based on OpenFGA/Google Zanzibar) for document-level access control in retrieval-augmented generation pipelines. The `FGARetriever` class wraps vector store retrievers with relationship-based permission checks, ensuring the LLM only uses data the authenticated user can view.

**Auth for MCP** secures Model Context Protocol servers using OAuth 2.1 + PKCE + Dynamic Client Registration (RFC 7591).

The SDK ecosystem is substantial: `@auth0/ai` (core), `@auth0/ai-vercel`, `@auth0/ai-langchain`, `@auth0/ai-llamaindex`, `@auth0/ai-genkit`, `@auth0/ai-redis`, `@auth0/ai-components` for JavaScript; `langchain-auth0-ai` and `llama-index-auth0-ai` for Python. All are under heavy development with frequent major version bumps.

**The fundamental difference:** Auth0 gives developers SDKs to embed auth into agent code. Okta Workforce gives IT admins a control plane to discover, register, and govern agents centrally. Auth0 handles consent at the user level (OAuth scopes, CIBA). Okta Workforce handles consent at the enterprise policy level (managed connections, no user prompts). XAA bridges both by giving enterprise IT oversight over developer-built agent applications.

---

## Standards Okta is authoring and tracking

Okta is directly authoring or deeply involved with five standards efforts that an SE should track:

**`draft-ietf-oauth-identity-assertion-authz-grant-02` (ID-JAG)** is the most critical — it's an active IETF OAuth Working Group document authored by Aaron Parecki (Okta), and it's the protocol specification underneath XAA. Currently at revision -02 (March 2, 2026).

**`draft-ietf-oauth-identity-chaining-08`** defines cross-domain identity and authorization chaining. ID-JAG is explicitly a derived specification of this. Today's XAA implements the single-domain profile; cross-domain support depends on this spec maturing. Okta's blog explicitly acknowledges cross-organizational trust as "an open industry problem."

**`draft-klrc-aiagent-auth-01`** proposes a comprehensive AI agent auth model built on the thesis that "agents are workloads" and should use existing workload identity standards. Individual draft (not yet WG-adopted), co-authored by engineers from Defakto Security, AWS, Zscaler, and Ping Identity. References ID-JAG and identity chaining extensively.

**IPSIE (Interoperability Profile for Secure Identity in the Enterprise)** is an OpenID Foundation working group Okta co-founded at Oktane 2024 with Ping Identity, Microsoft, SGNL, and Beyond Identity. It develops interoperability profiles for SSO, lifecycle management, entitlements, risk signal sharing, and session termination — all relevant to coordinated agent identity management across vendors.

**`draft-ietf-oauth-first-party-apps-02`** by Aaron Parecki (Okta) defines the Authorization Challenge Endpoint for native apps wanting browserless OAuth — relevant for agent UX patterns where browser-based auth is impractical.

---

## What doesn't work yet and what to watch

The honest limitations list matters more for an SE than the feature list:

**Single trust domain only.** XAA requires one IdP (Okta) to mediate all connections. If the requesting app and resource app use different IdPs, XAA cannot help today. Cross-organizational agent delegation depends on the identity chaining spec reaching maturity. Okta's own blog calls this "an open industry problem."

**No recursive delegation depth control.** Agent A delegating to Agent B delegating to Agent C has no standardized depth limits or multi-hop revocation signaling. Short-lived tokens limit blast radius but don't solve the fundamental problem.

**Coarse OAuth scopes.** A scope like `files:read_write` cannot distinguish between reading one file and deleting everything. There is no concept of blast radius, reversibility, or impact severity in the protocol.

**ISV adoption is nascent.** XAA launch partners include Automation Anywhere, AWS, Boomi, Box, Glean, Google Cloud, Grammarly, Miro, Salesforce, and WRITER. Both apps must be in the OIN with OIDC and XAA enabled. The catalog is growing but far from comprehensive.

**Non-deterministic agent behavior challenges static policy.** LLMs select tools at runtime and chain operations unpredictably. Policies written at provisioning time cannot anticipate actual execution sequences. Okta acknowledges this gap.

**No real-time revocation across active chains.** When a user's permissions change mid-chain, revocation does not reach operations already in flight. The **300-second ID-JAG TTL** limits exposure but doesn't eliminate it. Universal Logout for AI Agents is planned but not yet available.

**Agent Gateway and Agent Relay** (virtual MCP server, runtime tool-level enforcement) are announced but have no public EA/GA dates.

**MFA interaction caution:** If MFA policy is set to "Always" in the Auth0 dashboard, Token Vault token retrieval fails. This must be configured carefully when deploying Auth0 for AI Agents.

---

## Conclusion: implementation-ready takeaways

The XAA protocol and ID-JAG specification represent genuinely novel architecture — moving consent from per-app user prompts to centralized enterprise policy is a meaningful shift for IT governance of AI agents. The two-step token exchange (ID token → ID-JAG → scoped access token) gives full auditability while keeping tokens short-lived and scope-constrained.

For immediate implementation, start with XAA in EA: enable the feature flag, deploy the Agent0/Todo0 sample apps from OIN, and walk through the token exchange flow against the **xaa.dev** interactive playground. The `oktadev/okta-cross-app-access-mcp` GitHub repo provides working Node.js sample code. On the Auth0 side, the `auth0-samples/auth0-assistant0` repo is a full-stack reference implementation.

The gap to watch most closely is **cross-domain trust**. Enterprises with multi-vendor IdP environments or B2B agent delegation scenarios will hit this wall immediately. The IETF identity chaining specification (`draft-ietf-oauth-identity-chaining-08`) is the path forward, but it has no implementation timeline. Until then, XAA is a powerful but single-tenant solution — which, for many enterprises running Okta as their primary IdP, may be exactly enough.

**Key references for hands-on exploration:**
- XAA Admin Setup: `help.okta.com/oie/en-us/content/topics/apps/apps-cross-app-access.htm`
- AI Agent Registration: `help.okta.com/oie/en-us/content/topics/ai-agents/ai-agent-register.htm`
- AI Agent Token Exchange Guide: `developer.okta.com/docs/guides/ai-agent-token-exchange/-/main/`
- XAA Developer Walkthrough: `developer.okta.com/blog/2025/09/03/cross-app-access`
- Interactive Playground: `xaa.dev`
- IETF ID-JAG Spec: `datatracker.ietf.org/doc/draft-ietf-oauth-identity-assertion-authz-grant/`
- Auth0 AI Docs Hub: `auth0.com/ai/docs`
- Sample Code: `github.com/oktadev/okta-cross-app-access-mcp` and `github.com/auth0-samples/auth0-assistant0`