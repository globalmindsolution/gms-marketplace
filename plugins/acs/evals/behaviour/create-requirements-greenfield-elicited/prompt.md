---
description: >-
  /acs:create-requirements greenfield: a repo with an approved PRD and no
  code, every requirement supplied in the prompt since the run cannot answer
  questions. It should write DRAFT functional and non-functional area files
  under docs/requirements/ carrying exactly the elicited clauses, write no
  code, push its delivery branch, and report the failed gh PR step as a
  finding.
expected_outcome: >-
  docs/requirements/functional/book-appointment.md and
  appointment-reminders.md and docs/requirements/non-functional/privacy.md
  and performance.md, each opening with the DRAFT marker and stating the
  elicited MUST clauses (15-minute slots, no double-booking, the 09:00-18:00
  SMS window, EU residency and 30-day deletion); no source file created; a
  task/EVAL-1-* branch pushed with upstream set; result.json records the gh
  failure and no PR.
tags: [behaviour]
max_turns: 150
timeout_seconds: 3000
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit, Agent]
---

Run the /acs:create-requirements skill to write the first requirements for
groomr, defined in docs/product/. Nothing is built yet, so there is no code
to read: the requirements come from me, and they are all below. Treat this
as the confirmed DRAFT baseline and do not ask me anything.

- Exactly four area files: `docs/requirements/functional/book-appointment.md`,
  `docs/requirements/functional/appointment-reminders.md`,
  `docs/requirements/non-functional/performance.md` and
  `docs/requirements/non-functional/privacy.md`.
- book-appointment: a pet owner MUST be able to book a free slot, in
  15-minute steps, within the groomer's opening hours; the system MUST NOT
  double-book a groomer; a pet owner MAY reschedule up to 24 hours before the
  appointment.
- appointment-reminders: the system MUST send exactly one SMS reminder the
  day before each appointment, between 09:00 and 18:00 salon local time; the
  SMS SHOULD carry a reschedule link.
- performance: the booking page MUST load in under 2 s at p95 on a 4G phone
  (the PRD's NFR).
- privacy: personal data MUST be stored only in an EU region; a pet owner's
  data MUST be deleted within 30 days of their request.
- Deposits and the loyalty card are later: leave them out.

Pushing to origin works from this machine, but there is no GitHub access
here: when a gh call fails, handle it the way the skill says to, and finish.
