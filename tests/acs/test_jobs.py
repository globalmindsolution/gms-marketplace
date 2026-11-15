"""ADR-0125: deterministic commands that run beside a skill's subagents.

`acs.py job start` returns at once; `job wait` is ONE blocking call that returns
the moment every named job has ended (or exits 3 at its timeout, to be called
again) -- the alternative to a coordinator polling with `sleep`.
"""

import json
import os
import sys
import tempfile
import shutil
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from acs_case import AcsWorkspaceCase  # noqa: E402

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(REPO_ROOT, "plugins", "acs", "hooks", "scripts"))

import acs_lib as lib  # noqa: E402
from acs_lib import jobs as J  # noqa: E402


class JobLibTest(unittest.TestCase):

    def setUp(self):
        self.rdir = tempfile.mkdtemp(prefix="acs-jobs-")
        self.addCleanup(shutil.rmtree, self.rdir, True)

    def test_a_passing_and_a_failing_job(self):
        J.start(self.rdir, "ok", "echo hi", self.rdir)
        J.start(self.rdir, "bad", "echo boom >&2; exit 3", self.rdir)
        out = J.wait(self.rdir, ["ok", "bad"], timeout=30)
        self.assertTrue(out["done"])
        by = {j["name"]: j for j in out["jobs"]}
        self.assertEqual((by["ok"]["state"], by["ok"]["exit_code"]), ("passed", 0))
        self.assertEqual((by["bad"]["state"], by["bad"]["exit_code"]), ("failed", 3))
        self.assertIn("boom", by["bad"]["tail"])

    def test_wait_returns_at_its_timeout_with_the_job_still_running(self):
        J.start(self.rdir, "long", "sleep 30", self.rdir)
        self.addCleanup(J.stop, self.rdir, "long")
        out = J.wait(self.rdir, ["long"], timeout=0.5)
        self.assertFalse(out["done"])
        self.assertEqual(out["jobs"][0]["state"], "running")

    def test_a_running_job_cannot_be_started_twice_and_can_be_stopped(self):
        J.start(self.rdir, "long", "sleep 30", self.rdir)
        with self.assertRaises(lib.GateError):
            J.start(self.rdir, "long", "true", self.rdir)
        self.assertEqual(J.stop(self.rdir, "long")["state"], "stopped")
        self.assertEqual(J.status(self.rdir, "long")["state"], "stopped")

    def test_a_finished_job_is_replaced_and_unknown_names_are_missing(self):
        J.start(self.rdir, "x", "exit 1", self.rdir)
        J.wait(self.rdir, ["x"], timeout=30)
        J.start(self.rdir, "x", "true", self.rdir)
        self.assertEqual(J.wait(self.rdir, ["x"], timeout=30)["jobs"][0]["state"], "passed")
        self.assertEqual(J.status(self.rdir, "nope")["state"], "missing")

    def test_bad_names_are_refused(self):
        for name in ("Bad", "a/b", "", "x" * 41):
            with self.assertRaises(lib.GateError):
                J.start(self.rdir, name, "true", self.rdir)


class JobCliTest(AcsWorkspaceCase):

    def setUp(self):
        super().setUp()
        new = self.run_script("acs.py", "run", "new", "--prompt", "jobs")
        self.assertEqual(new.returncode, 0, new.stderr)

    def job(self, *args):
        return self.run_script("acs.py", "job", *args)

    def test_start_then_wait(self):
        out = self.job("start", "--name", "suite", "--", "echo", "it's fine")
        self.assertEqual(out.returncode, 0, out.stderr)
        waited = self.job("wait", "--name", "suite")
        self.assertEqual(waited.returncode, 0, waited.stderr)
        self.assertIn("it's fine", json.loads(waited.stdout)["jobs"][0]["tail"])

    def test_wait_exits_1_on_failure_and_3_on_timeout(self):
        self.job("start", "--name", "bad", "--", "exit 4")
        self.assertEqual(self.job("wait", "--name", "bad").returncode, 1)
        self.job("start", "--name", "long", "--", "sleep 30")
        self.assertEqual(self.job("wait", "--name", "long", "--timeout", "0.3").returncode, 3)
        self.assertEqual(json.loads(self.job("stop", "--name", "long").stdout)["job"]["state"],
                         "stopped")
        self.assertEqual(json.loads(self.job("status", "--name", "long").stdout)
                         ["jobs"][0]["state"], "stopped")

    def test_start_needs_a_command(self):
        self.assertNotEqual(self.job("start", "--name", "x").returncode, 0)


class ParallelSettingTest(unittest.TestCase):

    def test_default_and_bounds(self):
        self.assertEqual(lib.DEFAULT_SETTINGS["parallel"], {"max_agents": 4})
        lib.settings.validate_parallel({"max_agents": 1})
        lib.settings.validate_parallel({"max_agents": 16})
        for bad in (0, 17, "4", True, 2.5):
            with self.assertRaises(lib.GateError):
                lib.settings.validate_parallel({"max_agents": bad})
        with self.assertRaises(lib.GateError):
            lib.settings.validate_parallel([])

    def test_the_schema_matches(self):
        path = os.path.join(REPO_ROOT, "plugins", "acs", "schemas", "settings.schema.json")
        with open(path, encoding="utf-8") as fh:
            prop = json.load(fh)["properties"]["parallel"]["properties"]["max_agents"]
        self.assertEqual((prop["minimum"], prop["maximum"], prop["default"]),
                         (*lib.settings.MAX_AGENTS_RANGE, 4))


if __name__ == "__main__":
    unittest.main()
