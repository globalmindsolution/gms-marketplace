---
type: regex
target: { source: file, path: docs/product/features/order-tracking/analysis.md }
pattern: '(?i)opt[- ]?out|unsubscrib'
---

The per-order opt-out from tracking emails exists only in the attached spec
(attachments/order-tracking-spec.md) -- not in the PRD, the prompt or the
code. An analysis that carries it read the document container.
