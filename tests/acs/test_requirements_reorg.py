"""MAR-145 spec 02 — functional/non-functional requirements reorg.

Covers AC-4 (content-preservation across the flat -> functional/non-functional
re-split), the positive topology half of AC-4/AC-5 (the move is complete, not
a copy-and-leave), AC-2 (the README documents the functional/non-functional
model), and the no-hardcoding half of AC-6 (the merge-routing prose writes to
the located `<functional_dir>` / `<non_functional_dir>`, never a literal
marketplace path). ADR-0102 removed the `requirements_layout` setting MAR-145
introduced: the subfolders are found in the repo, else created at the
`functional/` / `non-functional/` convention.

Stdlib-only (json, os, re, unittest). Run:
  python3 -m unittest tests.acs.test_mar145_requirements_reorg -v
"""

import json
import os
import re
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(REPO_ROOT, "tests", "acs"))

import evidence_sidecar  # noqa: E402

REQ = os.path.join(REPO_ROOT, "docs", "requirements")
FUNCTIONAL = os.path.join(REQ, "functional")
NON_FUNCTIONAL = os.path.join(REQ, "non-functional")
FIXTURE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "fixtures", "mar145_clause_inventory.json")

ORIGINAL_FLAT_FILES = (
    "overview.md", "skills.md", "hooks.md", "workflow.md", "configuration.md",
    "reflection.md", "usage.md", "workspace-and-state.md", "tabp.md",
)

EXPECTED_FUNCTIONAL_FILES = {
    "workflow.md", "skills.md", "hooks.md", "reflection.md",
    "configuration.md", "workspace-and-state.md", "usage.md",
}

EXPECTED_NON_FUNCTIONAL_FILES = {
    "packaging-distribution.md", "portability.md", "statelessness.md",
    "security.md", "reliability-resumability.md", "performance-cost.md",
    "quality-gates.md",
}


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _tree_bodies():
    """Read every file under functional/ + non-functional/ once."""
    bodies = []
    for d in (FUNCTIONAL, NON_FUNCTIONAL):
        if not os.path.isdir(d):
            continue
        for name in os.listdir(d):
            if name.endswith(".md") and not evidence_sidecar.is_evidence_sidecar(name):
                bodies.append(read(os.path.join(d, name)))
    return bodies


