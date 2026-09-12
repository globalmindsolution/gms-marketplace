"""MAR-579 — this repo's own post-code eval gate is retired, and the docs say so.

Two guards over committed artifacts, both deterministic and stdlib-only:

1. `SettingsShapeTest` pins THIS repo's `.acs/settings.json` shape — no `e2e`
   object, no `suites.e2e` entry, `post_code_test` absent (or `enabled` null) —
   read twice: raw via `json.load`, and resolved via
   `acs_lib.load_settings(REPO_ROOT)` (which folds a configured `e2e` into
   `suites.e2e`, so the resolved view is the one `/acs:ship` actually reads).
   It then applies the shipped post-code test-gate rule
   (`plugins/acs/skills/ship/SKILL.md`, "Post-code test gate": an explicit
   `post_code_test.enabled` wins; otherwise the step is ON iff `settings.e2e`
   or `suites.e2e` is set) and requires it to resolve OFF. This pins a
   repo-local configuration choice, not plugin behaviour: the plugin's e2e
   layer is unchanged and stays opt-in for consumer repos (PRD G13).

2. `DocsPolicyTest` pins the policy the documents now state — acs-evals' tier-1
   deterministic suite becomes the per-PR brake when that suite is imported
   here, paid measurement runs at release cadence from it, and until then PRs
   are gated by the unit suite, the coverage hard-fail and the free pre-commit
   eval tier, with the in-repo paid suite kept as an on-demand tool
   for the forge scenarios (`s07_fanout_tracker_sync`, `s08_create_pr_forge`) —
   one test per changed document, each asserting both the new wording and the
   absence of the retired claim.

Stdlib-only (json, os, re, subprocess, sys, unittest), mirroring the sibling
committed-settings guards `test_settings_models_pinned.py` and
`test_release_settings_schema.py`, which read the same file through REPO_ROOT.

Run:  python3 -m unittest tests.acs.test_dogfood_eval_gate -v
"""

import json
import os
import re
import subprocess
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SETTINGS_PATH = os.path.join(REPO_ROOT, ".acs", "settings.json")
SCRIPTS = os.path.join(REPO_ROOT, "plugins", "acs", "hooks", "scripts")
sys.path.insert(0, SCRIPTS)

import acs_lib as lib  # noqa: E402

PRD_PATH = os.path.join(REPO_ROOT, "docs", "product", "prd.md")
ROADMAP_PATH = os.path.join(REPO_ROOT, "docs", "product", "roadmap.md")
EVALS_README_PATH = os.path.join(REPO_ROOT, "evals", "README.md")
TESTING_STRATEGY_PATH = os.path.join(REPO_ROOT, "docs", "quality", "testing-strategy.md")
RUNBOOK_PATH = os.path.join(REPO_ROOT, "docs", "operations", "release-runbook.md")
ADR_PATH = os.path.join(
    REPO_ROOT, "docs", "adr", "0022-behavioral-evals-local-only-ci-runs-no-llm-calls.md")

ADR_RELPATH = "docs/adr/0022-behavioral-evals-local-only-ci-runs-no-llm-calls.md"
AMENDMENT_HEADING = "## Amendment — MAR-579"


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def section(body, heading):
    """The text from a heading line up to the next heading of the same or higher level."""
    match = re.search(r"(?m)^" + re.escape(heading) + r".*$", body)
    if match is None:
        raise AssertionError("heading %r not found" % heading)
    level = len(heading) - len(heading.lstrip("#"))
    nxt = re.search(r"(?m)^#{1,%d} \S" % level, body[match.end():])
    end = match.end() + nxt.start() if nxt else len(body)
    return body[match.start():end]


LIST_MARKER = re.compile(r"\s*(?:[-*]|\d+\.)\s")


def list_item(body, marker):
    """A markdown list item (its continuation lines included) identified by a marker."""
    lines = body.splitlines()
    for index, line in enumerate(lines):
        if marker in line and LIST_MARKER.match(line):
            collected = [line]
            for follow in lines[index + 1:]:
                if follow.strip() == "" or LIST_MARKER.match(follow):
                    break
                collected.append(follow)
            return "\n".join(collected)
    raise AssertionError("no list item found containing %r" % marker)


def paragraph(body, marker):
    """The blank-line-delimited block containing a marker."""
    for block in body.split("\n\n"):
        if marker in block:
            return block
    raise AssertionError("no paragraph found containing %r" % marker)


def line_containing(body, needle):
    for line in body.splitlines():
        if needle in line:
            return line
    raise AssertionError("no line found containing %r" % needle)


def table_row(body, first_cell):
    return line_containing(body, "| %s |" % first_cell)


