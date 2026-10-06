---
status: "implemented"
version: 1
tickets: []
feature: "acs"
---

# Flow — Ticket status lifecycle

The statuses a ticket moves through from its creation to its archive, and what moves it; the merge that takes it to `done` is [ticket-lifecycle.md](ticket-lifecycle.md).

## Status lifecycle

```mermaid
stateDiagram-v2
    [*] --> open: created (/create-ticket, /breakdown-ticket child mint, import)
    open --> in_progress: first skill run starts work<br/>(child activity also flips its epic)
    in_progress --> in_review: /create-pr completed<br/>(or product-level skill records its PR)
    in_review --> done: /merge-pr completed
    done --> [*]: partition archived

    note right of in_progress
        the last invocation's status per step:
        in_progress | completed | failed | interrupted
        (a stop_reason belongs to `interrupted` only;
         gates read this, never ticket.status)
    end note
```