# Clauses the skills-independence refactor RETIRED, by the flat source file
# they were inventoried from. AC-4 guards the MAR-145 *move* (a clause must
# not vanish because a file was split); it was never meant to freeze the
# requirements against later decisions. Each entry below states a requirement
# ADR-0089 or ADR-0090 removed or replaced, and is skipped by the
# exactly-one-home check rather than kept alive as dead prose:
#
#   * the per-skill "Pre-hook gate (predecessor must be completed)" table and
#     its rows, the exit-code row that told the user "which skill to run
#     first", and the "if the predecessor is not complete ... exit 2" clause —
#     `_require_completed` is deleted; a pre-hook checks its own skill's
#     inputs plus safety brakes, and out-of-order is one advisory line
#     (ADR-0089). The surviving input/brake conditions are restated as the new
#     "Per-skill pre-hook conditions" table in hooks.md;
#   * the fixed "# | Skill" pipeline table and its rows — the order is
#     declared in workflows/ship.yaml and restated as the ship.yaml step table
#     in workflow.md (ADR-0089);
#   * the `/ship <prompt>` clauses — /ship takes a ticket id and is a loop over
#     `acs.py workflow next` (ADR-0089);
#   * "Hooks MUST read and write files only in the workspace folder" — hooks
#     write only there, but now also READ ticket documents from the repo docs
#     tree, so the clause is restated with that split (ADR-0090);
#   * the `status` row "Managed by hooks" — status is derived from the run
#     ledger, never stored (ADR-0090);
#   * the [ASSUMPTION] on hook naming — resolved by the shipped twenty-row
#     hook inventory it was hedging.
RETIRED_BY_SKILLS_INDEPENDENCE = {
    'workflow.md': (
        '- Each workflow skill MUST be followed by a **post-hook** that writes the',
        '- Each workflow skill MUST be guarded by a **pre-hook** that checks readiness',
        '- Every hook gate still applies: `/ship` adds orchestration only and MUST NOT',
        '- If the predecessor is not complete, the pre-hook MUST exit with code **2**,',
        '- SHOULD be resumable: re-running `/ship` for a ticket continues from the',
        'MUST run in the following order for a given ticket',
        '`/ship <prompt>` drives the pipeline end-to-end: it MUST run',
        'clarifications wherever a skill requires them, and MUST **stop before',
        'which blocks the skill from running, and SHOULD emit a clear message telling',
        '| # | Skill | Purpose (summary) |',
        '| 1 | `/create-ticket` | Analyze & clarify requirements from the user prompt, codebase, and docs; create a ticket of type **epic**, **story**, or **task**. |',
        '| 3 | `/code` | Analyze & clarify the specs; implement features / bug fixes / tasks using the **TDD pattern**, updating affected repo docs as part of the change. Its verifier also reviews the changeset for business logic, features, quality, technical standards, architecture, system design, security, and documentation — see [Review feedback loop](#review-feedback-loop). |',
        '| 5 | `/create-pr` | Create a pull request shipping the implementation. |',
        '| 6 | `/merge-pr` | Review PR readiness and merge it if possible; when the readiness check fails, it is **report-only** (no automatic fixes). **User-invoked only**, after the user has reviewed the PR themselves — never auto-triggered by the pipeline. |',
    ),
    'hooks.md': (
        '(Unconditional on lane — the code-planner self-authors folded spec content when `specs/` is absent or empty; see [skills.md](skills.md).) |',
        '**[ASSUMPTION]** Naming above follows the `pre-code.py` / `code-state.json`',
        '- Hooks MUST read and write files only in the **workspace folder**',
        '`/create-architecture`, and `/create-project` — MUST have a **pre-hook**',
        '| Skill | Pre-hook gate (predecessor must be completed) |',
        '| `/create-architecture` | `/setup` done; PRD doc set exists (`prd_path`). |',
        '| `/create-design` | `/create-ticket` completed; ticket flagged `needs_design`. |',
        '| `/create-operations` | `/setup` done; architecture doc set exists (`hld/tech-stack.md`). |',
        '| `/create-pr` | `/code` completed **and its verifier passed** (no blocking findings) — the automatic remediation loop inside `/code` runs until this holds ([workflow.md](workflow.md#review-feedback-loop)). |',
        '| `/create-prd` | `/setup` done; product-level — no ticket required. |',
        '| `/create-principles` | `/setup` done; architecture doc set exists (`hld/tech-stack.md`). |',
        '| `/create-project` | `/setup` done; architecture doc set exists (greenfield only). |',
        '| `/create-quality` | `/setup` done; architecture doc set exists (`hld/tech-stack.md`). |',
        '| `/create-standards` | `/setup` done; architecture doc set exists (`hld/tech-stack.md`). |',
        '| `/create-ticket` | `/setup` done (settings exist); no pipeline predecessor. |',
        '| `/merge-pr` | A PR reference is recorded: `/create-pr` completed (pipeline tickets), or the product-level skill completed with the PR reference in its state file (delivery tickets — [skills.md](skills.md#product-level-delivery-tickets)). |',
        '| `/standardize-project` | `/setup` done; architecture doc set exists (`hld/tech-stack.md`). |',
        '| `0` | Ready — the skill proceeds. |',
        "| `2` | **Blocked** — the skill MUST NOT run. The hook's stderr message tells the user what is missing and which skill to run first. |",
    ),
    'skills.md': (
        '- MUST NOT bypass any pre/post hook; it adds orchestration only.',
        '- Pre-hook (`pre-code.py`) MUST verify that `/create-ticket` has',
        '- SHOULD be resumable: re-running it for a ticket continues from the first',
        '- `/ship <prompt>` MUST run the workflow skills in the SAME order on every',
    ),
    'workspace-and-state.md': (
        'hooks MUST read and write their files in the workspace folder**, located',
        '| `status` | `"open"\\|"in_progress"\\|"in_review"\\|"done"` | Managed by hooks |',
    ),
}


# Clauses the doc-set fold (ADR-0094) reworded: the four per-set skill
# sections became one /acs:create-docs section, reflection.md's triad list
# lost the four legs, and configuration.md's *_path rows now name the set as
# `/acs:create-docs <set>` rather than a leg command that no longer exists.
RETIRED_BY_DOC_SET_FOLD = {
    'skills.md': (
        "- MUST take the **PRD's non-functional requirements** and the full",
        '- MUST take the **PRD** and the full `architecture_path` set as upstream',
        '- MUST take the **PRD**, the full `architecture_path` set, and the',
    ),
    'reflection.md': (
        'create-principles, create-standards, standardize-project, create-requirements) MUST apply the',
    ),
    'configuration.md': (
        '| `operations_path` | string (repo-relative path) or `null` | `"docs/operations"` | No | Location of the `operations/` doc set (release process, runbooks, observability, incident response) bootstrapped and maintained by `/acs:create-operations`. Unset = acs does not maintain this set for this repo. |',
        '| `principles_path` | string (repo-relative path) or `null` | `"docs/principles"` | No | Location of the `principles/` doc set (engineering principles + rationale) bootstrapped and maintained by `/acs:create-principles`. Unset = acs does not maintain this set for this repo. |',
        '| `quality_path` | string (repo-relative path) or `null` | `"docs/quality"` | No | Location of the `quality/` doc set (test strategy, coverage policy) bootstrapped and maintained by `/acs:create-quality`. Unset = acs does not maintain this set for this repo. |',
        '| `standards_path` | string (repo-relative path) or `null` | `"docs/standards"` | No | Location of the `standards/` doc set (coding standards & conventions — `coding-standards.md`, `conventions.md`, `review-checklist.md`) bootstrapped and maintained by `/acs:create-standards`, which also reads `principles_path` (when set) as an upstream grounding input. Unset = acs does not maintain this set for this repo. |',
    ),
}


