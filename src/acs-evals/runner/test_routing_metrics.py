#!/usr/bin/env python3
"""Tests for runner/routing_metrics.py — synthetic records, no model, no cost."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import routing_metrics as rm  # noqa: E402


def probe(pid, skill, routed, kind="routing", must_route=True, control=False,
          runs=None):
    """A routing probe whose runs each routed to the given label."""
    if runs is None:
        runs = [{"routed_to": r} for r in routed]
    return {"id": pid, "kind": kind, "skill": skill,
            "expect": {"must_route": must_route, "skill": skill,
                       "control": control},
            "runs": runs}


def measurement(*probes):
    return {"probes": list(probes)}


class PerfectRunTest(unittest.TestCase):

    def setUp(self):
        self.m = measurement(
            probe("ROUTE-a", "acs:a", ["acs:a"] * 3),
            probe("ROUTE-b", "acs:b", ["acs:b"] * 3))

    def test_every_label_is_perfect(self):
        rows = rm.per_label(rm.confusion(self.m))
        for row in rows:
            self.assertEqual(row["precision"], 1.0, row["label"])
            self.assertEqual(row["recall"], 1.0, row["label"])
            self.assertEqual(row["f1"], 1.0, row["label"])

    def test_micro_and_macro_agree_when_nothing_is_wrong(self):
        rep = rm.report(self.m)
        a = rep["averages"]
        self.assertEqual(a["micro_f1"], 1.0)
        self.assertEqual(a["macro_f1"], 1.0)
        self.assertEqual(a["runs"], 6)
        self.assertEqual(rep["confusions"], [])


class PrecisionNamesTheThiefTest(unittest.TestCase):
    """The failure mode the hit-rate metric cannot express.

    `b` answers two of `a`'s prompts. The existing metric says "probe a is
    3/5"; it never says that `b` is what took them.
    """

    def setUp(self):
        self.m = measurement(
            probe("ROUTE-a", "acs:a", ["acs:a", "acs:a", "acs:a", "acs:b", "acs:b"]),
            probe("ROUTE-b", "acs:b", ["acs:b"] * 5))
        self.rows = {r["label"]: r for r in rm.per_label(rm.confusion(self.m))}

    def test_the_victim_loses_recall_not_precision(self):
        a = self.rows["acs:a"]
        self.assertEqual(a["recall"], 0.6)
        self.assertEqual(a["precision"], 1.0)
        self.assertEqual(a["fn"], 2)

    def test_the_thief_loses_precision_not_recall(self):
        b = self.rows["acs:b"]
        self.assertEqual(b["recall"], 1.0)
        self.assertAlmostEqual(b["precision"], 5.0 / 7.0)
        self.assertEqual(b["fp"], 2)

    def test_the_confusion_is_named_with_a_direction(self):
        top = rm.report(self.m)["confusions"][0]
        self.assertEqual(top["truth"], "acs:a")
        self.assertEqual(top["predicted"], "acs:b")
        self.assertEqual(top["count"], 2)

    def test_macro_falls_further_than_micro(self):
        """Macro weights the small class equally, which is why it is reported."""
        a = rm.report(self.m)["averages"]
        self.assertLess(a["macro_f1"], a["micro_f1"])


class NegativeProbeIsNotAClassTest(unittest.TestCase):
    """The trap: "must not route to X" folded into the matrix scores the
    DESIRED outcome as an error.

    Both of acs's negative probes correctly route to the entry point that
    coordinates the leg. Counting that as a miss for `(none)` and a false
    positive for the entry point cost 10 of 175 runs on the 2026-09-15 data,
    every one of them correct.
    """

    def setUp(self):
        self.m = measurement(
            probe("ROUTE-a", "acs:a", ["acs:a"] * 5),
            probe("ROUTE-leg-negative", "acs:leg", ["acs:entry"] * 5,
                  must_route=False))

    def test_the_negative_probe_is_left_out_of_the_matrix(self):
        a = rm.report(self.m)["averages"]
        self.assertEqual(a["runs"], 5)
        self.assertEqual(a["micro_f1"], 1.0)

    def test_the_entry_point_is_not_charged_a_false_positive(self):
        labels = {r["label"] for r in rm.per_label(rm.confusion(self.m))}
        self.assertNotIn("acs:entry", labels)

    def test_it_is_scored_by_its_own_rule_and_held(self):
        constraints = rm.report(self.m)["constraints"]
        self.assertEqual(len(constraints), 1)
        entry = constraints[0]
        self.assertEqual(entry["kind"], "negative")
        self.assertIn("must NOT route to acs:leg", entry["rule"])
        self.assertEqual((entry["held"], entry["runs"]), (5, 5))

    def test_a_negative_probe_that_hits_its_own_leg_is_not_held(self):
        m = measurement(probe("ROUTE-leg-negative", "acs:leg",
                              ["acs:entry", "acs:leg"], must_route=False))
        entry = rm.report(m)["constraints"][0]
        self.assertEqual((entry["held"], entry["runs"]), (1, 2))


class ControlsAreReportedApartTest(unittest.TestCase):

    def test_a_control_never_enters_the_matrix(self):
        m = measurement(
            probe("ROUTE-a", "acs:a", ["acs:a"] * 2),
            probe("CONTROL-canary", "acs:setup", ["acs:setup"] * 2, control=True))
        self.assertEqual(rm.report(m)["averages"]["runs"], 2)
        kinds = [c["kind"] for c in rm.report(m)["constraints"]]
        self.assertEqual(kinds, ["control"])


class UndefinedPrecisionTest(unittest.TestCase):
    """A skill nothing routed to has no precision, and must not be scored 1.0."""

    def setUp(self):
        self.m = measurement(
            probe("ROUTE-a", "acs:a", [None, None]),
            probe("ROUTE-b", "acs:b", ["acs:b", "acs:b"]))
        self.rows = {r["label"]: r for r in rm.per_label(rm.confusion(self.m))}

    def test_a_skill_nothing_reached_has_null_precision(self):
        a = self.rows["acs:a"]
        self.assertIsNone(a["precision"])
        self.assertEqual(a["recall"], 0.0)
        self.assertIsNone(a["f1"])

    def test_a_run_that_routed_nowhere_is_a_real_label(self):
        self.assertIn(rm.NO_ROUTE, self.rows)
        self.assertEqual(self.rows[rm.NO_ROUTE]["fp"], 2)

    def test_the_macro_mean_skips_the_undefined_value(self):
        a = rm.averages(list(self.rows.values()), rm.confusion(self.m))
        # acs:a contributes a recall of 0.0 but no precision.
        self.assertIsNotNone(a["macro_precision"])
        self.assertLess(a["macro_recall"], 1.0)


class PerSkillRowsTest(unittest.TestCase):

    def test_a_skill_carries_its_routing_and_its_pipeline_results(self):
        m = measurement(
            probe("ROUTE-code", "acs:code", ["acs:code"] * 5),
            {"id": "PIPE-code", "kind": "pipeline", "skill": "acs:code",
             "runs": [{"ok": True}] * 3,
             "aggregate": {"reliability": {"hits": 3, "total": 3, "rate": 1.0},
                           "cost_usd": {"median": 1.73},
                           "seconds": {"median": 370.0},
                           "unmeasured": 0}})
        # The routing probe needs an aggregate for the per-skill view.
        m["probes"][0]["aggregate"] = {"reliability": {"hits": 5, "total": 5, "rate": 1.0}}
        rows = rm.per_skill(m)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["skill"], "acs:code")
        self.assertEqual(row["routing"][0]["hits"], 5)
        self.assertEqual(row["pipeline"][0]["scenario"], "PIPE-code")
        self.assertEqual(row["pipeline"][0]["cost_median"], 1.73)
        self.assertEqual(row["precision"], 1.0)

    def test_a_skill_with_no_pipeline_scenario_says_so_with_an_empty_list(self):
        m = measurement(probe("ROUTE-usage", "acs:usage", ["acs:usage"] * 5))
        m["probes"][0]["aggregate"] = {"reliability": {"hits": 5, "total": 5, "rate": 1.0}}
        row = rm.per_skill(m)[0]
        self.assertEqual(row["pipeline"], [])


class EmptyMeasurementTest(unittest.TestCase):

    def test_nothing_measured_is_not_a_crash(self):
        rep = rm.report({"probes": []})
        self.assertEqual(rep["per_label"], [])
        self.assertIsNone(rep["averages"]["micro_f1"])
        self.assertEqual(rm.per_skill({"probes": []}), [])


class ItIsNotAGateTest(unittest.TestCase):

    def test_the_module_says_so(self):
        note = rm.report({"probes": []})["note"]
        self.assertIn("Diagnostic only", note)
        self.assertIn("stricter", note)

    def test_no_threshold_file_key_is_read_here(self):
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               "routing_metrics.py"), encoding="utf-8") as fh:
            body = fh.read()
        self.assertNotIn("thresholds.json", body.replace(
            "`dataset/thresholds.json` reads none of this.", ""))


if __name__ == "__main__":
    unittest.main(verbosity=2)
