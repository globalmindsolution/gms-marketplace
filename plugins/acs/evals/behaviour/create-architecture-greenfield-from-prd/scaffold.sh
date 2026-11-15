#!/usr/bin/env bash
# A greenfield product with an approved PRD and roadmap and no code at all:
# the fixture repo with its code, tests and build config removed. The
# architecture is designed to satisfy the PRD, not reverse-engineered. A
# local bare repository stands in for GitHub.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
. "$here/../_fixtures/repo.sh"
acs_repo
git rm -rq src tests pyproject.toml CHANGELOG.md
cat > README.md <<'MD'
# groomr

Online booking for independent dog groomers. Nothing is built yet; the
product is defined in docs/product/.
MD
mkdir -p docs/product
cat > docs/product/prd.md <<'MD'
# PRD — groomr

## Vision

Every independent dog groomer takes bookings online without phone tag.

## Problem statement

Independent groomers lose hours a week to phone and text booking, and
no-shows cost them about a fifth of their slots.

## Target users & personas

- **Groomer** — runs a one- or two-person salon; sets hours and services.
- **Pet owner** — books and reschedules from a phone.

## Goals & success metrics

| Goal | Metric |
|---|---|
| G1 Online booking adoption | 500 bookings a week across all salons by 2027-03-31 |
| G2 Fewer no-shows | no-show rate below 5% of appointments by 2027-06-30 |

## Features (prioritized)

- **Must**: online booking (G1), SMS reminders the day before (G2)
- **Should**: deposits at booking (G2)
- **Could**: loyalty stamp card (G1)
- **Won't**: a marketplace ranking groomers

## Non-functional requirements

- Booking page loads in under 2 s at p95 on a 4G phone.
- 99.5% monthly availability.

## Constraints & assumptions

- EU customers only; personal data stays in an EU region under GDPR.
- SMS goes through a third-party SMS gateway.

## Out of scope

- Native mobile apps; payments beyond deposits.
MD
cat > docs/product/roadmap.md <<'MD'
# Roadmap

### Booking MVP — v0.1.0

Delivers online booking and SMS reminders.

### Deposits — v0.2.0

Delivers deposits at booking.

## Release versions

| Version | Milestone | Epic |
|---|---|---|
| v0.1.0 | Booking MVP | Online booking; SMS reminders |
| v0.2.0 | Deposits | Deposits |
MD
git add -A && git commit -qm "groomr PRD and roadmap, approved"
acs_local_origin
acs() { python3 "$ACS_SCRIPTS/acs.py" "$@"; }
# The run the skill resumes: a ticketless run (ADR-0127), opened here so
# its id -- and so every grader path -- is deterministic.
acs run new --prompt "Design the groomr architecture" > /dev/null
