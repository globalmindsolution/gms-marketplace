---
type: regex
target: { source: file, path: README.md }
pattern: '^# shop\n\nA small storefront service\.\n\n## API\n\n- `GET /health` returns `ok`\.\n- `GET /customers\?offset=&limit=` lists customers, 20 per page by default\.\n$'
---

README.md is byte-for-byte what main committed: the refactor changed no
behaviour it describes, so an edit here -- committed or not -- is a
speculative doc change.