#: MAR-97 retired the tabp feature and this change removed it from disk, so
#: every clause the inventory captured from `tabp.md` has no destination file
#: to land in. Retiring them here rather than deleting them from the fixture
#: keeps the inventory a faithful record of the pre-reorg tree, and keeps the
#: exactly-one-home guarantee in force for every clause that still has a home.
RETIRED_BY_TABP_REMOVAL = {
    'tabp.md': (
        '| File | Kind | Change |',
        '| File | Kind | Runtime path |',
        '| `"claude-code"` | Run executed under Claude Code runtime | `"estimate"` | Actuals from `~/.claude/projects/<cwd-slug>/*.jsonl` (MAR-38 auto-detect) |',
        '| `"cowork"` | Cowork self-reported usage (future hook, MAR-40) | `"actual"` | Self-reported in `run.json usage.tokens_in/out/cost_usd` |',
        '| `"estimate"` | Heuristic token estimate (e.g. Cowork estimate) | `"estimate"` | Pre-written tokens in `run.json usage.tokens_in/out` |',
        '| `"unavailable"` | No usage data available | `"unavailable"` | None — omitted from aggregate totals |',
        '| `docs/adr/0023-tabp-hybrid-quality-mechanism-instruction-driven-plus-stdlib-helper.md` | ADR | EDIT — appended MAR-40 amendment extending scope to dual-runtime |',
        '| `docs/adr/0024-tabp-state-in-cowork-project-folder.md` | ADR | EDIT — appended MAR-40 amendment documenting cwd-as-project-dir + no-git + `.gitignore` guidance |',
        '| `docs/adr/0025-tabp-independent-verifier-subagent.md` | ADR | NEW — records D1 (inline-artifact input), D2 (N=3 cap), always-on rule, and residual risk |',
        '| `docs/adr/0026-tabp-hybrid-cost-sourcing.md` | ADR | NEW — records D3a (transcript-actuals) and D3b (dated snapshot pricing + settings override) |',
        '| `docs/adr/0027-tabp-dual-runtime-detection.md` | ADR | NEW — records the dual-runtime detection decision (explicit flag + auto-detect + cwd-as-project-dir) |',
        '| `docs/architecture/hld/c4-container.md` | HLD C4 container diagram | EDIT line 13: `tabp_skills` skill count 1→2 (added /tabp:usage) |',
        '| `docs/architecture/hld/c4-container.md` | HLD C4 container diagram | EDIT — added `Rel(tabp_skills, cc, …)` dual-runtime edge; repaired `tabp_agents` count 2→3 (added `screen-verifier-subagent`) |',
        '| `docs/architecture/hld/tech-stack.md` | HLD tech-stack table | EDIT line 5: skill count 1→2; removed "not yet shipped" clause |',
        '| `docs/architecture/hld/tech-stack.md` | HLD tech-stack table | EDIT — tabp runtime framing → "Cowork + Claude Code" |',
        '| `docs/architecture/lld/flows/tabp-usage-read.md` | LLD flow doc (Mermaid sequence) | NEW — /tabp:usage read flow with step annotations |',
        '| `plugins/tabp/.claude-plugin/plugin.json` | Plugin manifest | EDIT — description runtime clause → "Claude Cowork and Claude Code" |',
        '| `plugins/tabp/README.md` | Plugin README | EDIT — dual-runtime framing; new "Runtimes & project folder" and `.gitignore` guidance subsections |',
        '| `plugins/tabp/README.md` | Plugin README | EDIT: added `### usage` subsection under `## Skills`; refreshed "usage stubs" → "usage aggregation" |',
        "| `plugins/tabp/agents/screen-verifier-subagent.md` | Subagent charter | NEW — defines the verifier's role, artifact-only input contract, five re-judgment checks, and `pass\\|blocking` output contract |",
        '| `plugins/tabp/helpers/tabp_helper.py` | Python stdlib helper | EDIT — added `_add_runtime_arg`, `_resolve_runtime`, `--runtime` on the coordinator subcommands, and the `usage-read` runtime override (no git dependency in `.tabp/` derivation) |',
        '| `plugins/tabp/helpers/tabp_helper.py` | Python stdlib helper | REPLACED `_cmd_usage_read` stub with real aggregation; added `_MODEL_PRICING`, `_PRICING_SNAPSHOT_DATE`, `_resolve_pricing`, `_cwd_slug`, `_read_transcript_tokens`, `_derive_cost`; extended `_cmd_run_finalize` args; extended `_cmd_settings_read` for `model_pricing` pass-through |',
        '| `plugins/tabp/schemas/README.md` | Contract documentation | — |',
        '| `plugins/tabp/schemas/decision.schema.json` | JSON Schema Draft 2020-12 | `<project>/.tabp/runs/<run-id>/decision.json` |',
        '| `plugins/tabp/schemas/decision.schema.json` | JSON Schema | UPDATED — `verification_passed` and `verification_notes` descriptions updated to reflect independent verifier step |',
        '| `plugins/tabp/schemas/evidence.schema.json` | JSON Schema Draft 2020-12 | `<project>/.tabp/runs/<run-id>/evidence-<candidate-id>.json` |',
        '| `plugins/tabp/schemas/history.schema.json` | JSON Schema Draft 2020-12 | WIDENED `runs[].usage_source` enum to four values |',
        '| `plugins/tabp/schemas/history.schema.json` | JSON Schema Draft 2020-12 | `<project>/.tabp/history.json` |',
        '| `plugins/tabp/schemas/lock.schema.json` | JSON Schema Draft 2020-12 | `<project>/.tabp/.lock` |',
        '| `plugins/tabp/schemas/run.schema.json` | JSON Schema Draft 2020-12 | WIDENED `usage.usage_source` enum to four values; ADDED optional `usage.cost_basis` field |',
        '| `plugins/tabp/schemas/run.schema.json` | JSON Schema Draft 2020-12 | `<project>/.tabp/runs/<run-id>/run.json` |',
        '| `plugins/tabp/schemas/samples/decision.sample.json` | Validating sample | — |',
        '| `plugins/tabp/schemas/samples/evidence.sample.json` | Validating sample | — |',
        '| `plugins/tabp/schemas/samples/history.sample.json` | Validating sample | — |',
        '| `plugins/tabp/schemas/samples/lock.sample.json` | Validating sample | — |',
        '| `plugins/tabp/schemas/samples/run.sample.json` | Validating sample | — |',
        '| `plugins/tabp/skills/screen-cvs/SKILL.md` Step 5a | Coordinator instruction | REPLACED — coordinator self-verification retired; independent verifier spawn + remediate loop (N=3) inserted |',
        '| `plugins/tabp/skills/screen-cvs/SKILL.md` Step 5b | Coordinator instruction | UPDATED — records independent verifier verdict (`verification_passed`), not a coordinator self-attestation |',
        '| `plugins/tabp/skills/screen-cvs/SKILL.md` | Coordinator protocol (SKILL.md) | EDIT — Step 0 reworded runtime-agnostically; Claude Code `--runtime claude-code` / `--project-dir <session-cwd>` note; no-git assertion; Bash-denied note generalized to "the runtime" |',
        '| `plugins/tabp/skills/usage/SKILL.md` | Coordinator protocol (SKILL.md) | EDIT — "recruiter\'s Cowork project folder" → "recruiter\'s project folder" (retained `usage_source` enum and the Cowork self-reported note unchanged) |',
        '| `plugins/tabp/skills/usage/SKILL.md` | Coordinator protocol (SKILL.md) | NEW — /tabp:usage skill with frontmatter, usage-read invocation, per-run + totals rendering, honesty rule, degradation path, guardrails |',
        '| `tests/tabp/test_tabp_usage_skill.py` | Structural test module (stdlib unittest) | NEW — TU-01..TU-30 asserting file presence, frontmatter, invocation markers, rendering markers, honesty/degradation, namespace guard |',
        '| `usage_source` | Meaning | `cost_basis` | Token source |',
    ),
}

