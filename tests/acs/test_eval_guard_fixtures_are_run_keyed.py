"""MAR-587 -- the run-keyed CLI families, and the proof the file-map guard is
armed rather than merely green.

v0.5.0 keys the workspace by RUN (ADR-0097; REDESIGN-IMPLEMENTATION-PIPELINE.md
:858-880, "lock.json ... the lock protocol, unchanged, relocated" and "agents/
... runtime scratch, unchanged, relocated"). Three golden families still stood
on the retired ticket partition:

* `12-filemap-guard.json` seeded `active-agents/` and `phases/code/
  iter-1-filemap.json` under the TICKET base -- paths `acs_lib.filemap` never
  consults -- so ten of its fifteen cases were green while asserting nothing:
  half one of the guard fails OPEN, and an unarmed guard allows everything.
  Relocating them is not a weakening, it is the only thing that makes those
  ten assert again.
* `05-lock.json` and `04-filemap.json` drove the retired `--ticket` flag.

So "all fifteen are run-keyed" is only half of AC-8. The other half is a
CAUSAL test: the deny has to come from the declared map. `FileMapGuardIsArmed`
runs GUARD-004 through the real PreToolUse hook and then removes only its map
seed; a guard that fails open cannot tell those two runs apart.

These checks live in `tests/` because CI runs `python3 -m unittest discover -s
tests` and nothing else -- `make -C src/acs-evals eval-source` is never read on
a pull request, which is how a vacuous pass survived a release.

Every fixture is a local temp dir: no model, no network, no cost.

Run:  python3 -m unittest tests.acs.test_eval_guard_fixtures_are_run_keyed -v
"""

import json
import os
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CASES = os.path.join(REPO_ROOT, "src", "acs-evals", "dataset", "cases")
RUNNER = os.path.join(REPO_ROOT, "src", "acs-evals", "runner")
PLUGIN_ROOT = os.path.join(REPO_ROOT, "src", "acs")

GUARD_FILE = "12-filemap-guard.json"
LOCK_FILE = "05-lock.json"
FILEMAP_FILE = "04-filemap.json"

#: The run-keyed spellings the guard actually reads, from the build under test:
#: `acs_lib.lifecycle.ACTIVE_AGENTS_DIRNAME` and
#: `acs_lib.filemap.FILEMAP_FILENAME` under `run.iteration_dir`.
AGENTS_SEED = "agents/"
MAP_SEED = "steps/code/iter-1/filemap.json"

#: The ticket-keyed spellings that must not survive anywhere in the three
#: files: each one names a directory level ADR-0097 removed.
RETIRED_SEGMENTS = ("active-agents/", "phases/", "iter-1-filemap.json", ".lock")


def _load_runner():
    """Import runner/run_golden.py and runner/harness.py without leaving either
    on `sys.modules` -- `src/acs-evals/behavioural/acs/harness.py` claims the
    name `harness` too, and whichever imported second would win."""
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
    """Pin the build under test to this checkout's src/acs, as
    `make eval-source` does."""
    global _SAVED_PLUGIN_ROOT
    _SAVED_PLUGIN_ROOT = os.environ.get("ACS_PLUGIN_ROOT")
    os.environ["ACS_PLUGIN_ROOT"] = PLUGIN_ROOT


def tearDownModule():
    if _SAVED_PLUGIN_ROOT is None:
        os.environ.pop("ACS_PLUGIN_ROOT", None)
    else:
        os.environ["ACS_PLUGIN_ROOT"] = _SAVED_PLUGIN_ROOT


def load_case_file(name):
    with open(os.path.join(CASES, name)) as fh:
        return json.load(fh)


def case_by_id(doc, case_id):
    for case in doc["cases"]:
        if case["id"] == case_id:
            return case
    raise AssertionError("%s carries no case %s" % (doc.get("group"), case_id))


def argv_of(case):
    return [str(a) for a in (case.get("invoke") or {}).get("argv", [])]


