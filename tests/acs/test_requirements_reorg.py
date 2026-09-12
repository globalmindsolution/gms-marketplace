"""MAR-145 spec 02 — functional/non-functional requirements reorg.

Covers AC-4 (content-preservation across the flat -> functional/non-functional
re-split), the positive topology half of AC-4/AC-5 (the move is complete, not
a copy-and-leave), AC-2 (the README documents the functional/non-functional
model + the requirements_layout setting), and the no-hardcoding half of AC-6
(the /acs:code merge-routing prose resolves the subfolder via settings, never
a literal marketplace path).

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
    "configuration.md", "workspace-and-state.md", "usage.md", "tabp.md",
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
            retired = RETIRED_BY_SKILLS_INDEPENDENCE.get(source, ())
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
        for source, clauses in RETIRED_BY_SKILLS_INDEPENDENCE.items():
            for clause in clauses:
                if self._homes(clause):
                    still_present.append((source, clause))
        self.assertEqual(
            still_present, [],
            "allowlisted-as-retired clauses that are still in the tree "
            "(drop them from RETIRED_BY_SKILLS_INDEPENDENCE): %r"
            % (still_present[:5],))

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
    structure plus the requirements_layout setting."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(os.path.join(REQ, "README.md"))

    def test_documents_index_lists_functional_subfolder(self):
        self.assertIn("functional/", self.body)

    def test_documents_index_lists_non_functional_subfolder(self):
        self.assertIn("non-functional/", self.body)

    def test_prose_names_the_model(self):
        lowered = self.body.lower()
        self.assertIn("functional", lowered)
        self.assertIn("non-functional", lowered)

    def test_mentions_requirements_layout_setting(self):
        self.assertIn("requirements_layout", self.body)

    def test_old_flat_table_rows_removed(self):
        # the old Documents table linked bare filenames directly under
        # docs/requirements/ (e.g. "[overview.md](overview.md)"); those bare
        # same-directory links must be gone now that the files moved.
        self.assertNotIn("[overview.md](overview.md)", self.body)
        self.assertNotIn("[skills.md](skills.md)", self.body)


class NoMarketplacePathHardcodingTest(unittest.TestCase):
    """AC-6 (no-hardcoding half): the requirements-merge routing prose
    resolves the functional/non-functional subfolder via
    settings.requirements_layout (placeholder syntax), never a literal
    marketplace-specific 'docs/requirements/functional/...' path. MAR-162
    moved the requirements-merge routing prose from /acs:code's producer
    files to /acs:docs-sync's executor (C-1); code-verifier.md retains it in
    the demoted advisory sub-check (b)."""

    SCOPED_FILES = (
        os.path.join(REPO_ROOT, "plugins", "acs", "agents", "docs-sync-executor.md"),
        os.path.join(REPO_ROOT, "plugins", "acs", "agents", "code-verifier.md"),
    )

    LITERAL_PATH_RE = re.compile(
        r"docs/requirements/(functional|non-functional)/\S")

    def test_no_literal_resolved_subfolder_path_in_merge_routing_prose(self):
        for path in self.SCOPED_FILES:
            body = read(path)
            m = self.LITERAL_PATH_RE.search(body)
            self.assertIsNone(
                m,
                "%s hardcodes a literal marketplace requirements path (%r) "
                "instead of resolving via settings.requirements_layout" % (
                    path, m.group(0) if m else None))

    def test_merge_routing_prose_uses_settings_placeholder(self):
        for path in self.SCOPED_FILES:
            body = read(path)
            self.assertIn(
                "requirements_layout", body,
                "%s must resolve the functional/non-functional subfolder "
                "via settings.requirements_layout, not a hardcoded path"
                % path)


if __name__ == "__main__":
    unittest.main()
