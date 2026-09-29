---
type: regex
target: { source: file, path: docs/principles/principles.md }
pattern: '^(?=[\s\S]*card data)(?=[\s\S]*standard library)(?=[\s\S]*\b90\s?%)'
flags: i
---

Tailored to the product, not the template's examples ("prefer composition
over inheritance", "fail closed"): the three principles the request
confirmed -- never store card data, standard library first, and the 90%
coverage floor.
