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

ADR-0104 deleted `metrics_render` and `metrics_aggregate` with the dashboards
they drew, so `release_notes` is the one split entry point left to guard.
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
        "release_notes": ("config", "git", "tickets"),
    }

    def test_the_split_modules_stay_split(self):
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
        so `python3 .../release_notes.py` keeps working — SKILL.md files invoke
        it by path."""
        import importlib.util
        scripts = os.path.join(PLUGIN, "hooks", "scripts")
        for name in ("release_notes.py",):
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
                            if m.startswith(("release_notes", "acs_lib"))]:
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


class WorkflowSplitTest(unittest.TestCase):
    """`acs_lib.workflow` crossed the budget when ADR-0095's delivery paths
    landed on top of it, and was split the way the three flat modules above
    were: into neighbours that own a layer, with the entry point re-exporting
    their whole surface so no caller had to move.

    The split is by LAYER, not by line count. `schemasubset` answers "does
    this document satisfy this schema" without loading, resolving or
    validating a pipeline document, which is what let `workflow` shed it in
    the first place. Anything that needs a workflow stays in `workflow`.

    `phases` was the second neighbour, answering "which skills exist and where
    do the plugin's files live" for `workflows/phases.yaml`. v0.5.0 retired
    that document -- a skill is a DIRECTORY, and a registry file naming the
    same skills was a second place for the set to drift -- so the neighbour
    went with it and `acs_lib.skills` answers the surviving half from the
    directories themselves."""

    #: What `workflow` was split into, and what each neighbour owns.
    NEIGHBOURS = ("schemasubset",)

    def _modules(self):
        import importlib
        sys.path.insert(0, os.path.join(PLUGIN, "hooks", "scripts"))
        return (importlib.import_module("acs_lib.workflow"),
                [importlib.import_module("acs_lib." + n) for n in self.NEIGHBOURS])

    def test_workflow_re_exports_each_neighbours_surface_by_identity(self):
        """`hasattr` alone would pass on a name rebound to something else, so
        this is identity: the facade must hand back the neighbour's object."""
        workflow, neighbours = self._modules()
        for neighbour in neighbours:
            for name, value in sorted(vars(neighbour).items()):
                if name.startswith("_"):
                    continue
                # Only what the neighbour DEFINES; modules it imported for its
                # own use are not part of the surface it owes the facade. A
                # MODULE object has no `__module__` at all, so the None arm
                # below would have adopted `re` and `json` as surface.
                import types
                if isinstance(value, types.ModuleType):
                    continue
                if getattr(value, "__module__", None) not in (neighbour.__name__, None):
                    continue
                with self.subTest(neighbour=neighbour.__name__, name=name):
                    self.assertTrue(
                        hasattr(workflow, name),
                        "acs_lib.workflow dropped %s from its re-exports" % name)
                    self.assertIs(getattr(workflow, name), value,
                                  "acs_lib.workflow.%s is not %s's object"
                                  % (name, neighbour.__name__))

    def test_the_neighbours_do_not_import_workflow_back(self):
        """A layer that reaches back up is not a layer. This is also what keeps
        the imports acyclic — `workflow` imports both, so either importing it
        would be a cycle Python resolves by luck of ordering."""
        for name in self.NEIGHBOURS:
            path = os.path.join(PLUGIN, "hooks", "scripts", "acs_lib", "%s.py" % name)
            with self.subTest(module=name), open(path, encoding="utf-8") as fh:
                body = fh.read()
            self.assertNotIn("from .workflow import", body)
            self.assertNotIn("from . import workflow", body)

    def test_one_error_class_spans_the_split(self):
        """A caller catching a bad schema and a caller catching a bad pipeline
        catch the same class — the split must not have forked it."""
        workflow, (schemasubset,) = self._modules()
        self.assertIs(workflow.WorkflowError, schemasubset.WorkflowError)

    def test_the_retired_neighbour_is_gone_rather_than_stubbed(self):
        """`workflows/phases.yaml` and its module are retired together. A stub
        left behind would be a second answer to "which skills exist" that
        nothing keeps in step with the directories."""
        self.assertFalse(
            os.path.isfile(os.path.join(PLUGIN, "hooks", "scripts", "acs_lib",
                                        "phases.py")))
        self.assertFalse(
            os.path.isfile(os.path.join(PLUGIN, "workflows", "phases.yaml")))


if __name__ == "__main__":
    unittest.main()
