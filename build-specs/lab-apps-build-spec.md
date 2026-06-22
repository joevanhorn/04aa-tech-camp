# TaskVantage Lab Apps — Build Specification

**Apps covered:** VantageCRM, VantageDesk
**Stack:** Python 3.12 + FastAPI, Redis-backed per-tenant store
**Audience:** the engineer(s) building the lab environment

---

## Part 0 — Overview and decisions

### What these apps are

VantageCRM and VantageDesk are fake business applications that stand in for Salesforce and ServiceNow in the Okta AI Agents Tech Camp. They exist so the camp is self-contained — no real SaaS licensing, no external provisioning.

They are deployed **once, centrally, as a multi-tenant pseudo-SaaS** that many attendee Okta orgs connect to — not once per attendee. See `adr/0001-central-multitenant-api-only.md` for the decision and rationale. The deployment supports labs of up to ~100 concurrent attendee orgs.

Each app is a **resource server only**. It validates the Bearer access token the MCP server presents on a user's behalf, and serves tenant-scoped data. There is no browser login, no human SSO, no UI — every interaction is an agentic API call. (The Module 1.5/1.6 "tour the app in a browser" steps are handled out-of-band, e.g. with rendered screenshots; see Part 4.)

### Tenancy in one paragraph

Tenant identity is the attendee's Okta org, keyed by the token **issuer**. The audience is a constant lab value (`api://vantage-crm` / `api://vantage-desk`) shared by every tenant, so audience is not the discriminator — `iss` is. Each tenant's data is partitioned in the store under its tenant key; a request can only ever read or write its own tenant's data. Tenant isolation is therefore a correctness-critical property on every data path (see Part 1.4, Part 4).

### What is in scope and what is not

In scope: both apps' REST API, multi-issuer token validation, the tenant registry, per-tenant data partitioning and reset, row-level filtering, access logging, containerization, local-dev compose.

Out of scope (separate deliverables, referenced but not specified here): the MCP server that fronts these apps (now **central/shared** — see ADR-0002) and the Okta MCP Adapter (stays **per-attendee** — see ADR-0001), the Okta org configuration (auth servers, scopes, access policies — covered in the lab modules), TLS termination and the reverse proxy (an infra concern; see Part 1.6 for the contract the apps expect).

### Why one repo, one spec

The two apps are structurally near-identical. Everything in Part 1 (token validation, tenancy, logging, config, store, deployment) is shared verbatim. Only the data models, endpoints, scope mapping, filtering rules, and seed data differ — those are Parts 2 and 3. A monorepo with a shared `common` package keeps the security-sensitive code (token validation and tenant resolution) in exactly one place, which is where it should be.

---

## Part 1 — Shared foundation

### 1.1 Repository layout

```
taskvantage-apps/
├── README.md
├── pyproject.toml                 # single project, both apps as packages
├── docker-compose.yml             # runs both apps + Redis for local dev
├── .env.example
├── common/
│   ├── __init__.py
│   ├── config.py                  # env-based settings (pydantic-settings)
│   ├── tenants.py                 # tenant registry: enrolled org issuers
│   ├── tokens.py                  # multi-issuer Bearer validation + tenant resolution
│   ├── access_log.py              # structured, tenant-scoped access logging
│   ├── deps.py                    # FastAPI deps (require_scope, current_api_user -> TokenContext w/ tenant)
│   └── store.py                   # Redis-backed, tenant-partitioned store base class
├── vantagecrm/
│   ├── __init__.py
│   ├── main.py                    # app factory; mounts api router
│   ├── models.py                  # Account, Contact, Opportunity
│   ├── seed.py                    # per-tenant seed data
│   ├── store.py                   # CrmStore(Store)
│   ├── filters.py                 # row-level visibility (within a tenant)
│   ├── api.py                     # /api/* (the 6 CRM tools) + /admin/access-log
│   └── Dockerfile
└── vantagedesk/
    ├── __init__.py
    ├── main.py
    ├── models.py                  # Ticket, Incident, KBArticle
    ├── seed.py
    ├── store.py                   # DeskStore(Store)
    ├── filters.py                 # scope-gated; see 3.4
    ├── api.py                     # /api/* (the 6 ITSM tools) + /admin/access-log
    └── Dockerfile
```

