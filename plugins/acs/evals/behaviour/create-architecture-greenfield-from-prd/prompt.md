---
description: >-
  /acs:create-architecture greenfield: an approved PRD in docs/product/ and
  no code, with the containers, flows and deployment decided up front. It
  should design the full HLD/LLD doc set under docs/architecture/ to satisfy
  the PRD (three containers, two flows, all Mermaid), write no code, push its
  delivery branch to origin, and report the failed gh PR step as a finding.
expected_outcome: >-
  The eight hld/ files, lld/contracts.md and the book-appointment and
  send-reminder flow files exist under docs/architecture/; c4-container.md
  names booking-api, reminder-worker and PostgreSQL; send-reminder is a
  Mermaid sequence diagram through the SMS gateway; no source file created; a
  task/EVAL-1-* branch pushed with upstream set; result.json records the gh
  failure and no PR.
tags: [behaviour]
max_turns: 150
timeout_seconds: 3000
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit, Agent]
---

Run the /acs:create-architecture skill to design the architecture for
groomr from its approved PRD in docs/product/. Nothing is built yet, so this
is a fresh design. Everything it would ask me is answered below. Treat all of
it as confirmed and do not ask me anything.

- Containers: exactly three. `booking-api`, a Python 3.12 web service that
  serves the booking page and its JSON API; `reminder-worker`, a Python 3.12
  process that runs once an hour and texts tomorrow's appointments through
  the external SMS gateway; and `postgres`, a PostgreSQL 16 database holding
  groomers, services, pet owners and appointments. The SMS gateway is an
  external system.
- Flows for lld/flows/: exactly two, in this order: `book-appointment` (a pet
  owner picks a free slot, booking-api checks it is still free and stores the
  appointment in postgres) and `send-reminder` (reminder-worker reads
  tomorrow's appointments from postgres and sends each one an SMS through the
  SMS gateway).
- Deployment: all three containers run with docker compose on one container
  host in an EU region (the PRD's GDPR constraint); postgres is backed up
  nightly to storage in the same region.
- Anything else you would confirm: take what the PRD says.

Pushing to origin works from this machine, but there is no GitHub access
here: when a gh call fails, handle it the way the skill says to, and finish.
