# Lab Architecture Diagram — Iteration v8

## Change in this iteration

**Dropped the `Browser → CRM` direct sign-in edge.** With MCP only constrained by the incoming edge from Adapter, Mermaid should now place it directly below Adapter, eliminating the crossing with `Adapter → MCP`.

Trade-off: the diagram no longer shows that users can sign into VantageCRM/VantageDesk directly. The lab text already covers this (Labs 1.5, 1.6 walk through direct sign-in as part of the environment tour), and the agent-mediated path is the architecture story this diagram is for.

If you want direct sign-in back, two options that won't re-tangle the layout:
- A small text label outside the diagram (e.g., "Users can also sign in to VantageCRM/VantageDesk directly via the browser")
- A dotted line from Browser that lands on the App Server subgraph as a whole, not a specific node inside it

---

```mermaid
%%{init: {'flowchart': {'nodeSpacing': 60, 'rankSpacing': 100, 'curve': 'basis'}}}%%
flowchart TB
    User([Lab Attendee])

    subgraph VDI["VDI"]
        direction LR
        Browser[Chrome Browser]
        Terminal[Terminal<br>check-environment.sh]
    end

    subgraph AgentLayer["Agent Layer"]
        direction LR
        Bedrock[Bedrock AgentCore<br>Path A]
        BYO[Bring Your Own Agent<br>Path B]
    end

    subgraph AppServer["App Server"]
        direction TB
        Adapter[Okta MCP Adapter<br>XAA + tool filtering]
        MCP[MCP Server<br>routes CRM and Desk]
        CRM[VantageCRM<br>fake CRM app]
        Desk[VantageDesk<br>fake ITSM app]
    end

    subgraph Okta["Okta Org"]
        direction LR
        UD[Universal Directory<br>users and groups]
        AIRegistry[AI Agents Registry]
        CRMAS[vantage-crm-as<br>custom auth server]
        DeskAS[vantage-desk-as<br>custom auth server]
        OIG[OIG<br>entitlements and certifications]
    end

    User --> Browser
    Browser -->|prompt the agent| AgentLayer

    AgentLayer -->|MCP protocol| Adapter
    Adapter -.verify agent<br>+ ID-JAG exchange.-> AIRegistry
    Adapter -->|filtered tool calls<br>with user-context tokens| MCP
    MCP --> CRM
    MCP --> Desk

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
    class Browser,Terminal infra
    class Bedrock,BYO,Adapter workflow
    class MCP action
    class CRM,Desk governance
    class UD,AIRegistry,CRMAS,DeskAS,OIG oktaCore

    style VDI fill:#607d8b14,stroke:#607d8b,stroke-width:1px
    style AgentLayer fill:#7b1fa214,stroke:#7b1fa2,stroke-width:1px
    style AppServer fill:#0277bd14,stroke:#0277bd,stroke-width:1px
    style Okta fill:#ef6c0014,stroke:#ef6c00,stroke-width:1px
```