### 1.2 Configuration (`common/config.py`)

The deployment is configured by environment variables. Use `pydantic-settings`. There is no per-org OIDC client config here — the app is a resource server, not a relying party, and tenant-specific issuer data lives in the tenant registry (1.3), not in env.

| Env var | Example | Used for |
| --- | --- | --- |
| `APP_NAME` | `VantageCRM` | logging, OpenAPI title |
| `RESOURCE_AUDIENCE` | `api://vantage-crm` | Expected `aud` on every tenant's API tokens (constant) |
| `REDIS_URL` | `redis://redis:6379/0` | Tenant-partitioned state |
| `TENANT_REGISTRY` | `https://org-a.okta.com,https://org-b.okta.com` | Comma-separated enrolled org base URLs (see 1.3) |
| `ADMIN_API_KEY` | (random) | Guards tenant enrollment + access-log read endpoints |
| `AGENT_CID_NAME_MAP` | `0oaxxxx=TaskVantage Sales Agent` | Optional: resolve `cid` → display name for access logs |
| `PORT` | `8001` | Listen port |

`TENANT_REGISTRY` seeds the enrolled orgs at boot (Heropa knows all attendee org URLs ahead of time). Orgs can also be enrolled at runtime via the admin API (1.3). `AGENT_CID_NAME_MAP` is a convenience so the access log can print `TaskVantage Sales Agent` instead of a raw client ID; if unset, the log prints the raw `cid`.

### 1.3 Tenancy and enrollment (`common/tenants.py`)

A tenant is an enrolled Okta org, identified by its base URL (`https://{org}.okta.com`). The registry holds the set of enrolled org bases. Because this is Okta-only, enrollment is **by org**, not by individual auth server — the app trusts any custom auth server under an enrolled org (`{org}/oauth2/{anyAuthServerId}`), proven by that issuer's JWKS signature. This matters for the lab: `vantage-desk-as` is created by the attendee mid-lab (Module 4), so its specific issuer does not exist at enrollment time. Enroll-by-org means it is trusted automatically the moment it exists, with no re-enrollment step.

The registry:
- Seeds from `TENANT_REGISTRY` at boot.
- Exposes `POST /admin/tenants {org_base_url}` and `DELETE /admin/tenants/{id}`, both guarded by `ADMIN_API_KEY`, for runtime enrollment.
- Maps an org base URL to a stable `tenant_id` (e.g. a slug of the org subdomain) used as the store partition key.

`resolve_tenant(issuer) -> tenant_id | None` returns the tenant whose org base is a prefix of `issuer` (i.e. `issuer.startswith(f"{org_base}/oauth2/")`), or `None` if no enrolled org matches. A `None` result is a 401 at the token layer.

### 1.4 Resource-server token validation (`common/tokens.py`)

This is the security-critical, shared, identical-across-both-apps piece — and the heart of tenant isolation. It validates the Bearer access token the MCP server presents on the user's behalf and resolves which tenant it belongs to.

```python
# Pseudocode contract for validate_access_token(authorization_header) -> TokenContext

token = strip_bearer(authorization_header)     # 401 if missing/malformed

unverified = jwt.decode(token, verify=False)   # read iss only; trust nothing yet
tenant_id  = resolve_tenant(unverified["iss"]) # 401 if org not enrolled
issuer     = unverified["iss"]                  # the exact custom-auth-server issuer

jwks = cached_fetch(f"{issuer}/v1/keys")        # per-issuer cache; refresh on unknown kid

claims = jwt.decode(
    token, jwks,
    algorithms=["RS256"],
    issuer=issuer,                              # 401 if iss mismatch
    audience=RESOURCE_AUDIENCE,                 # 401 if aud mismatch (constant across tenants)
    options={"require": ["exp", "iss", "aud", "sub"]},
)                                               # 401 if signature/exp invalid

return TokenContext(
    tenant_id= tenant_id,                       # store partition key — every read/write scopes to this
    subject  = claims["sub"],                   # the user the agent acts as
    client_id= claims.get("cid"),               # the agent's client id
    scopes   = claims.get("scp", []),           # granted scopes
    groups   = claims.get("groups", []),        # for row-level filtering
    audience = claims["aud"],
)
```

