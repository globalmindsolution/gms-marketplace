---
type: llm
---

PASS if the final reply says that no architecture set (no HLD, no
hld/tech-stack.md) was found, so there was nothing to audit, recommends
/acs:create-architecture to baseline one, and says nothing was changed.
FAIL if it reports any gap between the design and the code, treats the PRD
or the README as the design, says it wrote or regenerated architecture
documents, creates a ticket, or asks the user a question.