def post_code_test_gate(settings):
    """The shipped ship/SKILL.md rule: an explicit enabled wins, else e2e presence decides."""
    explicit = ((settings or {}).get("post_code_test") or {}).get("enabled")
    if isinstance(explicit, bool):
        return "on" if explicit else "off"
    has_e2e = bool((settings or {}).get("e2e"))
    has_suite = bool(((settings or {}).get("suites") or {}).get("e2e"))
    return "on" if (has_e2e or has_suite) else "off"


class SettingsShapeTest(unittest.TestCase):
    """[AC-1, AC-2] the committed settings carry no e2e configuration, so the
    post-code test step resolves off by the shipped e2e-presence rule."""

    @classmethod
    def setUpClass(cls):
        with open(SETTINGS_PATH, encoding="utf-8") as fh:
            cls.raw = json.load(fh)
        cls.resolved, cls.found = lib.load_settings(REPO_ROOT)

    def test_committed_settings_declare_no_e2e(self):
        self.assertNotIn(
            "e2e", self.raw,
            "this repo retired its per-ticket paid e2e gate (MAR-579): the top-level "
            "`e2e` object must not come back",
        )
        self.assertNotIn(
            "e2e", self.raw.get("suites") or {},
            "`suites.e2e` is the same gate under its non-deprecated name and must stay absent",
        )

    def test_committed_settings_leave_post_code_test_null(self):
        post_code_test = self.raw.get("post_code_test")
        self.assertIn(
            post_code_test, (None, {}),
            "post_code_test must stay unset so the gate resolves from e2e presence alone",
        )
        if isinstance(post_code_test, dict):
            self.assertIsNone(post_code_test.get("enabled"))

    def test_resolved_settings_expose_no_e2e_suite(self):
        # load_settings folds a configured `e2e` into `suites.e2e`, so this is the
        # view /acs:ship reads — with nothing to fold, neither key appears.
        self.assertIn(SETTINGS_PATH, self.found,
                      "the committed settings file must be one of the resolved scopes")
        self.assertNotIn("e2e", self.resolved)
        self.assertNotIn("e2e", self.resolved.get("suites") or {})

    def test_post_code_test_gate_resolves_off(self):
        self.assertEqual(post_code_test_gate(self.raw), "off")
        self.assertEqual(post_code_test_gate(self.resolved), "off")

    def test_gate_rule_still_turns_on_for_a_configured_consumer_repo(self):
        # The rule itself is unchanged — only this repo's configuration moved.
        configured = {"suites": {"e2e": {"command": "make e2e"}}}
        self.assertEqual(post_code_test_gate(configured), "on")
        self.assertEqual(post_code_test_gate({"e2e": {"command": "make e2e"}}), "on")
        self.assertEqual(
            post_code_test_gate({"post_code_test": {"enabled": False}, "e2e": {"command": "x"}}),
            "off",
        )


