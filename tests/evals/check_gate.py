"""scripts/eval_gate.py -- the release gate's judgement of a routing run.

Local-only like everything under tests/evals/ (ADR-0108): run by the
`acs-eval-checks` pre-commit hook and the release gate, never by CI.

Every result here is synthetic, shaped like the `--json` file `claude plugin
eval` writes (schema version 1: `cases[].arms.with[].score`), and named after
the REAL routing cases, because the gate maps a case to its skill and kind by
reading the case files. Pure: no `claude`, no network, no cost.
"""

import contextlib
import datetime
import importlib.util
import io
import json
import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
TESTS_ACS = HERE  # the strict case reader lives beside these checks
REPO_ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, TESTS_ACS)
import eval_cases as ec  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "eval_gate", os.path.join(REPO_ROOT, "scripts", "eval_gate.py"))
gate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gate)

NOW = datetime.datetime(2026, 9, 24, 12, 0, tzinfo=datetime.timezone.utc)
SETTINGS = os.path.join(REPO_ROOT, ".acs", "settings.json")


def gated(kind=None):
    return sorted((c for c in ec.routing_cases()
                   if c.kind in gate.GATED_KINDS and (kind is None or c.kind == kind)),
                  key=lambda c: c.name)


def result(scores=None, runs=3, started=NOW, **top):
    """A passing result for every gated case, with `scores` overriding cases:
    {case name: [run scores]}."""
    scores = scores or {}
    cases = [{"name": c.name,
              "arms": {"with": [{"score": s, "turns": 1, "error": None}
                                for s in scores.get(c.name, [1] * runs)]}}
             for c in gated()]
    out = {"schemaVersion": 1, "partial": False,
           "startedAt": started.isoformat().replace("+00:00", "Z"), "cases": cases}
    out.update(top)
    return out