#: Retired by ADR-0095 (static delivery-path routing). The `size`/`stakes`
#: axes and the lane derived from them are gone: rigor is one judgement, made
#: once from `plan.md` by /ship and recorded on run.json, so there
#: is no axis for /create-ticket to capture, nothing for an in-flight trigger
#: to raise, and nothing a user has to confirm before it can be lowered. The
#: guarantees these clauses carried did not lapse — they became unnecessary,
#: which is the only kind of clause that may be retired rather than re-homed.
RETIRED_BY_DELIVERY_PATH_ROUTING = {
    'skills.md': (
        '- MUST capture **`size`** and **`stakes`** during `/create-ticket` analysis (MAR-56):',
        'Stakes MUST NOT be silently lowered from a user-confirmed value; de-escalation requires',
        'axes may be automatically raised by an in-flight trigger, but MUST NOT be',
    ),
}

#: The v0.5.0 implementation-pipeline redesign REWORDED two clauses rather
#: than retiring them: the guarantee each carried is still in the tree, under
#: the name its carrier now has. That is a different fact from the four
#: tables above, and it earns a different check -- an allowlist that only said
#: "gone" would let a genuine loss hide behind a rename. Each entry maps the
#: pre-reorg wording to the successor text that MUST be present, and
#: `test_reworded_clauses_have_a_live_successor` asserts it.
REWORDED_BY_V050_REDESIGN = {
    'hooks.md': {
        # `skill-start.py` is `acs.py step start` and a ticket partition is a
        # run (ADR-0097). The permission -- a coordinator MAY read the parent
        # epic's state to resolve design -- is unchanged.
        "the coordinator's `skill-start.py` MAY read the parent epic's partition to":
            "`acs step start` MAY read the parent epic's run to",
    },
    'workflow.md': {
        # The review left `/acs:code` for `/acs:review-code` (ADR-0099), so
        # the actor in the sentence changed. The obligation -- blocking
        # findings MUST drive another remediation round, with no intervening
        # plan phase -- is unchanged, and is now carried by the workflow's
        # single `loops:` entry.
        '- When the verifier produces blocking findings, the coordinator MUST':
            "- When the review records blocking findings, the workflow's single `loops:`",
    },
    'configuration.md': {
        # Same actor change inside the `e2e` settings row: the agent that
        # runs the configured suite is `/acs:review-code`'s final gate, not a
        # verifier inside `/acs:code`. The REQUIREMENT -- a green run is
        # required for a passing verdict -- is unchanged, and the successor
        # is matched on that half.
        '| `e2e` | object | unset | No | **Deprecated compatibility alias** for `suites.e2e`: `{ "command", "setup"?, "teardown"?, "per_iteration"? }`. Still accepted and validated exactly as before, but normalized at load time into `suites["e2e"]` — new configuration should prefer `suites.e2e` directly; `/acs:setup` offers a one-time migration on re-run. Unset = no e2e suite. When configured: spec test plans state the e2e impact, `/code` authors the declared e2e tests in the same changeset, and the `code-verifier` runs the full suite (`setup` → `command` → `teardown` always) — a green run is required for a passing verdict; `per_iteration: false` (default) defers the run past iterations that already have other blocking findings. `/create-project` scaffolds the harness and proposes this block for greenfield repos with a user-facing surface. This same `e2e`/`suites.e2e` configuration is also the **single opt-in signal** for the CI required merge gate — no dedicated `e2e.ci`/`suites.e2e.ci` enable key exists, or is ever introduced (see the `/acs:setup` Step 3 note below). |':
            "and `/acs:review-code`'s final gate runs the full suite "
            "(`setup` \u2192 `command` \u2192 `teardown` always) \u2014 a green run is "
            "required for a passing verdict",
    },
    'overview.md(scoped:Packaging+Distribution+CorePrinciples)': {
        # The governance principle is untouched: blocking findings loop back
        # automatically, bounded at 3 iterations. What changed is who reviews
        # (ADR-0099) and that the loop re-enters `code`, so the round is
        # code -> review rather than plan -> execute.
        '| Automatic review loop | The `code-verifier` reviews the whole changeset (business logic, quality, architecture, security, …); blocking findings loop back through plan → execute automatically, max 3 iterations. |':
            "| Automatic review loop | `/acs:review-code` reviews the whole "
            "changeset",
    },
}