class DocsPolicyTest(unittest.TestCase):
    """[AC-3..AC-6] every document that stated the retired policy now names
    acs-evals as the gate."""

    def test_prd_g13_note_and_c17_point_at_acs_evals(self):
        body = read(PRD_PATH)
        g13 = line_containing(body, "G13 — Enforceable e2e integrity")
        self.assertIn("MAR-579", g13)
        self.assertIn("acs-evals", g13)
        self.assertRegex(g13, r"(?i)no e2e suite and no gate-enabled window")
        # The historical MAR-127 record and sub-metric (b) survive the reword.
        self.assertIn("First validated 2026-07-12 (MAR-127)", g13)
        self.assertIn("not yet wired", g13)
        self.assertIn("Sub-metric (b) reads **2/2 (100%)**", g13)

        self.assertNotIn("the paid tier remains the manual pre-release gate", body)
        self.assertNotIn("the paid tier remains a manual pre-release gate", body)
        for marker in ("Full behavioral eval coverage + per-release eval baseline",
                       "full eval coverage is additive over the shipped harness"):
            clause = line_containing(body, marker)
            self.assertIn("acs-evals", clause)
            self.assertIn("G32(iii)", clause)
        self.assertIn("behavioral/LLM evals stay local-only, never in CI (C-17)", body)
        self.assertIn("behavioral/LLM evals stay local-only", line_containing(
            body, "full eval coverage is additive over the shipped harness"))

    def test_roadmap_e1_marks_paid_scenarios_superseded(self):
        body = read(ROADMAP_PATH)
        e12 = list_item(body, "**E1.2 (done)**")
        e13 = list_item(body, "**E1.3 (done)**")
        e14 = list_item(body, "**E1.4 (done)**")
        for item in (e12, e13):
            self.assertRegex(item, r"(?i)supersed")
            self.assertIn("acs-evals", item)
        self.assertIn("22-skill routing coverage", e12)  # PR #526 owns this count
        self.assertIn("PIPE-", e13)
        self.assertIn("MAR-579", e14)
        self.assertRegex(e14, r"(?i)no longer .{0,40}per-ticket")
        self.assertIn("on-demand developer action", e14)

    def test_release_gate_docs_name_acs_evals(self):
        readme = read(EVALS_README_PATH)
        before_release = section(readme, "## Before a release")
        self.assertNotIn("The paid tier is the **release gate**", readme)
        self.assertIn("acs-evals", before_release)
        for command in ("make eval", "make measure", "make perf"):
            self.assertIn(command, before_release)
        self.assertRegex(before_release, r"(?i)on-demand")
        self.assertIn("s07", before_release)
        self.assertIn("s08", before_release)
        pre_commit = section(readme, "## Pre-commit and CI")
        self.assertRegex(pre_commit, r"(?i)not a gate")
        # C-4's grep invariant is not this ticket's to narrow.
        self.assertIn('grep -rn "run_evals\\|evals/" .github/workflows/', pre_commit)

        strategy = read(TESTING_STRATEGY_PATH)
        for layer in ("5", "6"):
            self.assertIn("acs-evals", table_row(strategy, layer))
        self.assertIn("acs-evals", paragraph(strategy, "Layers 1–4 are free"))
        principle = list_item(strategy, "**Cost-aware tiering.**")
        self.assertIn("acs-evals", principle)
        self.assertNotIn("`python3 evals/run_evals.py --paid` before tagging", principle)
        # The standing G13 validation-record section stays exactly where it was.
        self.assertIn("## G13 e2e-integrity validation", strategy)

        runbook = read(RUNBOOK_PATH)
        step_one = section(runbook, "## Steps").split("2. **Cut the release")[0]
        self.assertIn("acs-evals", step_one)
        for command in ("make eval", "make measure", "make perf"):
            self.assertIn(command, step_one)
        self.assertNotIn("**Run the pre-release quality gate** — the paid eval suite", runbook)
        self.assertRegex(step_one, r"(?i)on-demand")

    def test_ci_brake_is_stated_as_a_plan_not_current_fact(self):
        """No document claims this repo already runs acs-evals in CI."""
        planned = "imported into this repository"
        documents = (
            ("prd G13", line_containing(read(PRD_PATH), "G13 — Enforceable e2e integrity")),
            ("roadmap E1.4", list_item(read(ROADMAP_PATH), "**E1.4 (done)**")),
            ("ADR 0022 amendment", section(read(ADR_PATH), AMENDMENT_HEADING)),
        )
        for name, text in documents:
            self.assertIn(planned, text, "%s must state the CI brake as a plan" % name)
            self.assertNotIn("MAR-576", text, "%s names a retired ticket" % name)
        # Neither release doc may send a maintainer to a ref no workflow pins.
        for path in (RUNBOOK_PATH, EVALS_README_PATH):
            self.assertNotIn("the ref this repo's CI workflow pins", read(path))
        workflows = os.path.join(REPO_ROOT, ".github", "workflows")
        self.assertEqual(
            [name for name in sorted(os.listdir(workflows)) if "eval" in name], [],
            "an eval workflow landed — the planned-brake wording above is now stale",
        )

    def test_adr_0022_carries_the_amendment(self):
        body = read(ADR_PATH)
        self.assertIn(AMENDMENT_HEADING, body)
        headings = re.findall(r"(?m)^## .*$", body)
        self.assertEqual(
            headings,
            ["## Context", "## Options considered", "## Decision", "## Consequences",
             AMENDMENT_HEADING],
            "the amendment is append-only: it follows Consequences and adds no other section",
        )
        amendment = section(body, AMENDMENT_HEADING)
        self.assertIn("acs-evals", amendment)
        self.assertRegex(amendment, r"(?i)tier 1")
        self.assertIn("$7", amendment)
        self.assertRegex(amendment, r"(?i)local-only")
        self.assertRegex(amendment, r"(?i)opt-in")

    def test_adr_0022_sections_above_the_amendment_are_byte_identical(self):
        base = _base_ref()
        if base is None:
            self.skipTest("no base ref (origin/main or main) to diff the ADR prefix against")
        shown = subprocess.run(
            ["git", "show", "%s:%s" % (base, ADR_RELPATH)],
            cwd=REPO_ROOT, capture_output=True, text=True,
        )
        if shown.returncode != 0:
            self.skipTest("ADR 0022 is not readable at %s" % base)
        # rstrip only the blank line that now separates the amendment heading from
        # Consequences; every byte of the four original sections must match.
        baseline = shown.stdout.split(AMENDMENT_HEADING)[0].rstrip("\n")
        self.assertEqual(read(ADR_PATH).split(AMENDMENT_HEADING)[0].rstrip("\n"), baseline)


def _base_ref():
    """`origin/main` first, then a local `main`; a shallow CI checkout has neither."""
    for ref in ("origin/main", "main"):
        result = subprocess.run(
            ["git", "rev-parse", "--verify", ref],
            cwd=REPO_ROOT, capture_output=True, text=True,
        )
        if result.returncode == 0:
            return ref
    return None


if __name__ == "__main__":
    unittest.main()