class GateTestCase(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)

    def run_gate(self, data, *args):
        path = os.path.join(self.tmp, "result.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = gate.main([path] + list(args), now=NOW)
        return code, out.getvalue()

    def skill_cases(self, skill):
        return [c.name for c in gated("description") if c.skill == skill]


class PassTest(GateTestCase):

    def test_every_run_routed_passes(self):
        code, out = self.run_gate(result())
        self.assertEqual(code, 0, out)
        self.assertIn("routing gate: PASS", out)

    def test_exactly_the_skill_floor_passes(self):
        """Two of every three runs is exactly 2/3: the floor is inclusive, and
        compared as a fraction so 0.666... is not rounded below it."""
        names = self.skill_cases("create-ticket")
        self.assertGreaterEqual(len(names), 3)
        scores = {name: [1, 1, 0] for name in names}
        code, out = self.run_gate(result(scores))
        self.assertEqual(code, 0, out)

    def test_explicit_cases_are_reported_not_gated(self):
        data = result()
        explicit = [c.name for c in ec.routing_cases() if c.kind == "explicit"]
        data["cases"].append({"name": explicit[0], "arms": {"with": [{"score": 0}] * 3}})
        code, out = self.run_gate(data)
        self.assertEqual(code, 0, out)
        self.assertIn("not gated", out)


class MustNeverTest(GateTestCase):

    def test_one_misrouted_negative_run_fails(self):
        name = gated("negative")[0].name
        code, out = self.run_gate(result({name: [1, 1, 0]}))
        self.assertEqual(code, 1)
        self.assertIn(name, out)

    def test_one_control_run_that_fires_a_skill_fails(self):
        name = gated("control")[0].name
        code, out = self.run_gate(result({name: [0, 1, 1]}))
        self.assertEqual(code, 1)
        self.assertIn(name, out)


class ShouldRouteTest(GateTestCase):

    def test_a_skill_below_its_floor_fails_even_when_the_suite_passes(self):
        names = self.skill_cases("merge-pr")
        scores = {name: [1, 0, 0] for name in names}
        code, out = self.run_gate(result(scores))
        self.assertEqual(code, 1)
        self.assertIn("merge-pr routed %d of %d" % (len(names), 3 * len(names)), out)
        self.assertNotIn("the suite routed", out, "one weak skill does not sink the suite")

    def test_a_broad_slide_fails_the_suite_with_no_skill_below_its_floor(self):
        """Every skill at exactly 2/3 clears the floor, but 67% overall is
        below the 90% suite rate: nothing is broken, everything is worse."""
        scores = {c.name: [1, 1, 0] for c in gated("description")}
        code, out = self.run_gate(result(scores))
        self.assertEqual(code, 1)
        self.assertIn("the suite routed", out)
        self.assertNotRegex(out, r"(?m)^  FAIL ", "no single skill is below its floor")


class FailsClosedTest(GateTestCase):

    def test_a_partial_run_fails(self):
        code, out = self.run_gate(result(partial=True, partialReason="cost_ceiling"))
        self.assertEqual(code, 1)
        self.assertIn("partial (cost_ceiling)", out)

    def test_an_unknown_schema_fails(self):
        code, out = self.run_gate(result(schemaVersion=2))
        self.assertEqual(code, 1)
        self.assertIn("unknown result format", out)

    def test_a_stale_file_fails(self):
        code, out = self.run_gate(result(started=NOW - datetime.timedelta(hours=7)))
        self.assertEqual(code, 1)
        self.assertIn("stale file", out)

    def test_a_missing_gated_case_fails(self):
        data = result()
        dropped = data["cases"].pop()["name"]
        code, out = self.run_gate(data)
        self.assertEqual(code, 1)
        self.assertIn(dropped, out)

    def test_a_case_the_repo_does_not_have_fails(self):
        data = result()
        data["cases"].append({"name": "route-nothing", "arms": {"with": [{"score": 1}]}})
        code, out = self.run_gate(data)
        self.assertEqual(code, 1)
        self.assertIn("route-nothing is not a routing case", out)

    def test_a_run_without_a_score_fails(self):
        data = result()
        data["cases"][0]["arms"]["with"][0].pop("score")
        code, out = self.run_gate(data)
        self.assertEqual(code, 1)
        self.assertIn("no numeric score", out)

    def test_a_run_that_never_reached_the_model_fails(self):
        """A usage limit mid-run scores the rest 0 without marking the run
        partial, and a negative reads a run with no Skill call as a pass."""
        name = gated("negative")[0].name
        data = result()
        run = next(c for c in data["cases"] if c["name"] == name)["arms"]["with"][0]
        run.update(score=1, turns=0, error="exit 1: Claude AI usage limit reached")
        code, out = self.run_gate(data)
        self.assertEqual(code, 1)
        self.assertIn("never reached the model", out)

    def test_a_run_stopped_at_the_turn_limit_still_counts(self):
        data = result()
        data["cases"][0]["arms"]["with"][0].update(turns=1, error="exit 1: max turns reached")
        code, out = self.run_gate(data)
        self.assertEqual(code, 0, out)

    def test_an_unreadable_file_fails(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = gate.main([os.path.join(self.tmp, "absent.json")], now=NOW)
        self.assertEqual(code, 1)
        self.assertIn("cannot read", out.getvalue())


class ThisRepoWiresTheGateTest(unittest.TestCase):
    """The settings run the CLI and then this script, on the same file."""

    def setUp(self):
        with open(SETTINGS, encoding="utf-8") as fh:
            self.gate = json.load(fh)["release"]["pre_release_gate"]
        self.paid = [c for c in self.gate if "claude plugin eval" in c]
        self.judge = [c for c in self.gate if "scripts/eval_gate.py" in c]

    def test_one_paid_run_and_one_judgement(self):
        self.assertEqual((len(self.paid), len(self.judge)), (1, 1), self.gate)
        self.assertLess(self.gate.index(self.paid[0]), self.gate.index(self.judge[0]))

    def test_the_cli_leaves_the_judging_to_the_script(self):
        self.assertIn("--threshold 0 ", self.paid[0] + " ")
        self.assertIn("--ablation none", self.paid[0])

    def test_it_runs_exactly_the_gated_kinds(self):
        tags = self.paid[0].split("--tag ")[1:]
        self.assertEqual(sorted(t.split()[0] for t in tags), sorted(gate.GATED_KINDS))
        self.assertNotIn("--tag routing", self.paid[0], "routing would pull in explicit")

    def test_both_commands_name_the_same_result_file(self):
        written = self.paid[0].split("--json ")[1].split()[0]
        self.assertTrue(written.endswith(".json"))
        self.assertIn(" %s" % written, " " + self.judge[0])
        self.assertTrue(written.startswith("plugins/acs/evals/results/"),
                        "results/ is gitignored; a gate file must not dirty the tree")

    def test_the_thresholds_are_stated_not_defaulted(self):
        self.assertIn("--min-skill-rate", self.judge[0])
        self.assertIn("--min-suite-rate", self.judge[0])

    def test_ten_runs_a_case_at_nine_tenths_per_skill_and_every_run_overall(self):
        """ADR-0109: ten runs a case, each skill's pooled runs at 9/10, and the
        suite at 1.0 -- one misrouted description run fails the release."""
        self.assertIn(" --runs 10 ", " %s " % self.paid[0])
        self.assertIn(" --min-skill-rate 9/10 ", " %s " % self.judge[0])
        self.assertIn(" --min-suite-rate 1 ", " %s " % self.judge[0])


if __name__ == "__main__":
    unittest.main()
