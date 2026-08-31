"""MAR-4 — /acs:initialize sets up the in-repo state root (AC1, AC2).

Prose-contract unit test for `plugins/acs/skills/initialize/SKILL.md`. S3 of
the MAR-1 epic split (ADR 0069): the state root moves from a machine-local,
outside-the-repo `workspace_path` (always asked, validated to reject any path
inside a worktree) to an in-repo default `<main-checkout>/.acs/state-machine`,
derived via `acs_lib.default_state_root()` (already shipped by MAR-2), with
`workspace_path` becoming an optional, write-only-when-changed override.

This module pins:
  1. Step 3 drops the `workspace_path` must-ask/outside-repo-validator
     subsection, keeping only `ticket_prefix`.
  2. Step 4 gains a `workspace_path` optional-default bullet.
  3. Step 5 gains the two-layer `.acs/state-machine/` ignore mechanism
     (tracked `.gitignore` append + idempotent `info/exclude` append +
     `git check-ignore -v` assertion/warning).
  4. Step 5 also runs the broad-`.acs/`-rule guard unconditionally (promoted
     out of the old CI-enforcement-only Step 7c gate).
  5. Step 6 probes the *resolved* workspace value, not a literal placeholder
     that assumes Step 3 always collected one.
  6. A new sub-step after Step 6 offers the MAR-3 migrator for an existing
     external workspace.
  7. This repo's own `.gitignore` already carries the tracked
     `.acs/state-machine/` line (AC2 — regression pin, already satisfied by
     MAR-2's own merge).

Stdlib-only (os, re, unittest), mirroring tests/acs/test_initialize_offers.py
(REPO_ROOT/PLUGIN + read + bounded-window `section()` helper). Assertions are
bounded-window / co-occurrence anchored on real `## `/`### ` headings — never
bare file-wide assertIn — so a too-loose match cannot pass vacuously.

Run:  python3 -m unittest tests.acs.test_initialize_in_repo_state_root -v
"""

import os
import re
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLUGIN = os.path.join(REPO_ROOT, "plugins", "acs")
SKILL_PATH = os.path.join(PLUGIN, "skills", "initialize", "SKILL.md")
GITIGNORE_PATH = os.path.join(REPO_ROOT, ".gitignore")


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def section(body, heading):
    """Return the text of a markdown section: from the line whose start is
    `heading` (a real heading, matched at line-start) up to the next
    same-or-higher-level heading (or end of file)."""
    m = re.search(r"(?m)^" + re.escape(heading) + r"\b.*$", body)
    if m is None:
        raise AssertionError("heading %r not found in SKILL.md" % heading)
    start = m.start()
    level = len(heading) - len(heading.lstrip("#"))
    nxt = re.search(r"(?m)^#{1,%d} \S" % level, body[m.end():])
    end = m.end() + nxt.start() if nxt else len(body)
    return body[start:end]