#: ADR-0102 ("documents are found, not configured") REWORDED the clauses that
#: named a path setting. The location each setting carried is still stated --
#: as the conventional default in configuration.md's "Document and workspace
#: locations" table, or as the fixed workspace -- so each is a rewording with
#: a live successor, not a retirement. What the decision did remove is the
#: override/opt-out half some of them carried (`workspace_path` pointing
#: elsewhere, `adr_path: null`); those halves have no successor by design.
REWORDED_BY_ADR_0102 = {
    'skills.md': {
        # /setup still derives the workspace silently, with no prompt and no
        # required input; the optional override is what went.
        'workspace_path` derives silently to `<main-checkout>/.acs/state-machine`':
            "- The workspace derives silently to `<main-checkout>/.acs/state-machine` —",
        'no prompt, no required input; an explicit':
            "no prompt, no required input, and no override (ADR-0086,",
        # The PRD is still create-architecture's primary input and still
        # required; the skill checks for it at Start instead of the pre-hook.
        '- MUST take the **PRD** (`prd_path`) as its primary input — its pre-hook':
            "- MUST take the **PRD** as its primary input — the skill locates it at",
        '- MUST take the product architecture doc set (`architecture_path`) as':
            "- MUST take the product architecture doc set (found in the repo) as",
    },
    'configuration.md': {
        '`/setup` no longer requires `workspace_path`: when unset, it derives':
            "- `/setup` derives the workspace (`<main-checkout>/.acs/state-machine`) —",
        '| Project (local) | `<repo>/.acs/settings.local.json` | **gitignored** | Machine-specific keys — notably `workspace_path`. |':
            "| Project (local) | `<repo>/.acs/settings.local.json` | **gitignored** | "
            "Machine-specific overrides of any key. |",
        # The settings-table rows became rows of the conventional-defaults
        # table, which carry each set's producer/consumer obligations over.
        '| `adr_path` | string (repo-relative path) or `null` | `"docs/adr"` | No | `/code` commits the accepted decision records from the ticket\'s `design.md` to this path as part of its documentation updates — on by default so decisions outlive archived ticket partitions. Explicit `null` disables (designs then stay workspace-only). |':
            "| ADRs | `docs/adr/` | `/code` commits the accepted decision records "
            "from the ticket's `design.md` here, so decisions outlive archived "
            "ticket partitions. |",
        '| `architecture_path` | string (repo-relative path) | `"docs/architecture"` | No | Location of the product architecture doc set in the consumer repo — **HLD** (C4 levels 1–3, data model, deployment, tech stack) and **LLD** (per-flow sequence diagrams, contracts). Bootstrapped by `/create-architecture`, consumed by `/create-design`, kept current by `/code`. |':
            "| Architecture set | `docs/architecture/` (`hld/tech-stack.md` is its "
            "sentinel file) | **HLD** (C4 levels 1–3, data model, deployment, "
            "tech stack) and **LLD** (per-flow sequence diagrams, contracts). "
            "Bootstrapped by `/create-architecture`, consumed by `/create-design`, "
            "kept current by `/code`. |",
        '| `prd_path` | string (repo-relative path) | `"docs/product"` | No | Location of the PRD doc set (`prd.md`, `roadmap.md`) in the consumer repo — bootstrapped and amended by `/create-prd`; `/create-architecture` requires and is verified against it; `/create-ticket` traces tickets to it. |':
            "| PRD | `docs/product/prd.md` + `docs/product/roadmap.md` | Bootstrapped "
            "and amended by `/create-prd`; `/create-architecture` requires and is "
            "verified against it; `/create-ticket` traces tickets to it. |",
        '| `requirements_path` | string (repo-relative path) | `"docs/requirements"` | No | Location of the **living requirements** doc set — the standing behavioral contract, one file per feature area, accumulated ticket by ticket: `/code` merges each ticket\'s acceptance criteria and behavior-defining clarifications into the touched area\'s file as part of its documentation work; `/create-ticket` reads it as the area\'s current behavior and flags contradictions. Grows organically — no bootstrap skill required. |':
            "| Living requirements | `docs/requirements/` with `functional/` and "
            "`non-functional/` subfolders (an existing set's own subfolder names "
            "are followed) | The standing behavioral contract, one file per "
            "feature area: `/code` merges each ticket's acceptance criteria and "
            "behavior-defining clarifications into the touched area's file; "
            "`/create-ticket` reads it as the area's current behavior and flags "
            "contradictions. |",
        '| `workspace_path` | string (absolute path) | derived (`<main-checkout>/.acs/state-machine`)':
            "hooks read/write ticket state — is always "
            "`<main-checkout>/.acs/state-machine`,",
    },
}