class GuardFixturesAreRunKeyedTest(unittest.TestCase):
    """AC-8, first half: every GUARD fixture seeds where the guard looks."""

    @classmethod
    def setUpClass(cls):
        cls.doc = load_case_file(GUARD_FILE)

    def test_the_file_still_carries_all_fifteen_cases(self):
        """AC-6: relocating a fixture is not an excuse to drop a case. Stated as
        a floor, not an equality, so a later ticket may still add one."""
        self.assertGreaterEqual(len(self.doc["cases"]), 15,
                                "a GUARD case was lost rather than relocated")

    def test_every_guard_case_seeds_under_the_run_base(self):
        stray = ["%s %s -> base %r" % (c["id"], s["path"], s.get("base", "ticket"))
                 for c in self.doc["cases"] for s in c.get("files", [])
                 if s.get("base", "ticket") != "run"]
        self.assertEqual(stray, [],
                         "seeds outside the run base, where the guard never "
                         "looks: %s" % stray)

    def test_no_guard_seed_keeps_a_retired_ticket_keyed_path(self):
        stray = ["%s %s" % (c["id"], s["path"])
                 for c in self.doc["cases"] for s in c.get("files", [])
                 if any(seg in s["path"] for seg in RETIRED_SEGMENTS)]
        self.assertEqual(stray, [],
                         "seeds on a directory level ADR-0097 removed: %s" % stray)

    def test_the_armed_cases_seed_both_of_the_guard_s_inputs(self):
        """A relocation that dropped a seed would look identical to one that
        moved it: both halves of half one have to still be there."""
        armed = [c for c in self.doc["cases"]
                 if any(MAP_SEED in s["path"] for s in c.get("files", []))]
        self.assertGreaterEqual(len(armed), 13, "too few cases declare a map")
        for case in armed:
            paths = [s["path"] for s in case["files"]]
            self.assertTrue(any(p.startswith(AGENTS_SEED) for p in paths),
                            "%s declares a map but records no running executor, "
                            "so the guard is never armed" % case["id"])

    def test_the_file_cites_the_authority_for_the_relocation(self):
        """AC-5: the move is authorised by ADR-0097, not by what the build
        happens to print."""
        self.assertIn("ADR-0097", self.doc.get("covers") or [])
        notes = " ".join(c.get("note") or "" for c in self.doc["cases"])
        self.assertIn("ADR-0097", notes,
                      "covers names an authority no case note traces to")


class FileMapGuardIsArmedTest(unittest.TestCase):
    """AC-8, second half: the deny is CAUSED by the declared map.

    Every assertion here drives `dispatch.py file-map` -- the real PreToolUse
    entry point -- over the dataset's own GUARD-004 seeds, so it reads the
    dataset rather than a restatement of it.
    """

    DENY = "outside this task's file map"

    @classmethod
    def setUpClass(cls):
        cls.doc = load_case_file(GUARD_FILE)
        cls.case = case_by_id(cls.doc, "GUARD-004")
        cls.build = harness.resolve_build()

    def observe(self, case):
        """One case through a fresh sandbox, exactly as the golden tier runs it."""
        with harness.Sandbox(self.build, profile=self.doc.get("profile", "bare")) as sb:
            return run_golden.execute(case, sb)

    def without_the_map(self):
        files = [s for s in self.case.get("files", []) if MAP_SEED not in s["path"]]
        self.assertEqual(len(files), len(self.case["files"]) - 1,
                         "GUARD-004 no longer seeds exactly one file map")
        return dict(self.case, files=files)

    def test_a_write_outside_the_declared_map_is_denied(self):
        observed = self.observe(self.case)
        self.assertEqual(observed["exit_code"], 2,
                         "the guard allowed a write outside the declared map; "
                         "stderr was %r" % observed["stderr"])
        self.assertIn(self.DENY, observed["stderr"])

    def test_the_recorded_expectation_holds_against_the_live_hook(self):
        self.assertEqual(run_golden.compare(self.case["expect"], self.observe(self.case)),
                         [])

    def test_removing_the_declared_map_flips_the_denial_to_an_allow(self):
        """The armed-ness proof. Asserted as a PAIR on purpose: a guard that
        fails open returns 0 for both runs, so only the contrast can tell an
        armed guard from a switched-off one."""
        denied = self.observe(self.case)
        allowed = self.observe(self.without_the_map())
        self.assertEqual((denied["exit_code"], allowed["exit_code"]), (2, 0),
                         "the declared map did not decide the verdict: denied=%r "
                         "allowed=%r" % (denied, allowed))
        self.assertNotIn(self.DENY, allowed["stderr"])

    def test_the_retired_ticket_keyed_location_leaves_the_guard_unarmed(self):
        """The control, and the reason all fifteen moved rather than five: put
        the same seeds back where v0.4.9 kept them and the write sails through,
        which is what the ten 'passing' cases were really recording."""
        retired = dict(self.case, files=[
            dict(seed, base="ticket",
                 path=("phases/code/iter-1-filemap.json" if MAP_SEED in seed["path"]
                       else seed["path"].replace(AGENTS_SEED, "active-agents/")))
            for seed in self.case["files"]])
        observed = self.observe(retired)
        self.assertEqual(observed["exit_code"], 0,
                         "the ticket-keyed fixtures armed the guard after all — "
                         "then the relocation is not what AC-8 assumed")


