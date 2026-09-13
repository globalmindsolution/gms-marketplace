# acs plugin — evaluation report

**Release gate: PASSED**

All 337 cases match the behaviour recorded for acs 0.4.9. No regression in the surfaces this dataset covers.

| | |
|---|---|
| Result | **PASS** |
| Build under test | acs `0.4.9` |
| Target release | `v0.4.10` |
| Dataset | `1.0.0`, recorded against acs `0.4.9` |
| Cases | 337 passed, 0 failed, 337 total |
| Known divergences | 2 |
| Wall clock | 15.9s |
| Generated | 2026-09-08T18:31:20Z |

Scope: the deterministic tier only. No model, no network, no cost. The agentic routing tier (`evals/`, `claude plugin eval`) is authored but has never been executed — it is early access and was not enabled on the account this dataset was built with, so nothing in this report speaks to routing behaviour at runtime.

## Coverage by surface

| Group | Surface | Cases | Passed | Failed | Divergences |
|---|---|---:|---:|---:|---:|
| Derivation | `acs lane\|stakes\|slug\|fanout` | 32 | 32 | 0 | 0 |
| Merge readiness | `acs readiness` | 18 | 18 | 0 | 0 |
| Verifier verdict | `acs verdict` | 15 | 15 | 0 | 2 |
| Executor file map | `acs filemap` | 8 | 8 | 0 | 0 |
| Ticket locks | `acs lock` | 7 | 7 | 0 | 0 |
| Pipeline gates | `acs gate` | 45 | 45 | 0 | 0 |
| Pipeline spine | `acs context\|ticket, new-ticket.py` | 12 | 12 | 0 | 0 |
| Shipped JSON schemas | `schemas/*.json` | 35 | 35 | 0 | 0 |
| Internals | `pr-conventions.py\|structure_lint.py\|statusline.py\|metrics_aggregate.py\|dispatch.py` | 12 | 12 | 0 | 0 |
| Skill inventory | `skills/*/SKILL.md` | 25 | 25 | 0 | 0 |
| Schema constraints (generated) | `schemas/*.json` | 128 | 128 | 0 | 0 |
| **Total** | | **337** | **337** | **0** | **2** |

## Coverage by ticket

Cases are tagged with the ticket whose behaviour they pin. A ticket with no cases is not covered by this dataset.

| Ticket | Cases | Passed | Failed |
|---|---:|---:|---:|
| MAR-402 | 12 | 12 | 0 |
| MAR-520 | 12 | 12 | 0 |
| MAR-521 | 44 | 44 | 0 |
| MAR-522 | 32 | 32 | 0 |
| MAR-523 | 45 | 45 | 0 |
| MAR-524 | 18 | 18 | 0 |
| MAR-525 | 12 | 12 | 0 |
| MAR-526 | 25 | 25 | 0 |
| MAR-527 | 178 | 178 | 0 |
| MAR-528 | 45 | 45 | 0 |
| MAR-529 | 8 | 8 | 0 |
| MAR-530 | 170 | 170 | 0 |

## Known divergences

These cases pass because they pin what the build **actually does**, which differs from what its own contract states. They are recorded deliberately so that closing the gap fails loudly instead of passing unnoticed. Each needs a decision before release.

### `VERDICT-009` — DIVERGENCE: `verdict show` does not enforce iteration freshness

- **What the build does:** `acs verdict show --iteration 3` reports ok=true, passed=true for a document whose own `iteration` is 1.
- **What its contract says:** validate_verdict checks `iteration` when the caller supplies it, and MAR-527's stated rule is that iteration 1's clean verdict copied onto iteration 3's path is not iteration 3's verdict.
- **Cause:** acs_commands.py cmd_verdict_show calls validate_verdict(doc, lens=..., ticket_id=...) — it passes neither `skill` nor `iteration`, so those two freshness checks never run at this call site.
- **Blast radius:** Read-only. The two call sites that decide anything DO pass all three: acs_lib/derive.py (verifier_passed, the field gate_create_pr reads) and acs_lib/lifecycle.py (the SubagentStop hook). So no gate is bypassed — but the coordinator-facing read command reports a stale verdict as a clean pass.
- **Status:** pinned as observed on the build under test; if v0.4.10 wires the two arguments through, this case fails and should be flipped to expect exit 2.

### `VERDICT-014` — DIVERGENCE: `verdict show` does not enforce skill freshness either

- **What the build does:** `acs verdict show --skill code` accepts a document whose own `skill` is `docs-sync`.
- **Cause:** The same missing arguments as VERDICT-009 — one fix closes both.
- **Status:** pinned as observed; flip to exit 2 if v0.4.10 closes it.

## Reproducing this run

```bash
export ACS_PLUGIN_ROOT=/root/.claude/plugins/marketplaces/gms-marketplace/plugins/acs
make eval          # or: python3 runner/run_golden.py --json results/latest.json
make report        # regenerates this file
```

