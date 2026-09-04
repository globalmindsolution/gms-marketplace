"""MAR-531 (#507): epic E1's "every module under `acs/` is below 800 lines".

The criterion was a sentence on the epic. A sentence is not a check, and three
modules were already over it — `metrics_render.py` (1682), `metrics_aggregate.py`
(1288) and `release_notes.py` (821) — named in no child of the epic, so on a
plugin-wide reading E1 would have closed with its own success criterion unmet.

SCOPE DECISION (recorded on #417): "under `acs/`" is read **plugin-wide**.
`plugins/acs/` is the plugin root, and those three modules live under it; a
reading that covered only the package MAR-522 created would make the criterion
true by construction and say nothing about the plugin's maintainability, which
is what it exists to protect.

This module is the criterion as a test, so it cannot rot back into prose.
"""

import os
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLUGIN = os.path.join(REPO_ROOT, "plugins", "acs")

#: E1's number, unchanged. It is a budget, not a target: a module at 799 lines
#: is not "fine", it is one edit from a split.
LINE_BUDGET = 800

#: What the budget covers: every Python module the plugin ships. Tests, evals
#: and the consumer-repo templates are outside `plugins/acs/`.
def plugin_modules():
    for root, dirs, names in os.walk(PLUGIN):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for name in sorted(names):
            if name.endswith(".py"):
                yield os.path.join(root, name)


def line_count(path):
    with open(path, encoding="utf-8") as fh:
        return sum(1 for _ in fh)


class ModuleLineBudgetTest(unittest.TestCase):

    def test_every_shipped_module_is_under_the_budget(self):
        over = [(os.path.relpath(path, REPO_ROOT), line_count(path))
                for path in plugin_modules() if line_count(path) >= LINE_BUDGET]
        self.assertEqual(over, [], "over E1's %d-line budget: %s" % (LINE_BUDGET, over))

    def test_the_three_modules_the_ticket_names_are_split(self):
        """Named explicitly so a future rewrite that recombines them fails here
        rather than quietly re-crossing the budget."""
        for name in ("metrics_render", "metrics_aggregate", "release_notes"):
            with self.subTest(module=name):
                siblings = [p for p in plugin_modules()
                            if os.path.basename(p).startswith(name + "_")]
                self.assertTrue(siblings, "%s was not split into sibling modules" % name)

    def test_the_split_is_invisible_to_callers(self):
        """Each entry point re-exports its whole pre-split surface, so the
        SKILL.md invocations and the golden tests reach the same names. Asserted
        by importing and looking, not by reading the import lines."""
        import sys
        sys.path.insert(0, os.path.join(PLUGIN, "hooks", "scripts"))
        import metrics_aggregate, metrics_render, release_notes  # noqa: E402
        for module, names in (
                (metrics_render, ("render_terminal", "render_html", "render_pm_terminal",
                                  "render_usage_html", "PANEL_TITLES", "_esc", "_fmt_money")),
                (metrics_aggregate, ("aggregate", "PANEL_KEYS", "_safe_avg",
                                     "_usage_by_model_panel", "_panel7")),
                (release_notes, ("compute_status", "build_draft", "bump", "CATEGORIES",
                                 "validate_release_config", "pointer_set",
                                 "enumerate_merged_tickets", "gh_pr_list"))):
            for name in names:
                with self.subTest(module=module.__name__, name=name):
                    self.assertTrue(hasattr(module, name))

    def test_the_entry_points_stay_runnable_as_files(self):
        """The split kept sibling modules rather than making packages precisely
        so `python3 .../metrics_render.py` keeps working — three SKILL.md files
        invoke these by path."""
        for name in ("metrics_render.py", "metrics_aggregate.py", "release_notes.py"):
            path = os.path.join(PLUGIN, "hooks", "scripts", name)
            with self.subTest(module=name):
                self.assertTrue(os.path.isfile(path))
                with open(path, encoding="utf-8") as fh:
                    self.assertIn('if __name__ == "__main__":', fh.read())


if __name__ == "__main__":
    unittest.main()
