---
type: regex
target: { source: file, path: docs/requirements/functional/customer-listing.md }
pattern: '^(?=[\s\S]*\bMUST\b)(?=[\s\S]*\boffset\b)(?=[\s\S]*\b20\b)'
---

Behavioural-contract prose in the MUST/SHOULD/MAY vocabulary, grounded in the
code: the listing takes an `offset` and defaults to 20 per page
(`PAGE_SIZE = 20` in src/shop/__init__.py).
