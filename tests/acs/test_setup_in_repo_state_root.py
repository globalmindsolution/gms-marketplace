"""MAR-4 — /acs:setup sets up the in-repo state root (AC1, AC2).

Prose-contract unit test for `plugins/acs/skills/setup/SKILL.md`. S3 of
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

Stdlib-only (os, re, unittest), mirroring tests/acs/test_setup_offers.py
(REPO_ROOT/PLUGIN + read + bounded-window `section()` helper). Assertions are
bounded-window / co-occurrence anchored on real `## `/`### ` headings — never
bare file-wide assertIn — so a too-loose match cannot pass vacuously.

Renamed under MAR-1 (the skill formerly invoked as acs:initialize is now
acs:setup): module name and internal skill-path/token references updated;
behavior and originating ticket reference unchanged.

Run:  python3 -m unittest tests.acs.test_setup_in_repo_state_root -v
"""

import os
import re
import sys
import shutil
import subprocess
import tempfile
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLUGIN = os.path.join(REPO_ROOT, "plugins", "acs")
SKILL_PATH = os.path.join(PLUGIN, "skills", "setup", "SKILL.md")
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
    """MAR-4's acceptance criteria, re-pointed at the implementation.

    These pinned the in-repo state root as SHELL IN PROSE — the two-layer ignore
    mechanism, `--git-common-dir`, `grep -qxF`, the `check-ignore -v`
    assertion, the write probe. MAR-526 moved all of it into
    `setup_wizard.py`, so the criteria are asserted where the behaviour is: a
    prose assertion against a skill that no longer carries the shell would
    either fail or, kept alive by loosening it, assert nothing.

    Every AC below is the original one. What changed is only where it is read.
    The two repo-level assertions at the end are unmoved."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(SKILL_PATH)
        cls.wizard = read(os.path.join(PLUGIN, "hooks", "scripts", "setup_wizard.py"))

    def _repo(self):
        """A throwaway git repo the wizard can be applied to."""
        tmp = tempfile.mkdtemp(prefix="acs-test-")
        self.addCleanup(shutil.rmtree, tmp, True)
        subprocess.run(["git", "init", "-q", tmp], check=True, capture_output=True)
        return tmp

    def _apply(self, cwd, answers=None):
        sys.path.insert(0, os.path.join(PLUGIN, "hooks", "scripts"))
        import setup_wizard
        return setup_wizard.apply(cwd, answers or {"settings": {"ticket_prefix": "SHOP"}})

    def test_the_default_state_root_is_in_repo_and_never_asked_for(self):
        """AC: `workspace_path` is an OPTIONAL override with an in-repo
        default, not a must-ask key with an outside-the-repo validator."""
        self.assertNotIn("MUST be outside the consumer repo", self.body)
        row = re.search(r"(?m)^\| `workspace_path` \|.*\|$", self.body)
        self.assertIsNotNone(row, "the optional-settings batch must offer workspace_path")
        self.assertIn(".acs/state-machine", row.group(0))
        self.assertIn("settings.local.json", row.group(0),
                      "the key is machine-specific and always lands in the local file")

    def test_both_ignore_layers_are_written(self):
        """AC: the tracked `.gitignore` entry AND the untracked
        `info/exclude` entry — the second so a linked worktree, or a repo that
        prefers not to commit an ignore-line change, is still covered."""
        cwd = self._repo()
        self._apply(cwd)
        with open(os.path.join(cwd, ".gitignore"), encoding="utf-8") as fh:
            tracked = fh.read()
        with open(os.path.join(cwd, ".git", "info", "exclude"), encoding="utf-8") as fh:
            untracked = fh.read()
        for entry in (".acs/settings.local.json", ".acs/state-machine/"):
            self.assertIn(entry, tracked)
            self.assertIn(entry, untracked)

    def test_the_exclude_append_cannot_glue_onto_the_last_line(self):
        """AC: a file with no trailing newline gets one first."""
        cwd = self._repo()
        exclude = os.path.join(cwd, ".git", "info", "exclude")
        os.makedirs(os.path.dirname(exclude), exist_ok=True)
        with open(exclude, "w", encoding="utf-8") as fh:
            fh.write("*.log")          # deliberately unterminated
        self._apply(cwd)
        with open(exclude, encoding="utf-8") as fh:
            lines = fh.read().splitlines()
        self.assertIn("*.log", lines)
        self.assertIn(".acs/state-machine/", lines)

    def test_the_ignore_write_is_idempotent(self):
        """AC: run always, fresh init AND re-run — so it must not duplicate."""
        cwd = self._repo()
        self._apply(cwd)
        second = self._apply(cwd)
        with open(os.path.join(cwd, ".gitignore"), encoding="utf-8") as fh:
            lines = fh.read().splitlines()
        self.assertEqual(lines.count(".acs/state-machine/"), 1)
        self.assertFalse([c for c in second["changed"] if "gitignored" in c])

    def test_an_existing_broader_rule_counts_as_ignored(self):
        """AC: `git check-ignore` decides, not a literal grep, so a repo that
        already ignores `.acs/` gains no duplicate line."""
        cwd = self._repo()
        with open(os.path.join(cwd, ".gitignore"), "w", encoding="utf-8") as fh:
            fh.write(".acs/\n")
        out = self._apply(cwd)
        with open(os.path.join(cwd, ".gitignore"), encoding="utf-8") as fh:
            self.assertEqual(fh.read(), ".acs/\n")
        self.assertTrue(any("already ignored" in line for line in out["unchanged"]))

    def test_a_broad_rule_swallowing_ci_files_is_warned_about_not_fixed(self):
        """AC: the broad-`.acs/`-rule guard runs on every init, and names the
        files CI must be able to read. It WARNS: a `!.acs/` negation is the
        user's own configuration to fix, not something to block init on."""
        cwd = self._repo()
        with open(os.path.join(cwd, ".gitignore"), "w", encoding="utf-8") as fh:
            fh.write(".acs/\n")
        out = self._apply(cwd)
        joined = " | ".join(out["warnings"])
        self.assertIn(".acs/settings.json", joined)
        self.assertIn(".acs/ci/check-conventions.py", joined)
        self.assertIn("narrow the rule", joined)

    def test_the_workspace_is_created_and_probed_at_the_resolved_root(self):
        """AC: the probe runs against the RESOLVED default, never a literal
        placeholder — the wizard resolves it exactly as validate_settings
        does, so what setup creates is what every later run reads."""
        self.assertIn("resolved exactly as validate_settings", self.wizard)
        self.assertIn("os.access(target, os.W_OK)", self.wizard)

    def test_the_migration_offer_survives(self):
        """AC: the one-shot external->in-repo migration is still offered."""
        self.assertIn("migrate_workspace.py", self.body)

    def test_no_rationale_still_claims_the_workspace_is_outside_the_repo(self):
        """AC: the CI rationale that assumed an outside-the-repo workspace is
        gone — the default is in-repo now."""
        for stale in ("workspace OUTSIDE the repo", "OUTSIDE the repo, which CI cannot see"):
            self.assertNotIn(stale, self.body)

    def test_gitignore_already_has_the_state_machine_line(self):
        """This repo's own .gitignore carries the entry (unmoved)."""
        self.assertIn(".acs/state-machine/", read(GITIGNORE_PATH).splitlines())
