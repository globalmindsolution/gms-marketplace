---
type: regex
target: { source: file, path: docs/architecture/lld/customer-listing/EVAL-1/api-contract.md }
pattern: '(?<![\s\S])-{3}\n(?=(?:(?!-{3}\n)[\s\S])*^items:[ \t]*[1-9]\d*[ \t]*$)(?=(?:(?!-{3}\n)[\s\S])*^interfaces:(?:(?!-{3}\n)[\s\S])*api/customers\.md)[\s\S]*?^-{3}$[\s\S]*^## Scope & sources[ \t]*$[\s\S]*^## Interfaces[ \t]*$[\s\S]*^## Compatibility & versioning[ \t]*$[\s\S]*^## Traceability[ \t]*$[\s\S]*^## Gaps[ \t]*$'
flags: m
---

The run record's front matter counts at least one item and lists the
interface document it changed, `api/customers.md`, under `interfaces`; its
five headings follow in order.