class RunKeyedCliFamiliesTest(unittest.TestCase):
    """The LOCK and FILEMAP families the same relocation moves: the retired
    `--ticket` key is gone, and the lock seeds address `runs/<id>/lock.json`."""

    FILES = (LOCK_FILE, FILEMAP_FILE, GUARD_FILE)

    def test_no_case_drives_the_retired_ticket_flag(self):
        """`--ticket` is not a flag v0.5.0 has; a case still passing it is
        asserting against argparse, not against the surface."""
        stray = ["%s %s" % (name, case["id"])
                 for name in self.FILES
                 for case in load_case_file(name)["cases"]
                 if "--ticket" in argv_of(case)]
        self.assertEqual(stray, [], "cases on the retired --ticket key: %s" % stray)

    def test_every_lock_case_seeds_the_run_keyed_lock_file(self):
        stray = ["%s %s %s" % (case["id"], s.get("base", "ticket"), s["path"])
                 for case in load_case_file(LOCK_FILE)["cases"]
                 for s in case.get("files", [])
                 if (s.get("base"), s["path"]) != ("run", "lock.json")]
        self.assertEqual(stray, [], "lock seeds off runs/<id>/lock.json: %s" % stray)

    def test_every_filemap_seed_is_the_run_keyed_iteration_directory(self):
        stray = ["%s %s %s" % (case["id"], s.get("base", "ticket"), s["path"])
                 for case in load_case_file(FILEMAP_FILE)["cases"]
                 for s in case.get("files", [])
                 if (s.get("base"), s["path"]) != ("run", MAP_SEED)]
        self.assertEqual(stray, [], "file-map seeds off the iteration dir: %s" % stray)

    def test_the_lock_safety_verdicts_survive_the_re_record(self):
        """AC-6, stated as the thing this family exists for: a lock that
        refuses a second holder. Each basis below is one branch of
        `acs_lib.lock.lock_staleness`, and a re-record that quietly dropped one
        would leave the file green and the property unpinned."""
        cases = {c["id"]: c for c in load_case_file(LOCK_FILE)["cases"]}
        for case_id, basis in (("LOCK-002", "age-timeout"),
                               ("LOCK-003", "age-within-timeout"),
                               ("LOCK-004", "age-unknown"),
                               ("LOCK-008", "holder-process-live"),
                               ("LOCK-009", "holder-process-gone")):
            subset = cases[case_id]["expect"].get("stdout_json_subset") or {}
            self.assertEqual(subset.get("basis"), basis,
                             "%s no longer pins its staleness basis" % case_id)
            self.assertIn("stale", subset, "%s no longer pins a verdict" % case_id)
        self.assertFalse(cases["LOCK-004"]["expect"]["stdout_json_subset"]["stale"],
                         "FAIL CLOSED: an unreadable created_at must not read stale")
        self.assertIn("the following arguments are required: --reason",
                      cases["LOCK-005"]["expect"]["stderr_contains"])
        self.assertEqual(cases["LOCK-011"]["expect"]["stderr_excludes"],
                         ["looks stale", "force-unlock"],
                         "the fresh-lock branch must still refuse to suggest "
                         "breaking the lock")


if __name__ == "__main__":
    unittest.main(verbosity=2)
