---
type: regex
target: { source: file, path: docs/requirements/functional/book-appointment.md }
pattern: '^(?=DRAFT\s*[—–-]+\s*human-confirm-required)(?=[\s\S]*\bMUST\b)(?=[\s\S]*\b15.?minute)(?=[\s\S]*double.?book)'
flags: mi
---

The functional area file opens with the `DRAFT — human-confirm-required`
marker (greenfield too: an elicited requirement is a DRAFT baseline) and
states the elicited clauses in the MUST vocabulary: 15-minute slots, no
double-booking.
