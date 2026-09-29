---
type: regex
target: { source: file, path: docs/product/prd.md }
pattern: '^(?=[\s\S]*3\.5\s?%)(?=[\s\S]*300\s?ms)(?=[\s\S]*\bWon.?t\b)'
---

Grounded in the answers, not in a generic template: the G1 metric (3.5%), the
latency NFR (300 ms) and a MoSCoW `Won't` bucket all come only from the
request. The fixture's code and README carry none of them.
