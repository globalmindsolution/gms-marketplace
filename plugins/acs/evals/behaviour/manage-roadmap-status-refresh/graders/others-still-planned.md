---
type: regex
target: { source: file, path: docs/product/roadmap.md }
pattern: '^(?=[\s\S]*### Storefront — v2\.4\.0\n\n- Status: planned\n)(?=[\s\S]*### Order tracking — v2\.6\.0\n\n- Status: planned\n)(?=[\s\S]*\| v2\.4\.0 \| Storefront \| — \| planned \|)(?=[\s\S]*\| v2\.6\.0 \| Order tracking \| — \| planned \|)'
---

No ticket tracks Storefront or Order tracking, so both stay `planned`: the
status is a reading of the tickets, never asserted -- not even for the
customer listing everyone knows shipped.
