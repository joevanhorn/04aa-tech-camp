# Lab Architecture Diagram — Iteration v10 (central apps + central MCP server)

## Change in this iteration

**Reflects ADR-0001 + ADR-0002.** VantageCRM and VantageDesk are **one central, multi-tenant,
API-only deployment** shared by every attendee org, drawn in a separate `Central` subgraph (with
Redis for per-tenant state). The **MCP server is now also central/shared** (ADR-0002) and sits in
that `Central` subgraph — a stateless bearer-forwarding proxy every attendee's adapter connects to.
Only the **Okta MCP Adapter** remains the per-attendee edge.

**Removed the `Browser → CRM/Desk` direct sign-in concept entirely.** The apps are resource
servers with no human login and no UI, so there is no direct-sign-in edge to add back. The
browser is only used for the **Okta Admin Console**; the Module 1.5 / 1.6 "tour the apps" moments
are delivered out-of-band (screenshots / the Lab Toolkit), not as a browser app login.

This is the canonical source for the rendered diagram in `../lab-architecture.md` — keep the two in
sync.

---

```mermaid
%%{init: {'flowchart': {'nodeSpacing': 60, 'rankSpacing': 100, 'curve': 'basis'}}}%%
flowchart TB
    User([Lab Attendee])

    subgraph Heropa["Per attendee (Heropa)"]
        direction TB

        subgraph VDI["VDI"]
            direction LR
            Browser[Chrome Browser<br>Okta Admin Console]
            Toolkit[Lab Toolkit<br>desktop menu utility]
        end

        subgraph AgentLayer["Agent Layer"]
            direction LR
            OpenCode[OpenCode<br>pre-installed agent]
        end

        subgraph Edge["Adapter"]
            direction TB
            Adapter[Okta MCP Adapter<br>XAA + use-time authorization]
        end

        subgraph Okta["Okta Org"]
            direction LR
            UD[Universal Directory<br>users and groups]
            AIRegistry[AI Agents Registry]
            CRMAS[vantage-crm-as<br>custom auth server]
            DeskAS[vantage-desk-as<br>custom auth server]
            OIG[OIG<br>entitlements and certifications]
        end
    end

    subgraph Central["Central — shared by all orgs"]
        direction TB
        MCP[MCP Server<br>shared — routes CRM and Desk]
        CRM[VantageCRM API<br>resource server only]
        Desk[VantageDesk API<br>resource server only]
        Redis[(Redis<br>per-tenant partitions)]
    end

    User --> Browser
    Browser -->|configure org| Okta
    Browser -->|prompt the agent| AgentLayer

    AgentLayer -->|MCP protocol| Adapter
    Adapter -.verify agent<br>+ ID-JAG exchange.-> AIRegistry
    Adapter -->|authorized tool calls<br>with user-context tokens| MCP
    MCP -->|HTTPS + Bearer| CRM
    MCP -->|HTTPS + Bearer| Desk
    CRM -->|tenant by issuer| Redis
    Desk -->|tenant by issuer| Redis

    OIG -.governs.-> AIRegistry
    AIRegistry -.uses.-> CRMAS
    AIRegistry -.uses.-> DeskAS

    classDef trigger fill:#ffffff,stroke:#1565c0,stroke-width:2px,color:#0d47a1
    classDef infra fill:#ffffff,stroke:#546e7a,stroke-width:2px,color:#37474f
    classDef oktaCore fill:#ffffff,stroke:#ef6c00,stroke-width:2px,color:#e65100
    classDef workflow fill:#ffffff,stroke:#7b1fa2,stroke-width:2px,color:#4a148c
    classDef action fill:#ffffff,stroke:#0277bd,stroke-width:2px,color:#01579b
    classDef governance fill:#ffffff,stroke:#2e7d32,stroke-width:2px,color:#1b5e20

    class User trigger
    class Browser,Toolkit infra
    class OpenCode,Adapter workflow
    class MCP action
    class CRM,Desk,Redis governance
    class UD,AIRegistry,CRMAS,DeskAS,OIG oktaCore

    style VDI fill:#607d8b14,stroke:#607d8b,stroke-width:1px
    style AgentLayer fill:#7b1fa214,stroke:#7b1fa2,stroke-width:1px
    style Edge fill:#0277bd14,stroke:#0277bd,stroke-width:1px
    style Okta fill:#ef6c0014,stroke:#ef6c00,stroke-width:1px
    style Central fill:#2e7d3214,stroke:#2e7d32,stroke-width:1px
```