Two non-negotiables. The unverified `iss` read is used **only** to pick the issuer and tenant; nothing is trusted until the signature is verified against that issuer's own JWKS. And `tenant_id` flows into every store call — there is no code path that reads or writes data without a tenant key. A request whose token validates against org A can never touch org B's data, because the store is physically partitioned by `tenant_id` and the API layer never passes anything else.

`TokenContext` is the object the API routes, the store, and the access log all consume. The access token must carry `groups` and `scp` claims — configure these on each tenant's custom auth server (`vantage-crm-as` / `vantage-desk-as`) in Okta (note for the Okta-config side).

Scope enforcement is a thin layer on top:

```python
def require_scope(needed: str):
    def dep(ctx: TokenContext = Depends(current_api_user)):
        if needed not in ctx.scopes:
            raise HTTPException(403, f"missing required scope: {needed}")
        return ctx
    return dep
```

*Defense-in-depth note: the Okta MCP Adapter already filters tools by scope before the agent sees them, so in normal operation the app should never receive a request for a scope the user lacks. The app enforces scope anyway — a resource server that trusts an upstream filter to be its only gate is not a resource server. This double-check is also what makes the audit log meaningful.*

### 1.5 Access logging (`common/access_log.py`)

Every API request (not UI requests) emits one structured access-log record. The format must match what Module 4.10 shows attendees:

```
2026-04-23 11:24:08  GET  /api/tickets/TKT-1734
  Bearer subject:    kim.liu@atko.email
  Client:            TaskVantage Sales Agent
  Audience:          api://vantage-desk
  Scopes:            itsm.tickets.read
  Source:            mcp.taskvantage.lab
```

Field sources:

| Log field | Source |
| --- | --- |
| timestamp | request receipt time |
| tenant | `TokenContext.tenant_id` (recorded on every record; not shown in the Module 4.10 display format, but used to scope retrieval) |
| method + path | request line |
| Bearer subject | `TokenContext.subject` |
| Client | `AGENT_CID_NAME_MAP[cid]` if present, else `TokenContext.client_id` |
| Audience | `TokenContext.audience` |
| Scopes | `TokenContext.scopes` (space-joined) |
| Source | `X-Forwarded-Host` (set by the reverse proxy to the calling host); fall back to the socket peer |

Log to stdout (container-friendly), and keep a per-tenant ring buffer in Redis. Expose it at `GET /admin/access-log` — **scoped to the caller's tenant** and guarded by `ADMIN_API_KEY` (or the caller's own validated token). Module 4.10 currently has the attendee view this in a browser admin page; with the API-only model that step becomes a script (e.g. `~/Desktop/show-access-log.sh`) or a rendered screenshot. Flagged in Part 4.

### 1.6 Deployment contract

The deployment is a single central service per app (or one combined service exposing both), fronted by a reverse proxy:
- Each app listens on `PORT` (HTTP, plaintext — TLS terminated upstream).
- The proxy terminates TLS and routes by `Host` to the right app, at central hostnames (`vantagecrm.taskvantage.lab`, `vantagedesk.taskvantage.lab` pointed at the central deployment, not per-attendee servers).
- The proxy sets `X-Forwarded-Host` to the original calling host (used for the access-log `Source` field).
- Each app ships as its own container and is **horizontally scalable** — all state lives in Redis, so any replica can serve any request. Run 2+ replicas behind the proxy for HA.

