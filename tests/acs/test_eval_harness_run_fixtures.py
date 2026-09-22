"""MAR-587 -- the golden harness's run-keyed fixture base, and the golden
runner's refusal of a bare-string containment clause.

v0.5.0 keys the workspace by RUN rather than by ticket (`runs/<run-id>/...`,
ADR-0097), so a dataset case that seeds under the ticket partition seeds where
nothing reads and its guard fails open. These tests pin the `run` fixture base
the LOCK/FILEMAP/GUARD relocations need, the `{{run}}` / `{{run_dir}}` tokens
that address it, and -- the second defect in the same pair of files -- the
runner's refusal of a bare string where a list of needles belongs: `for needle
in "is not one of"` iterates CHARACTERS, so the clause passes as soon as the
stream shares a letter with it and the case is green while asserting nothing.

The dataset's own tier runs these checks only under `make verify-self` and
`make eval-source`, neither of which CI runs; this module is how they reach
`python3 -m unittest discover -s tests`.

Every fixture is a local temp dir: no model, no network, no cost.

Run:  python3 -m unittest tests.acs.test_eval_harness_run_fixtures -v
"""

import json
import os
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RUNNER = os.path.join(REPO_ROOT, "src", "acs-evals", "runner")
PLUGIN_ROOT = os.path.join(REPO_ROOT, "src", "acs")


def _load_runner():
    """Import runner/harness.py and runner/run_golden.py without leaving either
    on `sys.modules`, because `src/acs-evals/behavioural/acs/harness.py` claims
    the name `harness` too and whichever module imports second would silently
    get the other one's."""
    names = ("harness", "run_golden", "jsonschema_mini")
    saved_path = list(sys.path)
    saved_mods = {name: sys.modules.get(name) for name in names}
    sys.path.insert(0, RUNNER)
    for name in names:
        sys.modules.pop(name, None)
    try:
        import harness
        import run_golden
        return harness, run_golden
    finally:
        sys.path[:] = saved_path
        for name, module in saved_mods.items():
            if module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module


harness, run_golden = _load_runner()


def setUpModule():
    """Pin the build under test to this checkout's src/acs, the way
    `make eval-source` does."""
    global _SAVED_PLUGIN_ROOT
    _SAVED_PLUGIN_ROOT = os.environ.get("ACS_PLUGIN_ROOT")
    os.environ["ACS_PLUGIN_ROOT"] = PLUGIN_ROOT


def tearDownModule():
    if _SAVED_PLUGIN_ROOT is None:
        os.environ.pop("ACS_PLUGIN_ROOT", None)
    else:
        os.environ["ACS_PLUGIN_ROOT"] = _SAVED_PLUGIN_ROOT