#: Every rewording table: each maps pre-reorg wording to a successor that
#: must be live in the tree.
REWORDING_TABLES = (REWORDED_BY_V050_REDESIGN, REWORDED_BY_ADR_0102)


def _retired():
    """Every allowlist, merged: a clause is exempt when any fold retired it."""
    merged = {}
    for table in (RETIRED_BY_SKILLS_INDEPENDENCE, RETIRED_BY_DOC_SET_FOLD,
                  RETIRED_BY_TABP_REMOVAL, RETIRED_BY_DELIVERY_PATH_ROUTING):
        for source, clauses in table.items():
            merged[source] = merged.get(source, ()) + tuple(clauses)
    for rewording in REWORDING_TABLES:
        for source, mapping in rewording.items():
            merged[source] = merged.get(source, ()) + tuple(mapping)
    return merged

class ContentPreservationTest(unittest.TestCase):
    """AC-4: every MUST/SHOULD/MAY/[OPEN]/[ASSUMPTION]-tagged clause (or an
    equivalent clause-level unit — a markdown table data row) inventoried
    from the flat pre-reorg source files lands in EXACTLY ONE file under the
    reorganized functional/ + non-functional/ tree. The fixture was captured
    from docs/requirements/*.md before the move (commit d1531e3); overview.md
    contributes only its Packaging/Distribution/Core-principles sections —
    its Vision/Goals-framing/Target-domains/Out-of-scope content is retained
    as context in the rewritten README.md instead (design non-1:1 seam rule),
    which this functional/non-functional exact-one-place check deliberately
    does not cover."""

    @classmethod
    def setUpClass(cls):
        with open(FIXTURE, encoding="utf-8") as fh:
            cls.fixture = json.load(fh)["clauses_by_source_file"]
        cls.bodies = _tree_bodies()

    def _homes(self, clause):
        return [i for i, body in enumerate(self.bodies) if clause in body]

    def test_every_clause_lands_in_exactly_one_destination_file(self):
        missing = []
        duplicated = []
        for source, clauses in self.fixture.items():
            retired = _retired().get(source, ())
            for clause in clauses:
                if clause in retired:
                    continue
                homes = self._homes(clause)
                if len(homes) == 0:
                    missing.append((source, clause))
                elif len(homes) > 1:
                    duplicated.append((source, clause, len(homes)))
        self.assertEqual(
            missing, [],
            "clauses dropped by the reorg (present in no functional/"
            "non-functional file): %r" % (missing[:5],))
        self.assertEqual(
            duplicated, [],
            "clauses duplicated across >1 functional/non-functional file: "
            "%r" % (duplicated[:5],))

    def test_retired_allowlist_is_really_retired(self):
        """Every allowlisted clause must actually be absent — an entry that is
        still in the tree would silently exempt a clause the reorg guard is
        supposed to be watching."""
        still_present = []
        for source, clauses in _retired().items():
            for clause in clauses:
                if self._homes(clause):
                    still_present.append((source, clause))
        self.assertEqual(
            still_present, [],
            "allowlisted-as-retired clauses that are still in the tree "
            "(drop them from RETIRED_BY_SKILLS_INDEPENDENCE): %r"
            % (still_present[:5],))

    def test_reworded_clauses_have_a_live_successor(self):
        """A reworded clause is exempt from the exact-one-place check only
        because its successor is in the tree. Assert that, or the rewording
        table becomes the escape hatch the retirement tables are guarded
        against being."""
        missing = []
        for rewording in REWORDING_TABLES:
            for source, mapping in rewording.items():
                for old, successor in mapping.items():
                    if not self._homes(successor):
                        missing.append((source, old, successor))
        self.assertEqual(
            missing, [],
            "reworded clauses whose successor is in no functional/"
            "non-functional file: %r" % (missing[:5],))

    def test_reworded_table_only_names_inventoried_clauses(self):
        unknown = []
        for rewording in REWORDING_TABLES:
            for source, mapping in rewording.items():
                known = set(self.fixture.get(source, ()))
                for clause in mapping:
                    if clause not in known:
                        unknown.append((source, clause))
        self.assertEqual(
            unknown, [],
            "rewording entries not in the fixture: %r" % (unknown[:5],))

    def test_retired_allowlist_only_names_inventoried_clauses(self):
        """The allowlist may only exempt clauses the fixture actually
        inventoried, so it cannot become a general-purpose escape hatch."""
        unknown = []
        for source, clauses in RETIRED_BY_SKILLS_INDEPENDENCE.items():
            known = set(self.fixture.get(source, ()))
            for clause in clauses:
                if clause not in known:
                    unknown.append((source, clause))
        self.assertEqual(unknown, [], "allowlist entries not in the fixture: %r" % (unknown[:5],))

    def test_fixture_is_non_trivial(self):
        total = sum(len(v) for v in self.fixture.values())
        self.assertGreater(
            total, 200,
            "the clause fixture looks truncated (expected the full "
            "pre-reorg inventory, ~283 lines)")