State lives in **Redis, partitioned by `tenant_id`**. On enrollment (or first request from) a tenant, the store is seeded for that tenant from `seed.py`. A per-tenant reset is exposed at `POST /admin/tenants/{id}/reset` (guarded by `ADMIN_API_KEY`), which reseeds just that tenant's partition — one attendee can reset without touching anyone else's data. The seed is tiny, so 100 tenants' worth of data in Redis is negligible.

`docker-compose.yml` runs both apps plus a Redis container and a minimal local proxy (Caddy or nginx) so a developer can hit `https://vantagecrm.taskvantage.lab` locally with `/etc/hosts` entries.

---

## Part 2 — VantageCRM

### 2.1 Data models (`vantagecrm/models.py`)

```python
class Account(BaseModel):
    id: str                 # "ACC-1001"
    name: str               # "Northwind Trading Co."
    owner: str              # owning rep's email, e.g. "alex.martinez@atko.email"
    industry: str           # "Manufacturing"
    tier: str               # "Enterprise" | "Mid-Market" | "SMB"
    annual_revenue: int     # 4200000
    created: datetime

class Contact(BaseModel):
    id: str                 # "CON-2001"
    account_id: str         # FK -> Account.id
    name: str
    email: str
    title: str
    phone: str

class Opportunity(BaseModel):
    id: str                 # "OPP-3001"
    account_id: str         # FK -> Account.id
    name: str
    stage: str              # "Prospecting" | "Qualification" | "Proposal" | "Closed Won" | "Closed Lost"
    amount: int
    close_date: date
    owner: str              # owning rep's email
```

### 2.2 Scope → tool → endpoint map

| MCP tool | Required scope | HTTP endpoint |
| --- | --- | --- |
| `crm.lookup_account` | `crm.accounts.read` | `GET /api/accounts` (query: `id`, `name`) |
| `crm.create_account` | `crm.accounts.write` | `POST /api/accounts` |
| `crm.update_account` | `crm.accounts.write` | `PATCH /api/accounts/{id}` |
| `crm.lookup_contact` | `crm.contacts.read` | `GET /api/contacts` (query: `name`, `email`, `account_id`) |
| `crm.lookup_opportunity` | `crm.opportunities.read` | `GET /api/opportunities` (query: `name`, `stage`, `account_id`) |
| `crm.update_opportunity` | `crm.opportunities.write` | `PATCH /api/opportunities/{id}` |

These five scopes are the full set on `vantage-crm-as`: `crm.accounts.read`, `crm.accounts.write`, `crm.contacts.read`, `crm.opportunities.read`, `crm.opportunities.write`.

### 2.3 API endpoints (`vantagecrm/api.py`)

All under `/api`, all depend on `require_scope(...)`, all apply row-level filtering (2.4) using `TokenContext.subject` + `.groups`.

```
GET    /api/accounts?id=&name=        scope crm.accounts.read
        -> list[Account]  (filtered)
POST   /api/accounts                  scope crm.accounts.write
        body: {name, industry, tier, annual_revenue}
        -> Account  (owner set to caller's subject)
PATCH  /api/accounts/{id}             scope crm.accounts.write
        body: partial Account
        -> Account   (404 if not visible to caller)
GET    /api/contacts?name=&email=&account_id=   scope crm.contacts.read
        -> list[Contact]  (filtered by parent account visibility)
GET    /api/opportunities?name=&stage=&account_id=   scope crm.opportunities.read
        -> list[Opportunity]  (filtered)
PATCH  /api/opportunities/{id}        scope crm.opportunities.write
        body: {stage?, amount?, close_date?}
        -> Opportunity  (404 if not visible)
```

Response shape example (`GET /api/accounts?id=ACC-1001`):

```json
[{"id":"ACC-1001","name":"Northwind Trading Co.","owner":"alex.martinez@atko.email",
  "industry":"Manufacturing","tier":"Mid-Market","annual_revenue":4200000,
  "created":"2025-11-03T00:00:00"}]
```

