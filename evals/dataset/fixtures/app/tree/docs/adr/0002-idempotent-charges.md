# ADR 0002 — Charges are idempotent by key

**Status:** accepted · 2026-06-09

## Context

A retried `pay` after a timeout must not charge the customer twice.

## Decision

The gateway derives an idempotency key from `(order_id, amount_cents)`; a
charge whose key already exists returns the existing record unchanged and
records nothing new. Refunds are applied against a charge record and can never
exceed what remains on it.

## Consequences

- Changing an order's amount produces a new key, hence a new charge — callers
  must refund the first one explicitly.
- The key is deterministic, so replaying a request is safe by construction.
