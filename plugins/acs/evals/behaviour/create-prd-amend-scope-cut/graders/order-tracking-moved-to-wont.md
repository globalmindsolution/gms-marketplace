---
type: regex
target: { source: file, path: docs/product/prd.md }
pattern: '\bWon.?t\b(?:(?!^#{1,3}\s)[\s\S])*order tracking'
flags: mi
---

The cut feature lands in the MoSCoW Won't bucket of Features (prioritized):
`order tracking` appears after `Won't` within the same section, whether the
bucket is a one-line list or a sub-list.
