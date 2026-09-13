# ADR 0001 — One JSON document, written atomically

**Status:** accepted · 2026-06-02

## Context

The service holds a few hundred products and orders and runs as one process.
A database would be the largest dependency in the codebase.

## Decision

State is one JSON document (`data/store.json`) with four sections —
`products`, `stock`, `orders`, `charges`. Every save writes a temp file in the
same directory and `os.replace`s it over the document, so a crash mid-write
leaves the previous document intact.

## Consequences

- No concurrent writers: the process is the only writer.
- Reads are whole-document; fine at this size, revisit past ~10k orders.
