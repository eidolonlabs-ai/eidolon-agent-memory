# Eidolon Agent Memory Architecture

This page shows the main runtime and data-flow path from conversation input to memory retrieval and MCP tool response.

```mermaid
flowchart TD
    U[User Orchestrator / Client Agent] --> M[MCP Server]

    subgraph MCP[Runtime Layer]
        M --> T[Tools Layer\n27+ MCP tools]
        T --> S[Services Layer]
    end

    subgraph Services[Domain Services]
        S --> X[Extraction Service\nconversation -> facts]
        S --> Q[Search Service\nintent + semantic retrieval]
        S --> R[Memory Service\nCRUD + relationship updates]
        S --> L[LLM Service\nJSON completion + retry]
        S --> E[Embedding Service\ntext -> vectors]
    end

    X --> R
    L --> X
    L --> Q
    E --> X
    E --> Q

    subgraph Data[Persistence Layer]
        D[(PostgreSQL + pgvector)]
        N[MemoryNode\nentity, confidence, importance]
        G[MemoryEdge\nsubject-predicate-object\nsalience + scope metadata]
    end

    R --> D
    Q --> D
    D --> N
    D --> G

    Q --> F[Filtered Recall\nintent + emotional salience + scope]
    F --> T
    T --> M
    M --> A[Agent Response Context]

    classDef runtime fill:#e8f2ff,stroke:#4a7bd0,stroke-width:1px,color:#102a43;
    classDef service fill:#eef9f1,stroke:#3c8c5a,stroke-width:1px,color:#1f5130;
    classDef data fill:#fff3e6,stroke:#c97b2a,stroke-width:1px,color:#6b3f0d;
    classDef output fill:#f4ecff,stroke:#8c5ec9,stroke-width:1px,color:#3c2a63;

    class M,T runtime;
    class S,X,Q,R,L,E service;
    class D,N,G data;
    class F,A output;
```

## Notes

- Extraction and retrieval are both embedding-assisted but governed by intent and metadata.
- Emotional salience and scope are first-class fields on relationships, enabling graceful omission behavior.
- Tools are the only external interface; services and storage are internal implementation layers.