### 2.4 Row-level filtering (`vantagecrm/filters.py`)

This is what makes Alex and Susan see different data through the same agent (Module 1.5, and the premise of Module 3).

```
visible_accounts(ctx):
    accounts = store.accounts(ctx.tenant_id)    # tenant partition first — never global
    if "Sales Management" in ctx.groups:        # Susan
        return accounts
    else:                                        # Alex and other reps
        return [a for a in accounts if a.owner == ctx.subject]
```

The tenant scoping happens first and unconditionally: every read starts from `store.accounts(ctx.tenant_id)`, never a global collection. Row-level visibility then applies *within* that tenant's data. Two filters stacked — tenant, then ownership/role.

Contacts and Opportunities inherit their parent account's visibility: a contact/opportunity is visible iff its `account_id` resolves to a visible account (within the same tenant). `PATCH` and single-record `GET` return **404, not 403**, when the record exists but isn't visible to the caller — never reveal the existence of records the user can't see. (A record in another tenant is simply absent from `store.accounts(ctx.tenant_id)`, so it is invisible by construction, not by filter.)

*Row-level filtering is independent of scope. Scope decides whether the caller may call `GET /api/accounts` at all; row-level filtering decides which of the tenant's accounts come back. Kim (IT Help Desk, `crm.accounts.read` + `crm.contacts.read` via rule 3) can call the read endpoints but, owning no accounts and not being in Sales Management, sees an empty account list — the correct, if quiet, demonstration that scope and data visibility are separate gates.*

### 2.5 Seed data (`vantagecrm/seed.py`)

Eight accounts with deliberate ownership spread so Alex sees a subset and Susan sees all. At minimum:

| id | name | owner | tier |
| --- | --- | --- | --- |
| ACC-1001 | Northwind Trading Co. | alex.martinez@atko.email | Mid-Market |
| ACC-1002 | Contoso Logistics | alex.martinez@atko.email | SMB |
| ACC-1003 | Fabrikam Industries | susan.potter@atko.email | Enterprise |
| ACC-1004 | Tailspin Freight | jordan.lee@atko.email | Mid-Market |
| ACC-1005 | Adventure Works | jordan.lee@atko.email | Enterprise |
| ACC-1006 | Proseware Systems | morgan.diaz@atko.email | SMB |
| ACC-1007 | Wingtip Components | morgan.diaz@atko.email | Mid-Market |
| ACC-1008 | Litware Manufacturing | susan.potter@atko.email | Enterprise |

So Alex (rep) sees 2 accounts; Susan (manager) sees all 8. Seed 2–3 contacts and 1–2 opportunities per account. `jordan.lee` and `morgan.diaz` need not be real Okta users — they exist only as `owner` values to make the spread realistic.

### 2.6 Admin endpoint

`GET /admin/access-log` returns this tenant's access-log records (scoped to the caller's tenant; see 1.5). There is no browser UI — the Module 1.5 "tour the accounts as Susan vs Alex" demonstration is delivered out-of-band (screenshots) or via a read script that calls the API as each user. See Part 4.

---

## Part 3 — VantageDesk

### 3.1 Data models (`vantagedesk/models.py`)

```python
class Ticket(BaseModel):
    id: str                 # "TKT-1734"
    subject: str
    description: str
    status: str             # "Open" | "In Progress" | "Resolved" | "Closed"
    priority: str           # "P1" | "P2" | "P3" | "P4"
    assignee: str           # email
    requester: str          # email
    created: datetime
    updated: datetime

class Incident(BaseModel):
    id: str                 # "INC-5001"
    subject: str
    description: str
    status: str             # "Investigating" | "Identified" | "Monitoring" | "Resolved"
    severity: str           # "SEV1" | "SEV2" | "SEV3"
    assignee: str
    created: datetime
    updated: datetime

class KBArticle(BaseModel):
    id: str                 # "KB-9001"
    title: str
    body: str
    category: str
    tags: list[str]
    updated: datetime
```

