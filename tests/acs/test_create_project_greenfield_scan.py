"""create-project's greenfield scan agrees with /acs:project's mode.

`/acs:setup` writes `.github/workflows/acs-*.yml` onto a repo with no source,
and `acs_lib.project_mode` deliberately ignores CI workflows -- so it routed
that repo to create-project (bootstrap), whose own `git ls-files` scan counted
the workflows as substantive sources and refused it.
"""

import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from acs_case import lib  # noqa: E402

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SKILL = os.path.join(REPO_ROOT, "plugins", "acs", "skills", "create-project", "SKILL.md")

#: What /acs:setup and a fresh product repo hold before any scaffold.
SETUP_OUTPUT = [".acs/settings.json", ".github/workflows/acs-conventions.yml",
                ".github/workflows/acs-tests.yml", ".gitignore", "README.md",
                "docs/architecture/hld/tech-stack.md", "CLAUDE.md"]


def scan_pattern():
    with open(SKILL, encoding="utf-8") as fh:
        text = fh.read()
    match = re.search(r"ls-files \| grep -vE '([^']+)'", text)
    assert match, "the greenfield scan is no longer a `ls-files | grep -vE` line"
    return re.compile(match.group(1))


class GreenfieldScanTest(unittest.TestCase):

    def substantive(self, paths):
        pattern = scan_pattern()
        return [p for p in paths if not pattern.search(p)]

    def test_setup_output_alone_is_greenfield(self):
        self.assertEqual(self.substantive(SETUP_OUTPUT), [])

    def test_the_same_repo_is_bootstrap_for_project(self):
        import tempfile
        root = tempfile.mkdtemp()
        for rel in SETUP_OUTPUT:
            path = os.path.join(root, rel)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            open(path, "w").close()
        self.assertEqual(lib.project_mode({}, root)["mode"], "bootstrap")

    def test_a_source_tree_is_still_substantive(self):
        self.assertEqual(self.substantive(["src/app.py", "package.json"]),
                         ["src/app.py", "package.json"])


if __name__ == "__main__":
    unittest.main()