class PositiveTopologyTest(unittest.TestCase):
    """AC-4/AC-5: the reorganized tree exists and the move is complete (not
    a copy-and-leave) -- none of the 9 original flat content filenames sit
    directly under docs/requirements/ any more."""

    def test_functional_dir_exists_with_expected_files(self):
        self.assertTrue(os.path.isdir(FUNCTIONAL),
                         "docs/requirements/functional/ must exist")
        actual = {f for f in os.listdir(FUNCTIONAL)
                  if f.endswith(".md") and not evidence_sidecar.is_evidence_sidecar(f)}
        self.assertEqual(actual, EXPECTED_FUNCTIONAL_FILES)

    def test_non_functional_dir_exists_with_expected_files(self):
        self.assertTrue(os.path.isdir(NON_FUNCTIONAL),
                         "docs/requirements/non-functional/ must exist")
        actual = {f for f in os.listdir(NON_FUNCTIONAL)
                  if f.endswith(".md") and not evidence_sidecar.is_evidence_sidecar(f)}
        self.assertEqual(actual, EXPECTED_NON_FUNCTIONAL_FILES)

    def test_original_flat_files_no_longer_present(self):
        for name in ORIGINAL_FLAT_FILES:
            self.assertFalse(
                os.path.isfile(os.path.join(REQ, name)),
                "%s must no longer exist directly under docs/requirements/ "
                "(move must be complete, not copy-and-leave)" % name)

    def test_readme_still_present(self):
        self.assertTrue(os.path.isfile(os.path.join(REQ, "README.md")))