class Mar4InitStateRootCase(unittest.TestCase):
    """Fixture: read the initialize SKILL.md once."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(SKILL_PATH)
        cls.step3 = section(cls.body, "## Step 3")
        cls.step4 = section(cls.body, "## Step 4")
        cls.step5 = section(cls.body, "## Step 5")
        cls.step6 = section(cls.body, "## Step 6")
        cls.step7c = section(cls.body, "## Step 7c")

    # --- 1: Step 3 drops the must-ask/outside-repo validator ---

    def test_step3_drops_the_must_ask_outside_repo_validator(self):
        self.assertNotIn(
            "### workspace_path", self.step3,
            msg="Step 3 must no longer have a `### workspace_path` subsection "
                "(AC1) — it moves to Step 4 as an optional override",
        )
        self.assertNotIn(
            "git worktree list --porcelain", self.step3,
            msg="Step 3 must drop the outside-the-repo REJECT-loop snippet (AC1)",
        )
        self.assertNotIn(
            "MUST be outside the consumer repo", self.step3,
            msg="Step 3 must no longer claim workspace_path MUST be outside "
                "the consumer repo (AC1)",
        )
        self.assertIn(
            "### ticket_prefix", self.step3,
            msg="Step 3 must retain the `### ticket_prefix` subsection unaffected",
        )

    # --- 2: Step 4 offers workspace_path as an optional default ---

    def test_step4_offers_workspace_path_as_optional_default(self):
        m = re.search(r"(?m)^- `workspace_path`.*(?:\n(?!- `|### ).*)*", self.step4)
        self.assertIsNotNone(
            m, "Step 4 must gain a `- `workspace_path`` bullet (AC1)"
        )
        bullet = m.group(0)
        self.assertIn(".acs/state-machine", bullet)
        self.assertIn(
            "only when the user", bullet,
            msg="the workspace_path bullet must follow the write-only-when-"
                "changed pattern used by adr_path/quality_path/etc (AC1)",
        )
        self.assertIn(
            "GateError", bullet,
            msg="the workspace_path bullet must surface the D3 bare/submodule "
                "GateError escape hatch (AC1)",
        )

    # --- 3: Step 5 writes the two-layer ignore mechanism ---

    def test_step5_writes_the_two_layer_ignore_mechanism(self):
        self.assertIn(".acs/state-machine/", self.step5)
        self.assertIn(
            "--git-common-dir", self.step5,
            msg="Step 5 must derive the shared git dir via "
                "`git rev-parse --git-common-dir` (AC1)",
        )
        self.assertIn(
            "info/exclude", self.step5,
            msg="Step 5 must append to <git-common-dir>/info/exclude (AC1)",
        )
        self.assertIn(
            "grep -qxF", self.step5,
            msg="the info/exclude append must be idempotent (grep -qxF guard) (AC1)",
        )
        self.assertIn(
            "check-ignore -v", self.step5,
            msg="Step 5 must assert with `git check-ignore -v` (not just -q) (AC1)",
        )
        window = re.search(r"(?s)check-ignore -v.{0,200}", self.step5)
        self.assertIsNotNone(window)
        self.assertIn(
            "WARNING", window.group(0),
            msg="a failed check-ignore -v assertion must WARN, not hard-fail (AC1)",
        )

    # --- 4: Step 5 promotes the broad-.acs/-rule guard ---

    def test_step5_promotes_the_broad_acs_rule_guard(self):
        self.assertIn(
            ".acs/settings.json", self.step5,
            msg="the broad-.acs/-rule guard must now run inside Step 5, "
                "unconditionally (AC1)",
        )
        self.assertIn(".acs/ci/check-conventions.py", self.step5)
        self.assertIn("git check-ignore -q", self.step5)
        # Step 7c's own precondition no longer re-runs the guard as a
        # first-time check — it may still reference the two files, but not
        # a duplicate `for p in .acs/settings.json .acs/ci/check-conventions.py`
        # bash loop.
        self.assertNotIn(
            "for p in .acs/settings.json .acs/ci/check-conventions.py", self.step7c,
            msg="Step 7c must not re-run the broad-.acs/-rule guard as a "
                "duplicate first-time check now that Step 5 always runs it (AC1)",
        )
        flat_step7c = re.sub(r"\s+", " ", self.step7c.lower())
        self.assertIn(
            "already checked", flat_step7c,
            msg="Step 7c's precondition should reference the Step-5 guard "
                "instead of re-running it (AC1)",
        )

    # --- 5: Step 6 probes the resolved default, not a literal placeholder ---

    def test_step6_probes_the_resolved_default_not_a_literal_placeholder(self):
        self.assertNotIn(
            'mkdir -p "<workspace_path>"', self.step6,
            msg="Step 6 must not probe a literal `<workspace_path>` placeholder "
                "that assumes Step 3 always collected one (AC1)",
        )
        self.assertIn(
            "default_state_root", self.step6,
            msg="Step 6 must resolve via default_state_root() when no override "
                "is set (AC1)",
        )
        self.assertIn("mkdir -p", self.step6)
        self.assertIn(".acs-write-probe", self.step6)

    # --- 6: a new sub-step offers the MAR-3 migrator ---

    def test_new_substep_offers_the_mar3_migrator(self):
        idx6 = self.body.index(self.step6)
        after_step6 = self.body[idx6 + len(self.step6):]
        m = re.search(r"(?s)migrate_workspace\.py.{0,400}", after_step6)
        self.assertIsNotNone(
            m, "a sub-step after Step 6 must name migrate_workspace.py (AC1)"
        )
        window = m.group(0)
        for flag in ("--from", "--to", "--repo-root"):
            self.assertIn(
                flag, window,
                msg=f"the migration offer must name the {flag!r} flag (AC1)",
            )
        self.assertIn(
            "decline", after_step6.lower(),
            msg="the migration sub-step must frame this as an offer with a "
                "decline path, not an automatic run (AC1)",
        )
        # Must appear before Step 7 (Final validation).
        step7_idx = self.body.index("## Step 7 —")
        self.assertLess(
            self.body.index("migrate_workspace.py"), step7_idx,
            msg="the migration sub-step must land after Step 6 and before "
                "Step 7 (AC1)",
        )

    # --- 7: AC2 regression pin ---

    def test_gitignore_already_has_the_state_machine_line(self):
        gitignore = read(GITIGNORE_PATH)
        self.assertRegex(
            gitignore, r"(?m)^\.acs/state-machine/\s*$",
            msg="this repo's own .gitignore must carry a tracked "
                "`.acs/state-machine/` directory-form line (AC2)",
        )


if __name__ == "__main__":
    unittest.main()
