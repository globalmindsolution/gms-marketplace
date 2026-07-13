# 0055 — Promote `mermaid_lint.py` to a shared plugin helper + blocking diagram-lint gate

**Status**: Accepted · **Date**: 2026-07-13

## Context

Two acs verifiers judged Mermaid diagrams by soft, non-deterministic means:
`create-design-verifier.md`'s `completeness` dimension asked only whether each
diagram was "syntactically plausible" (an LLM judgment), and
`create-architecture-verifier.md`'s `mermaid-diagrams` dimension did a
structural check plus an ad-hoc grep, with an optional `mmdc` render path. A
deterministic linter already existed (`tests/acs/mermaid_lint.py`), but it ran
only in this marketplace's own pre-commit/CI — it did not ship with the
plugin, so it never protected a consumer repo's generated docs (PRD G36,
`prd.md:202`; C-20/C-21, `prd.md:706-707`).

## Decision

Promote the linter to `plugins/acs/hooks/scripts/mermaid_lint.py` (`git mv`,
history preserved) as the single shared, stdlib-only diagram-lint helper, and
wire both verifiers to invoke it as a deterministic, blocking gate:

- **Promotion (A1).** The module moves into the plugin; its public API
  (`lint_text`, `lint_file`, `Finding`, `main(argv)`) and all four rules
  (`unknown-diagram-type`, `sequence-semicolon`, `er-key-space`, `empty-block`)
  are unchanged — only the docstring `Usage:` path is updated.
- **Promotion mechanics (A-sub-1).** `.pre-commit-config.yaml`'s
  `mermaid-lint` entry and the two test importers
  (`tests/acs/test_mermaid_diagrams.py`, `tests/acs/test_mar121_docs_flow_eval.py`)
  are repointed to the new plugin path. This resolves a literal tension
  between AC-1 ("promoted from `tests/acs/mermaid_lint.py`", i.e. moved) and
  AC-5 ("`tests/acs/mermaid_lint.py` … stays unchanged"): AC-5 is read as
  **behavior-preserving** — the marketplace pre-commit hook and CI keep
  linting every committed `.md` — rather than literal-path-preserving, with
  the one config/import repoint recorded here as the intentional deviation
  that resolves it.
- **Verifier wiring.** `create-architecture-verifier.md` dimension 4
  (`mermaid-diagrams`) and `create-design-verifier.md` dimension 5
  (`completeness`, diagram sub-clause) both now Bash-invoke `python3
  ${CLAUDE_PLUGIN_ROOT}/hooks/scripts/mermaid_lint.py <doc>.md`: each stderr
  `source:line: [rule] message` becomes one `<finding severity="blocking">`;
  exit 0 passes the dimension with no finding; exit 2 (usage error or an
  unreadable file) is itself a finding, so a broken invocation cannot silently
  pass. This replaces both verifiers' soft checks with one deterministic
  0-syntax-error gate, invoked only via `${CLAUDE_PLUGIN_ROOT}` — no shipped
  verifier hardcodes this marketplace's `tests/` layout, so the gate travels
  to any consumer repo with the plugin installed (principles #1 and #4).

## Alternatives considered

- **A2 — each verifier re-implements the lint inline.** No file move, no
  pre-commit reconcile, but duplicated logic across verifiers guarantees
  drift, and an LLM re-deriving a parser per run is non-deterministic —
  defeats the point of a deterministic gate. Rejected.
- **A3 — verifiers shell out to the existing `tests/acs/mermaid_lint.py`
  path.** Zero move, AC-5's literal wording untouched, but hardcodes this
  marketplace's `tests/` layout into the shipped verifier — the path does not
  exist in a consumer repo, so the gate would never run there. Rejected on
  generality grounds (violates C-20 / principle #1).
- **A-sub-2 — keep `tests/acs/mermaid_lint.py` and copy the module into the
  plugin.** Honors AC-5 literally, but two copies of the rule set is the exact
  drift this promotion exists to kill. Rejected.
- **A-sub-3 — move to the plugin path, leave a thin re-export shim at
  `tests/acs/mermaid_lint.py`.** Honors AC-5's literal wording and keeps one
  logic source, at the cost of a shim file plus `sys.path` plumbing to
  maintain. Not implemented — kept as the documented fallback if a reviewer
  insists on AC-5's literal "unchanged" wording.

## Consequences

- One logic source for Mermaid linting, reachable by both verifiers in any
  consumer repo via `${CLAUDE_PLUGIN_ROOT}`, and still enforced on this
  marketplace's own commits via the repointed pre-commit/CI path.
- A generated doc with a broken Mermaid diagram now **blocks**
  `create-architecture` and `create-design` verification where it previously
  passed a soft check — the two skills' paid behavioral evals may be affected
  by this contract change; re-baselining them is out of scope here (validated
  instead by the in-changeset dogfood: a broken fixture exits 1 with a
  `sequence-semicolon` finding, a clean fixture exits 0 with none).
- No new runtime dependency: the helper remains stdlib-only (`re`, `sys`,
  `collections`) — no Node, no `mmdc` requirement.
- Sibling ticket MAR-138 will add a `structure`/`audience-style` dimension to
  these same two verifier files; this change was kept surgical (minimal-line,
  no dimension renumbering) specifically to minimize that rebase surface.
