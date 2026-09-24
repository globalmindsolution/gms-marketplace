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

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import acs_lib as lib  # noqa: E402

PRD_PATH = os.path.join(REPO_ROOT, "docs", "product", "prd.md")
ROADMAP_PATH = os.path.join(REPO_ROOT, "docs", "product", "roadmap.md")
EVALS_README_PATH = os.path.join(REPO_ROOT, "evals", "behavioural", "README.md")
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


def flat(text):
    """Collapse runs of whitespace, so a pinned phrase can straddle a hard wrap.

    These are hand-wrapped prose documents: a literal pinned across a line
    break breaks the moment someone reflows the paragraph, which says nothing
    about whether the fact is still true.
    """
    return " ".join(text.split())


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
