---
type: regex
target: { source: file, path: .git/HEAD }
pattern: '^ref: refs/heads/story/EVAL-1-'
---

The analysis is a repo file on the ticket branch: as the first Build step the
skill renders `{type}/{ticket_id}-{slug}` and creates
`story/EVAL-1-cursor-pagination-for-get-customers`. Still on `main` means the
analysis went to the default branch or was never committed on a branch.