class RunKeyedProfilesTest(unittest.TestCase):
    """The `run` and `run-epic` profiles: a ticket, and a run over it."""

    @classmethod
    def setUpClass(cls):
        cls.build = harness.resolve_build()
        cls.sb = harness.Sandbox(cls.build, profile="run")
        cls.addClassCleanup(cls.sb.close)

    def test_the_run_profile_opens_a_run_over_its_ticket(self):
        self.assertEqual(self.sb.run_id, self.sb.ticket_id)

    def test_the_run_directory_is_the_partition_s_run_for_that_id(self):
        self.assertEqual(self.sb.run_dir(),
                         os.path.join(self.sb.partition, "runs", self.sb.run_id))
        self.assertTrue(os.path.isfile(os.path.join(self.sb.run_dir(), "run.json")),
                        "the run profile left no run.json")

    def test_a_seed_on_the_run_base_lands_under_the_run_directory(self):
        rel = "steps/code/iter-1/filemap.json"
        path = self.sb.write("run", rel, {"declared": True})
        self.assertEqual(path, os.path.join(self.sb.run_dir(), rel))
        with open(path) as fh:
            self.assertEqual(json.load(fh), {"declared": True})

    def test_a_run_keyed_command_answers_on_a_run_sandbox(self):
        out = self.sb.run("acs.py", "lock", "status", "--run", self.sb.run_id)
        self.assertEqual(out["exit_code"], 0, out["stderr"])
        self.assertEqual(json.loads(out["stdout"])["lock_path"],
                         os.path.join(self.sb.run_dir(), "lock.json"))

    def test_the_same_command_refuses_on_a_ticketed_sandbox(self):
        """The contrast that proves the `run` base is what arms these cases:
        without a run, the v0.5.0 CLI has nothing to answer about."""
        with harness.Sandbox(self.build, profile="ticketed") as sb:
            out = sb.run("acs.py", "lock", "status", "--run", sb.ticket_id)
            self.assertEqual(out["exit_code"], 2, out["stdout"])
            self.assertIn("no run", out["stderr"])

    def test_the_run_epic_profile_opens_a_run_over_an_epic(self):
        with harness.Sandbox(self.build, profile="run-epic") as sb:
            self.assertEqual(sb.run_id, sb.ticket_id)
            with open(os.path.join(sb.ticket_dir(), "ticket.json")) as fh:
                self.assertEqual(json.load(fh)["type"], "epic")

    def test_the_six_existing_profiles_are_left_alone(self):
        """R3: the 290 cases that pass today all stand on these six, and a run
        inside `ticketed` would change what the gates resolve."""
        self.assertEqual(harness.PROFILES[:6],
                         ("bare", "seeded", "ticketed", "epic", "app", "app-ticketed"))
        with harness.Sandbox(self.build, profile="ticketed") as sb:
            self.assertIsNone(sb.run_id)
            self.assertFalse(os.path.exists(os.path.join(sb.partition, "runs")),
                             "the ticketed profile opened a run")


class RunTokensExpandTest(unittest.TestCase):
    """`{{run}}` and `{{run_dir}}`: how a case addresses the run base."""

    @classmethod
    def setUpClass(cls):
        cls.sb = harness.Sandbox(harness.resolve_build(), profile="run")
        cls.addClassCleanup(cls.sb.close)

    def test_run_expands_to_the_run_id(self):
        self.assertEqual(run_golden.expand("--run={{run}}", self.sb),
                         "--run=%s" % self.sb.run_id)

    def test_run_dir_expands_to_the_run_directory(self):
        self.assertEqual(run_golden.expand("{{run_dir}}/run.json", self.sb),
                         os.path.join(self.sb.run_dir(), "run.json"))

    def test_an_after_clause_reads_the_run_base(self):
        self.sb.write("run", "steps/code/state.json", {"status": "in_progress"})
        case = {"expect": {"after": [{"base": "run", "path": "steps/code/state.json",
                                      "json_subset": {"status": "in_progress"}}]}}
        seen = run_golden.read_after(case, self.sb)
        self.assertEqual(seen["steps/code/state.json"]["json"],
                         {"status": "in_progress"})


class BareStringContainmentIsRefusedTest(unittest.TestCase):
    """A containment clause written as a string asserts nothing; the runner
    must say so rather than iterate it."""

    OBSERVED = {"exit_code": 2, "stdout": "", "stderr": "acs path: invalid choice: 'path'"}

    def test_a_bare_string_contains_is_refused(self):
        errs = run_golden.compare({"stderr_contains": "is not one of"}, self.OBSERVED)
        self.assertTrue(errs, "a bare-string stderr_contains passed vacuously")
        self.assertIn("stderr_contains", errs[0])
        self.assertIn("list", errs[0])

    def test_a_bare_string_excludes_is_refused(self):
        errs = run_golden.compare({"stdout_excludes": "zzz"}, self.OBSERVED)
        self.assertTrue(errs, "a bare-string stdout_excludes passed vacuously")
        self.assertIn("stdout_excludes", errs[0])

    def test_a_list_of_needles_still_compares(self):
        """The control: the repair must not refuse the shape every case uses."""
        self.assertEqual(
            run_golden.compare({"stderr_contains": ["invalid choice"]}, self.OBSERVED), [])
        self.assertTrue(
            run_golden.compare({"stderr_contains": ["not emitted"]}, self.OBSERVED))


if __name__ == "__main__":
    unittest.main(verbosity=2)
