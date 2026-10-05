---
type: regex
target: { source: file, path: docs/architecture/lld/checkout-with-card-payments/EVAL-1/tech-design.md }
pattern: '^## LLD[ \t]*$(?:(?!^## )[\s\S])*^### API[ \t]*$(?:(?!^## )[\s\S])*^### Data[ \t]*$(?:(?!^## )[\s\S])*^### Flows[ \t]*$(?:(?!^## )[\s\S])*^### Components[ \t]*$'
flags: m
---

Under LLD, the four snapshot subsections in order -- API, Data, Flows,
Components. The feature has no living LLD document yet, so each reads "none
yet" with the skill that writes it (or "n/a" with a reason); a tech design
that drops a category fails the shape the team reviews.
