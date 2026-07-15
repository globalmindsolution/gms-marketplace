# Quality gates

Cross-cutting governance/quality principles the pipeline upholds on every
change. Moved out of `overview.md`'s "Core principles" table during the
MAR-145 functional/non-functional reorg (content unchanged); two rows of
that table ("Workspace isolation", "File-based state") moved instead to
[portability.md](portability.md) and [statelessness.md](statelessness.md)
respectively, per the reorg mapping.

| Principle | Requirement |
|-----------|-------------|
| Reflection | Each workflow and product-level skill runs plan → execute → verify with dedicated subagents. |
| Gated pipeline | A skill refuses to run (pre-hook exit 2) until its predecessor's state file says it is complete. |
| XML messaging | Coordinator ↔ subagent communication uses a defined XML format. |
| Dynamic decomposition | The coordinator decomposes work into subagent tasks dynamically based on the ticket/spec at hand, not a fixed task list. |
| TDD | `/code` implements via test-driven development against a configurable coverage target (default 90%). |
| Design gate | Architecturally significant tickets (`needs_design`) get an approved `design.md` before specs; specs and code are verified against it. |
| Living architecture | The product architecture doc set (HLD: C4 views; LLD: sequence-diagram flows) in the consumer repo frames every design; `/code` keeps it current as changes land. |
| PRD at the top | The PRD (vision, goals, features, product NFRs) is the root of the conformance chain **PRD → architecture → principles → standards → design → specs → code**; tickets trace to it, divergence is flagged. |
| Automatic review loop | The `code-verifier` reviews the whole changeset (business logic, quality, architecture, security, …); blocking findings loop back through plan → execute automatically, max 3 iterations. |
| Human merge gate | `/merge-pr` only runs on explicit user invocation, after the user has reviewed the PR themselves. |
