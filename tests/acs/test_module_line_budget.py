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
import sys
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

    #: What each entry point was actually split into. Named, because
    #: `assertTrue(siblings)` -- "at least one sibling exists" -- is satisfied by
    #: a recombination that leaves a single stub behind, which is exactly the
    #: rewrite the docstring claims to catch.
    EXPECTED_SIBLINGS = {
        "metrics_render": ("common", "terminal", "html", "panels", "tables"),
        "metrics_aggregate": ("common", "panels", "usage", "rows"),
        "release_notes": ("config", "git", "tickets"),
    }

    def test_the_three_modules_the_ticket_names_are_split(self):
        """Named explicitly so a future rewrite that recombines them fails here
        rather than quietly re-crossing the budget."""
        for name, parts in self.EXPECTED_SIBLINGS.items():
            with self.subTest(module=name):
                found = {os.path.basename(p)[len(name) + 1:-3] for p in plugin_modules()
                         if os.path.basename(p).startswith(name + "_")}
                self.assertEqual(found, set(parts),
                                 "%s's siblings changed: %s" % (name, sorted(found)))

    def test_the_split_is_invisible_to_callers(self):
        """Each entry point re-exports its whole pre-split surface, so the
        SKILL.md invocations and the golden tests reach the same names.

        Derived from the SIBLINGS, not from a hand-picked list: the facades
        export 94, 45 and 63 names, and checking twenty of them by `hasattr`
        pinned a tenth of the surface by presence only -- dropping any of the
        other ~180 re-exports passed. `assertIs` also makes it identity, not
        just existence, so a name rebound to a different object fails."""
        import sys
        sys.path.insert(0, os.path.join(PLUGIN, "hooks", "scripts"))
        import importlib
        for entry, parts in self.EXPECTED_SIBLINGS.items():
            facade = importlib.import_module(entry)
            for part in parts:
                sibling = importlib.import_module("%s_%s" % (entry, part))
                exported = [n for n in vars(sibling)
                            if not n.startswith("__") and n not in ("annotations",)]
                for name in exported:
                    value = getattr(sibling, name)
                    # Only names the sibling DEFINES (or deliberately re-exports
                    # as data) need to reach the facade; stdlib modules it
                    # imported for its own use do not.
                    if getattr(value, "__module__", None) not in (sibling.__name__, None):
                        continue
                    with self.subTest(entry=entry, part=part, name=name):
                        self.assertTrue(hasattr(facade, name),
                                        "%s dropped %s from its re-exports" % (entry, name))
                        self.assertIs(getattr(facade, name), value,
                                      "%s.%s is not the sibling's object" % (entry, name))

    def test_the_entry_points_stay_runnable_as_files(self):
        """The split kept sibling modules rather than making packages precisely
        so `python3 .../metrics_render.py` keeps working — three SKILL.md files
        invoke these by path."""
        import importlib.util
        scripts = os.path.join(PLUGIN, "hooks", "scripts")
        for name in ("metrics_render.py", "metrics_aggregate.py", "release_notes.py"):
            path = os.path.join(scripts, name)
            with self.subTest(module=name):
                self.assertTrue(os.path.isfile(path))
                with open(path, encoding="utf-8") as fh:
                    self.assertIn('if __name__ == "__main__":', fh.read())

                # LOAD it, with the scripts dir absent from sys.path. A
                # substring match cannot fail on a broken import, and neither
                # can `python3 <abspath>` -- Python prepends the script's own
                # directory, so the CLI works even when the module's sys.path
                # idiom is dead. Only an explicit load exposes that, which is
                # how the inverted insert (`import acs_lib` before the
                # sys.path.insert it needs) shipped green.
                saved = list(sys.path)
                sys.path[:] = [p for p in sys.path
                               if os.path.abspath(p) != os.path.abspath(scripts)]
                for mod in [m for m in list(sys.modules)
                            if m.startswith(("metrics_", "release_notes", "acs_lib"))]:
                    sys.modules.pop(mod, None)
                try:
                    spec = importlib.util.spec_from_file_location(
                        "budget_probe_" + name[:-3], path)
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                except Exception as exc:  # noqa: BLE001 - the assertion IS the report
                    self.fail("%s cannot be loaded by absolute path: %r" % (name, exc))
                finally:
                    sys.path[:] = saved


if __name__ == "__main__":
    unittest.main()
