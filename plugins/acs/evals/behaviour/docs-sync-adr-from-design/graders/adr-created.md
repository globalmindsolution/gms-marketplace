---
type: file_exists
path: docs/adr/0003-*.md
---

The design's accepted decision record lands as the NEXT ADR in the repo's own
numbering (`NNNN-title.md`, after 0001 and 0002). `file_exists` sees only
created paths, so the seeded ADRs never satisfy this.