### 3.2 Scope → tool → endpoint map

| MCP tool | Required scope | HTTP endpoint |
| --- | --- | --- |
| `itsm.lookup_ticket` | `itsm.tickets.read` | `GET /api/tickets` (query: `id`, `queue`, `assignee`) |
| `itsm.create_ticket` | `itsm.tickets.write` | `POST /api/tickets` |
| `itsm.update_ticket` | `itsm.tickets.write` | `PATCH /api/tickets/{id}` |
| `itsm.lookup_incident` | `itsm.incidents.read` | `GET /api/incidents` (query: `id`, `severity`) |
| `itsm.update_incident` | `itsm.incidents.write` | `PATCH /api/incidents/{id}` |
| `itsm.search_kb` | `itsm.kb.read` | `GET /api/kb` (query: `q`) |

These five scopes are the full set on `vantage-desk-as`: `itsm.tickets.read`, `itsm.tickets.write`, `itsm.incidents.read`, `itsm.incidents.write`, `itsm.kb.read`.

### 3.3 API endpoints (`vantagedesk/api.py`)

```
GET    /api/tickets?id=&queue=&assignee=     scope itsm.tickets.read
POST   /api/tickets                          scope itsm.tickets.write
        body: {subject, description, priority?}
        -> Ticket  (requester set to caller's subject; status "Open")
PATCH  /api/tickets/{id}                      scope itsm.tickets.write
        body: {status?, priority?, assignee?}
GET    /api/incidents?id=&severity=          scope itsm.incidents.read
PATCH  /api/incidents/{id}                    scope itsm.incidents.write
        body: {status?, severity?, assignee?}
GET    /api/kb?q=                            scope itsm.kb.read
        -> list[KBArticle]  (substring match on title/body/tags)
```

Response example (`GET /api/tickets?id=TKT-1734`) — must match Module 4.8 verbatim:

```json
[{"id":"TKT-1734",
  "subject":"Outlook calendar sync failing for Sales team",
  "status":"In Progress","priority":"P2",
  "assignee":"kim.liu@atko.email","requester":"susan.potter@atko.email",
  "created":"2026-04-22T09:14:00","updated":"2026-04-23T11:02:00",
  "description":"Multiple Sales team members reporting that calendar events created in Outlook aren't syncing to Google Workspace..."}]
```

### 3.4 Access filtering (`vantagedesk/filters.py`)

Access is governed entirely by **scope**, scoped to the tenant. The access policy on each tenant's `vantage-desk-as` only grants the ITSM scopes to the `IT Help Desk` group (Module 4.5), so non-help-desk users never get a token carrying these scopes in the first place. The API therefore needs no row-level filter beyond the tenant partition: every read starts from `store.tickets(ctx.tenant_id)` (etc.), and any caller holding the read scope sees that tenant's tickets/incidents.

The Module 1.6 distinction (Kim gets the full portal; Alex can only file a ticket via self-service) was a *UI* behavior. With the API-only model there is no portal and no self-service form — that distinction is now expressed purely through scope (Alex's token never carries the ITSM scopes) and is demonstrated out-of-band (screenshots) rather than by a live browser flow. See Part 4.

### 3.5 Seed data (`vantagedesk/seed.py`)

Must include **TKT-1734 exactly** as shown in 3.3 / Module 4.8. Around it, seed ~6 more tickets (varied status/priority/assignee), ~3 incidents, and ~4 KB articles. One KB article should plausibly relate to TKT-1734 (calendar sync) so `itsm.search_kb?q=calendar` returns something during demos.

| id | subject | status | priority | assignee |
| --- | --- | --- | --- | --- |
| TKT-1734 | Outlook calendar sync failing for Sales team | In Progress | P2 | kim.liu@atko.email |
| TKT-1735 | New hire laptop not enrolled in MDM | Open | P3 | kim.liu@atko.email |
| TKT-1736 | VPN drops every 30 minutes | In Progress | P2 | kim.liu@atko.email |
| TKT-1737 | Password reset for shared mailbox | Resolved | P4 | kim.liu@atko.email |
| ... | ... | ... | ... | ... |

### 3.6 Admin endpoint

`GET /admin/access-log` returns this tenant's access-log records (scoped to the caller's tenant; see 1.5). No browser UI — see 2.6 and Part 4. This is the endpoint behind Module 4.10's "find TKT-1734's access log" step, which becomes a script or screenshot rather than a browser admin page.

