"""scripts/record_baseline.py, checked for free -- locally, against a fake CLI.

Local-only like everything under tests/evals/ (ADR-0108). A reference
transcript teaches a `baseline` judge what a good run looks like, so the
recorder must never keep one from a run that failed its own graders or never
reached the model, and it must write the grader and its transcript together:
the CLI refuses a case whose `baseline_file` is missing.

The fake `claude` writes the `--json` result the real CLI would and leaves a
kept run directory with a trace, as `--keep-temp` does. Each test records into
a temp copy of a real case, so the suite itself is never touched.
"""

import json
import os
import shutil
import stat
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), "scripts"))
import eval_cases as ec  # noqa: E402
import record_baseline as rb  # noqa: E402

FAKE_CLAUDE = r"""#!/usr/bin/env python3
import json, os, sys, tempfile
args = sys.argv[1:]
out = args[args.index("--json") + 1]
case = args[args.index("--case") + 1]
mode = os.environ.get("FAKE_MODE", "clean")
run_dir = tempfile.mkdtemp(prefix="claude-eval-", dir=os.environ["FAKE_TMP"])
os.makedirs(os.path.join(run_dir, "out"))
trace = os.path.join(run_dir, "out", "trace.jsonl")
with open(trace, "w") as fh:
    fh.write(json.dumps({"type": "user", "message": {"content": "the prompt"}}) + "\n")
    fh.write(json.dumps({"type": "assistant", "message": {"content": [
        {"type": "tool_use", "name": "Skill", "input": {"skill": "acs:setup"}}]}}) + "\n")
graders = [{"name": "skill-fired", "passed": True, "scored": True},
           {"name": "outcome", "passed": mode != "failed-grader", "scored": True}]
error = {"session-limit": "exit 1: You've hit your session limit",
         "turn-limit": "exit 1: Reached maximum number of turns (30)"}.get(mode)
with open(out, "w") as fh:
    json.dump({"schemaVersion": 1, "partial": False, "cases": [{"name": case, "arms": {"with": [
        {"score": 1, "turns": 3, "error": error, "tracePath": trace, "graders": graders}]}}]}, fh)
"""


class RecordTest(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        fake = os.path.join(self.tmp, "claude")
        with open(fake, "w") as fh:
            fh.write(FAKE_CLAUDE)
        os.chmod(fake, os.stat(fake).st_mode | stat.S_IXUSR)
        self.runs = os.path.join(self.tmp, "runs")
        os.makedirs(self.runs)
        saved = {k: os.environ.get(k) for k in ("PATH", "FAKE_MODE", "FAKE_TMP")}
        self.addCleanup(self._restore, saved)
        os.environ["PATH"] = self.tmp + os.pathsep + os.environ.get("PATH", "")
        os.environ["FAKE_TMP"] = self.runs
        source = next(c for c in ec.all_cases() if c.name == "01-keep-defaults")
        self.case_dir = os.path.join(self.tmp, "01-keep-defaults")
        shutil.copytree(source.path, self.case_dir)
        self.case = ec.Case(self.case_dir)

    @staticmethod
    def _restore(saved):
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def record(self, mode):
        os.environ["FAKE_MODE"] = mode
        rb.record(self.case)

    def recorded(self):
        return (os.path.isfile(os.path.join(self.case_dir, rb.BASELINE_FILE)),
                os.path.isfile(os.path.join(self.case_dir, "graders", rb.GRADER_FILE)))

    def test_a_clean_run_writes_the_transcript_and_its_grader_together(self):
        self.record("clean")
        self.assertEqual(self.recorded(), (True, True))
        grader = ec.Grader(os.path.join(self.case_dir, "graders", rb.GRADER_FILE))
        self.assertEqual(grader.type, "baseline")
        self.assertEqual(grader.fm["baseline_file"], rb.BASELINE_FILE)
        with open(os.path.join(self.case_dir, rb.CRITERIA_FILE), encoding="utf-8") as fh:
            self.assertEqual(grader.body.strip(), fh.read().strip())
        with open(os.path.join(self.case_dir, rb.BASELINE_FILE), encoding="utf-8") as fh:
            self.assertEqual(len([json.loads(l) for l in fh if l.strip()]), 2)

    def test_a_run_stopped_at_its_turn_limit_is_still_clean(self):
        self.record("turn-limit")
        self.assertEqual(self.recorded(), (True, True))

    def test_a_run_that_failed_a_grader_is_refused(self):
        with self.assertRaises(rb.RecordError):
            self.record("failed-grader")
        self.assertEqual(self.recorded(), (False, False))

    def test_a_run_that_hit_a_usage_limit_is_refused(self):
        with self.assertRaises(rb.RecordError):
            self.record("session-limit")
        self.assertEqual(self.recorded(), (False, False))

    def test_a_case_without_criteria_is_refused_before_anything_runs(self):
        os.remove(os.path.join(self.case_dir, rb.CRITERIA_FILE))
        with self.assertRaises(rb.RecordError):
            self.record("clean")
        self.assertEqual(os.listdir(self.runs), [], "nothing should have run")

    def test_it_removes_only_the_directory_its_run_kept(self):
        other = tempfile.mkdtemp(prefix="claude-eval-", dir=self.runs)
        self.record("clean")
        self.assertEqual(os.listdir(self.runs), [os.path.basename(other)])


class MainTest(unittest.TestCase):

    def test_an_unknown_case_is_refused(self):
        self.assertEqual(rb.main(["no-such-case", "--dry-run"]), 2)

    def test_missing_selects_only_unrecorded_behaviour_cases(self):
        missing = [c.name for c in rb.behaviour_cases() if not rb.has_baseline(c)]
        self.assertTrue(all(ec.Case(c.path).group in rb.BEHAVIOUR_GROUPS
                            for c in rb.behaviour_cases()))
        self.assertEqual(rb.main(["--missing", "--dry-run"]), 0)
        self.assertTrue(missing, "no case left to record")


if __name__ == "__main__":
    unittest.main()
