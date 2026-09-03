"""The Codex adapter is gone and must stay gone.

MAR-518. `codex_adapter.py` (MAR-4) was built as the runtime seam's glue, but
its consumer never arrived: the MAR-5 wiring PR was rejected because Codex CLI
has no `Skill` hook matcher and no `SessionEnd` event. It sat as an argparse
stub with no caller for six releases.

Deleting a file is not self-enforcing -- nothing in the suite failed when it
existed unused, and nothing would fail if it came back. This module is that
guard, following the repo's own precedent for deletions
(test_release_skill_registry.py's test_no_release_agent_files_on_disk,
test_diagram_lint_verifiers.py's test_old_mmdc_grep_clause_removed).

Run:  python3 -m unittest tests.acs.test_codex_adapter_removed -v
"""

import os
import re
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLUGIN = os.path.join(REPO_ROOT, "plugins", "acs")
SCRIPTS = os.path.join(PLUGIN, "hooks", "scripts")

#: Where a reference is a record of the deletion rather than a live pointer.
HISTORY = (
    os.path.join(PLUGIN, "CHANGELOG.md"),
    os.path.join(REPO_ROOT, "docs", "adr"),
    os.path.join(REPO_ROOT, "docs", "architecture", "lld",
                 "runtime-coupling-inventory.md"),
    os.path.join(REPO_ROOT, "docs", "architecture", "lld",
                 "runtime-coupling-inventory.evidence.md"),
    os.path.join(REPO_ROOT, "docs", "product"),
    os.path.join(REPO_ROOT, "tests", "acs", "test_codex_adapter_removed.py"),
)

SEARCHED = (
    os.path.join(PLUGIN, "hooks"),
    os.path.join(PLUGIN, "skills"),
    os.path.join(PLUGIN, "agents"),
    os.path.join(PLUGIN, "schemas"),
    os.path.join(PLUGIN, "docs"),
    os.path.join(REPO_ROOT, "docs"),
    os.path.join(REPO_ROOT, "tests"),
    os.path.join(REPO_ROOT, ".acs", "ci"),
)


def _is_history(path):
    return any(os.path.abspath(path).startswith(os.path.abspath(h)) for h in HISTORY)


def _files():
    for root_dir in SEARCHED:
        for root, _dirs, names in os.walk(root_dir):
            for name in names:
                if name.endswith((".py", ".md", ".json", ".xsd", ".cfg", ".yml", ".yaml")):
                    yield os.path.join(root, name)


class CodexAdapterRemovedTest(unittest.TestCase):
    def test_the_module_is_not_on_disk(self):
        self.assertFalse(os.path.isfile(os.path.join(SCRIPTS, "codex_adapter.py")),
                         "codex_adapter.py was deleted in MAR-518 and has no consumer")

    def test_its_test_module_is_not_on_disk(self):
        self.assertFalse(
            os.path.isfile(os.path.join(REPO_ROOT, "tests", "acs", "test_codex_adapter.py")))

    def test_nothing_live_still_points_at_it(self):
        """A surviving reference in prose or config is a pointer to a missing
        file. Historical records (CHANGELOG, ADRs, the inventory's own
        supersession note) are exempt -- they describe the deletion."""
        offenders = []
        for path in _files():
            if _is_history(path):
                continue
            with open(path, encoding="utf-8", errors="replace") as fh:
                for lineno, line in enumerate(fh, 1):
                    if "codex_adapter" in line:
                        offenders.append("%s:%d" % (os.path.relpath(path, REPO_ROOT), lineno))
        self.assertEqual(offenders, [], "live references to the deleted codex_adapter")

    def test_it_is_not_in_the_coveragerc_omit_list(self):
        with open(os.path.join(REPO_ROOT, ".coveragerc"), encoding="utf-8") as fh:
            self.assertNotIn("codex_adapter", fh.read())


class HelperCliInventoryTest(unittest.TestCase):
    """INTERNALS' helper-CLI row is a hand-maintained list AND a hand-typed
    count, and this ticket's edit held the count at 17 across a deletion. Both
    halves are derived here from the row's own stated rule."""

    #: The row excludes these explicitly: the dispatcher, the 15 pre/15 post
    #: forwarders (counted in the Hooks row), and the 2 status lines.
    EXCLUDED = {"dispatch.py", "statusline.py", "subagent-statusline.py"}

    def _actual(self):
        names = []
        for name in sorted(os.listdir(SCRIPTS)):
            if not name.endswith(".py") or name in self.EXCLUDED:
                continue
            if name.startswith(("pre-", "post-")):
                continue
            with open(os.path.join(SCRIPTS, name), encoding="utf-8") as fh:
                if "__main__" in fh.read():
                    names.append(name[:-3])
        return names

    def _row(self):
        with open(os.path.join(PLUGIN, "docs", "INTERNALS.md"), encoding="utf-8") as fh:
            for line in fh:
                if line.startswith("| Helper CLIs |"):
                    return line
        self.fail("INTERNALS.md has no Helper CLIs row")

    def test_the_listed_names_are_the_files_on_disk(self):
        listed = re.search(r"\{([^}]+)\}", self._row()).group(1).split(",")
        self.assertEqual(sorted(n.strip() for n in listed), sorted(self._actual()))

    def test_the_count_matches_the_list(self):
        count = int(self._row().rstrip().rstrip("|").rsplit("|", 1)[1].strip())
        self.assertEqual(count, len(self._actual()))


if __name__ == "__main__":
    unittest.main()