---

## Part 4 — Lab alignment checklist

The apps and the lab modules must agree on these exact values, or the modules' expected outputs break. Verify before declaring the apps done:

| Item | Value | Referenced in |
| --- | --- | --- |
| CRM audience | `api://vantage-crm` (constant across all tenants) | Modules 1.9, 2.7 |
| Desk audience | `api://vantage-desk` (constant across all tenants) | Module 4.3 |
| CRM scopes | `crm.accounts.read/write`, `crm.contacts.read`, `crm.opportunities.read/write` | Modules 1.9, 3.3 |
| Desk scopes | `itsm.tickets.read/write`, `itsm.incidents.read/write`, `itsm.kb.read` | Module 4.4 |
| CRM tool names | the 6 in §2.2 | Module 3.3 |
| Desk tool names | the 6 in §3.2 | Modules 4.7, 4.8 |
| TKT-1734 detail | subject/status/priority/assignee/dates per §3.3 | Module 4.8 |
| Alex visible accounts | exactly 2 (ACC-1001, ACC-1002) per tenant | Module 1.5 (shown via agent calls / screenshots) |
| Susan visible accounts | all (8) per tenant | Module 1.5 |
| Alex's Desk token | carries no ITSM scopes (so no Desk tools) | Modules 1.6, 4.5 |
| Access-log fields | timestamp, tenant, method+path, subject, client, audience, scopes, source | Module 4.10 |
| User emails | `alex.martinez@`, `susan.potter@`, `kim.liu@`, `frank.boone@` `@atko.email` | Module 1.3 |
| Tool count | 12 total (6 CRM + 6 Desk) | Module 1.7 env-check ("14 tools registered" — see open item) |
| Seed identical per tenant | every enrolled org gets the same seed dataset | multi-tenant requirement |

### Open items (resolve with Joe / against the build)

- **UI-dependent module steps need rewriting for API-only.** Module 1.5 (tour accounts as Susan vs Alex), Module 1.6 (Kim portal vs Alex self-service), and Module 4.10 (find TKT-1734's access log in an admin page) all assume a live browser UI the central API-only app does not have. Each becomes either a script that calls the API as the relevant user, or a rendered screenshot. Decide per step which treatment it gets.
- **Tool count mismatch.** Module 1.7's env-check prints `14 tools registered`, but the modules only define 12 (6 CRM + 6 Desk). Either two tools are missing or the script should read 12. Confirm.
- **`requester` on TKT-1734.** Module 4.8 doesn't show a requester; seeded `susan.potter@` as plausible. Confirm or change.
- **Groups in the access token.** Each tenant's custom auth server must include a `groups` claim in the access token, or row-level filtering has nothing to read. Okta-side config; noted so it isn't missed when wiring each org. (No ID token / OIDC app is involved anymore — API-only.)
- **`cid` → agent name.** The access log's `Client: TaskVantage Sales Agent` line resolves the token's `cid` via `AGENT_CID_NAME_MAP`. Confirm the agent client ID(s) are known at deploy time, or print the raw `cid`.
- **Tenant isolation testing.** Before this goes near a 100-org room, the isolation property needs a test: a token validly issued by org A must never read or write org B's data on any endpoint (lookup, search, patch, access-log). This is the central correctness risk of the multi-tenant model.