class ReadmeDocumentsModelTest(unittest.TestCase):
    """AC-2 (README half): docs/requirements/README.md documents the
    functional/non-functional model -- its Documents index lists the two
    subfolders (replacing the old flat 8-row table) and the prose names the
    structure. MAR-145's prose also named the `requirements_layout` setting;
    ADR-0102 removed it, so the model prose must no longer present it (or
    `requirements_path`) as a live key. The dated decision-log rows are
    history and are exempt."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(os.path.join(REQ, "README.md"))
        # Everything but the dated decision-log rows ("| 2026-07-15 | ...").
        cls.prose = "\n".join(
            line for line in cls.body.splitlines()
            if not re.match(r"\|\s*\d{4}-\d{2}-\d{2}\s*\|", line))

    def test_documents_index_lists_functional_subfolder(self):
        self.assertIn("functional/", self.body)

    def test_documents_index_lists_non_functional_subfolder(self):
        self.assertIn("non-functional/", self.body)

    def test_prose_names_the_model(self):
        lowered = self.body.lower()
        self.assertIn("functional", lowered)
        self.assertIn("non-functional", lowered)

    def test_model_prose_no_longer_names_a_path_setting(self):
        for key in ("requirements_layout", "functional_subdir", "requirements_path"):
            self.assertNotIn(
                key, self.prose,
                "docs/requirements/README.md still describes the removed "
                "%r setting outside its dated decision log (ADR-0102)" % key)

    def test_old_flat_table_rows_removed(self):
        # the old Documents table linked bare filenames directly under
        # docs/requirements/ (e.g. "[overview.md](overview.md)"); those bare
        # same-directory links must be gone now that the files moved.
        self.assertNotIn("[overview.md](overview.md)", self.body)
        self.assertNotIn("[skills.md](skills.md)", self.body)


class NoMarketplacePathHardcodingTest(unittest.TestCase):
    """AC-6 (no-hardcoding half): the requirements-merge routing prose
    writes to the located functional/non-functional subfolder -- the
    `<functional_dir>` / `<non_functional_dir>` placeholders its task
    constraints carry (ADR-0102 removed the `requirements_layout` setting
    that used to name them) -- never a literal marketplace-specific
    'docs/requirements/functional/...' path. MAR-162
    moved the requirements-merge routing prose from /acs:code's producer
    files to /acs:docs-sync's executor (C-1).

    The second scoped file was code-verifier.md, which retained the prose in a
    demoted advisory sub-check. v0.5.0 retired the verifier with the review,
    and the sub-check went with it rather than moving, so the routing prose
    now lives in exactly one file. The scope is that one file, and the
    assertion below proves the set has not silently emptied."""

    SCOPED_FILES = (
        os.path.join(REPO_ROOT, "plugins", "acs", "agents", "docs-sync-executor.md"),
    )

    LITERAL_PATH_RE = re.compile(
        r"docs/requirements/(functional|non-functional)/\S")

    def test_the_scope_is_not_empty(self):
        """An exclusion list that empties itself passes every loop below
        vacuously -- the retirement of one scoped file must not read as the
        rule no longer applying anywhere."""
        self.assertTrue(self.SCOPED_FILES)
        for path in self.SCOPED_FILES:
            self.assertTrue(os.path.isfile(path), path)

    def test_no_literal_resolved_subfolder_path_in_merge_routing_prose(self):
        for path in self.SCOPED_FILES:
            body = read(path)
            m = self.LITERAL_PATH_RE.search(body)
            self.assertIsNone(
                m,
                "%s hardcodes a literal marketplace requirements path (%r) "
                "instead of the located <functional_dir>/<non_functional_dir>" % (
                    path, m.group(0) if m else None))

    def test_merge_routing_prose_uses_located_subfolder_placeholder(self):
        for path in self.SCOPED_FILES:
            body = read(path)
            for placeholder in ("`<functional_dir>/", "`<non_functional_dir>/"):
                self.assertIn(
                    placeholder, body,
                    "%s must route into the located subfolder (%s...), not a "
                    "hardcoded path" % (path, placeholder))
            self.assertNotIn(
                "requirements_layout", body,
                "%s still names the removed requirements_layout setting "
                "(ADR-0102)" % path)


if __name__ == "__main__":
    unittest.main()
