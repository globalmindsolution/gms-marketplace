---
type: regex
target: { source: file, path: docs/requirements/functional/customer-listing.md }
pattern: '^DRAFT\s*[—–-]+\s*human-confirm-required'
flags: m
---

The confirmed functional area file exists at the default location (no
requirements set existed, so `<functional_dir>` is
`docs/requirements/functional`) and carries the `DRAFT —
human-confirm-required` marker every newly written area file opens with: an
extracted requirement is never authoritative without confirmation.
